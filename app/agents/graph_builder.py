# from IPython.display import display, Image
from langgraph.graph import StateGraph, START, END
from app.agents.state import State
from app.agents.nodes import *

def build_graph():
    graph = StateGraph(State)
    graph.add_node("read_data_dict", read_data_dict)
    graph.add_node("search_similar", search_similar)
    graph.add_node("generate_sql", generate_sql)
    graph.add_node("sql_validation", sql_validation)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("classify_intent", classify_intent)

    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        lambda state: "read_data_dict" if state.get("classification") == "IN_SCOPE" else END,
        {
            "read_data_dict": "read_data_dict",
            END: END
        }
    )
    #graph.add_edge("classify_intent","read_data_dict")
    # graph.add_edge(START,"read_data_dict")
    graph.add_edge("read_data_dict", "search_similar")
    graph.add_edge("search_similar", "generate_sql")
    graph.add_edge("generate_sql", "sql_validation")
    # graph.add_edge("sql_validation", "execute_sql")
    graph.add_conditional_edges(
        "sql_validation",
        lambda state: "execute_sql" if state.get("valid_sql") else END,
        {
            "execute_sql": "execute_sql",
            END: END
        }
    )

    graph.add_edge("execute_sql", END)

    # Compiling the Graph
    graph_builder = graph.compile()
    return graph_builder

    # display(Image(graph_builder.get_graph().draw_mermaid_png()))