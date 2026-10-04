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

@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        # Analyze query for embedding
        analysis = legal_query_analyzer.analyze(request.message)
        query_text = analysis["embedding_text"]
        
        # Retrieve context
        retrieval_result = retrieval_service.retrieve(
            query=query_text,
            top_k=request.top_k,
            filters=None,
            sections=None
        )
        
        history_dicts = [{"role": msg.role, "content": msg.content} for msg in request.history]
        
        response = chat_service.generate_chat_response(
            query=request.message,
            history=history_dicts,
            retrieval_result=retrieval_result
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
