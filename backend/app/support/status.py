"""
Support subsystem readiness.

Rule: nothing is reported as healthy just because the process answered. Each
component is checked separately and the overall status is derived from the real
results:

* ``api``            — trivially up: this module is answering inside the process.
* ``knowledge_base`` — the support articles actually loaded.
* ``examples`` / ``capability_registry`` / ``troubleshooting`` — data files parsed.
* ``llm``            — whether a provider key is *configured*; whether it is
  *reachable* is only ever claimed after a real probe (``probe=true``), never
  inferred.
* ``vector_store``   — the ChromaDB collection the research feature uses.
* ``prediction``     — the outcome-model status read from the loaded model, so an
  untrained checkout reports the abstention and a trained one reports its
  classes and metrics.

The overall status is ``ok`` only when the support path a user needs is ready.
Missing optional pieces (an unconfigured LLM, an unreachable vector store) are
reported as ``degraded`` with a named reason instead of being hidden.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

logger = logging.getLogger("vidhiveda.support")

PROBE_TIMEOUT_SECONDS = 12.0


def _knowledge_base_component() -> Dict[str, Any]:
    from app.support.knowledge_base import support_knowledge_base

    stats = support_knowledge_base.stats()
    if not stats.get("available"):
        return {
            "status": "unavailable",
            "detail": "No support articles could be loaded.",
            "directory": stats.get("directory"),
        }
    return {
        "status": "ready",
        "articles": stats["articles"],
        "categories": len(stats.get("categories") or []),
    }


def _json_data_component(path_name: str, path) -> Dict[str, Any]:
    import json

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"status": "unavailable", "detail": f"{path_name} file not found", "path": str(path)}
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "detail": f"{path_name} unreadable: {exc}", "path": str(path)}
    return {"status": "ready", "path": str(path), "keys": sorted(data.keys())[:8]}


def _llm_component(probe: bool) -> Dict[str, Any]:
    from app.core.config import LLM_PROVIDER
    from app.rag.rag_service import get_llm_client

    components: Dict[str, Any] = {
        "configured": False,
        "provider": LLM_PROVIDER,
        "reachable": None,
        "checked": False,
    }
    try:
        client, model_name, provider = get_llm_client()
    except Exception as exc:  # pragma: no cover - defensive
        components["detail"] = f"provider resolution failed: {exc}"
        return components

    if client is None:
        components["detail"] = (
            "No usable provider key is configured, so answers come from the support "
            "documentation and retrieval templates instead of generated prose."
        )
        return components

    components["configured"] = True
    components["provider"] = provider or LLM_PROVIDER
    components["model"] = model_name

    if not probe:
        components["detail"] = (
            "Provider configured. Reachability was not probed; pass ?probe=true to "
            "attempt a real connectivity check."
        )
        return components

    components["checked"] = True
    started = time.time()
    try:
        if provider == "anthropic":
            client.messages.create(
                model=model_name,
                max_tokens=8,
                messages=[{"role": "user", "content": "ping"}],
            )
        else:
            client.chat.completions.create(
                model=model_name,
                max_tokens=8,
                messages=[{"role": "user", "content": "ping"}],
            )
        components["reachable"] = True
        components["latency_ms"] = round((time.time() - started) * 1000)
    except Exception as exc:
        components["reachable"] = False
        components["detail"] = f"Provider probe failed: {type(exc).__name__}"
    return components


def _vector_store_component() -> Dict[str, Any]:
    try:
        from app.core.config import CASE_LAW_COLLECTION
        from app.db.vector_store import legal_cases_store
    except Exception as exc:  # pragma: no cover - import failure
        return {"status": "unavailable", "detail": f"vector store import failed: {type(exc).__name__}"}

    try:
        count = int(legal_cases_store.get_count())
    except Exception as exc:
        return {"status": "unavailable", "collection": CASE_LAW_COLLECTION, "detail": type(exc).__name__}

    return {
        "status": "connected" if count else "empty",
        "collection": CASE_LAW_COLLECTION,
        "chunks": count,
    }


def _prediction_component() -> Dict[str, Any]:
    try:
        from app.ml.outcome_model import outcome_model_service

        status = outcome_model_service.status()
    except Exception as exc:  # pragma: no cover - defensive
        return {"status": "unknown", "available": None, "detail": type(exc).__name__}

    if not status.get("available"):
        return {
            "status": "not_available",
            "available": False,
            "reason": status.get("reason"),
            "detail": "No trained model artifact is present; no prediction is produced.",
        }

    metrics = status.get("metrics") or {}
    return {
        "status": "experimental",
        "available": True,
        "version": status.get("version"),
        "calibration": status.get("calibration"),
        "trained_at": status.get("trained_at"),
        "recorded_metrics": {
            "test_accuracy": metrics.get("accuracy"),
            "macro_f1": metrics.get("macro_f1"),
            "test_size": metrics.get("test_size"),
        },
        "detail": (
            "An experimental classifier is loaded: a statistical estimate from case facts, "
            "not a verdict, with a very small held-out test partition."
        ),
    }


def support_health(probe_llm: bool = False) -> Dict[str, Any]:
    """Build the readiness payload for ``GET /api/support/health``."""
    from app.support.examples import examples_store
    from app.support.features import FEATURES_PATH, feature_registry
    from app.support.knowledge_base import support_knowledge_base
    from app.support.troubleshooting import TROUBLESHOOTING_PATH, troubleshooting_store

    components: Dict[str, Any] = {
        "api": {"status": "up", "pid_alive": True},
        "knowledge_base": _knowledge_base_component(),
        "capability_registry": _json_data_component("capability registry", FEATURES_PATH),
        "examples": _json_data_component("examples", examples_store.path),
        "troubleshooting": _json_data_component("troubleshooting", TROUBLESHOOTING_PATH),
        "llm": _llm_component(probe_llm),
        "vector_store": _vector_store_component(),
        "prediction": _prediction_component(),
    }

    degraded_reasons: List[str] = []
    if components["knowledge_base"].get("status") != "ready":
        degraded_reasons.append("support knowledge base unavailable")
    if components["capability_registry"].get("status") != "ready":
        degraded_reasons.append("capability registry unavailable")
    if components["examples"].get("status") != "ready":
        degraded_reasons.append("example gallery unavailable")
    if components["troubleshooting"].get("status") != "ready":
        degraded_reasons.append("troubleshooting data unavailable")
    if not components["llm"].get("configured"):
        degraded_reasons.append("LLM provider not configured (answers use documentation only)")
    if components["llm"].get("reachable") is False:
        degraded_reasons.append("LLM provider probe failed")
    if components["vector_store"].get("status") != "connected":
        degraded_reasons.append(f"vector store {components['vector_store'].get('status')}")

    core_ready = components["knowledge_base"].get("status") == "ready"

    return {
        "status": "ok" if core_ready and not degraded_reasons else ("degraded" if core_ready else "unavailable"),
        "service": "vidhiveda-support",
        "checked_at": time.time(),
        "components": components,
        "degraded_reasons": degraded_reasons,
        "notes": [
            "The research corpus, the support knowledge base and the OKF bundle are separate stores and never blended.",
            "An unconfigured LLM is reported as degraded, not as healthy: generated summaries are unavailable, documentation answers still work.",
            "Reachability is only asserted after a real probe (?probe=true).",
        ],
    }
