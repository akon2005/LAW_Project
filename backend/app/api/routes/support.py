"""
/api/support — the VIDHIVEDA User Guide & Support Assistant.

Endpoints (all read-only except feedback, which is user-initiated):

| Method | Path                        | Purpose |
|---|---|---|
| POST   | /api/support/chat           | Ask a support question, get a grounded structured answer |
| GET    | /api/support/health         | Real readiness of the support subsystem |
| GET    | /api/support/articles       | List / search support articles |
| GET    | /api/support/articles/{id}  | One support article with its body |
| GET    | /api/support/examples       | Approved demo example gallery |
| GET    | /api/support/features       | Capability registry with real statuses |
| GET    | /api/support/tools          | Tool registry and permissions (diagnostic) |
| POST   | /api/support/feedback       | Helpful / not-helpful feedback |
| POST   | /api/support/report         | File a problem report (stored locally, no external tracker) |
| POST   | /api/support/session/reset  | Clear the current session's conversation |

Why these and no more: the support assistant needs exactly one conversational
endpoint, one readiness endpoint and read-only access to its data files. Every
additional endpoint is another surface to validate, so none were added purely for
completeness.

This module never touches the legal corpus, the OKF bundle or the legal RAG
pipeline. Legal questions are answered by pointing at the Research workspace.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from app.support.examples import examples_store
from app.support.features import feature_registry
from app.support.feedback import MAX_COMMENT, feedback_store
from app.support.knowledge_base import support_knowledge_base
from app.support.reports import REPORT_CATEGORIES, report_store
from app.support.service import MAX_MESSAGE_LENGTH, answer, reset_session, tool_catalog
from app.support.sessions import session_store
from app.support.status import support_health
from app.support.troubleshooting import troubleshooting_store

router = APIRouter()
logger = logging.getLogger("vidhiveda.support")

# Pages the frontend is allowed to report as context. Anything else is rejected,
# so page context can never be an arbitrary string carried into a prompt.
ALLOWED_PAGES = {"research", "statutes", "documents", "comparison", "knowledge", "settings", "guide"}
SESSION_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{6,64}$")


# ── Schemas ────────────────────────────────────────────────────────────
class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=2000)


class FeedbackPayload(BaseModel):
    rating: str = Field(..., pattern="^(helpful|not_helpful)$")
    comment: Optional[str] = Field(default=None, max_length=MAX_COMMENT)
    message_id: Optional[str] = Field(default=None, max_length=80)


class ReportPayload(BaseModel):
    category: str = Field(..., max_length=32)
    title: str = Field(..., min_length=4, max_length=120)
    description: str = Field(..., min_length=20, max_length=2000)
    steps: Optional[str] = Field(default=None, max_length=1000)
    page: Optional[str] = Field(default=None, max_length=32)
    contact: Optional[str] = Field(default=None, max_length=120)

    @field_validator("category")
    @classmethod
    def _category(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in REPORT_CATEGORIES:
            raise ValueError("category must be one of: " + ", ".join(REPORT_CATEGORIES))
        return normalized

    @field_validator("page")
    @classmethod
    def _page(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        normalized = value.strip().lower()
        if normalized not in ALLOWED_PAGES:
            raise ValueError("page must be one of: " + ", ".join(sorted(ALLOWED_PAGES)))
        return normalized


class SupportChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    session_id: Optional[str] = Field(default=None, max_length=64)
    page: Optional[str] = Field(default=None, max_length=32)
    demo_mode: bool = False
    # A bounded tail of the client's thread, used only when the server has no
    # history for this session (for example after a page reload).
    history: List[ChatTurn] = Field(default_factory=list, max_length=12)
    feedback: Optional[FeedbackPayload] = None

    @field_validator("session_id")
    @classmethod
    def _session(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        if not SESSION_PATTERN.match(value):
            raise ValueError("session_id must be 6-64 characters of [A-Za-z0-9_-]")
        return value

    @field_validator("page")
    @classmethod
    def _page(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        normalized = value.strip().lower()
        if normalized not in ALLOWED_PAGES:
            raise ValueError("page must be one of: " + ", ".join(sorted(ALLOWED_PAGES)))
        return normalized


class SourceRef(BaseModel):
    id: str
    title: str
    category: str
    updated: str = ""
    excerpt: str = ""
    relevance: float = 0.0
    match: str = ""


class QuickAction(BaseModel):
    id: str
    label: str
    kind: str
    target: str


class ToolRun(BaseModel):
    name: str
    ok: bool
    duration_ms: Optional[int] = None


class SupportChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    kind: str
    origin: str
    generated: bool
    intent: str
    sources: List[SourceRef] = []
    follow_ups: List[str] = []
    quick_actions: List[QuickAction] = []
    tools_used: List[ToolRun] = []
    page_context: Optional[str] = None
    degraded: List[str] = []
    warnings: List[str] = []
    demo: bool = False
    duration_ms: int = 0


# ── Helpers ────────────────────────────────────────────────────────────
def _require_knowledge_base() -> None:
    """The support path has one hard dependency: its own documentation."""
    if not support_knowledge_base.stats().get("available"):
        raise HTTPException(
            status_code=503,
            detail=(
                "The support knowledge base is unavailable, so no answer can be grounded. "
                "Expected articles under backend/support/articles/."
            ),
        )


# ── Chat ───────────────────────────────────────────────────────────────
@router.post("/support/chat", response_model=SupportChatResponse)
def support_chat(request: SupportChatRequest) -> SupportChatResponse:
    _require_knowledge_base()

    payload = answer(
        message=request.message,
        session_id=request.session_id,
        page=request.page,
        demo_mode=request.demo_mode,
        client_history=[turn.model_dump() for turn in request.history],
        feedback=request.feedback.model_dump() if request.feedback else None,
    )
    return SupportChatResponse(**payload)


@router.post("/support/session/reset")
def support_session_reset(request: Request, session_id: Optional[str] = Query(default=None, max_length=64)) -> Dict[str, Any]:
    if session_id and not SESSION_PATTERN.match(session_id):
        raise HTTPException(status_code=422, detail="session_id must be 6-64 characters of [A-Za-z0-9_-]")
    cleared = reset_session(session_id) if session_id else False
    return {
        "cleared": cleared,
        "session_id": session_id,
        "message": "Conversation cleared." if cleared else "There was no stored conversation for that session.",
        "sessions": session_store.stats(),
    }


# ── Readiness ──────────────────────────────────────────────────────────
@router.get("/support/health")
def support_health_endpoint(probe: bool = Query(default=False)) -> Dict[str, Any]:
    """
    Real readiness, not an assumption.

    ``probe=true`` performs an actual provider connectivity check (it costs a
    request to the provider); without it, reachability is reported as ``null``
    and explicitly not claimed.
    """
    return support_health(probe_llm=probe)


# ── Knowledge base ─────────────────────────────────────────────────────
@router.get("/support/articles")
def list_articles(
    q: Optional[str] = Query(default=None, max_length=300),
    category: Optional[str] = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
) -> Dict[str, Any]:
    _require_knowledge_base()
    if q:
        hits = support_knowledge_base.search(q, limit=limit)
        articles = [{**hit["article"].as_summary(), "relevance": hit["relevance"], "match": hit["match"]} for hit in hits]
        return {"total": len(articles), "query": q, "articles": articles, "categories": support_knowledge_base.categories()}

    articles = [
        article.as_summary()
        for article in support_knowledge_base.articles()
        if not category or article.category == category
    ][:limit]
    return {
        "total": len(articles),
        "category": category,
        "articles": articles,
        "categories": support_knowledge_base.categories(),
    }


@router.get("/support/articles/{article_id}")
def get_article(article_id: str) -> Dict[str, Any]:
    _require_knowledge_base()
    article = support_knowledge_base.get(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail=f"Support article '{article_id}' is not in the knowledge base.")
    data = article.as_summary()
    data["body"] = article.body
    return data


# ── Demo examples ──────────────────────────────────────────────────────
@router.get("/support/examples")
def list_examples(category: Optional[str] = Query(default=None, max_length=64)) -> Dict[str, Any]:
    examples = examples_store.all(category)
    if not examples and not examples_store.available():
        raise HTTPException(status_code=503, detail="The example gallery data file could not be read.")
    return {
        "total": len(examples),
        "category": category,
        "categories": examples_store.categories(),
        "examples": examples,
        "note": examples_store.note(),
    }


# ── Capability registry ────────────────────────────────────────────────
@router.get("/support/features")
def list_features() -> Dict[str, Any]:
    if not feature_registry.available():
        raise HTTPException(status_code=503, detail="The capability registry could not be read.")
    summary = feature_registry.summary()
    summary["known_problems"] = [
        {"id": entry["id"], "title": entry["title"]} for entry in troubleshooting_store.all()
    ]
    return summary


# ── Tool registry (diagnostic) ─────────────────────────────────────────
@router.get("/support/tools")
def list_tools() -> Dict[str, Any]:
    """The tools the assistant may run, with their permissions. Read-only."""
    return {
        "max_calls_per_request": 3,
        "tools": tool_catalog(),
        "notes": [
            "Arguments are validated by typed models before any handler runs.",
            "Navigation returns ids from an allowlist; the assistant cannot generate a route or a URL.",
            "Only submit_feedback and the report form write anything, and only when the user submits them.",
            "There is no shell, SQL, filesystem or arbitrary HTTP capability in the registry.",
        ],
    }


# ── Feedback ───────────────────────────────────────────────────────────
@router.post("/support/feedback")
def submit_feedback(
    payload: FeedbackPayload,
    session_id: Optional[str] = Query(default=None, max_length=64),
    page: Optional[str] = Query(default=None, max_length=32),
) -> Dict[str, Any]:
    if session_id and not SESSION_PATTERN.match(session_id):
        raise HTTPException(status_code=422, detail="session_id must be 6-64 characters of [A-Za-z0-9_-]")
    if page and page not in ALLOWED_PAGES:
        raise HTTPException(status_code=422, detail="page must be one of: " + ", ".join(sorted(ALLOWED_PAGES)))

    if feedback_store.check_rate(session_id or "anonymous"):
        raise HTTPException(status_code=429, detail="Too many feedback submissions. Please try again later.")

    try:
        result = feedback_store.submit(
            payload.rating, payload.comment, payload.message_id, session_id, page
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {**result, "message": "Thanks — your feedback was recorded."}


# ── Problem reports ────────────────────────────────────────────────────
@router.post("/support/report")
def submit_report(
    payload: ReportPayload,
    session_id: Optional[str] = Query(default=None, max_length=64),
) -> Dict[str, Any]:
    """Store a problem report in this deployment's local support log.

    No external ticketing service is integrated, so the response says the report
    was recorded locally. It never claims that a remote ticket exists.
    """
    if session_id and not SESSION_PATTERN.match(session_id):
        raise HTTPException(status_code=422, detail="session_id must be 6-64 characters of [A-Za-z0-9_-]")

    if report_store.check_rate(session_id or "anonymous"):
        raise HTTPException(
            status_code=429,
            detail="Too many reports submitted just now. Please try again in a few minutes.",
        )

    try:
        result = report_store.submit(
            category=payload.category,
            title=payload.title,
            description=payload.description,
            steps=payload.steps,
            page=payload.page,
            contact=payload.contact,
            session_id=session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail="The report could not be stored on the server (its support log is not writable).",
        ) from exc

    return {
        **result,
        "message": (
            "Report recorded in this deployment's local support log. "
            "No external ticket or email was created."
        ),
    }
