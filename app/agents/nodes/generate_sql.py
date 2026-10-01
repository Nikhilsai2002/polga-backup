import re
import asyncio
from app.agents.state import State
from app.core.llm_loader import llm

# ----------------- Helpers -----------------
def extract_tables(sql: str) -> set:
    """Extract table names from SQL after FROM / JOIN"""
    tables = re.findall(r"\bFROM\s+(\w+)|\bJOIN\s+(\w+)", sql, flags=re.IGNORECASE)
    return {tbl for tup in tables for tbl in tup if tbl}

def extract_columns(sql: str) -> set:
    """Extract column names from SQL after SELECT"""
    match = re.search(r"SELECT\s+(.*?)\s+FROM", sql, flags=re.IGNORECASE | re.DOTALL)
    if match:
        cols = match.group(1).split(",")
        return {c.strip().lower() for c in cols}
    return set()

async def is_followup_query(new_query: str, history: list, llm_instance=None) -> bool:
    """Determine if new_query is a follow-up to the last query in history"""
    if not history:
        return False
    
    last_question = history[-1]["question"]
    last_sql = history[-1]["sql"]

    last_tables = extract_tables(last_sql)
    new_tables = extract_tables(new_query)
    last_columns = extract_columns(last_sql)
    new_columns = extract_columns(new_query)

    if not (last_tables & new_tables):
        return False
    if not (last_columns & new_columns):
        return False

    if llm_instance is None:
        return False

    followup_check_prompt = f"""
    You are a SQL follow-up detector.

    Previous Question:
    {last_question}

    New Question:
    {new_query}

    Decide if the new question is a modification of the previous SQL query.
    A modification means the new question:
    - Adds or removes filters (WHERE clause),
    - Changes sorting or ordering (ORDER BY),
    - Groups or aggregates differently (GROUP BY, HAVING),
    - Adds/removes columns in SELECT,
    - Changes DISTINCT or LIMIT,
    - Changes conditions while keeping the same core intent.

    If the new question instead asks for a completely different data set or metric, then it is NOT a follow-up.

    Answer strictly with YES or NO.
    """

    # If llm supports async:
    # response = await llm_instance.ainvoke([{"role": "user", "content": followup_check_prompt}])
    # Otherwise:
    response = await asyncio.to_thread(llm_instance.invoke, [{"role": "user", "content": followup_check_prompt}])
    answer = response.content.strip().upper()
    return answer == "YES"

# ----------------- Main Function -----------------
async def generate_sql(state: State) -> State:
    """Generate SQL from user query with follow-up detection"""
    print("Generating SQL")
    query = state['question']
    u_query = ''.join([i for i in query if i.isalnum() or i.isspace()]).lower()
    context_text = state['context']
    session_id = state['session_id']

    prompt = f"""You are an SQL query generator. Use ONLY the provided schema and relations to generate SQL query for the user prompt.

            SCHEMA CONTEXT:
            {context_text}

            USER QUERY:
            {u_query}
    """

    system_message = (
        "STRICTLY use ONLY the provided context schema for generating queries. "
        "STRICTLY USE the correct column and table names as provided in the schema context. "
        "When making joins pay close attention to the foreign key relationships provided in the schema context. "
        "FK relationships are the ONLY valid joins you can make. "
        "The FROM and JOIN tables must be relevant to the user's query and MUST exist in the schema. "
        "STRICTLY DO NOT create, infer, assume, or rename any tables, columns, or relationships not explicitly listed in the schema. "
        "STRICTLY DO NOT map absent columns to existing schema columns even if they seem similar. "
        "Use the GROUP BY, WHERE, AND HAVING clause wherever it seems to be relevant to the prompt. "
        "Use the RELATION lines provided to determine joins; NEVER invent join conditions. "
        "If the query requires unavailable data, respond EXACTLY with: NOT PRESENT. "
        "Output MUST STRICTLY be a single raw executable SQL query with no additional commentary or information."
    )

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt},
    ]

    # If llm supports async:
    # response = await llm.ainvoke(messages)
    # Otherwise:
    response = await asyncio.to_thread(llm.invoke, messages)

    text = response.content.strip().replace("```sql", "").replace("```", "").replace("\n", " ").strip()
    state['sql'] = text
    return state
