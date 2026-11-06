"""
Tool registry for the support assistant.

Rules this module enforces, so the assistant can never do more than it should:

* **Explicit allowlist.** Every capability is a named tool with a typed argument
  model. There is no shell, no SQL, no filesystem browser, no arbitrary HTTP
  client and no code execution anywhere in the registry.
* **Argument validation before execution.** Arguments are parsed by a Pydantic
  model; a malformed call fails with a readable message and never reaches the
  handler.
* **Bounded execution.** Runs per request are capped, each call is timed and
  exceptions are converted into user-readable errors.
* **Safe logging.** Tool name, status and duration are logged; arguments and
  message text are not.
* **Consequential actions need confirmation.** ``submit_feedback`` only runs when
  the request itself carries the feedback payload (i.e. the user pressed the
  button). Otherwise the tool answers "confirmation required" and the assistant
  asks the user to use the UI.
* **Navigation is an allowlist, not a URL generator.** ``navigate_to_feature``
  returns an id from :data:`ACTION_CATALOG`; the model cannot produce an
  arbitrary route or link.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger("vidhiveda.support")

MAX_TOOL_CALLS_PER_REQUEST = 3

# ── Quick actions the frontend can actually perform ────────────────────
# ``kind='navigate'`` switches the workspace tab; ``kind='client'`` is handled by
# the assistant itself. Targets must match tabs that exist in App.jsx.
ACTION_CATALOG: List[Dict[str, str]] = [
    {"id": "open_research", "label": "Open Legal Research", "kind": "navigate", "target": "research"},
    {"id": "open_comparison", "label": "Compare Legal Arguments", "kind": "navigate", "target": "comparison"},
    {"id": "open_examples", "label": "Explore Example Queries", "kind": "navigate", "target": "guide"},
    {"id": "open_settings", "label": "Open Theme Settings", "kind": "navigate", "target": "settings"},
    {"id": "open_knowledge", "label": "Open Knowledge Bundle", "kind": "navigate", "target": "knowledge"},
    {"id": "open_documents", "label": "Browse Documents", "kind": "navigate", "target": "documents"},
    {"id": "open_statutes", "label": "Statutes & Articles", "kind": "navigate", "target": "statutes"},
    {"id": "show_features", "label": "View Supported Features", "kind": "client", "target": "features"},
    {"id": "show_status", "label": "Check System Status", "kind": "client", "target": "status"},
    {"id": "learn_about_rag", "label": "Learn About RAG", "kind": "client", "target": "rag"},
    {"id": "run_demo", "label": "Run a Demo", "kind": "client", "target": "demo"},
    {"id": "restart_conversation", "label": "Restart Conversation", "kind": "client", "target": "restart"},
    {"id": "report_problem", "label": "Report a Problem", "kind": "client", "target": "report"},
]

VALID_ACTION_TARGETS = {
    action["target"] for action in ACTION_CATALOG if action["kind"] == "navigate"
}


def action(action_id: str) -> Optional[Dict[str, str]]:
    for item in ACTION_CATALOG:
        if item["id"] == action_id:
            return dict(item)
    return None


def actions(action_ids: List[str]) -> List[Dict[str, str]]:
    resolved: List[Dict[str, str]] = []
    seen = set()
    for action_id in action_ids:
        item = action(action_id)
        if item and item["id"] not in seen:
            resolved.append(item)
            seen.add(item["id"])
    return resolved


# ── Argument models ────────────────────────────────────────────────────
class SearchDocsArgs(BaseModel):
    query: str = Field(..., min_length=2, max_length=300)
    limit: int = Field(default=4, ge=1, le=8)


class FeatureArgs(BaseModel):
    feature_id: str = Field(..., min_length=2, max_length=64)


class ExamplesArgs(BaseModel):
    category: Optional[str] = Field(default=None, max_length=64)
    example_id: Optional[str] = Field(default=None, max_length=64)


class StatusArgs(BaseModel):
    probe_llm: bool = False


class TroubleshootArgs(BaseModel):
    problem: str = Field(..., min_length=3, max_length=400)


class NoArgs(BaseModel):
    pass


class NavigateArgs(BaseModel):
    target: str = Field(..., min_length=2, max_length=40)


class FeedbackArgs(BaseModel):
    rating: str = Field(..., min_length=4, max_length=16)
    comment: Optional[str] = Field(default=None, max_length=500)
    message_id: Optional[str] = Field(default=None, max_length=80)
    confirmed: bool = False


@dataclass
class ToolSpec:
    id: str
    label: str
    description: str
    args_model: Type[BaseModel]
    handler: Callable[[BaseModel, Dict[str, Any]], Dict[str, Any]]
    side_effects: bool = False
    requires_confirmation: bool = False
    tags: List[str] = field(default_factory=list)


# ── Handlers ───────────────────────────────────────────────────────────
def _search_support_docs(args: SearchDocsArgs, ctx: Dict[str, Any]) -> Dict[str, Any]:
    from app.support.knowledge_base import support_knowledge_base

    hits = support_knowledge_base.search(
        args.query,
        limit=args.limit,
        intent=ctx.get("intent"),
        feature=ctx.get("feature"),
        category=ctx.get("category"),
    )
    return {
        "count": len(hits),
        "articles": [
            {
                **hit["article"].as_summary(),
                "score": hit["score"],
                "relevance": hit["relevance"],
                "match": hit["match"],
                "matched_terms": hit["matched"],
            }
            for hit in hits
        ],
    }


def _get_feature_help(args: FeatureArgs, ctx: Dict[str, Any]) -> Dict[str, Any]:
    from app.support.examples import examples_store
    from app.support.features import feature_registry
    from app.support.knowledge_base import support_knowledge_base

    feature = feature_registry.get(args.feature_id)
    if feature is None:
        return {
            "found": False,
            "feature_id": args.feature_id,
            "available_features": [item.get("id") for item in feature_registry.all()],
        }

    article = support_knowledge_base.get(str(feature.get("how_to") or ""))
    example = next(
        (item for item in examples_store.all() if item.get("article") == feature.get("how_to")),
        None,
    )
    return {
        "found": True,
        "feature": feature,
        "guide": article.as_summary() if article else None,
        "example": example,
    }


def _get_demo_examples(args: ExamplesArgs, ctx: Dict[str, Any]) -> Dict[str, Any]:
    from app.support.examples import examples_store

    if args.example_id:
        example = examples_store.get(args.example_id)
        return {"found": bool(example), "example": example, "categories": examples_store.categories()}
    return {
        "found": True,
        "examples": examples_store.all(args.category),
        "categories": examples_store.categories(),
    }


def _get_system_status(args: StatusArgs, ctx: Dict[str, Any]) -> Dict[str, Any]:
    from app.support.status import support_health

    return support_health(probe_llm=args.probe_llm)


def _get_troubleshooting_steps(args: TroubleshootArgs, ctx: Dict[str, Any]) -> Dict[str, Any]:
    from app.support.troubleshooting import troubleshooting_store

    entry = troubleshooting_store.match(args.problem)
    if entry is None:
        return {
            "found": False,
            "problem": args.problem,
            "known_problems": [
                {"id": item["id"], "title": item["title"]} for item in troubleshooting_store.all()
            ],
        }
    return {"found": True, "entry": entry}


def _get_supported_features(args: NoArgs, ctx: Dict[str, Any]) -> Dict[str, Any]:
    from app.support.features import feature_registry

    return feature_registry.summary()


def _navigate_to_feature(args: NavigateArgs, ctx: Dict[str, Any]) -> Dict[str, Any]:
    target = (args.target or "").strip().lower()
    allowed = {item["id"]: item for item in ACTION_CATALOG}
    match = next((item for item in ACTION_CATALOG if item["id"] == target), None)
    if match is None:
        match = next((item for item in ACTION_CATALOG if item["target"] == target), None)
    if match is None or match["kind"] != "navigate":
        return {
            "allowed": False,
            "requested": args.target,
            "message": "That destination is not part of the navigation allowlist.",
            "allowed_targets": sorted(VALID_ACTION_TARGETS),
        }
    return {"allowed": True, "action": match, "available_actions": list(allowed.keys())}


def _submit_feedback(args: FeedbackArgs, ctx: Dict[str, Any]) -> Dict[str, Any]:
    from app.support.feedback import feedback_store

    if not args.confirmed:
        return {
            "accepted": False,
            "confirmation_required": True,
            "message": "Feedback is only stored when the user submits it from the panel controls.",
        }
    key = ctx.get("session_id") or "anonymous"
    if feedback_store.check_rate(key):
        return {"accepted": False, "rate_limited": True, "message": "Too many submissions; try again later."}
    try:
        return feedback_store.submit(
            args.rating,
            args.comment,
            args.message_id,
            ctx.get("session_id"),
            ctx.get("page"),
        )
    except ValueError as exc:
        return {"accepted": False, "error": str(exc)}


def _explain_rag_pipeline(args: NoArgs, ctx: Dict[str, Any]) -> Dict[str, Any]:
    from app.core.config import (
        CASE_LAW_COLLECTION,
        EMBEDDING_MODEL_NAME,
        LLM_PROVIDER,
        LOW_CONFIDENCE_THRESHOLD,
        RERANKER_VERSION,
        USE_RERANKER,
    )
    from app.support.knowledge_base import support_knowledge_base

    article = support_knowledge_base.get("rag-explained")
    return {
        "article": article.as_summary() if article else None,
        "verified_configuration": {
            "collection": CASE_LAW_COLLECTION,
            "embedding_model": EMBEDDING_MODEL_NAME,
            "reranker_enabled": USE_RERANKER,
            "reranker_version": RERANKER_VERSION,
            "low_confidence_threshold": LOW_CONFIDENCE_THRESHOLD,
            "llm_provider": LLM_PROVIDER,
        },
        "stage_order": [
            "query_analysis",
            "embedding",
            "vector_search",
            "optional_rerank",
            "grounded_generation",
            "citation_verification",
            "fallback_when_weak",
        ],
    }


def _explain_search_results(args: NoArgs, ctx: Dict[str, Any]) -> Dict[str, Any]:
    from app.support.knowledge_base import support_knowledge_base

    articles = [
        support_knowledge_base.get("interpreting-results"),
        support_knowledge_base.get("citations-and-sources"),
    ]
    return {
        "articles": [item.as_summary() for item in articles if item],
        "key_points": [
            "Similarity is a retrieval measurement between the query vector and the stored chunk — not a probability of correctness.",
            "One judgment contributes many chunks; comparison groups chunks by source document so chunks are not miscounted as precedents.",
            "A verified citation means the text exists in the corpus and was retrieved; it does not prove the passage supports the proposition.",
            "Below the configured threshold no answer is generated; the sources are returned with a low-confidence status instead.",
        ],
    }


TOOLS: Dict[str, ToolSpec] = {
    "search_support_docs": ToolSpec(
        id="search_support_docs",
        label="Search support documentation",
        description="Search the approved support articles and return matching articles with references.",
        args_model=SearchDocsArgs,
        handler=_search_support_docs,
        tags=["retrieval", "read_only"],
    ),
    "get_feature_help": ToolSpec(
        id="get_feature_help",
        label="Explain a verified feature",
        description="Return instructions for a feature that exists in the capability registry.",
        args_model=FeatureArgs,
        handler=_get_feature_help,
        tags=["retrieval", "read_only"],
    ),
    "get_demo_examples": ToolSpec(
        id="get_demo_examples",
        label="List approved demo examples",
        description="Return the approved demonstration prompts and their expected behaviour.",
        args_model=ExamplesArgs,
        handler=_get_demo_examples,
        tags=["demo", "read_only"],
    ),
    "get_system_status": ToolSpec(
        id="get_system_status",
        label="Read live system status",
        description="Run the real readiness checks and summarise them.",
        args_model=StatusArgs,
        handler=_get_system_status,
        tags=["status", "read_only"],
    ),
    "get_troubleshooting_steps": ToolSpec(
        id="get_troubleshooting_steps",
        label="Return troubleshooting steps",
        description="Return structured steps for a recognised problem.",
        args_model=TroubleshootArgs,
        handler=_get_troubleshooting_steps,
        tags=["troubleshooting", "read_only"],
    ),
    "get_supported_features": ToolSpec(
        id="get_supported_features",
        label="List implemented features",
        description="Return the capability registry, grouped by real implementation status.",
        args_model=NoArgs,
        handler=_get_supported_features,
        tags=["status", "read_only"],
    ),
    "navigate_to_feature": ToolSpec(
        id="navigate_to_feature",
        label="Offer an allowlisted navigation",
        description="Return an allowlisted workspace destination as a quick action.",
        args_model=NavigateArgs,
        handler=_navigate_to_feature,
        tags=["navigation", "allowlist"],
    ),
    "submit_feedback": ToolSpec(
        id="submit_feedback",
        label="Submit user feedback",
        description="Store helpful/not-helpful feedback after the user confirms it.",
        args_model=FeedbackArgs,
        handler=_submit_feedback,
        side_effects=True,
        requires_confirmation=True,
        tags=["write", "confirmation_required"],
    ),
    "explain_rag_pipeline": ToolSpec(
        id="explain_rag_pipeline",
        label="Explain the RAG pipeline",
        description="Explain the project's real retrieval-augmented generation flow and its verified configuration.",
        args_model=NoArgs,
        handler=_explain_rag_pipeline,
        tags=["explanation", "read_only"],
    ),
    "explain_search_results": ToolSpec(
        id="explain_search_results",
        label="Explain search results and citations",
        description="Explain what similarity, citations and metadata mean, without implying legal correctness.",
        args_model=NoArgs,
        handler=_explain_search_results,
        tags=["explanation", "read_only"],
    ),
}


def catalog() -> List[Dict[str, Any]]:
    """Public description of the registry (used by the docs and the API)."""
    return [
        {
            "id": spec.id,
            "label": spec.label,
            "description": spec.description,
            "arguments": sorted((spec.args_model.model_fields or {}).keys()),
            "side_effects": spec.side_effects,
            "requires_confirmation": spec.requires_confirmation,
            "tags": spec.tags,
        }
        for spec in TOOLS.values()
    ]


def execute(name: str, raw_args: Optional[Dict[str, Any]], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and run one tool.

    Returns a uniform result envelope. Failures are reported, never raised, so a
    broken tool degrades the answer instead of failing the request.
    """
    started = time.time()
    spec = TOOLS.get(name or "")
    if spec is None:
        logger.warning("[support] rejected unknown tool: %s", name)
        return {
            "name": name or "",
            "ok": False,
            "error": "Unknown tool. Only allowlisted tools can run.",
            "duration_ms": 0,
        }

    try:
        args = spec.args_model.model_validate(raw_args or {})
    except ValidationError as exc:
        logger.info("[support] invalid tool arguments tool=%s", spec.id)
        return {
            "name": spec.id,
            "ok": False,
            "error": "Invalid arguments for this tool.",
            "details": [
                {"field": ".".join(str(part) for part in error.get("loc", ())), "message": error.get("msg")}
                for error in exc.errors()[:5]
            ],
            "duration_ms": round((time.time() - started) * 1000),
        }

    try:
        result = spec.handler(args, ctx or {})
        ok = True
        error = None
    except Exception as exc:  # noqa: BLE001 - a failing tool must not fail the request
        logger.error("[support] tool failed tool=%s type=%s", spec.id, type(exc).__name__)
        result = None
        ok = False
        error = "That check could not be completed right now."

    duration = round((time.time() - started) * 1000)
    logger.info("[support] tool tool=%s ok=%s duration_ms=%s", spec.id, ok, duration)
    return {
        "name": spec.id,
        "ok": ok,
        "result": result,
        "error": error,
        "duration_ms": duration,
    }
