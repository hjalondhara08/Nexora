"""
4-Stage Hybrid RAG Retriever Engine
===================================
1. Dense Retrieval: Qdrant Vector Store (Cohere Embeddings embed-english-v3.0)
2. Sparse Retrieval: BM25 keyword matching
3. Reciprocal Rank Fusion: EnsembleRetriever
4. Contextual Compression: Cohere Reranker (rerank-v3.5)
"""

from typing import Optional
from langchain_cohere import CohereEmbeddings, CohereRerank
from langchain_community.retrievers import BM25Retriever

try:
    from langchain.retrievers import EnsembleRetriever, ContextualCompressionRetriever
except (ImportError, ModuleNotFoundError):
    from langchain_classic.retrievers import EnsembleRetriever, ContextualCompressionRetriever

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from nexora.config import COHERE_API_KEY, QDRANT_URL, DEFAULT_DOC_PATH
from nexora.rag.loader import load_and_split_documents, sanitize_collection_name, resolve_pdf_path

# In-memory cache mapping file_path -> retriever instance
_GLOBAL_RETRIEVERS = {}


def build_hybrid_reranked_retriever(
    pdf_path: str,
    collection_name: Optional[str] = None,
):
    """
    Builds the 4-stage RAG pipeline for any document:
    Qdrant Dense + BM25 Sparse -> Ensemble (RRF) -> Cohere Reranker
    """
    resolved_path = resolve_pdf_path(pdf_path)
    try:
        if not collection_name:
            collection_name = sanitize_collection_name(resolved_path)

        embeddings = CohereEmbeddings(cohere_api_key=COHERE_API_KEY, model="embed-english-v3.0")
        client = QdrantClient(url=QDRANT_URL)

        chunks = load_and_split_documents(resolved_path)

        if client.collection_exists(collection_name=collection_name):
            print(f"📦 Collection '{collection_name}' already exists in Qdrant. Reusing existing embeddings!")
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
                url=QDRANT_URL,
                collection_name=collection_name,
            )

        dense_retriever = qdrant_store.as_retriever(search_kwargs={"k": 6})

        bm25_retriever = BM25Retriever.from_documents(chunks)
        bm25_retriever.k = 6

        ensemble_retriever = EnsembleRetriever(
            retrievers=[dense_retriever, bm25_retriever],
            weights=[0.5, 0.5],
        )

        reranker = CohereRerank(cohere_api_key=COHERE_API_KEY, model="rerank-v3.5", top_n=3)

        compression_retriever = ContextualCompressionRetriever(
            base_compressor=reranker,
            base_retriever=ensemble_retriever,
        )

        return compression_retriever
    except Exception as e:
        print(f"Error building hybrid reranked retriever for '{pdf_path}': {e}")
        raise e


def get_retriever(pdf_path: str = DEFAULT_DOC_PATH):
    """Retrieves or builds the RAG pipeline dynamically for the given uploaded file path."""
    global _GLOBAL_RETRIEVERS
    resolved = resolve_pdf_path(pdf_path)
    if resolved not in _GLOBAL_RETRIEVERS:
        _GLOBAL_RETRIEVERS[resolved] = build_hybrid_reranked_retriever(pdf_path=resolved)
    return _GLOBAL_RETRIEVERS[resolved]


def index_uploaded_file(file_path: str):
    """Indexes a newly uploaded document immediately into Qdrant + BM25."""
    try:
        print(f"📥 Indexing uploaded document: {file_path}")
        return get_retriever(pdf_path=file_path)
    except Exception as e:
        print(f"Error indexing uploaded file '{file_path}': {e}")
        raise e
