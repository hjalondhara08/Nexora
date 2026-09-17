"""
PDF Document Loader and Chunking for Nexora RAG Pipeline.
"""

import os
import re
from pathlib import Path
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from nexora.config import BASE_DIR, SAMPLE_DIR


def resolve_pdf_path(pdf_path: str) -> str:
    """Resolves relative or basename PDF paths to absolute paths gracefully."""
    p = Path(pdf_path)
    if p.exists():
        return str(p.resolve())
    # Check sample directory
    sample_path = SAMPLE_DIR / p.name
    if sample_path.exists():
        return str(sample_path.resolve())
    # Check base directory
    base_path = BASE_DIR / p.name
    if base_path.exists():
        return str(base_path.resolve())
    return pdf_path


def load_and_split_documents(pdf_path: str, max_chunks: int = 30) -> List[Document]:
    """Loads a PDF from dynamic file path and splits it into overlapping chunks."""
    resolved_path = resolve_pdf_path(pdf_path)
    try:
        loader = PyPDFLoader(resolved_path)
        docs = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
        chunks = splitter.split_documents(docs)
        if max_chunks and len(chunks) > max_chunks:
            chunks = chunks[:max_chunks]
        return chunks
    except Exception as e:
        print(f"Error loading and splitting document '{pdf_path}': {e}")
        raise e


def sanitize_collection_name(file_path: str) -> str:
    """Generates a valid Qdrant collection name dynamically from the uploaded filename."""
    filename = os.path.splitext(os.path.basename(file_path))[0]
    clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', filename)
    return f"rag_{clean_name.lower()}"
