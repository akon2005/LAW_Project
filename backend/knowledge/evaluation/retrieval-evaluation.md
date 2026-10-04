---
type: Evaluation Methodology
title: Retrieval evaluation
description: Reproducible retrieval and citation evaluation for the VIDHIVEDA pipeline,
  run by scripts/evaluate.py.
tags:
- evaluation
- retrieval
- reproducibility
status: stable
generated:
  by: process:vidhiveda-okf-builder/1.0
  at: '2026-10-02T17:22:27Z'
verified:
- by: process:vidhiveda-okf-validator/1.0
  at: '2026-10-02T17:22:27Z'
sources:
- id: gold-set
  resource: scripts/build_gold_set.py
  title: Derived gold set builder
metrics:
- recall_at_5
- recall_at_10
- recall_at_20
- mrr
- ndcg_at_10
---
# Metrics

Retrieval: Recall@5, Recall@10, Recall@20, MRR, nDCG@10.
Generation: citation precision, citation coverage, unsupported-claim rate.

# How to run

```bash
python scripts/build_gold_set.py
python scripts/evaluate.py --no-rerank
python scripts/evaluate.py --rerank
```

# Honesty

The gold set is derived from the corpus, not hand-labelled legal ground truth. Metric values are produced by the scripts above and are never asserted in documentation without a run.

# Related

* [Dataset](/datasets/india-case-legal-rag.md)
