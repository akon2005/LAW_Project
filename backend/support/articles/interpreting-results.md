---
id: interpreting-results
title: How to interpret retrieved precedents and similarity
category: how-to
tags: [interpret, similarity, relevance, score, reliability, confidence, precedent, interpret results]
intents: [how_to, legal_research_guidance, feature_explanation]
features: [research, citations]
updated: 2026-10-16
---

## Similarity is a retrieval measurement, not a verdict

The percentage on each card is a **dense vector similarity** between your query
and the stored chunk. It says how close the passages are in embedding space. It
is *not* a probability that the passage is legally correct, and it is not a
prediction of anything.

Use it to rank candidates. Never cite it as a measure of legal strength.

## "Precedent" here means a retrieved chunk

The corpus is chunked judgment text: one judgment contributes many chunks. The
Compare tab groups chunks by source document so several chunks of one judgment
are not counted as several precedents, and it reports `matched_chunks` for how
many chunks of that judgment matched.

## Low confidence

Below the configured threshold (`LOW_CONFIDENCE_THRESHOLD`, default 0.30) the
system does not generate an answer. It returns the sources it found with a
"low confidence" status and the reason — more useful than a confident-sounding
guess.

## Limitations to keep in mind

* If the corpus does not contain the point, retrieval cannot produce it.
* The corpus is a subset of Indian Supreme Court judgments (100 documents), not
  the whole body of Indian law.
* Retrieval ranking is not a legal analysis of relevance or authority.
