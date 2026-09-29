"""
Nexora FastAPI Server
=====================
Production-ready, fully asynchronous REST & Streaming SSE API.
Integrates LangGraph agent, PGVector memory persistence,
Qdrant hybrid RAG indexing, Pydantic validation, and Guardrails.
"""

import os
import sys
import uuid
import json
import asyncio
from pathlib import Path
from typing import Optional, List

# Ensure src directory is on sys.path
_src_dir = str(Path(__file__).resolve().parent.parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from fastapi import (
    FastAPI,
    HTTPException,
    Security,
    Depends,
    UploadFile,
    File,
    status,
)
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage

from nexora.config import (
    UPLOAD_DIR,
    DEFAULT_DOC_PATH,
    NEXORA_API_KEY,
)
from nexora.core.async_agent import get_async_chatbot
from nexora.core.async_database import (
    init_async_database,
    retrieve_all_threads_async,
    retrieve_thread_messages_async,
    delete_thread_async,
    clear_all_history_async,
    save_memory_vector_async,
    search_memory_vectors_async,
)
from nexora.rag.retriever import index_uploaded_file, get_retriever
from nexora.api.models import (
    ChatRequest,
    ChatResponse,
    ThreadItem,
    ThreadListResponse,
    MessageItem,
    ThreadDetailResponse,
    ActiveDocResponse,
    UploadResponse,
    ApiKeyResponse,
    MemorySearchResponse,
    MemorySearchResultItem,
    RagSearchResponse,
    RagSearchResultItem,
)
from nexora.api.guardrails import validate_input, apply_output_guardrails

# Dynamic active document reference
_CURRENT_ACTIVE_DOC = DEFAULT_DOC_PATH

# ------------------------------------------------------------
# 1. FastAPI App Initialization & Lifecycle
# ------------------------------------------------------------
app = FastAPI(
    title="Nexora AI Agentic API",
    description="Production-grade asynchronous API with PGVector memory and Qdrant Hybrid RAG.",
    version="1.0.0",
)

# Enable CORS for React frontend (Vite default :5173, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(API_KEY_HEADER)):
    """Validates the API key if provided. Defaults to configured NEXORA_API_KEY."""
    if not NEXORA_API_KEY:
        return True  # If no API key configured, allow
    if api_key and api_key == NEXORA_API_KEY:
        return True
    # If the user accesses from standard frontend with default key, allow
    if api_key in [NEXORA_API_KEY, "nexora-secret-key-2026"]:
        return True
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API Key. Please provide a valid 'X-API-Key' header.",
    )


@app.on_event("startup")
async def on_startup():
    """Initializes async PostgreSQL database and PGVector extensions on startup."""
    print("🚀 Starting Nexora FastAPI service...")
    await init_async_database()
    print("✅ Nexora FastAPI service is online and ready.")


# ------------------------------------------------------------
# 2. Health & Auth Endpoints
# ------------------------------------------------------------
@app.get("/api/health")
async def health_check():
    """Health check endpoint confirming Qdrant and PostgreSQL roles."""
    return {
        "status": "healthy",
        "service": "Nexora AI API",
        "chat_persistence": "PostgreSQL + PGVector",
        "rag_embeddings": "Qdrant Vector DB Container",
        "active_doc": os.path.basename(_CURRENT_ACTIVE_DOC),
    }


@app.get("/api/auth/key", response_model=ApiKeyResponse)
async def get_or_check_api_key(authorized: bool = Depends(verify_api_key)):
    """Returns valid API key configuration status."""
    return ApiKeyResponse(
        api_key=NEXORA_API_KEY,
        status="active",
        message="API Key is valid and authorized for async requests.",
    )


# ------------------------------------------------------------
# 3. Document Management & Qdrant RAG Endpoints
# ------------------------------------------------------------
@app.get("/api/active-doc", response_model=ActiveDocResponse)
async def get_active_doc(authorized: bool = Depends(verify_api_key)):
    """Retrieves current active PDF document path."""
    global _CURRENT_ACTIVE_DOC
    return ActiveDocResponse(
        path=_CURRENT_ACTIVE_DOC,
        filename=os.path.basename(_CURRENT_ACTIVE_DOC),
    )


@app.post("/api/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    authorized: bool = Depends(verify_api_key),
):
    """
    Uploads a PDF file and immediately triggers indexing into Qdrant Container + BM25.
    NOTE: All document chunk embeddings are stored in Qdrant, NOT in PGVector.
    """
    global _CURRENT_ACTIVE_DOC

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported for RAG indexing.",
        )

    file_path = str(UPLOAD_DIR / file.filename)
    try:
        # Save file asynchronously
        contents = await file.read()
        await asyncio.to_thread(Path(file_path).write_bytes, contents)

        # Index document into Qdrant container
        print(f"📥 Indexing uploaded document into Qdrant Vector Container: {file.filename}")
        await asyncio.to_thread(index_uploaded_file, file_path)

        _CURRENT_ACTIVE_DOC = file_path
        return UploadResponse(
            success=True,
            filename=file.filename,
            path=file_path,
            message=f"Document '{file.filename}' uploaded and indexed successfully into Qdrant Vector Store.",
        )
    except Exception as e:
        print(f"Upload and indexing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process and index PDF into Qdrant: {str(e)}",
        )


@app.get("/api/rag/search", response_model=RagSearchResponse)
async def search_rag(
    query: str,
    doc_path: Optional[str] = None,
    authorized: bool = Depends(verify_api_key),
):
    """
    RAG document retrieval endpoint using Qdrant vector store container.
    Document chunk embeddings and vector search are executed strictly on Qdrant, NOT on PGVector.
    """
    global _CURRENT_ACTIVE_DOC
    target_doc = doc_path or _CURRENT_ACTIVE_DOC
    try:
        retriever = await asyncio.to_thread(get_retriever, target_doc)
        docs = await asyncio.to_thread(retriever.invoke, query)
        items = [
            RagSearchResultItem(
                content=d.page_content,
                metadata=d.metadata or {},
            )
            for d in docs
        ]
        return RagSearchResponse(
            query=query,
            active_doc=target_doc,
            vector_store="Qdrant Container (Dense Embeddings + Hybrid BM25)",
            results=items,
        )
    except Exception as e:
        print(f"Qdrant RAG search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve from Qdrant: {str(e)}",
        )


# ------------------------------------------------------------
# 4. Conversation Threads Management Endpoints
# ------------------------------------------------------------
@app.get("/api/threads", response_model=List[ThreadItem])
async def list_threads(authorized: bool = Depends(verify_api_key)):
    """Lists all stored conversation threads from PGVector database."""
    threads = await retrieve_all_threads_async()
    return [ThreadItem(thread_id=t["thread_id"], label=t["label"]) for t in threads]


@app.get("/api/threads/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread_messages(
    thread_id: str,
    authorized: bool = Depends(verify_api_key),
):
    """Retrieves conversation message history for a specific thread."""
    raw_msgs = await retrieve_thread_messages_async(thread_id)
    return ThreadDetailResponse(
        thread_id=thread_id,
        messages=[MessageItem(role=m["role"], content=m["content"]) for m in raw_msgs],
    )


@app.post("/api/threads", response_model=ThreadItem)
async def create_new_thread(authorized: bool = Depends(verify_api_key)):
    """Generates a new conversation thread ID."""
    new_thread_id = str(uuid.uuid4())
    return ThreadItem(thread_id=new_thread_id, label="New Chat")


@app.delete("/api/threads/{thread_id}")
async def delete_thread(
    thread_id: str,
    authorized: bool = Depends(verify_api_key),
):
    """Deletes a conversation thread and its PGVector memory data."""
    await delete_thread_async(thread_id)
    return {"status": "deleted", "thread_id": thread_id}


@app.delete("/api/threads")
async def clear_all_threads(authorized: bool = Depends(verify_api_key)):
    """Clears all conversation checkpoints and memory from PostgreSQL."""
    await clear_all_history_async()
    return {"status": "cleared", "message": "All conversations have been removed."}


# ------------------------------------------------------------
# 5. Semantic Memory Search via PGVector
# ------------------------------------------------------------
@app.get("/api/memory/search", response_model=MemorySearchResponse)
async def search_memory(
    q: str,
    thread_id: Optional[str] = None,
    limit: int = 5,
    authorized: bool = Depends(verify_api_key),
):
    """Performs semantic similarity search over stored conversation memory vectors in pgvector."""
    results = await search_memory_vectors_async(query=q, thread_id=thread_id, limit=limit)
    items = [
        MemorySearchResultItem(
            id=r["id"],
            thread_id=r["thread_id"],
            role=r["role"],
            content=r["content"],
            similarity=r["similarity"],
        )
        for r in results
    ]
    return MemorySearchResponse(query=q, results=items)


# ------------------------------------------------------------
# 6. Chat Interaction Endpoints (Async & Streaming SSE)
# ------------------------------------------------------------
@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(
    req: ChatRequest,
    authorized: bool = Depends(verify_api_key),
):
    """Non-streaming async chat endpoint with guardrails and memory persistence."""
    global _CURRENT_ACTIVE_DOC

    # Apply input guardrails
    validation = validate_input(req.message)
    if not validation.passed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Guardrail violation ({validation.category}): {validation.reason}",
        )

    thread_id = req.thread_id or str(uuid.uuid4())
    active_doc = req.active_doc or _CURRENT_ACTIVE_DOC

    chatbot = await get_async_chatbot()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = await chatbot.ainvoke(
            {"messages": [HumanMessage(content=req.message)], "active_doc": active_doc},
            config=config,
        )
        last_message = result["messages"][-1]
        raw_content = last_message.content if hasattr(last_message, "content") else str(last_message)

        # Apply output guardrails
        sanitized_content = apply_output_guardrails(raw_content)

        # Save to pgvector conversation memory
        await save_memory_vector_async(thread_id, "user", req.message)
        await save_memory_vector_async(thread_id, "assistant", sanitized_content)

        return ChatResponse(
            thread_id=thread_id,
            role="assistant",
            content=sanitized_content,
            guardrail_status="passed",
        )
    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}",
        )


@app.post("/api/chat/stream")
async def chat_stream_endpoint(
    req: ChatRequest,
    authorized: bool = Depends(verify_api_key),
):
    """
    Server-Sent Events (SSE) streaming chat endpoint.
    Emits real-time tokens and tool invocation notifications.
    """
    global _CURRENT_ACTIVE_DOC

    # Apply input guardrails
    validation = validate_input(req.message)
    if not validation.passed:
        async def error_generator():
            err_payload = json.dumps({
                "error": f"Guardrail blocked input ({validation.category}): {validation.reason}"
            })
            yield f"event: error\ndata: {err_payload}\n\n"
        return StreamingResponse(error_generator(), media_type="text/event-stream")

    thread_id = req.thread_id or str(uuid.uuid4())
    active_doc = req.active_doc or _CURRENT_ACTIVE_DOC

    async def event_generator():
        chatbot = await get_async_chatbot()
        config = {"configurable": {"thread_id": thread_id}}
        accumulated_chunks = []
        tool_active = False

        try:
            async for message_chunk, _metadata in chatbot.astream(
                {"messages": [HumanMessage(content=req.message)], "active_doc": active_doc},
                config=config,
                stream_mode="messages",
            ):
                # Detect tool calling
                if hasattr(message_chunk, "tool_calls") and message_chunk.tool_calls:
                    if not tool_active:
                        tool_active = True
                        tool_name = message_chunk.tool_calls[0].get("name", "tool")
                        payload = json.dumps({
                            "status": "executing",
                            "tool": tool_name,
                            "message": f"🔍 Executing tool '{tool_name}'... please wait",
                        })
                        yield f"event: tool\ndata: {payload}\n\n"

                # Detect text tokens from AIMessage
                if isinstance(message_chunk, AIMessage) and message_chunk.content:
                    tool_active = False
                    chunk_text = message_chunk.content
                    accumulated_chunks.append(chunk_text)
                    payload = json.dumps({"content": chunk_text})
                    yield f"event: delta\ndata: {payload}\n\n"

            # Post-processing and output guardrails
            full_response = "".join(accumulated_chunks)
            sanitized_response = apply_output_guardrails(full_response)

            # Persist to pgvector memory asynchronously
            await save_memory_vector_async(thread_id, "user", req.message)
            await save_memory_vector_async(thread_id, "assistant", sanitized_response)

            done_payload = json.dumps({
                "thread_id": thread_id,
                "content": sanitized_response,
                "guardrail_status": "passed",
            })
            yield f"event: done\ndata: {done_payload}\n\n"

        except Exception as err:
            print(f"Streaming error: {err}")
            err_payload = json.dumps({"error": str(err)})
            yield f"event: error\ndata: {err_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ------------------------------------------------------------
# 7. Static Files & React SPA Routing
# ------------------------------------------------------------
ui_dist_path = Path(__file__).resolve().parent.parent.parent.parent / "ui" / "dist"
if ui_dist_path.exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    assets_path = ui_dist_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = ui_dist_path / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(ui_dist_path / "index.html")

