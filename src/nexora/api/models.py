"""
Nexora API Pydantic Models
==========================
Defines request and response schemas with strict validation.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="User input prompt for the agentic assistant.",
    )
    thread_id: Optional[str] = Field(
        None,
        description="Unique UUID identifying the conversation thread.",
    )
    active_doc: Optional[str] = Field(
        None,
        description="Path to currently active PDF document for Hybrid RAG.",
    )


class ChatResponse(BaseModel):
    thread_id: str
    role: str = "assistant"
    content: str
    tools_called: List[str] = Field(default_factory=list)
    guardrail_status: str = "passed"


class ThreadItem(BaseModel):
    thread_id: str
    label: str


class ThreadListResponse(BaseModel):
    threads: List[ThreadItem]
    count: int


class MessageItem(BaseModel):
    role: str
    content: str


class ThreadDetailResponse(BaseModel):
    thread_id: str
    messages: List[MessageItem]


class ActiveDocResponse(BaseModel):
    path: str
    filename: str


class UploadResponse(BaseModel):
    success: bool
    filename: str
    path: str
    message: str


class MemorySearchResultItem(BaseModel):
    id: int
    thread_id: str
    role: str
    content: str
    similarity: float


class MemorySearchResponse(BaseModel):
    query: str
    results: List[MemorySearchResultItem]


class GuardrailValidationResult(BaseModel):
    passed: bool
    category: Optional[str] = None
    reason: Optional[str] = None
    sanitized_content: Optional[str] = None


class ApiKeyResponse(BaseModel):
    api_key: str
    status: str
    message: str


class RagSearchResultItem(BaseModel):
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RagSearchResponse(BaseModel):
    query: str
    active_doc: str
    vector_store: str = "Qdrant Container"
    results: List[RagSearchResultItem]
