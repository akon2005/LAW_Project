#!/usr/bin/env python
"""
VIDHIVEDA outcome-model training (Steps 16-20, 49).

    python scripts/train_outcome_model.py
    python scripts/train_outcome_model.py --dataset indian-supreme-court-judgments
    python scripts/train_outcome_model.py --status

This script REFUSES to train when the preconditions for an honest model are not
met, and says exactly why:

  * the dataset exposes no outcome/label field; or
  * the dataset exposes no *pre-judgment* feature field (training on the
    judgment text would leak the verdict into the features — Step 17).

No fake classifier is ever produced to make the UI look complete.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml.label_normalizer import OutcomeLabelNormalizer  # noqa: E402
from app.ml.outcome_model import OutcomeModel, fit_classifier, outcome_model_service  # noqa: E402
from app.services.dataset_service import PRIMARY_DATASET, get_dataset_config  # noqa: E402
from app.services.schema_service import (  # noqa: E402
    dot_get,
    iter_dataset,
    resolve_field_mapping,
    sample_records,
)


def _prepare(
    dataset_key: str, limit: Optional[int]
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Return ``(records, None)`` or ``(None, reason)`` when training is unsafe."""
    config = get_dataset_config(dataset_key)

    # Fast, offline-safe refusal: if the registry declares no outcome field and
    # no OUTCOME_FIELD override is configured, there is nothing to train on —
    # no need to stream (and potentially hang on) the dataset.
    if not (config.get("fields") or {}).get("outcome"):
        from app.core.config import OUTCOME_FIELD

        if not OUTCOME_FIELD:
            return None, (
                "no outcome/label field was detected in the dataset schema, so a "
                "reliable labeled training set could not be identified"
            )

    try:
        sample = sample_records(dataset_key, count=10)
    except Exception as exc:
        return None, f"could not sample the dataset: {exc}"

    mapping = resolve_field_mapping(dataset_key, sample_records=sample)
    outcome_field = mapping.get("outcome")
    if not outcome_field:
        return None, (
            "no outcome/label field was detected in the dataset schema, so a "
            "reliable labeled training set could not be identified"
        )

    feature_field = config.get("feature_field")
    if not feature_field:
        return None, (
            "the dataset declares no pre-judgment feature field; training on the "
            "judgment text would leak the verdict into the features (Step 17)"
        )

    normalizer = OutcomeLabelNormalizer()
    records: List[Dict[str, Any]] = []
    for raw in iter_dataset(dataset_key, limit=limit):
        facts = dot_get(raw, feature_field)
        raw_label = dot_get(raw, outcome_field)
        if not facts or not raw_label:
            continue
        label = normalizer.normalize(str(raw_label))
        if label == "unmapped":
            continue
        year = dot_get(raw, mapping.get("year") or "year")
        records.append({"facts": str(facts), "label": label, "year": year})

    if not records:
        return None, "no records with both a usable pre-judgment feature and a mapped outcome label"
    return records, None


def _temporal_split(records: List[Dict[str, Any]]) -> Tuple[list, list, list]:
    """Chronological split (older → train, later → validation, latest → test)."""
    dated = [r for r in records if isinstance(r.get("year"), int)]
    undated = [r for r in records if not isinstance(r.get("year"), int)]
    dated.sort(key=lambda r: r["year"])
    n = len(dated)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)
    train = dated[:train_end] + undated
    val = dated[train_end:val_end]
    test = dated[val_end:]
    return train, val, test


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the VIDHIVEDA outcome model.")
    parser.add_argument("--dataset", default=PRIMARY_DATASET)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.status:
        print(json.dumps(outcome_model_service.status(), indent=2))
        return 0

    print("VIDHIVEDA — Outcome Model Training")
    print("-" * 40)

    records, reason = _prepare(args.dataset, args.limit)
    if records is None:
        print("NOT TRAINED.")
        print(
            "Outcome prediction model is not currently available because a "
            "reliable labeled training set was not identified."
        )
        print(f"Reason: {reason}.")
        return 0

    train, val, test = _temporal_split(records)
    if not train or not test:
        print("NOT TRAINED: the temporal split produced an empty train or test partition.")
        return 0

    print(f"Usable labeled records: {len(records)}")
    print(f"Temporal split — train: {len(train)}, validation: {len(val)}, test: {len(test)}")

    from app.rag.embedding_service import embedding_service

    def embed(rows: list) -> np.ndarray:
        return np.asarray(
            embedding_service.generate_embeddings([r["facts"] for r in rows]), dtype=np.float32
        )

    x_train = embed(train)
    x_test = embed(test)
    y_train = [r["label"] for r in train]
    y_test = [r["label"] for r in test]

    estimator, calibration = fit_classifier(x_train, y_train)

    # Honest evaluation on held-out data (Steps 19, 20).
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
    )

    predictions = estimator.predict(x_test)
    metrics = {
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "macro_precision": round(float(precision_score(y_test, predictions, average="macro", zero_division=0)), 4),
        "macro_recall": round(float(recall_score(y_test, predictions, average="macro", zero_division=0)), 4),
        "macro_f1": round(float(f1_score(y_test, predictions, average="macro", zero_division=0)), 4),
        "weighted_f1": round(float(f1_score(y_test, predictions, average="weighted", zero_division=0)), 4),
        "confusion_matrix": confusion_matrix(y_test, predictions).tolist(),
        "classes": sorted(set(y_train) | set(y_test)),
        "test_size": len(test),
        "train_size": len(train),
    }

    model = OutcomeModel(
        estimator=estimator,
        classes=list(getattr(estimator, "classes_", sorted(set(y_train)))),
        calibration=calibration,
        metrics=metrics,
        n_train=len(train),
        version=f"outcome-{calibration}",
    )
    target = model.save()
    print(f"Saved model to {target}")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
