"""
OKF knowledge API (Phase 16).

Read-only access to the Open Knowledge Format v0.2 bundle:

* ``GET /api/knowledge``                 — list/filter concepts
* ``GET /api/knowledge/stats``           — bundle-level counts and trust summary
* ``GET /api/knowledge/validate``        — conformance report (§11)
* ``GET /api/knowledge/{concept_id}``    — one concept with resolved relationships

The bundle is generated from the real corpus by
``scripts/build_okf_bundle.py`` and validated by ``scripts/validate_okf.py``.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.config import OKF_VERSION
from app.okf import okf_service

router = APIRouter()


def _ensure_bundle() -> None:
    if not okf_service.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "OKF knowledge bundle not found. Build it with "
                "`python scripts/build_okf_bundle.py` from backend/."
            ),
        )


@router.get("/knowledge/stats")
def knowledge_stats() -> Dict[str, Any]:
    """Bundle summary: concept counts by type, trust tiers, provenance coverage."""
    if not okf_service.exists():
        return {
            "available": False,
            "okf_version": OKF_VERSION,
            "bundle": str(okf_service.bundle_root),
            "detail": "Bundle not built. Run scripts/build_okf_bundle.py.",
        }
    return okf_service.stats()


@router.get("/knowledge/validate")
def knowledge_validate(refresh: bool = False) -> Dict[str, Any]:
    """
    Conformance report for the bundle (OKF §11).

    Broken links and missing optional frontmatter families are reported but do
    not make a bundle non-conformant.
    """
    _ensure_bundle()
    if refresh:
        okf_service.reload()
    return okf_service.validate()


@router.get("/knowledge")
def knowledge_list(
    type: Optional[str] = Query(default=None, description="exact concept type"),
    status: Optional[str] = Query(default=None, description="draft|stable|deprecated"),
    tag: Optional[str] = None,
    q: Optional[str] = Query(default=None, description="substring match over title/tags/body"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """Enumerate concepts, optionally filtered by type, status, tag or text."""
    _ensure_bundle()
    return okf_service.list_concepts(
        concept_type=type, status=status, tag=tag, query=q, limit=limit, offset=offset
    )


@router.get("/knowledge/search")
def knowledge_search(
    q: str = Query(..., min_length=2),
    top_k: int = Query(default=5, ge=1, le=50),
    type: Optional[str] = None,
) -> Dict[str, Any]:
    """Lexical lookup over concepts (retrieval relevance, not a legal score)."""
    _ensure_bundle()
    results = okf_service.search(q, top_k=top_k, concept_type=type)
    return {"query": q, "count": len(results), "results": results}


@router.get("/knowledge/{concept_id:path}")
def knowledge_concept(concept_id: str) -> Dict[str, Any]:
    """One concept: frontmatter, body, trust tier and resolved relationships."""
    _ensure_bundle()
    concept = okf_service.get_concept(concept_id)
    if concept is None:
        raise HTTPException(
            status_code=404,
            detail=f"Concept '{concept_id}' is not present in the OKF bundle.",
        )
    return concept
