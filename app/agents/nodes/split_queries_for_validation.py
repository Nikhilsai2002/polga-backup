from app.agents.state import State, SQLValidation
from typing import List
from app.agents.sql_validation_graph import sql_validation_graph_build as graph_builder
import asyncio

async def split_queries_for_validation(state: State) -> State:
    print("Splitting queries for validation")
    res: List[SQLValidation] = []

    for q in state["top_5_queries"]:
        print("validating")
        sqlState = {
            "query": q,
            "session_id": state["session_id"],
            "question": state["question"]
        }

        # If graph_builder.invoke is async:
        # result: SQLValidation = await graph_builder.invoke(sqlState)

        # If graph_builder.invoke is sync (most likely):
        result: SQLValidation = await graph_builder.ainvoke(sqlState)


        if result['valid_sql']:
            res.append(result)

    # Sort by accuracy descending
    res.sort(key=lambda x: x['accuracy'], reverse=True)

    state["top_5_queries"] = [r["query"] for r in res]

    if len(res) > 0 and res[0]["accuracy"] >= 50:
        state['sql'] = res[0]["query"]

    return state
