"""
Capability registry.

``backend/support/features.json`` is the single maintained list of what actually
works in this project. It is the only source the support assistant uses to answer
"which features are implemented?", so a feature can never be advertised by
accident: if it is not in the registry, the assistant says it does not know
rather than inventing it.

Status labels (also stored in the file so they travel with the data):
``implemented`` · ``partial`` · ``experimental`` · ``planned`` · ``not_available``
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import BACKEND_ROOT

logger = logging.getLogger("vidhiveda.support")

FEATURES_PATH = BACKEND_ROOT / "support" / "features.json"

STATUS_ORDER = ["implemented", "partial", "experimental", "planned", "not_available"]


class FeatureRegistry:
    def __init__(self, path: Path = FEATURES_PATH) -> None:
        self.path = path
        self._data: Optional[Dict[str, Any]] = None

    def _load(self) -> Dict[str, Any]:
        if self._data is not None:
            return self._data
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.error("[support] capability registry missing: %s", self.path)
            self._data = {"features": [], "status_legend": {}, "available": False}
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("[support] capability registry unreadable: %s", exc)
            self._data = {"features": [], "status_legend": {}, "available": False}
        return self._data

    def available(self) -> bool:
        return bool(self._load().get("features"))

    def legend(self) -> Dict[str, str]:
        return dict(self._load().get("status_legend") or {})

    def all(self) -> List[Dict[str, Any]]:
        return list(self._load().get("features") or [])

    def get(self, feature_id: str) -> Optional[Dict[str, Any]]:
        target = (feature_id or "").strip().lower()
        for feature in self.all():
            if str(feature.get("id", "")).lower() == target:
                return feature
        return None

    def by_status(self) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {status: [] for status in STATUS_ORDER}
        for feature in self.all():
            status = str(feature.get("status") or "not_available")
            grouped.setdefault(status, []).append(feature)
        return {status: items for status, items in grouped.items() if items}

    def live_overrides(self) -> Dict[str, Dict[str, Any]]:
        """
        Status that can only be known at runtime.

        ``prediction`` is the one entry whose real state depends on whether a
        trained model artifact exists on this machine: the artifact is not
        committed, so a clean checkout reports the capability as unavailable,
        while a working tree that has trained a model reports an experimental
        classifier with its recorded metrics. The registry's static entry says
        what the capability is; this override says what it currently is, and the
        assistant quotes the override when it exists.
        """
        try:
            from app.ml.outcome_model import outcome_model_service

            status = outcome_model_service.status()
        except Exception as exc:  # pragma: no cover - defensive
            return {
                "prediction": {
                    "status": "not_available",
                    "live": True,
                    "summary": f"The outcome-model loader could not be inspected ({type(exc).__name__}).",
                }
            }

        if not status.get("available"):
            return {
                "prediction": {
                    "status": "not_available",
                    "live": True,
                    "reason": status.get("reason"),
                    "summary": (
                        "No trained outcome model is present, so no prediction is produced. "
                        "The API reports available: false with the reason rather than inventing a classifier."
                    ),
                }
            }

        metrics = status.get("metrics") or {}
        return {
            "prediction": {
                "status": "experimental",
                "live": True,
                "version": status.get("version"),
                "calibration": status.get("calibration"),
                "trained_at": status.get("trained_at"),
                "classes": status.get("classes"),
                "recorded_metrics": {
                    "test_accuracy": metrics.get("accuracy"),
                    "weighted_f1": metrics.get("weighted_f1"),
                    "macro_f1": metrics.get("macro_f1"),
                    "test_size": metrics.get("test_size"),
                    "class_distribution_test": metrics.get("class_distribution_test"),
                },
                "summary": (
                    "An experimental supervised classifier is loaded and returns a calibrated "
                    "probability with a low-confidence flag. It is a statistical estimate from "
                    "case facts, not a verdict, and its held-out test partition is very small — "
                    "so it is reported as experimental, never as validated."
                ),
            }
        }

    def summary(self, live: bool = True) -> Dict[str, Any]:
        grouped = self.by_status()
        features = [dict(item) for item in self.all()]
        overrides = self.live_overrides() if live else {}
        if overrides:
            for feature in features:
                override = overrides.get(str(feature.get("id")))
                if override:
                    feature["static_status"] = feature.get("status")
                    feature.update(override)

        counts: Dict[str, int] = {}
        for feature in features:
            status = str(feature.get("status") or "not_available")
            counts[status] = counts.get(status, 0) + 1

        return {
            "available": self.available(),
            "counts": {status: counts[status] for status in STATUS_ORDER if status in counts},
            "features": features,
            "legend": self.legend(),
            "updated": self._load().get("updated"),
            "live_status_included": bool(overrides),
        }


feature_registry = FeatureRegistry()
