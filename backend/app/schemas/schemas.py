from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Natural language legal search query")
    filters: Optional[Dict[str, Any]] = Field(None, description="Key-value pairs for metadata filtering")
    top_k: int = Field(default=8, ge=1, le=50, description="Number of results to retrieve")
    document_type: Optional[str] = None
    jurisdiction: Optional[str] = None
    court: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None


class RetrievedCase(BaseModel):
    case_id: str = ""
    doc_id: str = ""
    case_name: str = ""
    title: str = ""
    citation: Optional[str] = None
    year: Optional[int] = None
    court: Optional[str] = None
    legal_domain: Optional[str] = None
    section: Optional[str] = None
    source: Optional[str] = None
    record_type: Optional[str] = None
    similarity_score: float = 0.0
    relevance_score: float = 0.0
    retrieval_document: str = ""
    snippet: str = ""


class SourceDocument(BaseModel):
    doc_id: str = ""
    case_id: str = ""
    title: str = ""
    case_name: str = ""
    document_type: str = "case_law"
    court: Optional[str] = None
    year: Optional[int] = None
    relevance_score: float = 0.0
    similarity_score: float = 0.0
    snippet: str = ""
    citation: Optional[str] = None
    sections: List[str] = []


class SearchResponse(BaseModel):
    # Primary fields used by ResearchAnswer.jsx
    answer: str = ""
    sources: List[SourceDocument] = []
    key_principles: List[str] = []
    disclaimer: str = "This is AI-generated research support and does not constitute legal advice."
    processing_time_seconds: float = 0.0

    # Extended research schema compatibility
    explanation: str = ""
    prediction_context: List[RetrievedCase] = []
    confidence: str = "High"
    low_confidence: bool = False
    citations: List[str] = []
    unverified_citation: bool = False


class DocumentResult(BaseModel):
    doc_id: str
    title: str
    document_type: str = "case_law"
    jurisdiction: Optional[str] = None
    court: Optional[str] = None
    year: Optional[int] = None
    full_text: str = ""
    sections: List[str] = []
    summary: Optional[str] = None
    outcome: Optional[str] = None
    source_url: Optional[str] = None
    relevance_score: float = 0.0


class DocumentListResponse(BaseModel):
    documents: List[DocumentResult]
    total: int
    page: int
    limit: int
    total_pages: int


class SectionInfo(BaseModel):
    section: str
    title: Optional[str] = None
    description: Optional[str] = None
    act: Optional[str] = None


class SimilarRequest(BaseModel):
    doc_id: str = Field(..., description="Document ID to find similar cases for")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of similar results")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional metadata filters")


class SimilarResponse(BaseModel):
    source_doc: Optional[SourceDocument] = None
    similar_docs: List[SourceDocument] = []
    processing_time_seconds: float = 0.0


class TrendRequest(BaseModel):
    topic: str = Field(..., min_length=2, description="Legal topic to analyze trends for")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional metadata filters")
    top_k: int = Field(default=20, ge=1, le=50, description="Number of documents for trend analysis")


class TrendResponse(BaseModel):
    topic: str = ""
    analysis: str = ""
    sources: List[SourceDocument] = []
    key_principles: List[str] = []
    disclaimer: str = "This trend analysis is provided as research input only and does not predict or recommend any judicial outcome."
    processing_time_seconds: float = 0.0


class SummarizeRequest(BaseModel):
    doc_id: str = Field(..., description="Document ID to summarize")


class SummarizeResponse(BaseModel):
    doc_id: str = ""
    title: str = ""
    summary: str = ""
    key_points: List[str] = []
    cited_sections: List[str] = []
    processing_time_seconds: float = 0.0
