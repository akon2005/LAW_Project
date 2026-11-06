---
id: troubleshooting-overview
title: Troubleshooting overview
category: troubleshooting
tags: [troubleshoot, error, problem, broken, not working, fix, issue, fails]
intents: [troubleshooting, how_to]
features: []
updated: 2026-10-16
---

When something does not work, the support assistant answers with a structured
troubleshooting entry rather than a guess. Each entry contains:

* **What the problem means** — the situation in plain language.
* **Likely causes** — the usual reasons, most likely first.
* **Safe steps** — what you can try yourself, in order.
* **Retrying** — whether retrying is appropriate for this problem.
* **When to escalate** — what to tell the project administrator.

## Recognised problems

| Problem | Typical symptom |
|---|---|
| Chatbot not responding | The assistant panel stays empty or spins forever. |
| Backend unavailable | The UI says the API could not be reached. |
| Request timeout | The request runs and then fails after a long wait. |
| LLM provider not configured | Results appear, but no generated summary. |
| Rate limit or quota exceeded | The provider rejects requests after a burst. |
| Empty or irrelevant search results | Zero matches, or matches that miss the point. |
| Missing source citations | The answer cites nothing you can check. |
| Invalid request input | A 422 response or an inline validation message. |
| Authentication or session problems | You are returned to the sign-in screen unexpectedly. |
| Theme or UI rendering issues | Colours, contrast or layout look wrong. |
| Network errors | "Failed to fetch" in the browser console or the UI. |
| Unsupported browser features | Microphone or other browser API is unavailable. |

## How to get help fast

Ask the assistant directly, for example: *"The legal search returned no results.
What should I do?"* It will return the relevant entry with the steps.

One rule the assistant follows: it never claims the server is healthy unless a
real health check says so. When the backend genuinely cannot be reached, the
honest answer is that it is unavailable — not that your query was wrong.
