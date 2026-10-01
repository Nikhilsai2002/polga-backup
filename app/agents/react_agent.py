from datetime import UTC, datetime
from typing import Dict, List, Literal, cast, Optional
import re

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime

from app.agents.state import ReActState
from app.agents.tools import TOOLS
from app.agents.nodes import classify_intent
from app.core.llm_loader import get_llm

# Hardcoded configuration
SYSTEM_PROMPT = """
You are a specialized banking agent designed to answer financial and operational questions
by using the tools provided. Be humble while answering.

Current time: {system_time}

Available tool:

**query_banking_data**
- Purpose: Retrieve financial or operational insights from a banking data warehouse.
- Input: A natural language question (e.g., "Show me the total deposits by region for Q2").
- Behavior: This tool converts the input into a SQL query, executes it against the data warehouse,
  and returns the result.

Instructions:
- Always use the tool to answer banking related user queries.
- If the tool returns structured data, already summarize it in plain language for the user.

Always be clear, concise, and helpful.

When you need banking data, output exactly:
query_banking_data "<question>"
Do not add explanations or extra text.
"""

MODEL_NAME = "gpt-4o-mini"

# Load the model from Azure OpenAI
def load_chat_model(model_name: str = MODEL_NAME):
    return get_llm(model_name)

# Regex parser for tool calls
def parse_tool_call(text: str) -> Optional[dict[str, str]]:
    match = re.search(r'query_banking_data\s+"(.+?)"', text)
    if match:
        return {"name": "query_banking_data", "input": match.group(1)}
    return None

# Node: call the model
async def call_model(state: ReActState, runtime: Runtime) -> Dict[str, List[AIMessage]]:
    model = load_chat_model()
    system_message = SYSTEM_PROMPT.format(system_time=datetime.now(tz=UTC).isoformat())

    response = cast(
        AIMessage,
        await model.ainvoke([{"role": "system", "content": system_message}, *state.messages])
    )

    print("\n🧠 Model reasoning:")
    print(response.content)

    tool_call = parse_tool_call(response.content)
    if tool_call:
        # Normalize into AIMessage.tool_calls so ToolNode can pick it up
        normalized = AIMessage(
            content="",  # tool messages usually have empty content
            tool_calls=[{
                "id": f"call-{int(datetime.now().timestamp())}",
                "name": tool_call["name"],
                "args": {"question": tool_call["input"]},
            }]
        )
        print("\n🔄 Tool call detected. Normalizing for ToolNode.")
        return {"messages": [normalized]}

    return {"messages": [response]}

# Router: decide whether to end or go to tools
def route_model_output(state: ReActState) -> Literal["__end__", "tools"]:
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )
    if not last_message.tool_calls:
        print("\n✅ No tool calls detected. Ending conversation.")
        return "__end__"

    print("\n🔄 Tool call detected. Routing to tools.")
    return "tools"

# Build the graph
def build_graph():
    builder = StateGraph(ReActState, input_schema=ReActState)

    builder.add_node(call_model)
    builder.add_node("tools", ToolNode(TOOLS))
    builder.add_node("classify_intent", classify_intent)


    builder.add_edge("__start__", "classify_intent")
    builder.add_conditional_edges(
        "classify_intent",
        lambda state: "call_model" if state.classification == "IN_SCOPE" else "END",
        {
            "call_model": "call_model",
            "END": "__end__",
        }
    )
    # builder.add_edge("__start__", "call_model")
    builder.add_conditional_edges("call_model", route_model_output)

    # Instead of looping back, end after tools
    builder.add_edge("tools", "__end__")

    return builder.compile(name="ReAct Agent")


ReActAgent = build_graph()
