import time
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from app.models.schemas import SearchRequest, SearchResponse
from app.services.pipeline import retrieve, generate_explanation

router = APIRouter()

@router.post("/search", response_model=SearchResponse)
def legal_search(request: SearchRequest):
    """
    Accepts {query, filters, top_k} + optional top-level filter fields,
    retrieves semantically matching judicial precedents from ChromaDB,
    and returns a structured legal research answer with citations.
    """
    start_time = time.time()
    print(f"[Search API] Received query: '{request.query}' | top_k: {request.top_k}")

    # Merge top-level filter params into filters dictionary if present
    filters = request.filters or {}
    if request.document_type and "document_type" not in filters:
        filters["document_type"] = request.document_type
    if request.court and "court" not in filters:
        filters["court"] = request.court
    if request.year_from and "year_from" not in filters:
        filters["year_from"] = request.year_from
    if request.year_to and "year_to" not in filters:
        filters["year_to"] = request.year_to

    try:
        retrieved_cases, is_low_confidence = retrieve(
            query=request.query, 
            top_k=request.top_k, 
            filters=filters if filters else None
        )
        print(f"[Search API] Retrieved {len(retrieved_cases)} cases (low_confidence={is_low_confidence})")
        
        gen_result = generate_explanation(request.query, retrieved_cases)
        
        elapsed = round(time.time() - start_time, 2)
        
        return SearchResponse(
            answer=gen_result.get("answer") or gen_result.get("explanation") or "",
            explanation=gen_result.get("explanation") or gen_result.get("answer") or "",
            sources=gen_result.get("sources", []),
            prediction_context=gen_result.get("prediction_context", []),
            key_principles=gen_result.get("key_principles", []),
            disclaimer=gen_result.get("disclaimer", "This is AI-generated research support and does not constitute legal advice."),
            processing_time_seconds=elapsed,
            confidence="High" if not is_low_confidence else "Low",
            low_confidence=is_low_confidence,
            citations=gen_result.get("citations", []),
            unverified_citation=gen_result.get("unverified_citation", False),
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
