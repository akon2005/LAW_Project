---
id: voice-input
title: Using voice input
category: how-to
tags: [voice, microphone, dictation, speech, speech recognition, mic, accessibility, voice input]
intents: [how_to, feature_explanation]
features: [voice]
updated: 2026-10-16
---

A microphone button sits inside the research search bar (and in a few other
inputs, such as the Knowledge filter and the Compare panel fields).

## How it works

1. Click the microphone. Your browser asks for microphone permission the first
   time.
2. While listening, the button shows a listening state and the interim transcript
   appears under the search bar.
3. Recognized speech is written into the **same input box**. It is never
   auto-submitted — you review and edit the text, then submit normally.

## Language

The dictation language defaults to English (India) (`en-IN`) and can be changed
in the Filters panel.

## Browser support

Voice input uses the browser's Web Speech API. It works in browsers that expose
`SpeechRecognition` (or the `webkit` variant) and where the page is not blocked
by permissions. If the API is missing, the button explains that speech
recognition is not supported in that browser — typed input keeps working.

## States you may see

Permission denied, no microphone found, no speech detected, network error and
start failure are each reported as their own message instead of a generic
failure.

## Privacy note

Browser speech recognition may send audio to the browser vendor's cloud service.
It is **not** guaranteed to be local, offline or private, and the project does not
control that processing. For sensitive facts, type instead.
