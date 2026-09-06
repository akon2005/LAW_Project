"""
Documents API routes for VIDHIVEDA.
GET /api/documents — browse/filter legal documents (from cases table)
GET /api/documents/{doc_id} — get single document
GET /api/documents/filters/options — distinct filter values from the database
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, Dict, List, Any
import math

from app.models.schemas import DocumentResult, DocumentListResponse
from app.models.database import get_db, Case

router = APIRouter()


def _case_to_doc(c: Case) -> DocumentResult:
    """Map a Case ORM row to the DocumentResult schema the frontend expects."""
    sections = [s.strip() for s in c.section.split(",")] if c.section else []
    return DocumentResult(
        doc_id=c.case_id,
        title=c.case_name,
        document_type=c.legal_domain or "case_law",
        jurisdiction="India",
        court=c.court,
        year=c.year,
        full_text=(
            f"{c.case_name} ({c.year}) — {c.court}. "
            f"Section(s): {c.section or 'N/A'}. "
            f"Domain: {c.legal_domain or 'N/A'}. "
            f"Citation: {c.citation or 'N/A'}."
        ),
        sections=sections,
        summary=None,
        outcome=None,
        source_url=c.source if c.source and c.source.startswith("http") else None,
        relevance_score=0.0,
    )


@router.get("/documents/filters/options")
async def get_filter_options(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Return distinct values for every filterable field, derived from actual data."""
    courts = [
        row[0] for row in
        db.query(Case.court).filter(Case.court.isnot(None))
        .distinct().order_by(Case.court).all()
    ]
    legal_domains = [
        row[0] for row in
        db.query(Case.legal_domain).filter(Case.legal_domain.isnot(None))
        .distinct().order_by(Case.legal_domain).all()
    ]
    record_types = [
        row[0] for row in
        db.query(Case.record_type).filter(Case.record_type.isnot(None))
        .distinct().order_by(Case.record_type).all()
    ]
    min_year = db.query(func.min(Case.year)).scalar() or 1900
    max_year = db.query(func.max(Case.year)).scalar() or 2026

    return {
        "courts": courts,
        "legal_domains": legal_domains,
        "record_types": record_types,
        "year_range": {"min": min_year, "max": max_year},
    }


@router.get("/documents", response_model=DocumentListResponse)
async def browse_documents(
    document_type: Optional[str] = Query(None, description="Filter by legal_domain"),
    jurisdiction: Optional[str] = Query(None, description="Filter by jurisdiction (unused — all cases are India)"),
    court: Optional[str] = Query(None, description="Filter by court name"),
    year_from: Optional[int] = Query(None, description="Filter by start year"),
    year_to: Optional[int] = Query(None, description="Filter by end year"),
    section: Optional[str] = Query(None, description="Filter by legal section"),
    query: Optional[str] = Query(None, description="Search in case name/citation"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Browse, search, and filter legal documents (case law) in the database."""
    q = db.query(Case)

    # Type filter → match against legal_domain (the meaningful category)
    if document_type:
        q = q.filter(Case.legal_domain.ilike(f"%{document_type}%"))

    # Court filter — case-insensitive partial match
    if court:
        q = q.filter(Case.court.ilike(f"%{court}%"))

    # Year range
    if year_from:
        q = q.filter(Case.year >= year_from)
    if year_to:
        q = q.filter(Case.year <= year_to)

    # Section filter
    if section:
        q = q.filter(Case.section.ilike(f"%{section}%"))

    # Free-text search in case name or citation
    if query:
        q = q.filter(
            (Case.case_name.ilike(f"%{query}%")) | (Case.citation.ilike(f"%{query}%"))
        )

    # Jurisdiction is not stored per-row (all are India), so we skip it.
    # The frontend can still send it; we just don't filter on it.

    # Count total
    total = q.count()
    total_pages = math.ceil(total / limit) if total > 0 else 1

    # Paginate
    cases = q.order_by(Case.year.desc()).offset((page - 1) * limit).limit(limit).all()

    documents = [_case_to_doc(c) for c in cases]

    return DocumentListResponse(
        documents=documents,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


@router.get("/documents/{doc_id}", response_model=DocumentResult)
async def get_document(doc_id: str, db: Session = Depends(get_db)):
    """Get a single legal document by ID."""
    doc = db.query(Case).filter(Case.case_id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _case_to_doc(doc)
