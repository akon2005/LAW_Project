---
id: writing-a-query
title: How to write a research query
category: how-to
tags: [query, facts, refine, prompt, wording, improve, better results, case facts]
intents: [how_to, legal_research_guidance]
features: [research]
updated: 2026-10-16
---

## What works

Describe the dispute the way you would explain it to a colleague:

* the legal issue ("whether the termination was wrongful"),
* the key facts (who did what, what the contract or provision said),
* the kind of answer you are researching ("damages for breach").

Example: *"Whether a landlord can forfeit a security deposit when the tenant
vacated after the lease expired without notice."*

## What works less well

* Single generic words ("property", "contract") — they match too broadly.
* A whole case narrative in one prompt — retrieve in stages instead.
* A bare section number ("Section 138") unless you also state the issue.

## Sections and provision references

If you name a statutory provision (for example "IPC Section 302"), query analysis
normalizes the section reference and can apply it as a filter on retrieval.
Section references are stored metadata, not generated text.

## Typed or dictated

You can type the query or dictate it with the microphone button; dictation fills
the same box so you can correct it before submitting. See "Using voice input".

## When the answer says the evidence is weak

The pipeline reports low confidence instead of forcing an answer. That is the
honest path: broaden the query, remove a filter, or search the legal principle
rather than the exact fact pattern.
