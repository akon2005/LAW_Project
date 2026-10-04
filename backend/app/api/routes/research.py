"""
POST /api/research (Steps 12, 25, 29) — the real retrieval pipeline.

Request → query analysis → embedding → ChromaDB → section/metadata filter →
optional rerank → RAG generation → citation verification → structured JSON.

Also exposes read-only endpoints used to prove a result really came out of the
vector store (Step 20 / verification):

* ``GET /api/research/corpus``             — which collection, how many chunks
* ``GET /api/research/corpus/facets``      — filter values the corpus can satisfy
* ``GET /api/research/chunk/{chunk_id}``   — the exact stored row for a chunk id
"""
from __future__ import annotations

import logging
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import (
    CASE_LAW_COLLECTION,
    DATASET_NAME,
    EMBEDDING_MODEL_NAME,
    INDEX_VERSION,
    LOW_CONFIDENCE_THRESHOLD,
    MIN_EVIDENCE_SCORE,
    PROMPT_VERSION,
    RERANKER_VERSION,
    RETRIEVAL_TOP_K,
    RETRIEVER_VERSION,
    USE_RERANKER,
)
from app.db.vector_store import VectorStoreError, legal_cases_store
from app.ml.outcome_model import outcome_model_service
from app.okf import okf_service
from app.rag.query_analyzer import legal_query_analyzer
from app.rag.rag_service import rag_service
from app.rag.retrieval_service import RetrievalError, retrieval_service

router = APIRouter()
logger = logging.getLogger("vidhiveda.research")

DISCLAIMER = (
    "VIDHIVEDA is a research and decision-support system and does not replace "
    "professional legal judgment or judicial decision-making."
)


# ── Schemas ────────────────────────────────────────────────────────────
class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Natural-language legal question")
    law_area: Optional[str] = None
    court: Optional[str] = None
    year: Optional[int] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    document_type: Optional[str] = None
    sections: List[str] = Field(default_factory=list, description="Requested statutory sections")
    top_k: int = Field(default=RETRIEVAL_TOP_K, ge=1, le=50)


class SourceResponse(BaseModel):
    """A retrieved corpus chunk. Every field is either stored metadata or the
    stored document text — nothing is synthesised."""

    case_name: str = ""
    court: str = ""
    year: Any = ""
    source: str = ""
    similarity_score: float = 0.0
    text: str = ""
    chunk_id: str = ""
    document_id: str = ""
    chunk_index: int = 0
    total_pages: int = 0
    petitioner: str = ""
    respondent: str = ""
    judgment_date: str = ""
    citation: str = ""
    source_url: str = ""
    sections: List[str] = []
    articles: List[str] = []
    dataset: str = ""
    verified: bool = True
    rerank_method: str = "dense"


class CitationResponse(BaseModel):
    case_name: str = ""
    source: str = ""
    chunk_id: str = ""
    document_id: str = ""
    court: str = ""
    year: Any = ""
    judgment_date: str = ""
    citation: str = ""
    source_url: str = ""
    sections: List[str] = []
    articles: List[str] = []
    similarity_score: float = 0.0
    verified: bool = False
    reference: str = ""


class CorpusInfo(BaseModel):
    collection: str
    chunk_count: int
    dataset: str
    embedding_model: str
    top_k: int
    low_confidence_threshold: float
    reranker_enabled: bool


class ResearchResponse(BaseModel):
    query: str = ""
    status: str = "ok"  # ok | low_confidence | no_results
    answer: str = ""
    # Retrieval confidence (best dense similarity) — NOT a prediction confidence.
    confidence: float = 0.0
    confidence_basis: str = "dense_retrieval_similarity"
    sources: List[SourceResponse] = []
    citations: List[CitationResponse] = []
    supporting_sources: List[CitationResponse] = []
    unverified_references: List[Dict[str, Any]] = []
    warning: Optional[str] = None
    message: Optional[str] = None
    low_confidence: bool = False
    low_confidence_reason: Optional[str] = None
    answer_origin: str = "none"
    retrieval_time: float = 0.0
    generation_time: float = 0.0
    reranked: bool = False
    corpus: CorpusInfo

    # ── Structured extension (Steps 25, 29) ────────────────────────────
    precedents: List[SourceResponse] = []
    prediction: Dict[str, Any] = {
        "available": False,
        "label": None,
        "confidence": None,
        "low_confidence": False,
        "reason": None,
    }
    legal_provisions: List[Dict[str, Any]] = []
    # Supplementary OKF knowledge concepts related to the query. These never
    # replace the retrieved original source chunks (OKF §3.8 / Phase 8).
    knowledge: List[Dict[str, Any]] = []
    evidence_sufficient: bool = False
    retrieval: Dict[str, Any] = {}
    query_analysis: Dict[str, Any] = {}
    limitations: List[str] = []
    disclaimer: str = DISCLAIMER
    versions: Dict[str, Any] = {}


# ── Helpers ────────────────────────────────────────────────────────────
def _corpus_info() -> CorpusInfo:
    try:
        count = legal_cases_store.get_count()
    except VectorStoreError:
        count = 0
    return CorpusInfo(
        collection=CASE_LAW_COLLECTION,
        chunk_count=count,
        dataset=DATASET_NAME,
        embedding_model=EMBEDDING_MODEL_NAME,
        top_k=RETRIEVAL_TOP_K,
        low_confidence_threshold=LOW_CONFIDENCE_THRESHOLD,
        reranker_enabled=USE_RERANKER,
    )


def _to_source(record: Dict[str, Any]) -> SourceResponse:
    return SourceResponse(
        case_name=record.get("case_name") or "",
        court=record.get("court") or "",
        year=record.get("year") or "",
        source=record.get("source") or "",
        similarity_score=float(record.get("similarity_score") or 0.0),
        text=record.get("text") or "",
        chunk_id=record.get("chunk_id") or "",
        document_id=record.get("document_id") or "",
        chunk_index=int(record.get("chunk_index") or 0),
        total_pages=int(record.get("total_pages") or 0),
        petitioner=record.get("petitioner") or "",
        respondent=record.get("respondent") or "",
        judgment_date=record.get("judgment_date") or "",
        citation=record.get("citation") or "",
        source_url=record.get("source_url") or "",
        sections=record.get("sections") or [],
        articles=record.get("articles") or [],
        dataset=record.get("dataset") or "",
        verified=True,
        rerank_method=record.get("rerank_method") or "dense",
    )


def _build_filters(request: ResearchRequest) -> Optional[Dict[str, Any]]:
    """
    Only filters backed by real stored metadata are applied; ``VectorStore``
    silently drops unknown keys. ``law_area`` has no column in the indexed
    corpus, so it must not be turned into a filter (it would return nothing).
    """
    filters: Dict[str, Any] = {}
    if request.court:
        filters["court"] = request.court
    if request.year:
        filters["year"] = request.year
    if request.year_from:
        filters["year_from"] = request.year_from
    if request.year_to:
        filters["year_to"] = request.year_to
    return filters or None


def _build_prediction(analysis: Dict[str, Any], evidence_sufficient: bool) -> Dict[str, Any]:
    """
    Outcome prediction, reported separately from retrieval confidence (Step 21).
    Never claims a prediction when the model is untrained or evidence is thin.
    """
    status = outcome_model_service.status()
    if not evidence_sufficient:
        return {
            "available": False,
            "label": None,
            "confidence": None,
            "low_confidence": False,
            "reason": "Insufficient retrieved evidence to support an outcome prediction.",
        }
    if not status.get("available"):
        return {
            "available": False,
            "label": None,
            "confidence": None,
            "low_confidence": False,
            "reason": status.get("reason"),
        }
    try:
        result = outcome_model_service.predict_from_texts([analysis["embedding_text"]])
    except Exception as exc:  # prediction must never break retrieval
        logger.warning("[research] Prediction failed: %s", exc)
        return {
            "available": False,
            "label": None,
            "confidence": None,
            "low_confidence": False,
            "reason": f"Outcome model could not be applied: {exc}",
        }
    return result


def _legal_provisions(
    analysis: Dict[str, Any], sources: List[SourceResponse]
) -> List[Dict[str, Any]]:
    """
    Provisions the answer may rely on: those the user asked about, plus those
    actually printed in the retrieved evidence. Nothing else is added.
    """
    provisions: List[Dict[str, Any]] = []
    seen = set()

    def add(label: str, statute: Optional[str], section: str, origin: str, chunk_id: str = "") -> None:
        if not label or label in seen:
            return
        seen.add(label)
        provisions.append(
            {
                "statute": statute,
                "section": section,
                "label": label,
                "origin": origin,
                "chunk_id": chunk_id,
            }
        )

    for record in analysis.get("legal_sections", []):
        add(record["normalized_text"], record.get("statute"), record.get("section"), "query")
    for article in analysis.get("articles", []):
        add(article, "Constitution", article, "query")

    for source in sources:
        for section in source.sections:
            label = section if section.lower().startswith("section") else f"Section {section}"
            add(label, None, section, "retrieved_evidence", source.chunk_id)
        for article in source.articles:
            label = article if article.lower().startswith("article") else f"Article {article}"
            add(label, "Constitution", article, "retrieved_evidence", source.chunk_id)

    return provisions


def _build_limitations(
    request: ResearchRequest,
    analysis: Dict[str, Any],
    retrieval_result: Dict[str, Any],
    rag_result: Dict[str, Any],
    sources: List[SourceResponse],
    evidence_sufficient: bool,
    prediction: Dict[str, Any],
) -> List[str]:
    limitations: List[str] = []

    if not evidence_sufficient:
        limitations.append(
            "No sufficiently relevant legal evidence was retrieved for this query. "
            "Try narrowing the query with a legal section, court or year range."
        )
    if request.law_area:
        limitations.append(
            "'law_area' is not part of the indexed corpus metadata, so it was not "
            "applied as a filter."
        )
    if request.document_type:
        limitations.append(
            "'document_type' is not part of the indexed corpus metadata, so it was "
            "not applied as a filter."
        )
    if not sources:
        limitations.append(
            "No sufficiently relevant legal evidence was retrieved for this query."
        )
    if prediction.get("reason") and not prediction.get("available"):
        limitations.append(prediction["reason"])
    if rag_result.get("answer_origin") == "retrieval_template":
        limitations.append(
            "No language model was configured, so the answer lists the retrieved "
            "sources without generated legal analysis."
        )
    if rag_result.get("warning"):
        limitations.append(str(rag_result["warning"]))

    # Requested provisions that never appeared in the evidence.
    requested = {
        record["normalized_text"].lower() for record in analysis.get("legal_sections", [])
    }
    if requested and sources:
        evidence_text = " ".join(
            f"{' '.join(s.sections)} {' '.join(s.articles)} {s.text[:2000]}" for s in sources
        ).lower()
        missing = [label for label in requested if label.split()[-1] not in evidence_text]
        if missing:
            limitations.append(
                "The requested provision(s) "
                + ", ".join(sorted(missing))
                + " could not be verified in the retrieved evidence."
            )

    return limitations


def _knowledge_concepts(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    OKF concepts related to the query. Supplementary only: the answer is still
    generated from the retrieved original source material, and OKF documents are
    never injected into the generation prompt in place of that evidence.
    """
    try:
        if not okf_service.exists():
            return []
        return okf_service.search(query, top_k=top_k)
    except Exception as exc:  # knowledge lookup must never break research
        logger.warning("[research] OKF lookup failed: %s", exc)
        return []


def _versions() -> Dict[str, Any]:
    return {
        "embedding_model": EMBEDDING_MODEL_NAME,
        "index_version": INDEX_VERSION,
        "retriever_version": RETRIEVER_VERSION,
        "reranker_version": RERANKER_VERSION,
        "prompt_version": PROMPT_VERSION,
        "outcome_model_version": outcome_model_service.status().get("version"),
    }


# ── Facets ─────────────────────────────────────────────────────────────
_FACETS: Dict[str, Any] = {"data": None, "built_at": 0.0}
_FACETS_TTL_SECONDS = 300.0


def _build_facets() -> Dict[str, Any]:
    """
    Real filter values with their counts, read from the vector store.

    These are the values that can actually be matched by ``where`` clauses, so
    the UI never offers a filter option the corpus cannot satisfy. Keys listed
    in ``unfiltered_fields`` are deliberately absent from the corpus schema.
    """
    rows = legal_cases_store.get_metadatas()
    courts: Counter = Counter()
    years: Counter = Counter()

    for row in rows:
        metadata = row.get("metadata") or {}
        court = metadata.get("court")
        if court:
            courts[str(court)] += 1
        year = metadata.get("year")
        if year:
            try:
                years[int(year)] += 1
            except (TypeError, ValueError):
                continue

    return {
        "collection": CASE_LAW_COLLECTION,
        "chunk_count": len(rows),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "courts": [
            {"value": value, "count": count} for value, count in courts.most_common()
        ],
        "years": [
            {"value": value, "count": count}
            for value, count in sorted(years.items(), reverse=True)
        ],
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
        "unfiltered_fields": ["law_area", "document_type"],
    }


@router.get("/research/corpus", response_model=CorpusInfo)
def corpus_info() -> CorpusInfo:
    """Corpus actually behind the search box, as read from ChromaDB."""
    return _corpus_info()


@router.get("/research/corpus/facets")
def corpus_facets(refresh: bool = False) -> Dict[str, Any]:
    """Filter options the corpus can actually satisfy (courts, years)."""
    now = time.time()
    cached = _FACETS.get("data")
    if cached is None or refresh or (now - float(_FACETS.get("built_at") or 0.0)) > _FACETS_TTL_SECONDS:
        _FACETS["data"] = _build_facets()
        _FACETS["built_at"] = now
    return _FACETS["data"]


@router.get("/research/chunk/{chunk_id}")
def get_chunk(chunk_id: str) -> Dict[str, Any]:
    """
    Fetch one chunk straight from the vector store by id.

    Use this to confirm a citation in a research answer is a real stored row:
    the returned text and metadata are read directly from ChromaDB.
    """
    try:
        stored = legal_cases_store.collection.get(
            ids=[chunk_id], include=["metadatas", "documents"]
        )
    except VectorStoreError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Vector store error: {exc}") from exc

    ids = stored.get("ids") or []
    if chunk_id not in ids:
        raise HTTPException(
            status_code=404, detail=f"Chunk '{chunk_id}' is not present in the corpus."
        )

    index = ids.index(chunk_id)
    return {
        "collection": CASE_LAW_COLLECTION,
        "chunk_id": chunk_id,
        "metadata": (stored.get("metadatas") or [{}])[index],
        "text": (stored.get("documents") or [""])[index],
    }


# ── Main pipeline ──────────────────────────────────────────────────────
def _execute_research(request: ResearchRequest) -> ResearchResponse:
    started = time.time()
    corpus = _corpus_info()

    if corpus.chunk_count == 0:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Collection '{CASE_LAW_COLLECTION}' is empty. Run "
                "`python scripts/ingest.py` to index the legal corpus."
            ),
        )

    # Step 14 — query understanding: sections, issue, court, years, task.
    analysis = legal_query_analyzer.analyze(request.query)
    sections = request.sections or [
        record["normalized_text"] for record in analysis["legal_sections"]
    ]
    filters = _build_filters(request)

    # 1-2. Embed query (facts + sections + issue) and retrieve from ChromaDB.
    try:
        retrieval_result = retrieval_service.retrieve(
            query=analysis["embedding_text"],
            top_k=request.top_k,
            filters=filters,
            sections=sections or None,
        )
    except RetrievalError as exc:
        logger.error("Retrieval failed for %r: %s", request.query, exc)
        raise HTTPException(status_code=503, detail=f"Retrieval unavailable: {exc}") from exc

    # 3-4. Generate (or return a low-confidence payload) and verify citations.
    try:
        rag_result = rag_service.generate_response(request.query, retrieval_result)
    except Exception as exc:  # generation must never 500 the whole request
        logger.exception("Generation failed for %r", request.query)
        rag_result = {
            "status": "low_confidence",
            "answer": "",
            "confidence": float(retrieval_result.get("best_similarity") or 0.0),
            "sources": retrieval_result.get("results", []),
            "citations": [],
            "supporting_sources": [],
            "unverified_references": [],
            "message": "Answer generation failed; retrieved sources are shown unmodified.",
            "warning": f"Generation error: {exc}",
            "low_confidence": True,
            "answer_origin": "none",
            "generation_time": 0.0,
            "low_confidence_reason": retrieval_result.get("low_confidence_reason"),
        }

    sources = [_to_source(record) for record in rag_result.get("sources", [])]
    citations = [CitationResponse(**item) for item in rag_result.get("citations", [])]
    supporting = [
        CitationResponse(**item) for item in rag_result.get("supporting_sources", [])
    ]

    best_similarity = float(retrieval_result.get("best_similarity") or 0.0)
    evidence_sufficient = bool(
        sources
        and not retrieval_result.get("is_low_confidence")
        and best_similarity >= MIN_EVIDENCE_SCORE
    )
    prediction = _build_prediction(analysis, evidence_sufficient)
    limitations = _build_limitations(
        request, analysis, retrieval_result, rag_result, sources, evidence_sufficient, prediction
    )

    total_time = time.time() - started

    # Step 42 — one structured log line per request, no credentials included.
    logger.info(
        "research_request timestamp=%s query=%r results=%s retrieval_time=%.3fs "
        "generation_time=%.3fs confidence=%.4f status=%s answer_origin=%s "
        "prediction_available=%s retrieved_document_ids=%s",
        datetime.now(timezone.utc).isoformat(),
        request.query,
        len(sources),
        float(rag_result.get("retrieval_time") or retrieval_result.get("retrieval_time") or 0.0),
        float(rag_result.get("generation_time") or 0.0),
        float(rag_result.get("confidence") or 0.0),
        rag_result.get("status", "ok"),
        rag_result.get("answer_origin", "none"),
        prediction.get("available", False),
        [record.get("chunk_id") for record in rag_result.get("sources", [])],
    )

    return ResearchResponse(
        query=request.query,
        status=rag_result.get("status", "ok"),
        answer=rag_result.get("answer", "") or "",
        confidence=float(rag_result.get("confidence") or 0.0),
        confidence_basis=rag_result.get("confidence_basis", "dense_retrieval_similarity"),
        sources=sources,
        citations=citations,
        supporting_sources=supporting,
        unverified_references=rag_result.get("unverified_references", []),
        warning=rag_result.get("warning"),
        message=rag_result.get("message"),
        low_confidence=bool(rag_result.get("low_confidence", False)),
        low_confidence_reason=rag_result.get("low_confidence_reason")
        or retrieval_result.get("low_confidence_reason"),
        answer_origin=rag_result.get("answer_origin", "none"),
        retrieval_time=float(retrieval_result.get("retrieval_time") or 0.0),
        generation_time=float(rag_result.get("generation_time") or 0.0),
        reranked=bool(retrieval_result.get("reranked", False)),
        corpus=corpus,
        precedents=sources,
        prediction=prediction,
        legal_provisions=_legal_provisions(analysis, sources),
        knowledge=_knowledge_concepts(request.query),
        evidence_sufficient=evidence_sufficient,
        retrieval={
            "semantic_count": retrieval_result.get("candidate_count", len(sources)),
            "reranked_count": len(sources),
            "best_similarity": best_similarity,
            "topical_overlap": retrieval_result.get("topical_overlap", 0.0),
            "sections_filter": retrieval_result.get("sections_filter", []),
            "collection": retrieval_result.get("collection"),
        },
        query_analysis=analysis,
        limitations=limitations,
        disclaimer=DISCLAIMER,
        versions=_versions(),
    )


@router.post("/research", response_model=ResearchResponse)
def research(request: ResearchRequest) -> ResearchResponse:
    return _execute_research(request)
