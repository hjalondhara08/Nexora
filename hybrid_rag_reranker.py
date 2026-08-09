"""
Hybrid Search RAG with Qdrant, BM25, Cohere Embeddings, and Cohere Reranker
========================================================================
Supports dynamic file paths when documents are uploaded from the frontend.
"""

import os
import re
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from langchain_cohere import CohereEmbeddings, CohereRerank
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever, ContextualCompressionRetriever
from langchain_core.tools import tool
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient


def load_and_split_documents(pdf_path: str, max_chunks: int = 30) -> List[Document]:
    """Loads a PDF from any dynamic file path uploaded by the frontend and splits it into chunks."""
    try:
        loader = PyPDFLoader(pdf_path)
        docs = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
        chunks = splitter.split_documents(docs)
        if max_chunks and len(chunks) > max_chunks:
            chunks = chunks[:max_chunks]
        return chunks
    except Exception as e:
        print(f"Error found this is not working: {e}")
        raise e


def sanitize_collection_name(file_path: str) -> str:
    """Generates a clean, valid Qdrant collection name dynamically from the uploaded filename."""
    filename = os.path.splitext(os.path.basename(file_path))[0]
    clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', filename)
    return f"rag_{clean_name.lower()}"


def build_hybrid_reranked_retriever(
    pdf_path: str,
    collection_name: Optional[str] = None,
):
    """
    Builds 4-stage RAG pipeline for any uploaded file:
    Qdrant Dense (Cohere Embeddings) + BM25 Sparse -> Ensemble (Hybrid RRF) -> Cohere Reranker
    """
    try:
        if not collection_name:
            collection_name = sanitize_collection_name(pdf_path)

        cohere_api_key = os.getenv("COHERE_API_KEY")
        embeddings = CohereEmbeddings(cohere_api_key=cohere_api_key, model="embed-english-v3.0")

        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        client = QdrantClient(url=qdrant_url)

        chunks = load_and_split_documents(pdf_path)

        if client.collection_exists(collection_name=collection_name):
            print(f"📦 Collection '{collection_name}' already exists in Qdrant. Reusing existing stored embeddings!")
            qdrant_store = QdrantVectorStore(
                client=client,
                collection_name=collection_name,
                embedding=embeddings,
            )
        else:
            print(f"🆕 Creating collection '{collection_name}' in Qdrant and generating embeddings...")
            qdrant_store = QdrantVectorStore.from_documents(
                chunks,
                embeddings,
                url=qdrant_url,
                collection_name=collection_name,
            )
        dense_retriever = qdrant_store.as_retriever(search_kwargs={"k": 6})

        bm25_retriever = BM25Retriever.from_documents(chunks)
        bm25_retriever.k = 6

        ensemble_retriever = EnsembleRetriever(
            retrievers=[dense_retriever, bm25_retriever],
            weights=[0.5, 0.5],
        )

        reranker = CohereRerank(cohere_api_key=cohere_api_key, model="rerank-v3.5", top_n=3)

        compression_retriever = ContextualCompressionRetriever(
            base_compressor=reranker,
            base_retriever=ensemble_retriever,
        )

        return compression_retriever
    except Exception as e:
        print(f"Error found this is not working: {e}")
        raise e


# Cache mapping file_path -> retriever instance
_GLOBAL_RETRIEVERS = {}


def get_retriever(pdf_path: str = "Atomic_Habit.pdf"):
    """
    Retrieves or builds the RAG pipeline dynamically for the given uploaded file path.
    """
    global _GLOBAL_RETRIEVERS
    if pdf_path not in _GLOBAL_RETRIEVERS:
        _GLOBAL_RETRIEVERS[pdf_path] = build_hybrid_reranked_retriever(pdf_path=pdf_path)
    return _GLOBAL_RETRIEVERS[pdf_path]


def index_uploaded_file(file_path: str):
    """
    Call this function from your frontend upload handler (FastAPI / Streamlit / Flask)
    whenever a user uploads a new PDF file.
    """
    try:
        print(f"📥 Indexing uploaded file dynamically: {file_path}")
        return get_retriever(pdf_path=file_path)
    except Exception as e:
        print(f"Error found this is not working: {e}")
        raise e


@tool
def hybrid_rag_tool(query: str, file_path: str = "Atomic_Habit.pdf") -> dict:
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
        print(f"Error found this is not working: {e}")
        return {"error": f"Error found this is not working: {e}", "status": "failed"}


if __name__ == "__main__":
    test_query = "What are atomic habits?"
    print(f"🔍 Running Hybrid Search for: '{test_query}'...")
    res = hybrid_rag_tool.invoke({"query": test_query, "file_path": "Atomic_Habit.pdf"})
    print("Results:", res)
