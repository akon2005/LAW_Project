---
type: Dataset
title: dedol-hf/india-case-legal-rag
description: Indian Supreme Court and High Court judgment chunks used as the VIDHIVEDA
  retrieval corpus.
resource: https://huggingface.co/datasets/dedol-hf/india-case-legal-rag
tags:
- dataset
- case-law
- india
- rag
status: stable
generated:
  by: process:vidhiveda-okf-builder/1.0
  at: '2026-10-02T17:22:27Z'
verified:
- by: process:vidhiveda-okf-validator/1.0
  at: '2026-10-02T17:22:27Z'
sources:
- id: hf-dataset
  resource: https://huggingface.co/datasets/dedol-hf/india-case-legal-rag
  title: Hugging Face dataset dedol-hf/india-case-legal-rag
  author: team:dedol-hf
  last_modified: null
chunk_count: 9375
judgment_count: 100
---
# Overview

`dedol-hf/india-case-legal-rag` is the case-law corpus indexed into the ChromaDB collection `vidhiveda_legal_cases`.

# Observed schema

| Field | Description |
|---|---|
| `text` | Judgment chunk text. |
| `case_name` | Case title, derived from document text where available. |
| `court` | Court name as recorded upstream. |
| `judgment_date` | Judgment date when recorded. |
| `year` | Judgment year. |
| `sections` | Section labels printed in the chunk. |
| `articles` | Constitutional articles printed in the chunk. |
| `source` | Source PDF filename. |

# Corpus facts (observed)

* Indexed chunks: 9375
* Source judgments: 100
* Distinct courts (as recorded): 44
* Distinct section labels: 316
* Years present: 1950, 1951

# License and usage

License and redistribution terms are determined by the upstream dataset and its source judgments; consult the dataset card before redistribution.

# Related

* [Embedding model](/models/all-minilm-l6-v2.md)
* [Retrieval evaluation](/evaluation/retrieval-evaluation.md)
