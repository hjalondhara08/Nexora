"""
State definition for the Nexora LangGraph Agent.
"""

from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ChatState(TypedDict):
    """Represents the conversation state in the LangGraph execution flow."""
    messages: Annotated[list[BaseMessage], add_messages]
    active_doc: str
