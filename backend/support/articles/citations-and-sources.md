---
id: citations-and-sources
title: What citations and source references mean
category: how-to
tags: [citation, citations, source, sources, reference, verify, chunk, provenance, footnote, check, response, judgment, "supported by a judgment", cited]
intents: [how_to, feature_explanation, legal_research_guidance]
features: [citations]
updated: 2026-10-16
---

## Two different things are shown

1. **Verified citations** — the sources the generated answer actually referenced,
   checked against the retrieved chunks before they are marked verified.
2. **Retrieved records** — everything the search returned, whether or not the
   answer cited it.

## Every citation carries a chunk id

A citation row shows the case name, court, date/year, the source filename, the
chunk id and the similarity. The source filename and the chunk id are how you get
back to the stored row.

## How to verify a citation

* Open the record in the reading view and read the stored chunk text.
* Or fetch the row directly from the API:

```bash
curl http://127.0.0.1:8000/api/research/chunk/157_62
```

If the text in the response matches the passage you are relying on, the citation
is grounded. If a citation does not appear in the retrieved records, treat it as
unverified.

## What a citation does not prove

A verified citation proves the text exists in the corpus and was retrieved. It
does not prove that the passage supports the legal proposition, that the judgment
is still good law, or that it applies to your facts. Read the passage.
