from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from app.services.chat_service import chat_service
from app.rag.retrieval_service import retrieval_service
from app.rag.query_analyzer import legal_query_analyzer
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    conversation_id: Optional[str] = None
    top_k: int = 5

class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    conversation_id: str

def _build_filters_from_analysis(analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    filters = {}
    if analysis.get("court"):
        filters["court"] = analysis["court"]
    if analysis.get("year"):
        filters["year"] = analysis["year"]

    # Range handling is tricky in basic Chroma filters without operators,
    # but the retrieval service allows passing dicts. We'll stick to exact matches for now
    # unless the vector store explicitly supports $gte/$lte
    if analysis.get("year_from") and analysis.get("year_to"):
        filters["year"] = {"$gte": analysis["year_from"], "$lte": analysis["year_to"]}

    return filters if filters else None

@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        history_dicts = [{"role": msg.role, "content": msg.content} for msg in request.history]

        # 1. Query Rewriting (Contextualization)
        # If the user says "summarize the second case", we need the LLM to rewrite it
        # into a standalone query based on the history.
        rewritten_query = chat_service.rewrite_query(request.message, history_dicts)

        # 2. Query Analysis
        analysis = legal_query_analyzer.analyze(rewritten_query)
        query_text = analysis["embedding_text"]

        # Extract sections and metadata filters
        sections = [record["normalized_text"] for record in analysis.get("legal_sections", [])]
        filters = _build_filters_from_analysis(analysis)

        # 3. Retrieval
        retrieval_result = retrieval_service.retrieve(
            query=query_text,
            top_k=request.top_k,
            filters=filters,
            sections=sections if sections else None
        )

        # 4. Generation
        response = chat_service.generate_chat_response(
            original_query=request.message,
            history=history_dicts,
            retrieval_result=retrieval_result,
            analysis=analysis
        )

        return ChatResponse(
            answer=response.get("answer", ""),
            sources=response.get("sources", []),
            citations=response.get("citations", []),
            conversation_id=request.conversation_id or "new_chat"
        )
    except Exception as e:
        logger.exception("Chat error")
        raise HTTPException(status_code=500, detail=str(e))
