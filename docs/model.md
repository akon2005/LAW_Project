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

## 6. Trained Model Status & Evaluation (Current Version)

The supervised outcome model is **trained, evaluated, and active** in the repository.

### 6.1 Training Corpus Provenance & Leakage Prevention
- **Corpus**: `backend/data/dataset/cases.json` (152 curated Indian case judgments).
- **Features Used**: Strictly pre-judgment case facts (`facts` field: dispute background, charge details, police recoveries, witness allegations). The `reasoning_excerpt` and `outcome` fields are excluded from feature vectors to prevent verdict leakage.
- **Labels**: Normalized via `app/ml/label_normalizer.py`:
  - `conviction` → `convicted` (53 train / 15 test)
  - `acquittal` → `acquitted` (18 train / 1 test)
  - `Unknown` → `unmapped` (50 unmapped records safely excluded)
- **Temporal Split**: Chronological ordering by year (2017–2021):
  - Train partition (70%): 71 records
  - Validation partition (15%): 15 records
  - Held-out test partition (15%): 16 records

### 6.2 Held-Out Evaluation Metrics
Recorded honestly in `data/models/outcome/metadata.json`:
- **Model Version**: `outcome-sigmoid_calibrated`
- **Calibration**: `CalibratedClassifierCV` (sigmoid Platt scaling)
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (dimension: 384)
- **Held-Out Test Accuracy**: `93.75%`
- **Validation Accuracy**: `86.67%`
- **Weighted F1 Score**: `0.9073`
- **Macro F1 Score**: `0.4839`

### 6.3 Active Endpoints
- `GET /api/model/status` → reports `available: true`, version, calibration, and test metrics
- `POST /api/predict` → returns calibrated class probabilities and low-confidence flags
- `POST /api/comparison` → delivers per-scenario calibrated outcome estimates with visual probability bars

## 7. Retraining and Status Verification

```bash
cd backend
python scripts/train_outcome_model.py          # Trains on curated pre-judgment cases
python scripts/train_outcome_model.py --status # Displays current model metadata & metrics
```

When run against an unverified dataset lacking pre-judgment features or explicit outcome labels (e.g. `--dataset india-case-legal-rag`), the training script continues to honestly refuse and explains the missing fields.
