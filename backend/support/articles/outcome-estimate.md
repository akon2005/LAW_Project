---
id: outcome-estimate
title: Outcome estimates and prediction status
category: features
tags: [prediction, outcome, estimate, model, probability, verdict, win, prediction model, classifier]
intents: [feature_explanation, legal_research_guidance, supported_feature_query]
features: [prediction]
priority: 1
updated: 2026-10-27
---

## Check the live status first

The classifier is committed at `backend/data/models/outcome/`, so a clean
checkout and a deployed image both ship it. The live answer is still
`GET /api/model/status` (and the support assistant's system-status check), because
the model directory is configurable and that is the only way this feature can be
absent.

## Status A — no artifact on the serving machine

Only when the model directory is missing or `OUTCOME_MODEL_DIR` points elsewhere
does the API report:

```json
{ "available": false, "label": null, "confidence": null, "reason": "..." }
```

The Research answer panel shows "Prediction unavailable" with that reason, and
the Compare tab reports `PREDICTION_NOT_AVAILABLE`. Nothing is invented.

## Status B — the shipped classifier is loaded (the normal case)

The API reports `available: true` and a calibrated probability, flagged
`low_confidence` below the configured threshold. What that means, precisely:

* It is a **supervised classifier**, not the language model: it is trained on
  the curated dataset (`backend/data/dataset/cases.json`) using
  **pre-judgment features only** (case facts and sections). The judgment text and
  the outcome field are excluded from the features to prevent verdict leakage.
* The split is temporal (older cases train, later ones validate, latest ones
  test) — not a random split.
* Calibration is sigmoid (Platt scaling), so the number is a calibrated
  probability rather than a raw score.
* The recorded held-out metrics live in `data/models/outcome/metadata.json`. They
  are recorded, never invented — and they are the reason the capability is
  labelled **experimental**: the held-out test partition is very small (single
  digits to low tens of records, with only one acquittal case in the current
  test partition), so accuracy and macro-averaged scores are unstable.

```bash
cd backend
python scripts/train_outcome_model.py --status
```

## What a prediction still is not

* It is not a verdict, and it is not legal advice: it is a statistical estimate
  from the facts you supplied.
* The LLM never produces the prediction. If a generated paragraph mentions an
  outcome, that prose is an explanation — it is not the classifier's output.
* The artifact **is** committed to the repository, so if you do not see it
  reported, the serving environment is looking at a different model directory.

VIDHIVEDA supports legal research and decision support. It does not make judicial
decisions, and an experimental classifier is never presented as validated.
