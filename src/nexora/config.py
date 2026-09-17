"""
Nexora Configuration Module
===========================
Centralizes environment variables, directory paths, and default settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Ensure environment variables from .env are loaded
load_dotenv()

# Root directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Data directories
DATA_DIR = BASE_DIR / "data"
SAMPLE_DIR = DATA_DIR / "sample"
UPLOAD_DIR = DATA_DIR / "uploads"

# Ensure data directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Default PDF Document in data/sample/
DEFAULT_DOC_NAME = "Atomic_Habit.pdf"
DEFAULT_DOC_PATH = str(SAMPLE_DIR / DEFAULT_DOC_NAME)

# Persistent SQLite Database in data/
DB_PATH = str(DATA_DIR / "chatbot.db")

# Sandbox Base Directory
SANDBOX_BASE = Path("/tmp/bot_sandboxes")
SANDBOX_BASE.mkdir(parents=True, exist_ok=True)

# API Keys & Endpoints
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "C9PE94QUEW9VWGFM")
