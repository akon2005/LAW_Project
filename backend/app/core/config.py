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
# The backend package root (``backend/``). The persisted ChromaDB store and the
# raw dataset artefacts live here, not under ``app/``.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
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
# Swapping this for InLegalBERT / Legal-BERT is an .env change only: every
# service reads the model name from here.
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
EMBEDDING_DIMENSION = 384  # all-MiniLM-L6-v2 outputs 384-dim vectors

# ── ChromaDB ──────────────────────────────────────────────────────────
# Case-law corpus lives in the persistent vector store; statute data must be
# kept in a *separate* collection so the two are never blended.
CHROMA_PERSIST_DIR = str(CHROMA_DIR)
VECTOR_STORE_DIR = os.getenv("VECTOR_STORE_DIR", str(BACKEND_ROOT / "chroma_db"))
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "lexrag_documents")
CASE_LAW_COLLECTION = os.getenv("CASE_LAW_COLLECTION", "vidhiveda_legal_cases")
STATUTE_COLLECTION = os.getenv("STATUTE_COLLECTION", "vidhiveda_statutes")

# ── Dataset ───────────────────────────────────────────────────────────
DATASET_NAME = os.getenv("DATASET_NAME", "india-case-legal-rag")
MAX_RECORDS = int(os.getenv("MAX_RECORDS", "9375"))

# ── Retrieval ─────────────────────────────────────────────────────────
RETRIEVAL_TOP_K = int(os.getenv("TOP_K", os.getenv("RETRIEVAL_TOP_K", "5")))
LOW_CONFIDENCE_THRESHOLD = float(os.getenv("LOW_CONFIDENCE_THRESHOLD", "0.30"))
USE_RERANKER = os.getenv("USE_RERANKER", "false").strip().lower() in {"1", "true", "yes", "on"}
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANK_CANDIDATES = int(os.getenv("RERANK_CANDIDATES", "25"))
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
# "legal_aware" | "fixed". Legal-aware prefers paragraph/section boundaries.
CHUNK_STRATEGY = os.getenv("CHUNK_STRATEGY", "legal_aware")
# Alias with the name used in the target architecture (Step 13).
RERANKING_ENABLED = USE_RERANKER
# How many evidence chunks survive reranking (Step 13).
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "10"))

# ── Dataset field mapping (Step 4) ────────────────────────────────────
# Blank value means "auto-detect from the dataset schema" (see
# scripts/inspect_dataset.py). Only set these when a dataset's columns are
# named differently from the registry defaults in dataset_service.py.
TEXT_FIELD = os.getenv("TEXT_FIELD", "")
CASE_ID_FIELD = os.getenv("CASE_ID_FIELD", "")
CASE_NAME_FIELD = os.getenv("CASE_NAME_FIELD", "")
COURT_FIELD = os.getenv("COURT_FIELD", "")
DATE_FIELD = os.getenv("DATE_FIELD", "")
YEAR_FIELD = os.getenv("YEAR_FIELD", "")
OUTCOME_FIELD = os.getenv("OUTCOME_FIELD", "")
SECTION_FIELD = os.getenv("SECTION_FIELD", "")
SOURCE_URL_FIELD = os.getenv("SOURCE_URL_FIELD", "")

# ── Outcome prediction (Steps 16-21) ──────────────────────────────────
# Below this calibrated confidence a prediction is flagged low_confidence;
# the API still reports prediction_available=true rather than hiding it.
MIN_PREDICTION_CONFIDENCE = float(os.getenv("MIN_PREDICTION_CONFIDENCE", "0.60"))
# Minimum retrieval score required before evidence is considered sufficient.
MIN_EVIDENCE_SCORE = float(os.getenv("MIN_EVIDENCE_SCORE", "0.30"))
OUTCOME_MODEL_DIR = Path(
    os.getenv("OUTCOME_MODEL_DIR", str(BACKEND_ROOT / "data" / "models" / "outcome"))
)

# ── Ingestion state (Steps 5, 36, 37) ─────────────────────────────────
INGESTION_STATUS_PATH = Path(
    os.getenv("INGESTION_STATUS_PATH", str(BACKEND_ROOT / "data" / "ingestion_status.json"))
)
CHECKPOINT_DIR = Path(os.getenv("CHECKPOINT_DIR", str(BACKEND_ROOT / "data" / "checkpoints")))

# ── OKF knowledge bundle (Phase 3) ────────────────────────────────────
# Portable Open Knowledge Format v0.2 bundle generated from the real corpus.
OKF_BUNDLE_DIR = Path(
    os.getenv("OKF_BUNDLE_DIR", str(BACKEND_ROOT / "knowledge"))
)
OKF_VERSION = os.getenv("OKF_VERSION", "0.2")

# ── Model / pipeline versioning (Step 41) ─────────────────────────────
INDEX_VERSION = os.getenv("INDEX_VERSION", "1")
RETRIEVER_VERSION = os.getenv("RETRIEVER_VERSION", "hybrid-v1")
RERANKER_VERSION = os.getenv("RERANKER_VERSION", "bm25+ce-v1")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "vidhiveda-rag-v1")
OUTCOME_MODEL_VERSION = os.getenv("OUTCOME_MODEL_VERSION", "untrained")

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

