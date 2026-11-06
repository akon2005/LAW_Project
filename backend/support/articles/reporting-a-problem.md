---
id: reporting-a-problem
title: Reporting a problem or bug
category: support
tags: [report, reporting, bug, problem, issue, defect, error, broken, complaint, feedback, ticket, contact support]
intents: [report_problem, troubleshooting, how_to, feature_explanation]
features: [support_assistant]
priority: 1
updated: 2026-10-28
---

## Use the in-app report form

1. Open the support assistant (the sparkle button, bottom-right).
2. Choose **Report a Problem** in its toolbar, or ask it how to report a problem
   and press the action it offers.
3. Fill in the issue category, a short title, and what happened. Reproduction
   steps, the page you were on, and a contact are optional.
4. Press **Submit report**. The confirmation shows the reference id the backend
   stored, or an error if the write failed.

## What happens to the report

The report is validated and appended to this deployment's support log at
`backend/data/support/reports.jsonl`. Reports are not sent to an external
ticketing service, so the confirmation never claims a remote ticket or email was
created. Only the fields in the form are stored — not your chat transcript or
your research queries.

## What to include

* The page and control you used, for example "Compare → Analyze both scenarios".
* What you expected and what happened instead.
* The exact message shown, if any.
* Whether the backend was reachable, if the assistant's **System Status** panel
  shows a problem.

## What not to include

Do not paste real case facts, passwords, API keys or other confidential material
into a report. Credentials that look like keys or tokens are redacted before
storage, but it is better not to type them at all.

## Limits

A report records an issue; it does not fix it and it does not notify you when
the issue is resolved. If the backend cannot write the report, the form says so
and no reference id is shown.
