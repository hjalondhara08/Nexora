"""
Hybrid RAG LangGraph Tool
=========================
Exposes document retrieval to the agent with Qdrant, BM25, and Cohere Reranking.
"""

from langchain_core.tools import tool
from nexora.config import DEFAULT_DOC_PATH
from nexora.rag.retriever import get_retriever


@tool
def hybrid_rag_tool(query: str, file_path: str = DEFAULT_DOC_PATH) -> dict:
    """
    Retrieve relevant information, summaries, or specific answers from an uploaded PDF document using Qdrant + BM25 + Cohere Reranking.
    ONLY invoke this tool when the user's query specifically asks to summarize, search, or answer questions about an uploaded file or book.
    DO NOT invoke this tool for general conversation, greetings, math, or web search queries.

    Args:
        query: Specific search query or question about the document content.
        file_path: Dynamic path of the document (PDF) to query.
    """
    try:
        retriever = get_retriever(pdf_path=file_path)
        results = retriever.invoke(query)

        context = [doc.page_content for doc in results]
        metadata = [doc.metadata for doc in results]

        return {
            "query": query,
            "file_path": file_path,
            "context": context,
            "metadata": metadata,
            "status": "success",
        }
    except Exception as e:
        print(f"Error executing hybrid_rag_tool: {e}")
        return {"error": f"Error executing hybrid_rag_tool: {e}", "status": "failed"}
