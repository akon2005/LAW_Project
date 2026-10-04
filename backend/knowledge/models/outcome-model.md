---
type: Model
title: Outcome prediction model
description: Experimental case-outcome classifier. Currently unavailable because no
  reliable labelled training set was identified.
tags:
- ml
- outcome-prediction
- unavailable
status: draft
generated:
  by: process:vidhiveda-okf-builder/1.0
  at: '2026-10-02T17:22:27Z'
verified:
- by: process:vidhiveda-okf-validator/1.0
  at: '2026-10-02T17:22:27Z'
sources:
- id: dataset
  resource: https://huggingface.co/datasets/dedol-hf/india-case-legal-rag
  title: dedol-hf/india-case-legal-rag
available: false
reason: The active corpus carries no outcome/label field, and its text is judgment
  text, so training an outcome model on it would leak the verdict into the features.
version: untrained
---
# Status

**Unavailable.** No outcome model is trained or served.

# Why

The active corpus has no outcome label, and the judgment text contains the verdict itself, so it cannot be used as a feature without leakage. The system reports `prediction.available = false` with a reason instead of inventing a classifier.

# Boundary

Retrieval relevance and prediction confidence are separate quantities. This project never derives a prediction from retrieval similarity.
