"""
Reference Data API route for LexRAG.
GET /api/reference-data — Returns contents of reference JSONs for the Statutes UI.
"""
import json
from fastapi import APIRouter
from app.config import DATA_DIR
from typing import Dict, Any

router = APIRouter()

@router.get("/reference-data", response_model=Dict[str, Any])
async def get_reference_data():
    """Retrieve all static reference data for the Statutes & Articles UI."""
    data = {}
    
    try:
        with open(DATA_DIR / "dataset" / "constitution.json", "r", encoding="utf-8") as f:
            data["constitution"] = json.load(f)
    except FileNotFoundError:
        data["constitution"] = []

    try:
        with open(DATA_DIR / "dataset" / "criminal_law_mapping.json", "r", encoding="utf-8") as f:
            data["criminal_law"] = json.load(f)
    except FileNotFoundError:
        data["criminal_law"] = []
        
    try:
        with open(DATA_DIR / "dataset" / "landmark_cases.json", "r", encoding="utf-8") as f:
            data["landmark_cases"] = json.load(f)
    except FileNotFoundError:
        data["landmark_cases"] = []

    return data
