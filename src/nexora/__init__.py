"""
Nexora — Production Hybrid RAG & Multi-Tool Agentic Platform
============================================================
"""

__version__ = "0.1.0"

from nexora.core.agent import chatbot, create_agent
from nexora.core.database import retrieve_all_threads, clear_all_history

__all__ = [
    "__version__",
    "chatbot",
    "create_agent",
    "retrieve_all_threads",
    "clear_all_history",
]
