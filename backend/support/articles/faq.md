---
id: faq
title: Frequently asked questions
category: faq
tags: [faq, questions, common, cost, offline, private, accurate, no results]
intents: [feature_explanation, general_greeting, unknown]
features: []
priority: 2
updated: 2026-10-27
---

**Do I need an account?**
The workspace is gated behind a sign-in screen. When no authentication endpoint is
configured the app runs in a clearly labelled *demo* mode: credentials are
validated locally and the screen says authentication is not yet connected to a
server.

**Does it use the internet?**
Locally, retrieval works from the committed vector store and the embedding model
on disk. Two things can reach the network: the LLM provider, when an API key is
configured, and browser speech recognition, which may use the browser vendor's
service.

**Can I use it without an LLM key?**
Yes. Retrieval, results, sources and citations all work; you get a clearly
labelled note that no generated summary was produced, plus a deterministic listing
of the retrieved passages.

**Is the answer legal advice?**
No. It is research support. The project states this in the About notice and in
every research response's `disclaimer` field.

**Does it predict who will win?**
Only experimentally, and only as a calibrated statistical estimate from your
stated facts — never as a validated prediction. The classifier ships with the
project (`backend/data/models/outcome/`) and is trained on 102 curated case
records whose held-out test partition contains a single acquittal, so treat the
probability as supporting signal rather than a forecast. `GET /api/model/status`
reports whether the environment actually has it loaded. See "Outcome estimates
and prediction status".

**Why did my search return nothing?**
Either no indexed chunk matched with the current filters, or the query was too
specific. See "The legal search returned no results".

**How many documents are indexed?**
9,375 chunks from 100 Indian Supreme Court judgment PDFs. The UI always shows the
corpus actually in use.

**How do I report a bug?**
Open this assistant and choose **Report a Problem**. The form records the issue
category, a short title, what happened, optional reproduction steps, the page you
were on and an optional contact. Reports are written to this deployment's own
support log at `backend/data/support/reports.jsonl`; no external ticket is
created, and the confirmation tells you the reference id it stored.
