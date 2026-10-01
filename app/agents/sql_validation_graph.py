from langgraph.graph import StateGraph, START, END
from app.agents.state import SQLValidation
from app.agents.nodes import *

def sql_validation_graph():
    graph = StateGraph(SQLValidation)

    graph.add_node("sql_validation", sql_validation)

    graph.add_edge(START, "sql_validation")
    graph.add_edge("sql_validation", END)

    graph_builder = graph.compile()
    return graph_builder

sql_validation_graph_build = sql_validation_graph()
