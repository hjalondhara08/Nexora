"""
SQLite Checkpoint Persistence & Thread Management.
"""

import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from nexora.config import DB_PATH

_conn = None
_checkpointer = None


def get_connection() -> sqlite3.Connection:
    """Returns a shared thread-safe SQLite connection for checkpointer."""
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(database=DB_PATH, check_same_thread=False)
    return _conn


def get_checkpointer() -> SqliteSaver:
    """Returns the singleton SqliteSaver checkpointer instance."""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = SqliteSaver(conn=get_connection())
    return _checkpointer


def retrieve_all_threads() -> list[str]:
    """Returns all unique thread IDs stored in the SQLite checkpoint database."""
    checkpointer = get_checkpointer()
    all_threads = []
    seen = set()
    for checkpoint in checkpointer.list(None):
        tid = checkpoint.config.get("configurable", {}).get("thread_id")
        if tid and tid not in seen:
            seen.add(tid)
            all_threads.append(tid)
    return all_threads


def clear_all_history() -> None:
    """Wipes all conversation history from the SQLite checkpoint database."""
    with sqlite3.connect(DB_PATH, check_same_thread=False) as c:
        c.execute("DELETE FROM checkpoints;")
        c.execute("DELETE FROM writes;")
        c.commit()
