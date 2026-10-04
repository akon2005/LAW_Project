"""
VIDHIVEDA — FastAPI Application Entry Point
AI-Powered Legal Research Engine for Indian Commercial Courts
SIH1701 — Department of Justice, Ministry of Law & Justice
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback
import sys

from app.core.config import CORS_ORIGINS, API_HOST, API_PORT, CASE_LAW_COLLECTION
from app.db.database import init_db
from app.api.routes import search, reference, documents, sections, similar, trends, summarize, research, pipeline, knowledge


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    print("=" * 60)
    print("  VIDHIVEDA — AI-Powered Legal Research Engine")
    print("  SIH1701 · Department of Justice, Ministry of Law & Justice")
    print("=" * 60)

    init_db()
    print("[Startup] Database initialized.")

    # Pre-load the embedding model and report the real corpus behind /api/research.
    try:
        from app.core.config import CASE_LAW_COLLECTION
        from app.db.vector_store import legal_cases_store
        from app.rag.embedding_service import embedding_service

        embedding_service.warm_up()
        count = legal_cases_store.get_count()
        print(
            f"[Startup] ChromaDB collection '{CASE_LAW_COLLECTION}' ready. "
            f"Indexed chunks: {count}"
        )
        if count == 0:
            print(
                "[Startup] WARNING: corpus is empty. Run "
                "`python scripts/ingest_legal_data.py` from backend/."
            )
    except Exception as e:
        print(f"[Startup] Pipeline init warning: {e}")

    print("[Startup] Ready to serve requests.")
    print("=" * 60)
    yield
    print("[Shutdown] VIDHIVEDA shutting down.")


app = FastAPI(
    title="VIDHIVEDA API",
    description=(
        "AI-Powered Legal Research Engine for Indian Commercial Courts. "
        "Uses RAG (Retrieval-Augmented Generation) with ChromaDB."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": str(exc)})

is_wildcard = "*" in CORS_ORIGINS
# Local dev is allowed on any port (5173, 5178, preview builds, ...) so the UI
# can call the API without editing CORS_ORIGINS for every Vite port.
LOCAL_DEV_ORIGIN_REGEX = r"http://(localhost|127\.0\.0\.1)(:\d+)?"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if is_wildcard else CORS_ORIGINS,
    allow_origin_regex=rf"({LOCAL_DEV_ORIGIN_REGEX})|https://.*\.vercel\.app",
    allow_credentials=not is_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NOTE: /api/search is the legacy endpoint backed by the bundled sample-CSV
# collection. The real corpus pipeline lives at POST /api/research.
app.include_router(search.router, prefix="/api", tags=["Legacy Search"], deprecated=True)
app.include_router(research.router, prefix="/api", tags=["Research"])
app.include_router(pipeline.router, prefix="/api", tags=["Pipeline"])
app.include_router(reference.router, prefix="/api", tags=["Reference Data"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])
app.include_router(sections.router, prefix="/api", tags=["Sections"])
app.include_router(similar.router, prefix="/api", tags=["Similar Documents"])
app.include_router(trends.router, prefix="/api", tags=["Trend Analysis"])
app.include_router(summarize.router, prefix="/api", tags=["Summarization"])
app.include_router(knowledge.router, prefix="/api", tags=["Knowledge (OKF)"])


@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "VIDHIVEDA Legal Research API",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/health")
@app.get("/api/health")
async def health_check():
    doc_count = 0
    collection = CASE_LAW_COLLECTION
    try:
        from app.db.vector_store import legal_cases_store

        doc_count = legal_cases_store.get_count()
    except Exception:
        collection = "unavailable"
    return {
        "status": "healthy",
        "version": "1.0.0",
        "components": {
            "document_count": doc_count,
            "collection": collection,
            "chromadb": "connected" if collection != "unavailable" else "unavailable",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=API_HOST, port=API_PORT, reload=True)

