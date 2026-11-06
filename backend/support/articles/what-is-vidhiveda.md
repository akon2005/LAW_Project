---
id: what-is-vidhiveda
title: What VIDHIVEDA is and what it does
category: overview
tags: [overview, purpose, introduction, about, what is]
intents: [feature_explanation, general_greeting, project_architecture, how_to]
features: []
priority: 6
updated: 2026-10-16
---

## In one paragraph

VIDHIVEDA is an AI-powered legal research engine. You describe a legal issue in
plain language, it retrieves relevant passages from an indexed corpus of Indian
Supreme Court judgments, and it produces a research answer that keeps every
claim tied to a retrieved source.

## What problem it solves

Reading case law by hand is slow: the relevant principle may sit in one paragraph
of a 200-page judgment. VIDHIVEDA does the retrieval step for you and shows you
exactly which stored passage each part of the answer came from, so the research
trail stays visible.

## The workflow

1. Sign in to the workspace.
2. Type your question in the **Research** tab and submit it.
3. Read the retrieved records and the grounded answer on the right.
4. Open any record in the reading view, and verify a citation if you need to.
5. Use **Compare** when two competing accounts of one dispute must be weighed.

## What is actually running

* Retrieval: a real ChromaDB collection (`vidhiveda_legal_cases`) holding 9,375
  chunks from 100 Indian Supreme Court judgment PDFs from the dataset
  `dedol-hf/india-case-legal-rag`.
* Embeddings: `sentence-transformers/all-MiniLM-L6-v2` unless `EMBEDDING_MODEL`
  is changed.
* Generation: an LLM, only when an API key is configured in `backend/.env`.

## What it is not

It is a research and decision-support tool. It does not issue judgments, give
legal advice, or replace a lawyer. It also does not offer a validated
court-outcome prediction: the classifier it ships is experimental and trained on
102 curated case records (see "Outcome estimates and prediction status").
