import asyncio
from app.agents.state import State
from app.core.llm_loader import llm

async def summarize(state: State) -> State:
    print("Generating summary...")
    sql_data = state["result"]
    question = state["question"]
    prompt = f"""
    You are an SQL query result summariser. I am giving you the result of an SQL query in JSON format, and I want you to STRICTLY ONLY summarise the TABULAR RESULT correctly in plain English.
    USER PROMPT: {question}
    TABULAR RESULT: {sql_data}
    """

    messages = [
        {
            "role": "system",
            "content": (
                "You are capable of reading tabular data and summarising it correctly into plain English. "
                "STRICTLY always interpret the data correctly. "
                "STRICTLY use human friendly English language to explain. "
                "STRICTLY DO NOT read the data as it is. "
                "STRICTLY DO NOT provide any code or script. Just give me plain english summary."
                "STRICTLY FORM THE FINDINGS in concise sentences to show ONGOING TRENDS and possible OUTLIERS. "
                "I am also providing you with the user prompt, STRICTLY USE this along with the data to better craft the summary."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    # If llm supports async:
    # response = await llm.ainvoke(messages)

    # Otherwise, run sync invoke in a thread:
    response = await asyncio.to_thread(llm.invoke, messages)
 
    state["summary"] = response.content
    return state
