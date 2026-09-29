"""
Nexora Core Async Agent Graph
==============================
Defines the asynchronous LangGraph StateGraph, nodes, edges, LLM binding,
and compiled chatbot backed by AsyncPostgresSaver checkpointer.
"""

import sys
from pathlib import Path
from typing import Optional

# Ensure src directory is on sys.path for direct invocation
_src_dir = str(Path(__file__).resolve().parent.parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import HumanMessage, BaseMessage

from nexora.config import GROQ_API_KEY, GROQ_MODEL, DEFAULT_DOC_PATH
from nexora.core.state import ChatState
from nexora.core.prompts import build_system_prompt
from nexora.core.async_database import get_async_checkpointer
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
# 2. Async Graph Nodes & Edges
# ------------------------------------------------------------
async def chat_node(state: ChatState):
    """Async LLM node: evaluates user intent and responds or calls appropriate tools."""
    active_doc = state.get("active_doc", DEFAULT_DOC_PATH)
    system_prompt = build_system_prompt(active_doc)
    messages = [system_prompt] + state["messages"]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


def create_async_workflow():
    """Builds the uncompiled StateGraph agent workflow."""
    workflow = StateGraph(ChatState)
    workflow.add_node("chat_node", chat_node)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "chat_node")
    workflow.add_conditional_edges("chat_node", tools_condition, END)
    workflow.add_edge("tools", "chat_node")
    return workflow


_async_chatbot = None


async def get_async_chatbot():
    """Returns the singleton compiled async chatbot with AsyncPostgresSaver checkpointer."""
    global _async_chatbot
    if _async_chatbot is None:
        checkpointer = await get_async_checkpointer()
        workflow = create_async_workflow()
        _async_chatbot = workflow.compile(checkpointer=checkpointer)
    return _async_chatbot
