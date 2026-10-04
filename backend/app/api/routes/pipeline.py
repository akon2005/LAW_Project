"""
Pipeline API routes (Step 28).

Exposes each stage of the VIDHIVEDA pipeline separately so it can be inspected
in isolation, plus the composite ``/api/rag`` endpoint:

* ``GET  /api/model/status``       — outcome model + version metadata
* ``GET  /api/ingestion/status``   — persistent ingestion state
* ``GET  /api/cases/{document_id}``— every stored chunk of one document
* ``POST /api/retrieve``           — hybrid retrieval only (no generation)
* ``POST /api/predict``            — outcome prediction only (honest if untrained)
* ``POST /api/rag``                — full structured answer (same as /api/research)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import (
    CASE_LAW_COLLECTION,
    EMBEDDING_MODEL_NAME,
    INDEX_VERSION,
    MIN_EVIDENCE_SCORE,
    MIN_PREDICTION_CONFIDENCE,
    PROMPT_VERSION,
    RERANKER_VERSION,
    RETRIEVAL_TOP_K,
    RETRIEVER_VERSION,
    USE_RERANKER,
)
from app.db.vector_store import VectorStoreError, legal_cases_store
from app.ml.outcome_model import outcome_model_service
from app.rag.embedding_service import EmbeddingError, embedding_service
from app.rag.query_analyzer import legal_query_analyzer
from app.rag.retrieval_service import RetrievalError, retrieval_service
from app.services.ingestion_status import ingestion_status

router = APIRouter()
logger = logging.getLogger("vidhiveda.pipeline")


# ── Schemas ────────────────────────────────────────────────────────────
class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=RETRIEVAL_TOP_K, ge=1, le=50)
    court: Optional[str] = None
    year: Optional[int] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    sections: List[str] = Field(default_factory=list)
    document_type: Optional[str] = None


class PredictRequest(BaseModel):
    query: str = Field(..., min_length=2)


class RagRequest(BaseModel):
    query: str = Field(..., min_length=2)
    sections: List[str] = Field(default_factory=list)
    court: Optional[str] = None
    year: Optional[int] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    law_area: Optional[str] = None
    document_type: Optional[str] = None
    top_k: int = Field(default=RETRIEVAL_TOP_K, ge=1, le=50)


def _combined_filters(payload: Any) -> Optional[Dict[str, Any]]:
    """Only filters backed by real stored metadata are returned."""
    filters: Dict[str, Any] = {}
    if getattr(payload, "court", None):
        filters["court"] = payload.court
    if getattr(payload, "year", None):
        filters["year"] = payload.year
    if getattr(payload, "year_from", None):
        filters["year_from"] = payload.year_from
    if getattr(payload, "year_to", None):
        filters["year_to"] = payload.year_to
    return filters or None


# ── Status endpoints ───────────────────────────────────────────────────
@router.get("/model/status")
def model_status() -> Dict[str, Any]:
    """Which models are actually loaded, and the pipeline versions in use."""
    prediction = outcome_model_service.status()
    return {
        "embedding_model": EMBEDDING_MODEL_NAME,
        "retrieval_top_k": RETRIEVAL_TOP_K,
        "reranking_enabled": USE_RERANKER,
        "min_prediction_confidence": MIN_PREDICTION_CONFIDENCE,
        "min_evidence_score": MIN_EVIDENCE_SCORE,
        "outcome_model": prediction,
        "versions": {
            "index_version": INDEX_VERSION,
            "retriever_version": RETRIEVER_VERSION,
            "reranker_version": RERANKER_VERSION,
            "prompt_version": PROMPT_VERSION,
            "embedding_model": EMBEDDING_MODEL_NAME,
        },
    }


@router.get("/ingestion/status")
def ingestion_status_endpoint() -> Dict[str, Any]:
    """Persistent ingestion state (dataset, progress, last checkpoint)."""
    return ingestion_status.read()


@router.get("/cases/{document_id}")
def get_document(document_id: str) -> Dict[str, Any]:
    """
    Every stored chunk of one document, read straight from ChromaDB.

    This is the ground-truth view used to confirm that precedents shown in an
    answer really exist in the corpus.
    """
    try:
        stored = legal_cases_store.collection.get(
            where={"document_id": document_id},
            include=["metadatas", "documents"],
        )
    except VectorStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Vector store error: {exc}") from exc

    ids = stored.get("ids") or []
    if not ids:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{document_id}' is not present in the corpus.",
        )

    metadatas = stored.get("metadatas") or []
    documents = stored.get("documents") or []
    chunks = [
        {
            "chunk_id": chunk_id,
            "metadata": metadatas[index] if index < len(metadatas) else {},
            "text": documents[index] if index < len(documents) else "",
        }
        for index, chunk_id in enumerate(ids)
    ]
    chunks.sort(key=lambda item: item["metadata"].get("chunk_index", 0))
    return {
        "collection": CASE_LAW_COLLECTION,
        "document_id": document_id,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


# ── Retrieval ──────────────────────────────────────────────────────────
@router.post("/retrieve")
def retrieve_endpoint(request: RetrieveRequest) -> Dict[str, Any]:
    """Hybrid retrieval only: evidence, scores, and the query analysis."""
    if legal_cases_store.get_count() == 0:
        raise HTTPException(
            status_code=503,
            detail=f"Collection '{CASE_LAW_COLLECTION}' is empty; run ingestion first.",
        )

    analysis = legal_query_analyzer.analyze(request.query)
    sections = request.sections or [
        record["normalized_text"] for record in analysis["legal_sections"]
    ]
    try:
        result = retrieval_service.retrieve(
            query=analysis["embedding_text"],
            top_k=request.top_k,
            filters=_combined_filters(request),
            sections=sections or None,
        )
    except RetrievalError as exc:
        raise HTTPException(status_code=503, detail=f"Retrieval unavailable: {exc}") from exc

    return {
        "query": request.query,
        "query_analysis": analysis,
        "retrieval": {
            "candidate_count": result.get("candidate_count", 0),
            "best_similarity": result.get("best_similarity", 0.0),
            "topical_overlap": result.get("topical_overlap", 0.0),
            "reranked": result.get("reranked", False),
            "retrieval_time": result.get("retrieval_time", 0.0),
            "low_confidence": result.get("is_low_confidence", True),
            "low_confidence_reason": result.get("low_confidence_reason"),
            "collection": result.get("collection"),
        },
        "results": result.get("results", []),
    }


# ── Prediction ─────────────────────────────────────────────────────────
@router.post("/predict")
def predict_endpoint(request: PredictRequest) -> Dict[str, Any]:
    """
    Outcome prediction from case facts.

    Feature text is the analyzed query (case facts + sections + issue) — never
    retrieved verdict text — so no post-judgment information leaks into the
    model (Step 17). If no model is trained, ``available`` is false.
    """
    analysis = legal_query_analyzer.analyze(request.query)
    try:
        prediction = outcome_model_service.predict_from_texts([analysis["embedding_text"]])
    except EmbeddingError as exc:
        raise HTTPException(status_code=503, detail=f"Embedding unavailable: {exc}") from exc

    prediction["features_used"] = "query_facts_and_sections"
    prediction["query_analysis"] = {
        "legal_sections": analysis["legal_sections"],
        "legal_issue": analysis["legal_issue"],
    }
    return prediction


# ── Composite RAG (delegates to the research pipeline) ─────────────────
@router.post("/rag")
def rag_endpoint(request: RagRequest):
    """Full pipeline result. Same implementation as ``POST /api/research``."""
    from app.api.routes.research import ResearchRequest, _execute_research

    return _execute_research(
        ResearchRequest(
            query=request.query,
            sections=request.sections,
            court=request.court,
            year=request.year,
            year_from=request.year_from,
            year_to=request.year_to,
            law_area=request.law_area,
            document_type=request.document_type,
            top_k=request.top_k,
        )
    )
