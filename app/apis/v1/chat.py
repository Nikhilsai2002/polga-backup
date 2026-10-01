# app/api/sql_routes.py
from fastapi import APIRouter, Depends, Query
from app.agents.graph_builder_1 import sql_generation_graph as graph_builder
from app.agents.state import ReActState 
# from app.agents.graph_builder_1 import build_graph
#from app.agents.memory.conversation_history import get_history
from app.schemas.chat import ChatResultStatus, ChatRequest
#from app.agents.memory.conversation_history import get_history, add_to_history 
import os
import csv, asyncio
from app.models import *
from app.schemas.chat import *
from app.core import get_db
import json
from app.utils.json_custom_serializer import custom_serializer
from app.utils.paraphraser import paraphrase
from app.utils.redshift_connection import redshift_connection as authenticate_redshift_user
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.utils.sql_metadata import extract_sql_metadata
from app.models.metadataresponsemodel import SQLParseResult
import httpx
import re
import ast

router = APIRouter()
 
@router.post("/chat")
async def chat_sql(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    question = payload.question
    user = payload.user
    analysis_id = payload.analysis_id

    # db: Session = SessionLocal()

    # Async DB query
    analysisObj = await db.execute(
        select(Analysis).filter(Analysis.created_by == user, Analysis.id == analysis_id)
    )
    analysis = analysisObj.scalars().first()

    if not analysis:
        return {
            "message" : "There is no Analysis with this ID"
        }

    # ?? Run graph builder
    state = {
        "question": question,
        "session_id": "1234"
    }

    result = await graph_builder.ainvoke(state)

    # user_input = ReActState(messages=[{"role": "user", "content": question}])
    # result = await graph_builder.ainvoke(user_input)
    # for message in result["messages"]:
    #     if (message.content):
    #         msg=message.content
        #print(1)
        #print(message.content)
        #print(msg)
    # print("Printing MSG")
    # print(msg)

    try:
        # pattern = r"Decimal\('(?P<value>.*?)'\)"
        # replaced_string = re.sub(pattern, r"'\g<value>'", msg)
        # null_to_string_pattern = r'\bnull\b'
        # replaced_string = re.sub(null_to_string_pattern, '"null"', replaced_string)
        # #print(2)
        # python_dict = ast.literal_eval(replaced_string)
        # #print(3)
        # # Convert the dictionary to a valid JSON string using json.dumps()
        # json_string = json.dumps(python_dict,default=custom_serializer)
        # #print(4)
        # #print(json_string)
        # result = json.loads(json_string)
        #print(5)
        output = result.get("result")
        sql = result.get("sql")
        summary = result.get("summary")
        
        if not sql or sql in ('GENERIC_QUERY_FAILED_VALIDATION_OR_ACCURACY_CHECK', 'INVALID_QUERY_FAILED_EXECUTION'):
            #summary = f"This assistant is specialized for banking analytics; I can’t answer questions about {question}."
            summary = f"This assistant is specialized in targeted analytics; I can’t answer question: {question}."

        execution_output=json.dumps(output,default=custom_serializer)
        #execution_output = json.dumps(output, default=str)

        history_entry = Conversation(
            analysis_id = analysis.id,
            user_question = question,
            sql_generated = sql,
            execution_output = execution_output,
            summary = summary
        )
        db.add(history_entry)
        await db.commit()
        await db.refresh(history_entry)
        return {
            "user": user,
            "question": question,
            "display_type" : "chart",
            "chart_type" : "bar",
            "sql": sql,
            #"validquery": result.get("valid_sql"),
            "result":result.get("result"),
            "classification":result.get("classification"),
            "summary" : summary,
            "suggestions": result.get("suggestions"),
            "created_at" : history_entry.created_at,
            "conversation_id": history_entry.id
        }
    except Exception as e:
        #print(e)
        if msg == question:
            msg = f"This assistant is specialized for banking analytics; I can’t answer questions about {question}."

        return {
            "user": user,
            "question": question,
            "display_type" : "chart",
            "chart_type" : "bar",
            "sql": "GENERIC_QUERY_FAILED_VALIDATION_OR_ACCURACY_CHECK",
            #"validquery": result.get("valid_sql"),
            "result": "",
            "classification":"",
            "summary" : msg,
            "suggestions": "",
            "created_at" : "",
            "conversation_id": ""
        }
        
@router.post("/update_result")
async def update_prompts_repo(req: ChatResultStatus, db: AsyncSession = Depends(get_db)):
    file_path = os.path.join("app", "static", "PE_PAIRS.csv")
    row_data = [req.query, req.prompt]

    try:
        # Run blocking Redshift connection in a thread
        conn = await authenticate_redshift_user(
            username="ptx_developer",
            password="PTX_dev@aws775"
        )
        if conn is None:
            return {"message": "Cannot Update Prompts Repo as cannot connect to redshift to validate query"}

        cursor = conn.cursor()
        try:
            # Run blocking cursor operations in a thread
            await asyncio.to_thread(cursor.execute, "SET search_path TO l2_reporting_sch;")
            await asyncio.to_thread(cursor.execute, req.query)
            rows = await asyncio.to_thread(cursor.fetchall)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
        finally:
            cursor.close()
            conn.close()

        # Append to CSV in a thread
        def append_row(path, data):
            with open(path, mode="a", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(data)

        await asyncio.to_thread(append_row, file_path, row_data)

    except Exception:
        return {"message": "Cannot Update Prompts Repo due to invalid query"}

    return {"message": "Prompts Repo Updated Successfully"}

@router.get("/get_analysis_by_user")
async def get_analysis_by_user(user: str, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Analysis)
        .where(Analysis.created_by == user)
        .order_by(Analysis.created_at.desc())
    )
    result = await db.execute(stmt)
    analyses = result.scalars().all()

    return [
        {
            "analysis_id": s.id,
            "analysis_name": s.name,
            "created_at": s.created_at,
        }
        for s in analyses
    ]

@router.post("/create_analysis")
async def create_analysis(req: AnalysisRequest, db: AsyncSession = Depends(get_db)):
    # Check if analysis with same name already exists for this user
    stmt = select(Analysis).where(
        Analysis.name == req.analysis_name,
        Analysis.created_by == req.user
    )
    result = await db.execute(stmt)
    check = result.scalars().first()

    if check:
        return {"message": "Analysis name already exists"}

    analysis = Analysis(
        name=req.analysis_name,
        created_by=req.user
    )

    try:
        db.add(analysis)
        await db.commit()
        # Refresh to populate autogenerated fields like id
        await db.refresh(analysis)

        return {
            "message": "Analysis Created",
            "analysis_id": analysis.id
        }
    except Exception:
        await db.rollback()
        return {"message": "Unable to Create new Analysis"}

@router.get("/get_conversation_by_analysis_id")
async def get_conversation_by_analysis_id(
    analysis_id: int,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Conversation)
        .where(Conversation.analysis_id == analysis_id)
        .order_by(Conversation.id.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [
        {   
            "conversation_id": r.id,
            "question": r.user_question,
            "sql": r.sql_generated,
            "execution_output": json.loads(r.execution_output),
            "summary": r.summary,
            "created_at": r.created_at,
        }
        for r in rows
    ]

@router.post("/generate-engagement")
async def generate_engagement(request: EngagementRequest):
    user_query = request.user_query.strip()

    welcome_phrases = [
        "Okay, I understood your query, you want me to",
        "Got it! You're asking me to",
        "Sure, you're looking for me to",
        "Understood. You'd like me to",
        "Alright, you're requesting me to",
        "Thanks for the question! You want me to",
        "Let me help you with this — you want me to"
    ]

    selected_phrase = random.choice(welcome_phrases)

    # If paraphrase is blocking (e.g. calls a model), run it in a thread
    paraphrased_query = await paraphrase(user_query)

    engagement_line = f"{selected_phrase} {paraphrased_query}"

    return {"engagementline": engagement_line}

@router.get("/get_sql_metadata_by_conversation_id", response_model=SQLParseResult)
async def get_sql_metadata_by_conversation_id(conversation_id: int, username: str, db: AsyncSession = Depends(get_db)):
    try:
        try:
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await db.execute(stmt)
            conversation = result.scalars().first()
        except Exception:
            return {"message": "Error fetching conversation from database"}
        if not conversation:
            return {"message": "Conversation not found"}
        sql_query = conversation.sql_generated
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://ec2-54-197-97-14.compute-1.amazonaws.com:9995/check_privilege_by_user",
                    json={"user": username, "privilege": "List Technical Source"}
                )
                privilege_data = response.json()
        except Exception:
            return {"message": "Privilege check failed"}
        try:
            metadata = await extract_sql_metadata(sql_query)
        except Exception:
            return {"message": "Error extracting SQL metadata"}
        if not privilege_data.get("has_privilege", False):
            metadata.sql = None
        return metadata
    except Exception:
        return {"message": "Unexpected error occurred"}
