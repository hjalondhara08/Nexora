# 🚀 Nexora — Production Hybrid RAG & Multi-Tool Agentic Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Framework-LangGraph%200.2-orange.svg)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/UI-React%20SPA-61DAFB.svg)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%20%2B%20PGVector-336791.svg)](https://github.com/pgvector/pgvector)
[![Qdrant](https://img.shields.io/badge/Vector%20DB-Qdrant-red.svg)](https://qdrant.tech/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Nexora** is an enterprise-ready, intelligent agentic chatbot platform built on **LangGraph**, **FastAPI**, **PostgreSQL (PGVector)**, **Qdrant**, and **React**. It seamlessly combines a **4-Stage Hybrid RAG Engine** with **Multi-Tool Reasoning**, persistent thread memory via PGVector checkpoints, and session-isolated file execution sandboxes.

---

## ✨ Key Features

- 🧠 **Intelligent Dynamic Routing**: Powered by an asynchronous LangGraph state graph. Everyday chat & math execute directly; document queries trigger RAG; real-time web searches and financial queries auto-route to specialized tools.
- 🔍 **4-Stage Hybrid RAG Pipeline**:
  1. **Dense Retrieval**: Qdrant Vector Search (`Cohere embed-english-v3.0`).
  2. **Sparse Retrieval**: BM25 keyword matching via `rank-bm25`.
  3. **Reciprocal Rank Fusion (RRF)**: Merges dense and sparse score ranks.
  4. **Cohere Reranking**: Re-ranks top candidates using `rerank-v3.5` for high-precision context retrieval.
- ⚡ **Persistent Embedding Caching**: Automatic Qdrant collection hash check skips re-embedding uploaded documents if already indexed, dramatically cutting API cost and latency.
- 🛡️ **Session-Isolated Execution Sandbox**: Enables safe creation and modification of Office documents (`.docx`, `.xlsx`, `.pptx`) and plain-text files via `OfficeCLI` inside `/tmp/bot_sandboxes/` without touching the host workspace.
- 💾 **Stateful Thread Memory & PGVector Persistence**: Fully asynchronous PostgreSQL checkpointer (`AsyncPostgresSaver`) and semantic conversation memory powered by **PGVector** (`vector(1024)`), preserving threads and chat history.
- 💻 **Modern Dark-Grey React UI**: Simple, professional dark-grey single-page application (SPA) featuring document uploading, chat history navigation, code snippet copying, and real-time Server-Sent Events (SSE) streaming.

---

## 🏗️ Architecture Overview

```mermaid
flowchart TD
    User([👤 User]) -->|Input Message / PDF Upload| Frontend[💻 React Web UI]
    Frontend -->|Async REST & SSE Streaming| Backend[⚡ FastAPI Server]
    
    Backend -->|Upload PDF / Index Request| Indexer[📄 Indexing Engine]
    Indexer -->|Dense Embeddings| Qdrant[(⚡ Qdrant Vector DB)]
    Indexer -->|Sparse Index| BM25[📚 BM25 Retriever]
    
    Backend -->|Invoke Async Graph| Agent[🤖 LangGraph Agent / LLM]
    Agent -->|Evaluate Intent| Router{Routing Decision}
    
    Router -->|General Chat| LLM[⚡ Groq LLM llama-3.1-8b-instant]
    Router -->|Web Search| DDG[🌐 DuckDuckGo Search]
    Router -->|Math & Finance| Tools[🧮 Calculator / Alpha Vantage Stock API]
    Router -->|Document Q&A| HybridRAG[🔍 4-Stage Hybrid RAG Engine]
    Router -->|File Edit/Create| Sandbox[🛡️ Session Sandbox / OfficeCLI]
    
    HybridRAG -->|Dense Top-K| Qdrant
    HybridRAG -->|Sparse Top-K| BM25
    HybridRAG -->|RRF & Rerank| Cohere[🎯 Cohere Reranker v3.5]
    Cohere -->|Ranked Passages| LLM
    
    LLM -->|Stream SSE Tokens| Backend
    Backend -->|Async State Checkpointing| Postgres[(🐘 PostgreSQL + PGVector)]
    Backend -->|Save Semantic Memory Vectors| Postgres
    Backend -->|Stream Response Events| Frontend
```

---

## 📁 Repository Structure

```
Nexora/
├── src/nexora/                 # Core Nexora Python package
│   ├── __init__.py             # Package exports (version, chatbot, helpers)
│   ├── config.py               # Centralized configuration & environment loader
│   ├── api/                    # Async FastAPI REST & SSE Streaming Backend
│   │   ├── __init__.py
│   │   ├── server.py           # FastAPI server endpoints & static UI mount
│   │   ├── models.py           # Pydantic request/response schemas
│   │   └── guardrails.py       # Input validation & output safety guardrails
│   ├── core/                   # LangGraph Agent Core & Persistence
│   │   ├── __init__.py
│   │   ├── agent.py            # Synchronous StateGraph builder & compiled agent
│   │   ├── async_agent.py      # Fully asynchronous LangGraph agent for FastAPI
│   │   ├── async_database.py   # PostgreSQL & PGVector checkpointer & vector memory
│   │   ├── database.py         # SQLite checkpointer (legacy fallback)
│   │   ├── state.py            # TypedDict ChatState definition
│   │   └── prompts.py          # Dynamic system prompt generator
│   ├── rag/                    # 4-Stage Hybrid RAG Engine
│   │   ├── __init__.py
│   │   ├── loader.py           # Document loading, path resolution, text chunking
│   │   └── retriever.py        # Qdrant dense + BM25 sparse + RRF + Cohere reranker
│   └── tools/                  # Agent Tool Implementations
│       ├── __init__.py         # Tool registry & unified export
│       ├── calculator.py       # Arithmetic calculator tool
│       ├── search.py           # DuckDuckGo live web search tool
│       ├── finance.py          # Alpha Vantage financial stock price tool
│       ├── rag_tool.py         # Hybrid RAG document retrieval tool
│       └── sandbox_tool.py     # Session-isolated sandbox tool (OfficeCLI & text)
├── ui/                         # Modern React Single-Page Application (SPA)
│   ├── src/                    # React components (Sidebar, ChatArea, ChatInput)
│   ├── dist/                   # Production-compiled assets served by FastAPI
│   ├── index.html              # HTML entry point
│   ├── package.json            # Node.js dependencies
│   └── vite.config.js          # Vite build configuration
├── data/                       # Persistent data storage
│   ├── sample/                 # Sample documents (e.g. Atomic_Habit.pdf)
│   └── uploads/                # Dynamic user PDF uploads
├── run.sh                      # Automated all-in-one startup & management script
├── main.py                     # Primary CLI launcher (auto-detects .venv)
├── docker-compose.yml          # Multi-container orchestration (PostgreSQL, Qdrant, App)
├── Dockerfile                  # Production container definition
├── pyproject.toml              # Project configuration & package definitions
├── requirements.txt            # Production dependency specifications
├── .env.example                # Environment variable configuration template
└── .gitignore                  # Version control ignore definitions
```

---

## 🛠️ Quickstart & Setup Guide

### 1. Prerequisites

- Python `3.10+`
- Docker & Docker Compose (used to run PostgreSQL with PGVector and Qdrant)

Start PostgreSQL (PGVector) and Qdrant database services:
```bash
docker compose up -d postgres qdrant
```

### 2. Installation

Clone the repository and install Python dependencies:

```bash
git clone https://github.com/hjalondhara08/Nexora.git
cd Nexora

# Create & activate virtual environment
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install dependencies and project package
pip install -r requirements.txt
pip install -e .
```

### 3. Environment Configuration

Copy the template `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Edit `.env`:
```ini
GROQ_API_KEY=gsk_your_groq_key
COHERE_API_KEY=your_cohere_key
QDRANT_URL=http://localhost:6333
POSTGRES_URL=postgresql://nexora:nexora_password@localhost:5433/nexora_db
NEXORA_API_KEY=nexora-secret-key-2026
```

---

## 🚀 Running the Application

### Option A: Using the Startup Script (Recommended)

Run Nexora with the automated all-in-one startup script:

```bash
./run.sh
```

**What this automatically does:**
1. Verifies your `.env` configuration file exists.
2. Ensures **PostgreSQL (PGVector)** on port `5433` and **Qdrant** on port `6333` are running and healthy.
3. Automatically activates the Python virtual environment (`.venv`).
4. Launches the **FastAPI async backend** and serves the compiled **React SPA** at [http://localhost:8000](http://localhost:8000).

**Other script modes:**
```bash
./run.sh --docker    # Run the full application stack in Docker containers
./run.sh --dev       # Run FastAPI backend + Vite React dev server in parallel
./run.sh --status    # Check health and port status of containers
./run.sh --stop      # Stop all Docker services
```

### Option B: Manual CLI Launch

```bash
source .venv/bin/activate
export PYTHONPATH=src
uvicorn nexora.api.server:app --host 0.0.0.0 --port 8000 --reload
# Or simply:
python main.py
```

### Option C: Full Stack Docker Compose

```bash
docker compose up -d
```

### 🌐 Access Points
- **Web UI & API**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Qdrant Vector Dashboard**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
- **PostgreSQL Database**: `localhost:5433` (DB: `nexora_db`, User: `nexora`)

---

## 📊 How the Hybrid RAG Works

1. **Document Ingestion**: When a PDF is uploaded via the React UI, it is automatically chunked into overlapping text passages.
2. **Dual Indexing**:
   - Chunks are vectorized with `Cohere embed-english-v3.0` and stored in **Qdrant**.
   - Chunks are indexed in memory with **BM25**.
3. **Smart Cache Verification**: On file upload, Qdrant is queried for an existing collection matching the file's collection name. If found, re-indexing is bypassed.
4. **Reciprocal Rank Fusion**: Dense & Sparse search results are combined using RRF scoring:
   $$RRF\_Score(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
5. **Reranking**: The top candidate passages are passed to Cohere's `rerank-v3.5` endpoint to select the most contextually relevant passages before prompt injection.

---

## 🛡️ Sandbox & OfficeCLI Integration

Nexora includes a session-scoped sandbox tool (`sandbox_tool.py`) that interacts with **OfficeCLI**. When requested to create or edit documents:
- Operations execute inside isolated directories (`/tmp/bot_sandboxes/`).
- Prevents path-traversal attacks (`../`) and unintended workspace modifications.
- Supports generating Word (`.docx`), Excel (`.xlsx`), and PowerPoint (`.pptx`) presentations on the fly.

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:
1. Fork the project repository.
2. Create a feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more details.
