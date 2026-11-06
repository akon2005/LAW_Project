---
id: limitations
title: System limitations
category: faq
tags: [limitations, limits, caveats, scope, accuracy]
intents: [feature_explanation, supported_feature_query, legal_research_guidance]
features: []
priority: 1
updated: 2026-10-27
---

These are the limitations the project states about itself.

1. **Corpus scope** — 100 Indian Supreme Court judgment PDFs (9,375 chunks), not
   all of Indian law.
2. **Outcome prediction is experimental** — the classifier is committed and
   loaded, so a clean checkout reports the capability as available; it is trained
   on 102 curated case records whose held-out test partition contains a single
   acquittal (a 15:1 majority class), and it must not be treated as validated.
3. **Similarity is not correctness** — retrieval similarity ranks passages; it
   does not establish that a passage is good law or applies to your facts.
4. **No area-of-law filter** — the corpus metadata records no area field, so none
   is offered.
5. **Chunked text** — judgments are stored in chunks, so a passage may begin or
   end mid-paragraph. The chunk id and source filename let you locate the record.
6. **Generated text still needs reading** — the system prompt forbids inventing
   cases, citations, statutes and dates, but prose must be read and citations
   verified.
7. **The support assistant answers only from project documentation** — it says
   when something cannot be verified rather than guessing.
8. **Preferences are per browser** — theme and reader settings are stored locally
   and do not follow you between devices.
9. **No persistent support history** — support conversations are held in memory
   for the session only.
10. **It is decision support** — no judgment, no advice; human decision-making
    remains outside the system.
