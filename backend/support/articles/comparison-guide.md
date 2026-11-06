---
id: comparison-guide
title: Comparing two opposing legal arguments
category: how-to
tags: [compare, comparison, opposing, arguments, two scenarios, both sides, dispute, compare arguments]
intents: [how_to, legal_research_guidance, feature_explanation]
features: [comparison]
updated: 2026-10-16
---

## What the Compare tab does

It compares two competing accounts of the *same* dispute against the retrieved
corpus. It is evidence-based argument analysis, not a "who is right" classifier.

## Step by step

1. Open the **Compare** tab.
2. Fill in the legal issue (required), the case facts, and any provisions.
3. Write each side's position in the two scenario boxes — a label and the
   position text. One scenario alone is also allowed and produces a
   single-scenario analysis.
4. Submit. The response has one half per scenario.

## What each half contains

* **Supporting precedents** — retrieved chunks whose text is topically closest to
  that account, with a required margin; otherwise the judgment is reported as
  neutral.
* **Contrary precedents** — the same judgments seen from the other side.
* **Strengths, weaknesses and missing evidence** — derived only from what was
  retrieved and what was not.

An **evidence quality** status is reported:
`SUFFICIENT_EVIDENCE_FOR_ANALYSIS`, `LIMITED_EVIDENCE` or
`INSUFFICIENT_EVIDENCE`. When evidence is insufficient the system abstains and
explains what extra facts or sources would help.

## Honest limits

* Citations carry the stored chunk id, verifiable with
  `GET /api/research/chunk/{chunk_id}`.
* The outcome prediction is reported separately from evidence quality: a
  calibrated probability, its `low_confidence` flag and the model version.
* Similarity is reported as similarity, never as a probability of winning.
