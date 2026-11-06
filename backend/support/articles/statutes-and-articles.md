---
id: statutes-and-articles
title: The Statutes and Articles tab
category: features
tags: [statutes, articles, instruments, acts, library, reference, acts and sections]
intents: [feature_explanation, how_to, website_navigation]
features: [statutes]
updated: 2026-10-16
---

**Statutes & Articles** lists the instruments referenced in the bundled frontend
dataset (acts, codes and constitutional material), with the number of records
whose text matches each instrument.

Each row has a **Search** action that fills the research box with the
instrument's prepared query and switches to the Research tab. The Research tab
also shows a **Legal library** section with a shortlist of the same instruments.

What to expect: this tab is a *reference shell* over the bundled dataset. It runs
searches against the indexed case-law corpus; it does not open the full text of a
statute, and the separate statute collection (`vidhiveda_statutes`) declared in
`app/services/dataset_service.py` is not ingested in this build.
