"""
Outcome prediction model (Steps 16-21).

This is a *separate* supervised model. It is deliberately NOT the LLM and NOT
derived from retrieval similarity: dense similarity says "this evidence is
topically close", not "the court will decide X". Prediction confidence is a
calibrated class probability.

Honesty rules enforced here:
  * If no model has been trained, ``available`` is ``False`` and the API says so
    instead of fabricating a prediction (Step 49).
  * Below ``MIN_PREDICTION_CONFIDENCE`` the result is returned with
    ``low_confidence=True`` — it is not hidden, and it is not presented as
    certain.
  * Features must come from information available *before* the judgment
    (Step 17); this module never reads the verdict to build its own features.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from app.core.config import (
    EMBEDDING_MODEL_NAME,
    MIN_PREDICTION_CONFIDENCE,
    OUTCOME_MODEL_DIR,
    OUTCOME_MODEL_VERSION,
)

logger = logging.getLogger(__name__)

MODEL_FILENAME = "model.joblib"
METADATA_FILENAME = "metadata.json"

UNAVAILABLE_REASON = (
    "Outcome prediction model is not currently available because a reliable "
    "labeled training set was not identified."
)


class OutcomeModelError(RuntimeError):
    """Raised when a model file exists but cannot be loaded or used."""


@dataclass
class OutcomeModel:
    """A fitted classifier plus the metadata needed for reproducibility."""

    estimator: Any
    classes: List[str]
    embedding_model: str = EMBEDDING_MODEL_NAME
    embedding_dimension: Optional[int] = None
    version: str = OUTCOME_MODEL_VERSION
    calibration: str = "uncalibrated_logistic"
    trained_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metrics: Dict[str, Any] = field(default_factory=dict)
    n_train: int = 0

    # ── Inference ──────────────────────────────────────────────────────
    def predict_proba(self, vectors: np.ndarray) -> np.ndarray:
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        try:
            return self.estimator.predict_proba(matrix)
        except Exception as exc:  # pragma: no cover - defensive
            raise OutcomeModelError(f"Outcome model inference failed: {exc}") from exc

    def predict(self, vectors: np.ndarray) -> List[Dict[str, Any]]:
        probabilities = self.predict_proba(vectors)
        results: List[Dict[str, Any]] = []
        for row in probabilities:
            best = int(np.argmax(row))
            confidence = float(row[best])
            results.append(
                {
                    "prediction": self.classes[best],
                    "confidence": round(confidence, 4),
                    "probabilities": {
                        self.classes[i]: round(float(p), 4) for i, p in enumerate(row)
                    },
                    "low_confidence": confidence < MIN_PREDICTION_CONFIDENCE,
                }
            )
        return results

    # ── Persistence ────────────────────────────────────────────────────
    def save(self, directory: Optional[Path] = None) -> Path:
        import joblib

        target = Path(directory or OUTCOME_MODEL_DIR)
        target.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.estimator, target / MODEL_FILENAME)
        metadata = {
            "version": self.version,
            "classes": self.classes,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "calibration": self.calibration,
            "trained_at": self.trained_at,
            "metrics": self.metrics,
            "n_train": self.n_train,
            "prompt_version": None,
        }
        (target / METADATA_FILENAME).write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("[outcome] Saved model v%s to %s", self.version, target)
        return target

    @classmethod
    def load(cls, directory: Optional[Path] = None) -> Optional["OutcomeModel"]:
        import joblib

        target = Path(directory or OUTCOME_MODEL_DIR)
        model_path = target / MODEL_FILENAME
        meta_path = target / METADATA_FILENAME
        if not model_path.exists() or not meta_path.exists():
            return None
        try:
            estimator = joblib.load(model_path)
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise OutcomeModelError(f"Could not load outcome model: {exc}") from exc

        return cls(
            estimator=estimator,
            classes=list(metadata.get("classes") or []),
            embedding_model=metadata.get("embedding_model") or EMBEDDING_MODEL_NAME,
            embedding_dimension=metadata.get("embedding_dimension"),
            version=metadata.get("version") or OUTCOME_MODEL_VERSION,
            calibration=metadata.get("calibration") or "uncalibrated_logistic",
            trained_at=metadata.get("trained_at") or "",
            metrics=metadata.get("metrics") or {},
            n_train=int(metadata.get("n_train") or 0),
        )


class OutcomeModelService:
    """Lazily loads the trained model (if any) and serves predictions."""

    def __init__(self, model_dir: Optional[Path] = None) -> None:
        self.model_dir = Path(model_dir or OUTCOME_MODEL_DIR)
        self._model: Optional[OutcomeModel] = None
        self._loaded = False

    def _resolve(self) -> Optional[OutcomeModel]:
        if not self._loaded:
            self._model = OutcomeModel.load(self.model_dir)
            self._loaded = True
        return self._model

    def reload(self) -> Optional[OutcomeModel]:
        self._loaded = False
        return self._resolve()

    @property
    def is_available(self) -> bool:
        return self._resolve() is not None

    def status(self) -> Dict[str, Any]:
        model = self._resolve()
        if model is None:
            return {
                "available": False,
                "reason": UNAVAILABLE_REASON,
                "model_dir": str(self.model_dir),
                "calibration": None,
                "classes": [],
                "version": None,
                "trained_at": None,
                "metrics": {},
            }
        return {
            "available": True,
            "reason": None,
            "model_dir": str(self.model_dir),
            "version": model.version,
            "calibration": model.calibration,
            "classes": model.classes,
            "embedding_model": model.embedding_model,
            "embedding_dimension": model.embedding_dimension,
            "trained_at": model.trained_at,
            "n_train": model.n_train,
            "metrics": model.metrics,
            "min_prediction_confidence": MIN_PREDICTION_CONFIDENCE,
        }

    def predict_from_vectors(self, vectors: np.ndarray) -> Dict[str, Any]:
        """Predict from pre-computed embeddings (no text leakage possible)."""
        model = self._resolve()
        if model is None:
            return {
                "available": False,
                "label": None,
                "confidence": None,
                "low_confidence": False,
                "probabilities": {},
                "model_version": None,
                "reason": UNAVAILABLE_REASON,
            }
        result = model.predict(vectors)[0]
        return {
            "available": True,
            "label": result["prediction"],
            "confidence": result["confidence"],
            "low_confidence": result["low_confidence"],
            "probabilities": result["probabilities"],
            "model_version": model.version,
            "calibration": model.calibration,
            "reason": None,
        }

    def predict_from_texts(self, texts: List[str]) -> Dict[str, Any]:
        """
        Embed case-fact text and predict. The caller is responsible for passing
        only pre-judgment facts (Step 17) — never the verdict text.
        """
        model = self._resolve()
        if model is None:
            return self.predict_from_vectors(np.zeros((1, 1)))
        from app.rag.embedding_service import embedding_service

        vectors = np.asarray(
            embedding_service.generate_embeddings(texts), dtype=np.float32
        )
        return self.predict_from_vectors(vectors)


outcome_model_service = OutcomeModelService()


def fit_classifier(
    vectors: np.ndarray,
    labels: List[str],
    calibrate: bool = True,
) -> tuple:
    """
    Fit a logistic-regression baseline over sentence embeddings (Step 19).

    Returns ``(estimator, calibration_name)``. Calibration uses a sigmoid
    ``CalibratedClassifierCV`` when each class has enough samples; otherwise the
    raw (uncalibrated) logistic probabilities are returned and clearly labelled.
    """
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.linear_model import LogisticRegression

    matrix = np.asarray(vectors, dtype=np.float32)
    base = LogisticRegression(max_iter=2000, class_weight="balanced")

    counts: Dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    min_count = min(counts.values()) if counts else 0

    if calibrate and len(counts) >= 2 and min_count >= 5:
        folds = max(2, min(5, min_count))
        estimator = CalibratedClassifierCV(base, method="sigmoid", cv=folds)
        return estimator.fit(matrix, labels), "sigmoid_calibrated"
    return base.fit(matrix, labels), "uncalibrated_logistic"
