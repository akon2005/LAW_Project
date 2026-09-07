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

from app.config import CORS_ORIGINS, API_HOST, API_PORT
from app.models.database import init_db
from app.api.routes import search, reference, documents, sections, similar, trends, summarize


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    print("=" * 60)
    print("  VIDHIVEDA — AI-Powered Legal Research Engine")
    print("  SIH1701 · Department of Justice, Ministry of Law & Justice")
    print("=" * 60)

    init_db()
    print("[Startup] Database initialized.")

    # Pre-load embedding model for faster first query
    try:
        from app.services.pipeline import get_embedding_model, get_collection
        get_embedding_model()
        col = get_collection()
        print(f"[Startup] ChromaDB collection ready. Documents: {col.count()}")
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if is_wildcard else CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=not is_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix="/api", tags=["Search & Research"])
app.include_router(reference.router, prefix="/api", tags=["Reference Data"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])
app.include_router(sections.router, prefix="/api", tags=["Sections"])
app.include_router(similar.router, prefix="/api", tags=["Similar Documents"])
app.include_router(trends.router, prefix="/api", tags=["Trend Analysis"])
app.include_router(summarize.router, prefix="/api", tags=["Summarization"])


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
    try:
        from app.services.pipeline import get_collection
        doc_count = get_collection().count()
    except Exception:
        pass
    return {
        "status": "healthy",
        "version": "1.0.0",
        "components": {
            "document_count": doc_count,
            "chromadb": "connected"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=API_HOST, port=API_PORT, reload=True)

