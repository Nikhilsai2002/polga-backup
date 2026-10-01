import asyncio
from app.agents.state import State, SQLValidation
from app.agents.sql_validation_graph import sql_validation_graph_build as graph_builder

async def validate_generic_sql(state: State) -> State:
    sqlState = {
        "query": state["sql"],
        "session_id": state["session_id"],
        "question": state["question"]
    }

    # If graph_builder.invoke is async:
    # result: SQLValidation = await graph_builder.invoke(sqlState)

    # If it's synchronous (most likely):
    result: SQLValidation = await graph_builder.ainvoke(sqlState)


    if not result['valid_sql']:
        state["sql"] = "GENERIC_QUERY_FAILED_VALIDATION_OR_ACCURACY_CHECK"

    return state
