"""
Sections API route for VIDHIVEDA.
GET /api/sections — list unique legal sections from the cases database.
"""
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.models.schemas import SectionInfo
from app.models.database import get_db, Case

router = APIRouter()


@router.get("/sections", response_model=List[SectionInfo])
async def list_sections(db: Session = Depends(get_db)):
    """List all unique legal sections found across the case law database."""
    rows = db.query(Case.section, Case.legal_domain).filter(Case.section.isnot(None)).distinct().all()

    seen = set()
    sections = []
    for row in rows:
        for part in row.section.split(","):
            s = part.strip()
            if s and s not in seen:
                seen.add(s)
                sections.append(SectionInfo(
                    section=s,
                    title=s,
                    description=f"Legal section referenced in {row.legal_domain or 'Indian'} case law",
                    act=row.legal_domain,
                ))
    return sorted(sections, key=lambda x: x.section)
