"""
POST /api/comparison — two-scenario legal argument comparison (evidence-based).

Two competing accounts of the same legal dispute are retrieved against the
existing ChromaDB corpus and compared. The endpoint returns structured,
source-backed argument analysis plus an explicit evidence-quality status. It
never returns a verdict, and it reports an outcome estimate only when a trained,
evaluated classifier exists — otherwise ``available`` is false with a reason.

Deploy/repo constraint: this endpoint only reads the existing corpus. It writes
nothing and calls no external service.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import CASE_LAW_COLLECTION, RETRIEVAL_TOP_K
from app.db.vector_store import legal_cases_store
from app.rag.retrieval_service import RetrievalError
from app.services.comparison_service import comparison_service

router = APIRouter()
logger = logging.getLogger("vidhiveda.comparison")

# Bounds keep a single request small and prevent runaway prompts/cost.
MAX_POSITION_CHARS = 6000
MAX_FACTS_CHARS = 8000
MAX_ISSUE_CHARS = 2000


class ScenarioInput(BaseModel):
    label: str = Field(default="", max_length=120)
    position: str = Field(
        ...,
        min_length=2,
        max_length=MAX_POSITION_CHARS,
        description="This party's account: the facts and legal argument it relies on.",
    )


class ComparisonRequest(BaseModel):
    legal_issue: str = Field(
        ..., min_length=2, max_length=MAX_ISSUE_CHARS, description="The legal question in dispute"
    )
    case_facts: Optional[str] = Field(default=None, max_length=MAX_FACTS_CHARS)
    provisions: List[str] = Field(default_factory=list, max_length=40)
    scenario_a: ScenarioInput
    scenario_b: Optional[ScenarioInput] = None
    court: Optional[str] = None
    year: Optional[int] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    top_k: int = Field(default=RETRIEVAL_TOP_K, ge=1, le=20)


def _filters(request: ComparisonRequest) -> Optional[Dict[str, Any]]:
    """Only filters backed by real stored metadata are returned."""
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


@router.post("/comparison")
def compare_scenarios(request: ComparisonRequest) -> Dict[str, Any]:
    """Compare two competing accounts against the indexed legal corpus."""
    try:
        chunk_count = legal_cases_store.get_count()
    except Exception as exc:  # vector store unavailable
        raise HTTPException(status_code=503, detail=f"Vector store error: {exc}") from exc

    if chunk_count == 0:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Collection '{CASE_LAW_COLLECTION}' is empty. Run "
                "`python scripts/ingest.py` to index the legal corpus."
            ),
        )

    scenario_b_dict = (
        {"label": request.scenario_b.label, "position": request.scenario_b.position}
        if request.scenario_b and request.scenario_b.position
        else None
    )

    payload = {
        "legal_issue": request.legal_issue,
        "case_facts": request.case_facts or "",
        "provisions": [p.strip() for p in request.provisions if p and p.strip()],
        "scenario_a": {"label": request.scenario_a.label, "position": request.scenario_a.position},
        "scenario_b": scenario_b_dict,
        "top_k": request.top_k,
        "filters": _filters(request),
    }

    try:
        result = comparison_service.compare(payload)
    except RetrievalError as exc:
        raise HTTPException(status_code=503, detail=f"Retrieval unavailable: {exc}") from exc

    # One structured log line per request; scenario text is not logged.
    logger.info(
        "comparison_request timestamp=%s issue_len=%s evidence_status=%s "
        "precedents=%s prediction_available=%s scenario_a_supporting=%s scenario_b_supporting=%s",
        datetime.now(timezone.utc).isoformat(),
        len(request.legal_issue),
        result["evidence_quality"]["status"],
        len(result["precedents"]),
        result["outcome_prediction"]["available"],
        result["scenario_a"]["supporting_count"],
        result["scenario_b"]["supporting_count"] if result.get("scenario_b") else 0,
    )
    return result
