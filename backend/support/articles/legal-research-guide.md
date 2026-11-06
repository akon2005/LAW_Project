---
id: legal-research-guide
title: How to use the Legal Research workspace
category: how-to
tags: [research, search, query, precedent, judgment, find, case law, steps, workspace]
intents: [how_to, legal_research_guidance, feature_explanation]
features: [research]
updated: 2026-10-16
---

## Step by step

1. Open the **Research** tab (this is where you land after signing in).
2. Type your legal issue in the search box — a sentence or two of facts and
   questions works better than keywords.
3. Press **Enter** or the arrow button.
4. The page scrolls to the workspace. On the left is the filter panel, in the
   middle the retrieved records, on the right the grounded answer.
5. Open any record with **Read** to see the full stored passage.
6. Check the **Verified citations** block to see which chunks the answer used.

## About the filters

The **Court** and **Year** filters are built from the corpus itself, with the
chunk count next to each value, so a filter option can never be offered that no
indexed chunk can satisfy. The year list covers only years the corpus actually
contains. There is **no area-of-law filter**: the corpus metadata records no area
field, and offering one would silently return nothing.

## What the result cards show

* the case name and court/year as stored in the corpus (or an explicit
  "not recorded" label),
* a passage from the stored chunk,
* the chunk id, the source filename, and the similarity percentage.

## If you get nothing back

Refine the query (see "How to write a research query"), clear the filters, or
read the message in the answer panel — the system distinguishes "no corpus record
matched" from "the backend is unavailable".
