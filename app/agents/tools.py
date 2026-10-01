from typing import Any, Callable, List

from app.agents.graph_builder_1 import sql_generation_graph as graph_builder  # your compiled LangGraph

async def query_banking_data(question: str) -> dict[str, Any]:
    """Run a query against the banking data warehouse using a LangGraph agent."""
    state = {
        "question": question,
        "session_id": "1234"
    }

    result = await graph_builder.ainvoke(state)
    return result

TOOLS: List[Callable[..., Any]] = [query_banking_data]
