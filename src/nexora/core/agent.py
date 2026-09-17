"""
Nexora Core Agent Graph
=======================
Defines the LangGraph StateGraph, nodes, edges, LLM binding, and compiled chatbot.
"""

import sys
from pathlib import Path

# Ensure src directory is on sys.path for direct invocation
_src_dir = str(Path(__file__).resolve().parent.parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import HumanMessage

from nexora.config import GROQ_API_KEY, GROQ_MODEL, DEFAULT_DOC_PATH
from nexora.core.state import ChatState
from nexora.core.prompts import build_system_prompt
from nexora.core.database import get_checkpointer, retrieve_all_threads, clear_all_history
from nexora.tools import tools

# ------------------------------------------------------------
# 1. LLM Initialization & Tool Binding
# ------------------------------------------------------------
llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model=GROQ_MODEL,
)

llm_with_tools = llm.bind_tools(tools)
tool_node = ToolNode(tools)


# ------------------------------------------------------------
# 2. Graph Nodes & Edges
# ------------------------------------------------------------
def chat_node(state: ChatState):
    """LLM node: evaluates user intent and responds or calls appropriate tools."""
    active_doc = state.get("active_doc", DEFAULT_DOC_PATH)
    system_prompt = build_system_prompt(active_doc)
    messages = [system_prompt] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def create_agent(checkpointer=None):
    """Builds and compiles the StateGraph agent."""
    if checkpointer is None:
        checkpointer = get_checkpointer()

    workflow = StateGraph(ChatState)
    workflow.add_node("chat_node", chat_node)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "chat_node")
    workflow.add_conditional_edges("chat_node", tools_condition, END)
    workflow.add_edge("tools", "chat_node")

    return workflow.compile(checkpointer=checkpointer)


# Singleton compiled agent for easy import across modules
checkpointer = get_checkpointer()
chatbot = create_agent(checkpointer=checkpointer)


# ------------------------------------------------------------
# Quick CLI test
# ------------------------------------------------------------
if __name__ == "__main__":
    test_msg = "Hello! Tell me who you are and what tools you have."
    print(f"Testing Agent with query: '{test_msg}'...")
    res = chatbot.invoke(
        {"messages": [HumanMessage(content=test_msg)]},
        config={"configurable": {"thread_id": "cli-test"}},
    )
    print("Agent Response:\n", res["messages"][-1].content)
