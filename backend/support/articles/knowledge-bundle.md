---
id: knowledge-bundle
title: The Knowledge bundle tab
category: features
tags: [knowledge, okf, concepts, graph, trust tier, provenance, open knowledge format]
intents: [feature_explanation, project_architecture, how_to]
features: [knowledge]
updated: 2026-10-16
---

**Knowledge** exposes the project's Open Knowledge Format v0.2 bundle — a
portable directory of markdown concepts generated from the indexed corpus
(100 judgments, 44 courts and 316 provision references, plus dataset, model and
evaluation concepts).

You can filter by type (judgment, court, provision, dataset, model, evaluation),
search by title/tag/body text, and open a concept to read its body, its sources,
its related concepts and its backlinks.

## Trust tiers matter

Every concept records where it came from and a trust tier. The bundle is
generated and checked by processes, so concepts are **machine-confirmed**, not
**human-reviewed**. Where the corpus does not record a value (for example a
section's parent statute) the field is left empty and stated as unknown rather
than guessed.

## How it relates to research

`POST /api/research` returns a supplementary list of related concepts. Original
retrieved chunks remain authoritative: OKF summaries are never injected into the
generation prompt in place of source evidence.

Regenerate and validate the bundle from `backend/` with
`python scripts/build_okf_bundle.py` and `python scripts/validate_okf.py`.
