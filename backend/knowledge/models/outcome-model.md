---
type: Model
title: Outcome prediction model
description: Experimental case-outcome classifier. Trained on 102 curated pre-judgment
  records; held-out accuracy 0.9375 against a macro F1 of 0.4839.
tags:
- ml
- outcome-prediction
- experimental
status: draft
generated:
  by: process:vidhiveda-okf-builder/1.0
  at: '2026-10-02T17:22:27Z'
verified:
- by: process:vidhiveda-okf-validator/1.0
  at: '2026-10-02T17:22:27Z'
sources:
- id: training-data
  resource: data/dataset/cases.json
  title: Curated pre-judgment case records (facts + normalized outcome)
available: true
version: outcome-sigmoid_calibrated
---
# Status

**Available and experimental.** The classifier is committed at `data/models/outcome/` and served; `GET /api/model/status` reports its version, calibration and recorded metrics.

# Training data

Trained from 102 records of `data/dataset/cases.json` (80 convictions, 22 acquittals), using pre-judgment `facts` as the only features; 50 further records are excluded as unmapped. The retrieval corpus is not used for training: its text is judgment text, so it would leak the verdict into the features.

# Metrics

Held-out: accuracy 0.9375, macro F1 0.4839, on 16 test records of which 15 are convictions. Read both numbers together — the accuracy is carried by the majority class.

# Boundary

Retrieval relevance and prediction confidence are separate quantities. This project never derives a prediction from retrieval similarity.
