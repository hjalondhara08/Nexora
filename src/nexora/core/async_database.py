"""
Nexora Async PostgreSQL & PGVector Memory Persistence Module
============================================================
Provides fully async LangGraph checkpointing via AsyncPostgresSaver,
and semantic memory vector persistence via PGVector (vector(1024)).
"""

import os
import asyncio
from typing import Optional, List, Dict, Any
import numpy as np
import psycopg
from psycopg_pool import AsyncConnectionPool
from pgvector.psycopg import register_vector_async
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.messages import HumanMessage, AIMessage
from langchain_cohere import CohereEmbeddings

from nexora.config import POSTGRES_URL, COHERE_API_KEY

_pool: Optional[AsyncConnectionPool] = None
_checkpointer: Optional[AsyncPostgresSaver] = None
_embeddings: Optional[CohereEmbeddings] = None


def get_embeddings_client() -> Optional[CohereEmbeddings]:
    """Returns CohereEmbeddings instance if COHERE_API_KEY is configured."""
    global _embeddings
    if _embeddings is None and COHERE_API_KEY:
        try:
            _embeddings = CohereEmbeddings(
                cohere_api_key=COHERE_API_KEY,
                model="embed-english-v3.0",
            )
        except Exception as e:
            print(f"Warning: Could not initialize CohereEmbeddings: {e}")
    return _embeddings


async def get_async_pool() -> AsyncConnectionPool:
    """Returns singleton AsyncConnectionPool with autocommit enabled."""
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=POSTGRES_URL,
            min_size=2,
            max_size=15,
            open=False,
            kwargs={"autocommit": True},
        )
        await _pool.open()
    return _pool


async def get_async_checkpointer() -> AsyncPostgresSaver:
    """Returns singleton AsyncPostgresSaver checkpointer instance."""
    global _checkpointer
    if _checkpointer is None:
        pool = await get_async_pool()
        _checkpointer = AsyncPostgresSaver(pool)
    return _checkpointer


async def init_async_database() -> None:
    """Initializes PGVector extension, checkpointer migrations, and conversation_memory table."""
    pool = await get_async_pool()
    async with pool.connection() as conn:
        # Enable pgvector extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await register_vector_async(conn)

        # Create conversation_memory table with vector(1024)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_memory (
                id SERIAL PRIMARY KEY,
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding vector(1024),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_conv_memory_thread ON conversation_memory (thread_id);
        """)

    # Setup LangGraph Postgres checkpointer tables
    checkpointer = await get_async_checkpointer()
    await checkpointer.setup()
    print("✅ Async PostgreSQL & PGVector memory initialization complete.")


async def save_memory_vector_async(thread_id: str, role: str, content: str) -> None:
    """Generates embedding for a message and stores it into pgvector conversation_memory."""
    if not content or not content.strip():
        return

    vec = None
    embedder = get_embeddings_client()
    if embedder:
        try:
            raw_emb = await asyncio.to_thread(embedder.embed_query, content[:1500])
            if raw_emb and len(raw_emb) == 1024:
                vec = np.array(raw_emb, dtype=np.float32)
        except Exception as e:
            print(f"Notice: Memory embedding generation skipped: {e}")

    pool = await get_async_pool()
    async with pool.connection() as conn:
        await register_vector_async(conn)
        if vec is not None:
            await conn.execute(
                """
                INSERT INTO conversation_memory (thread_id, role, content, embedding)
                VALUES (%s, %s, %s, %s::vector);
                """,
                (thread_id, role, content, vec),
            )
        else:
            await conn.execute(
                """
                INSERT INTO conversation_memory (thread_id, role, content)
                VALUES (%s, %s, %s);
                """,
                (thread_id, role, content),
            )


async def search_memory_vectors_async(
    query: str,
    thread_id: Optional[str] = None,
    limit: int = 4,
) -> List[Dict[str, Any]]:
    """Performs semantic cosine similarity search in conversation_memory using pgvector."""
    embedder = get_embeddings_client()
    if not embedder:
        return []

    try:
        raw_emb = await asyncio.to_thread(embedder.embed_query, query)
        query_vec = np.array(raw_emb, dtype=np.float32)
    except Exception as e:
        print(f"Memory search embedding error: {e}")
        return []

    pool = await get_async_pool()
    results = []
    async with pool.connection() as conn:
        await register_vector_async(conn)
        async with conn.cursor() as cur:
            if thread_id:
                sql = """
                    SELECT id, thread_id, role, content, (1 - (embedding <=> %s::vector)) AS similarity
                    FROM conversation_memory
                    WHERE embedding IS NOT NULL AND thread_id = %s
                    ORDER BY embedding <=> %s::vector ASC
                    LIMIT %s;
                """
                await cur.execute(sql, (query_vec, thread_id, query_vec, limit))
            else:
                sql = """
                    SELECT id, thread_id, role, content, (1 - (embedding <=> %s::vector)) AS similarity
                    FROM conversation_memory
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector ASC
                    LIMIT %s;
                """
                await cur.execute(sql, (query_vec, query_vec, limit))

            rows = await cur.fetchall()
            for r in rows:
                results.append({
                    "id": r[0],
                    "thread_id": r[1],
                    "role": r[2],
                    "content": r[3],
                    "similarity": float(r[4]) if r[4] is not None else 0.0,
                })
    return results


async def retrieve_all_threads_async() -> List[Dict[str, Any]]:
    """Returns all unique conversation threads with preview labels and metadata."""
    pool = await get_async_pool()
    threads = []
    seen = set()

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Query distinct threads from checkpoints and conversation_memory
            await cur.execute("""
                SELECT DISTINCT thread_id FROM (
                    SELECT thread_id FROM checkpoints
                    UNION
                    SELECT thread_id FROM conversation_memory
                ) combined
                ORDER BY thread_id DESC;
            """)
            rows = await cur.fetchall()

            for (tid,) in rows:
                if not tid or tid in seen:
                    continue
                seen.add(tid)

                # Fetch the first user message for a clean preview label
                await cur.execute("""
                    SELECT content FROM conversation_memory
                    WHERE thread_id = %s AND role = 'user'
                    ORDER BY id ASC LIMIT 1;
                """, (tid,))
                first_msg_row = await cur.fetchone()

                if first_msg_row and first_msg_row[0]:
                    txt = first_msg_row[0].strip()
                    label = (txt[:26] + "...") if len(txt) > 26 else txt
                else:
                    label = f"{tid[:8]}..." if len(str(tid)) > 12 else str(tid)

                threads.append({
                    "thread_id": tid,
                    "label": label,
                })

    return threads


async def retrieve_thread_messages_async(thread_id: str) -> List[Dict[str, str]]:
    """Loads all human and assistant messages for a thread from pgvector conversation_memory or checkpointer."""
    pool = await get_async_pool()
    messages = []

    # First attempt: load structured message history from conversation_memory
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                SELECT role, content FROM conversation_memory
                WHERE thread_id = %s
                ORDER BY id ASC;
            """, (thread_id,))
            rows = await cur.fetchall()
            for role, content in rows:
                if content and content.strip():
                    messages.append({"role": role, "content": content})

    # Fallback to checkpoint state if memory table is empty for this thread
    if not messages:
        checkpointer = await get_async_checkpointer()
        checkpoint_tuple = await checkpointer.aget_tuple(config={"configurable": {"thread_id": thread_id}})
        if checkpoint_tuple and checkpoint_tuple.checkpoint:
            state_msgs = checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
            for msg in state_msgs:
                if isinstance(msg, HumanMessage) and msg.content:
                    messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg, AIMessage) and msg.content:
                    messages.append({"role": "assistant", "content": msg.content})

    return messages


async def delete_thread_async(thread_id: str) -> None:
    """Permanently deletes a thread from checkpointer tables and pgvector memory."""
    pool = await get_async_pool()
    async with pool.connection() as conn:
        await conn.execute("DELETE FROM conversation_memory WHERE thread_id = %s;", (thread_id,))
        await conn.execute("DELETE FROM checkpoints WHERE thread_id = %s;", (thread_id,))
        await conn.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s;", (thread_id,))
        await conn.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s;", (thread_id,))


async def clear_all_history_async() -> None:
    """Wipes all conversation histories and pgvector memory data."""
    pool = await get_async_pool()
    async with pool.connection() as conn:
        await conn.execute("DELETE FROM conversation_memory;")
        await conn.execute("DELETE FROM checkpoints;")
        await conn.execute("DELETE FROM checkpoint_writes;")
        await conn.execute("DELETE FROM checkpoint_blobs;")
