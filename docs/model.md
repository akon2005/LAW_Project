# VIDHIVEDA — Outcome Prediction Model

The outcome model is a **separate supervised classifier**. It is not the LLM,
and its confidence is never derived from retrieval similarity.

## 1. Labels

`app/ml/label_normalizer.py` maps raw disposition text onto an explicit set of
classes using a configurable table:

```
allowed · dismissed · partly_allowed · convicted · acquitted · disposed
```

Phrasings are matched longest-first, so `appeal partly allowed` maps to
`partly_allowed`, not `allowed`. A label that cannot be mapped returns
`unmapped` and is **excluded from training** — it is never coerced into a nearby
class. Override the table with `OUTCOME_LABEL_MAP` (JSON `{class: [synonyms]}`).

## 2. Leakage prevention

Training never uses information that only became available after the judgment.
The features must come from **pre-judgment inputs** (case facts, sections, case
metadata). Training on judgment text is refused, because the verdict is inside
it. The training script therefore requires a dataset that declares a
`feature_field` distinct from the judgment text.

## 3. Split

A temporal split is used, not a random one:

```
older cases → train · later cases → validation · latest cases → test
```

The exact year boundaries depend on the date range the dataset actually covers.

## 4. Baseline and calibration

- Features: sentence embeddings (default `all-MiniLM-L6-v2`).
- Model: `LogisticRegression` with `class_weight="balanced"`.
- Calibration: sigmoid `CalibratedClassifierCV` when each class has enough
  samples; otherwise the raw logistic probabilities are returned and labelled
  `uncalibrated_logistic`.

## 5. Metrics (recorded, never invented)

`accuracy`, `macro precision/recall/F1`, `weighted F1`, per-class performance
and the confusion matrix, computed on the held-out test partition.

## 6. Honest unavailability (current status)

This repository has **no outcome model trained**. The active corpus
(`dedol-hf/india-case-legal-rag`) exposes **no outcome/label field**, and its
text is judgment text (which would leak the verdict into the features).
Therefore:

- `GET /api/model/status` → `outcome_model.available = false`;
- `POST /api/predict` → `available = false` with a reason;
- `POST /api/research` → `prediction.available = false` with a reason;
- the UI states *"Prediction unavailable"*.

No fake classifier is created to make the interface look complete.

## 7. Training (when a suitable labeled dataset exists)

```bash
cd backend
python scripts/train_outcome_model.py --dataset <key>
python scripts/train_outcome_model.py --status
```

The script refuses and explains exactly why when labels or a pre-judgment
feature field are missing. When it succeeds it writes `model.joblib` and
`metadata.json` (version, classes, embedding model, calibration, metrics) to
`OUTCOME_MODEL_DIR`.
