---
id: privacy-and-data
title: Privacy and data handling
category: faq
tags: [privacy, data, logs, analytics, storage, secret, security, sensitive]
intents: [feature_explanation, project_architecture, unknown]
features: []
updated: 2026-10-16
---

## What is stored in your browser

* The signed-in session — `localStorage` if you chose "Remember me", otherwise
  `sessionStorage`, expiring after 12 hours.
* Reader preferences under `vidhiveda.reader`.
* Theme mode and palette choices.

Clearing site data removes all of it, and **Sign out** clears the session.

## What the backend handles

* **Support chat:** your message, optional page context, and a bounded amount of
  recent conversation for the current session. Session state is held in memory,
  keyed by an opaque session id, isolated per session, bounded in size and dropped
  when it expires. It is not written to disk.
* **Feedback:** if you submit optional helpful / not-helpful feedback, the rating
  and a short comment are appended to a local file. Keep personal data out of the
  comment.
* **Logs:** operations and tool names are logged with safe status metadata, not
  full message content, and never credentials.

## What is never sent to the language model

Passwords, tokens, API keys, and anything outside the retrieved support articles
plus your message, the current page name and the recent turns of that
conversation. The support subsystem does not receive the legal corpus or your
research query history.

## API keys

Provider keys live in backend environment variables only. They are never placed in
`VITE_*` variables or in browser JavaScript, because anything shipped to the
browser is public.

## Browser speech recognition

Dictation is handled by the browser's own speech API, which may send audio to the
browser vendor's cloud service. That processing is outside this project's control,
so dictated text should not be treated as private. Type sensitive facts instead.

## Error information

Users see readable error messages. Stack traces, internal configuration and
infrastructure details are not returned to the browser.
