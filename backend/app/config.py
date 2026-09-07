"""
VIDHIVEDA Configuration
Centralized settings for the AI-powered Legal Research Engine.
SIH1701 — Department of Justice, Ministry of Law & Justice
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATASET_DIR = DATA_DIR / "dataset"
CHROMA_DIR = (DATA_DIR / "chroma_store") if (DATA_DIR / "chroma_store").exists() else (DATA_DIR / "chromadb")
DB_DIR = DATA_DIR / "db"

# Ensure directories exist
for d in [DATASET_DIR, CHROMA_DIR, DB_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Database ───────────────────────────────────────────────────────────
DATABASE_URL = f"sqlite:///{DB_DIR / 'lexrag.db'}"

# ── Document Types ─────────────────────────────────────────────────────
DOCUMENT_TYPES = ["case_law", "statute", "notification", "regulation"]

# ── Embedding Model ───────────────────────────────────────────────────
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIMENSION = 384  # all-MiniLM-L6-v2 outputs 384-dim vectors

# ── ChromaDB ──────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = str(CHROMA_DIR)
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "lexrag_documents")

# ── Retrieval ─────────────────────────────────────────────────────────
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "8"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# ── LLM Generation ───────────────────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "huggingface")  # "huggingface", "openai" or "anthropic"
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# ── Server ────────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PORT", os.getenv("API_PORT", "8000")))

raw_cors = os.getenv("CORS_ORIGINS", "*")
if raw_cors == "*" or not raw_cors.strip():
    CORS_ORIGINS = ["*"]
else:
    CORS_ORIGINS = [origin.strip() for origin in raw_cors.split(",") if origin.strip()]
    if "https://frontend-akon2005s-projects.vercel.app" not in CORS_ORIGINS:
        CORS_ORIGINS.append("https://frontend-akon2005s-projects.vercel.app")

