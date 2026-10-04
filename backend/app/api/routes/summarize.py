"""
Summarize API route for VIDHIVEDA.
POST /api/summarize — Generate AI summary for a legal document.
"""
import time
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.schemas.schemas import SummarizeRequest, SummarizeResponse
from app.db.database import get_db, Case

router = APIRouter()


def _case_to_summary_dict(c: Case) -> dict:
    """Map a Case ORM row to a dict suitable for summarization."""
    sections = [s.strip() for s in c.section.split(",")] if c.section else []
    full_text = (
        f"{c.case_name} ({c.year}) — {c.court}. "
        f"Section(s): {c.section or 'N/A'}. "
        f"Domain: {c.legal_domain or 'N/A'}. "
        f"Citation: {c.citation or 'N/A'}."
    )
    return {
        "doc_id": c.case_id,
        "title": c.case_name,
        "document_type": c.legal_domain or "case_law",
        "court": c.court,
        "year": c.year,
        "sections": sections,
        "full_text": full_text,
    }


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_document(request: SummarizeRequest, db: Session = Depends(get_db)):
    """
    Generate an AI-powered summary for a specific legal document.
    Falls back to a structured local summary if no LLM is configured.
    """
    start_time = time.time()

    try:
        # Fetch the document from SQLite
        doc = db.query(Case).filter(Case.case_id == request.doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document '{request.doc_id}' not found")

        doc_dict = _case_to_summary_dict(doc)

        # Generate summary using local template (reliable, no API dependency)
        summary, key_points = _generate_local_summary(doc_dict)

        sections = [s.strip() for s in doc.section.split(",")] if doc.section else []

        elapsed = round(time.time() - start_time, 2)

        return SummarizeResponse(
            doc_id=doc.case_id,
            title=doc.case_name,
            summary=summary,
            key_points=key_points,
            cited_sections=sections,
            processing_time_seconds=elapsed,
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def _generate_local_summary(doc: dict) -> tuple:
    """
    Generate a structured local summary from document metadata.
    Returns (summary_text, key_points_list).
    """
    title = doc.get("title", "Unknown Document")
    year = doc.get("year", "N/A")
    court = doc.get("court", "N/A")
    doc_type = doc.get("document_type", "case_law")
    sections = doc.get("sections", [])
    full_text = doc.get("full_text", "")

    section_list = ", ".join(sections) if sections else "N/A"

    summary = f"""## Document Summary: {title}

### Background
- **Year**: {year}
- **Court**: {court}
- **Type**: {doc_type.replace('_', ' ').title()}
- **Sections/Articles**: {section_list}

### Document Content
{full_text}

### Key Observations
1. This document is classified under **{doc_type.replace('_', ' ').title()}** within the Indian legal framework.
2. It was decided/issued in **{year}** by **{court}**.
3. The relevant legal sections are: **{section_list}**.

---
*This summary is auto-generated from metadata and does not constitute legal analysis.*"""

    key_points = [
        f"Document type: {doc_type.replace('_', ' ').title()}",
        f"Court: {court}",
        f"Year: {year}",
        f"Sections: {section_list}",
    ]

    return summary, key_points
