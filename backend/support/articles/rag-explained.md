---
id: rag-explained
title: How retrieval-augmented generation works here
category: architecture
tags: [rag, retrieval, embeddings, vector, chromadb, generation, augmented, how does rag work]
intents: [rag_explanation, project_architecture, feature_explanation]
features: [research]
updated: 2026-10-16
---

## The short version

Retrieval first, generation second. The system finds stored legal passages, then
asks a language model to write an answer *from those passages only*.

## The steps in this project

1. **Query analysis** — normalizes the question and picks up statutory section
   references.
2. **Embedding** — the query becomes a vector with the configured embedding model
   (`sentence-transformers/all-MiniLM-L6-v2` by default).
3. **Vector search** — ChromaDB compares it against 9,375 indexed chunks in the
   `vidhiveda_legal_cases` collection and returns the closest ones.
4. **Reranking** — optional and off by default (`USE_RERANKER`); when enabled it
   adds lexical and cross-encoder scoring.
5. **Generation** — the retrieved chunks are numbered as SOURCE blocks and sent to
   the LLM with a system prompt that forbids inventing cases, citations, statutes
   or dates.
6. **Citation verification** — the answer's references are checked against the
   retrieved chunks; a citation is only marked verified if it matches.
7. **Fallback** — if retrieval is weak, no answer is generated. If no LLM key is
   configured you still get retrieval, with a clearly labelled note that no
   summary was produced.

## Why do it this way

A language model alone can produce fluent text about law that is grounded in
nothing. RAG constrains it to your stored sources and leaves a trail to check.

## What RAG does not do

Retrieval similarity is not a measure of legal correctness. RAG reduces
invention; it does not remove the need to read the sources. A retrieved passage
can still be inapplicable, out of date, or about a different fact pattern.
