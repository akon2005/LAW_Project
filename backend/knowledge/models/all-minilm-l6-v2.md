---
type: Embedding Model
title: all-MiniLM-L6-v2
description: Sentence-transformer producing 384-dimensional vectors for the VIDHIVEDA
  corpus.
tags:
- embedding
- sentence-transformers
- retrieval
status: stable
generated:
  by: process:vidhiveda-okf-builder/1.0
  at: '2026-10-02T17:22:27Z'
verified:
- by: process:vidhiveda-okf-validator/1.0
  at: '2026-10-02T17:22:27Z'
sources:
- id: model-card
  resource: all-MiniLM-L6-v2
  title: all-MiniLM-L6-v2
resource: null
dimensions: 384
provider: sentence-transformers
---
# Model

* Identifier: `all-MiniLM-L6-v2`
* Embedding dimension: 384
* Provider: sentence-transformers

# Index compatibility

Changing the embedding model changes the vector space. The ChromaDB collection must be re-ingested after any change; vectors from incompatible embedding spaces must never be mixed.

# Related

* [Dataset](/datasets/india-case-legal-rag.md)
