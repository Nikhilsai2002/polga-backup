# from IPython.display import display, Image
from langgraph.graph import StateGraph, START, END
from app.agents.state import State
from app.agents.nodes import *

from typing import TypedDict, Annotated, List, Dict
from langgraph.graph.message import add_messages

# from IPython.display import Image, display


def build_graph():
    graph = StateGraph(State)

    graph.add_node("classify_intent", classify_intent)
    graph.add_node("prompt_matching", get_associated_query)
    # graph.add_node("semantic_sql_extraction", semantic_sql_extraction)
    # graph.add_node("split_queries_for_validation", split_queries_for_validation)
    # graph.add_node("trim_data_dictionary_and_generate_sql", trim_data_dictionary_and_generate_sql)
    # graph.add_node("split_queries_for_validation_2", split_queries_for_validation)
    graph.add_node("read_data_dict", read_data_dict)
    graph.add_node("search_similar", search_similar)
    graph.add_node("generate_sql", generate_sql)
    graph.add_node("sql_validation", validate_generic_sql)
    graph.add_node("execute_sql", execute_sql)
    graph.add_node("summarize", summarize)
    

    # Semantic Search SQL Generation
    graph.add_edge(START, "classify_intent")
    # graph.add_edge(START, "prompt_matching")
    graph.add_conditional_edges(
        "classify_intent",
        lambda state: "prompt_matching" if state.get("classification") == "IN_SCOPE" else END,
        {
            "prompt_matching": "prompt_matching",
            END: END
        }
    )
    # graph.add_edge("semantic_sql_extraction", "split_queries_for_validation")
    graph.add_conditional_edges(
        "prompt_matching",
        lambda state: "execute_sql" if "sql" in state else "read_data_dict",
        {
            "execute_sql": "execute_sql",
            "read_data_dict": "read_data_dict"
        }
    )

    # Trimmed Data Dictionary SQL Generation
    # graph.add_edge("trim_data_dictionary_and_generate_sql", "split_queries_for_validation_2")
    # graph.add_conditional_edges(
    #     "split_queries_for_validation_2",
    #     lambda state: "execute_sql" if "sql" in state else "read_data_dict",
    #     {
    #         "execute_sql": "execute_sql",
    #         "read_data_dict": "read_data_dict"
    #     }
    # )

    # Generic SQL Generation
    graph.add_edge("read_data_dict", "search_similar")
    graph.add_edge("search_similar", "generate_sql")
    graph.add_edge("generate_sql", "sql_validation")
    # graph.add_edge("sql_validation", "execute_sql")
    graph.add_conditional_edges(
        "sql_validation",
        lambda state: "execute_sql" if state["sql"] != "GENERIC_QUERY_FAILED_VALIDATION_OR_ACCURACY_CHECK" else END,
        {
            "execute_sql": "execute_sql",
            END: END
        }
    )

    graph.add_conditional_edges(
        "execute_sql",
        lambda state: "summarize" if state["sql"] != "INVALID_QUERY_FAILED_EXECUTION" else END,
        {
            "summarize": "summarize",
            END: END
        }
    )
    graph.add_edge("summarize", END)


    # Compiling the Graph
    graph_builder = graph.compile()
    return graph_builder

    # display(Image(graph_builder.get_graph().draw_mermaid_png()))

# graph_builder = build_graph()
# display(Image(graph_builder.get_graph().draw_mermaid_png()))
sql_generation_graph = build_graph()

