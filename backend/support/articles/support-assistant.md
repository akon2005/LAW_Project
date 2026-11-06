---
id: support-assistant
title: Using the VIDHIVEDA support assistant
category: overview
tags: [assistant, chatbot, support, help, guide, bubble, ask, this assistant]
intents: [feature_explanation, how_to, general_greeting]
features: [support_assistant]
updated: 2026-10-28
---

## What this assistant is for

This is the **User Guide & Support Assistant**. It explains how VIDHIVEDA works,
walks you through features, helps you troubleshoot, and can open features or demo
examples for you.

It is a different assistant from the legal research engine. Research questions
belong in the **Research** tab; the support assistant answers questions about the
*system* and hands you over to the research interface when you need case law.

## Opening it

Click the sparkle button in the bottom-right corner. The panel opens with
suggested questions and a row of quick actions.

## What you get back

* An answer, and where it came from — the documentation, the language model, a
  troubleshooting rule, or a demo example. The response states which.
* **References** to the support articles that were used.
* **Follow-up questions** you can click.
* **Quick actions** that open real features (Research, Compare, Settings, the
  example gallery, and so on).

## Things it can do

* Explain a feature, its inputs and its outputs.
* Report the implementation status of a feature honestly (implemented, partial,
  experimental, planned, or not available).
* Give structured troubleshooting steps for a recognised error.
* Show approved demo examples with the learning objective for each.
* Read live system status.

## Reporting a problem

Choose **Report a Problem** in the assistant's toolbar, or ask how to report a
problem and use the action it offers. The form asks for:

* an issue category (Research, Compare, Documents, and so on);
* a short title and a description of what happened;
* optional steps to reproduce;
* the page you were on and an optional contact.

The report is validated and stored in this deployment's own support log
(`backend/data/support/reports.jsonl`). There is **no external ticketing
integration**: the confirmation shows the stored reference id and says plainly
that no remote ticket or email was created. If the server cannot write the
report, the form says so — it never shows a success message for a failed write.

Never include passwords, API keys or confidential case facts in a report.

## Session behaviour

Your conversation is held for the session you are in. It is not shared with other
users, and **Restart** clears it. Do not paste passwords, tokens or confidential
case facts into the assistant; describe the problem instead.

## Limits

The assistant answers from the project's own documentation and live status
checks. If the documentation does not cover a question it will say that the
answer could not be verified rather than guess.
