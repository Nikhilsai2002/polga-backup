from __future__ import annotations

from typing import TypedDict, Annotated, List, Dict, Required
from langgraph.graph.message import add_messages
from dataclasses import dataclass, field
from typing import Sequence, Optional
from langchain_core.messages import AnyMessage
from langgraph.managed import IsLastStep
from typing_extensions import Annotated


# class State(TypedDict, total=False):
#     question: Required[str]
#     top_5_queries: str
#     sql: str
#     valid_sql: bool
#     context: str
#     classification: str
#     result: Dict
#     session_id: Required[str]

class SQLValidation(TypedDict, total=False):
    session_id: Required[str]
    question: Required[str]
    query: Required[str]
    valid_sql: bool
    accuracy: float

class SemanticSQLRetrievalState(TypedDict, total=False):
    session_id: Required[str]
    question: Required[str]
    top_5_queries: List[str]
    validated_queries: List[SQLValidation]
    sql: str

class LimitedDataDictionarySQLQueryGenerationState(TypedDict, total=False):
    session_id: Required[str]
    question: Required[str]
    sql_query_retrieved: Required[str]
    # sql: str
    validated_queries: List[SQLValidation]

class State(TypedDict, total=False):
    session_id: str
    question: Required[str]
    top_5_queries: List[str]
    sql: str
    context: str
    result: Dict
    summary: str
    suggestions: List[str]
    classification: str = field(default='IN_SCOPE')

@dataclass
class ReActState:
    """Represents the complete state of the agent.

    This class stores all information needed throughout the agent's lifecycle.
    """

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(default_factory=list)
    """
    Tracks the conversation history and tool interactions.
    """

    is_last_step: IsLastStep = field(default=False)
    """
    Indicates whether the current step is the last one before the graph raises an error.
    """

    tool_request: Optional[dict[str, str]] = field(default=None)
    """
    Stores parsed tool call information from the model, if any.
    Format: {"name": <tool_name>, "input": <tool_input>}
    """

    classification: str = field(default='IN_SCOPE')

