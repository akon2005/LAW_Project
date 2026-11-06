/**
 * Browser speech-recognition helpers (pure — no React, no DOM globals at import
 * time, so they can be unit-checked from Node).
 *
 * These wrap the Web Speech API (`SpeechRecognition` / `webkitSpeechRecognition`).
 * Browser support is feature-detected, never assumed. Note that browser speech
 * recognition may send audio to the vendor's recognition service; it is not
 * guaranteed to be processed locally or privately.
 */

/** Languages offered in the microphone control. */
export const SPEECH_LANGUAGES = [
  { value: 'en-IN', label: 'English (India)' },
  { value: 'en-US', label: 'English (US)' },
  { value: 'hi-IN', label: 'Hindi' },
]

/**
 * Resolve the SpeechRecognition constructor, or null when the browser has none.
 * Accepts a scope so tests can inject a mock window.
 */
export function getSpeechRecognitionCtor(scope) {
  const target = scope ?? (typeof window !== 'undefined' ? window : undefined)
  if (!target) return null
  return target.SpeechRecognition || target.webkitSpeechRecognition || null
}

export function isSpeechRecognitionSupported(scope) {
  return Boolean(getSpeechRecognitionCtor(scope))
}

/**
 * Pull the final and interim transcript out of a `SpeechRecognitionEvent`.
 * Only results from `resultIndex` onward are read, so already-finalized text is
 * not reprocessed. Missing/short events yield empty strings instead of throwing.
 */
export function extractTranscript(event, fromIndex) {
  const result = { final: '', interim: '' }
  const results = event?.results
  if (!results || typeof results.length !== 'number') return result
  const start = typeof fromIndex === 'number'
    ? fromIndex
    : (typeof event.resultIndex === 'number' ? event.resultIndex : 0)
  for (let i = start; i < results.length; i += 1) {
    const item = results[i]
    const alternative = item && item[0]
    const text = (alternative && alternative.transcript) || ''
    if (item && item.isFinal) result.final += text
    else result.interim += text
  }
  return result
}

/**
 * Append a transcript to the current input value, preserving whatever the user
 * already typed or edited. Empty additions change nothing.
 */
export function mergeTranscript(base, addition) {
  const left = String(base ?? '')
  const right = String(addition ?? '').trim()
  if (!right) return left
  if (!left.trim()) return right
  if (left.trimEnd().endsWith(right)) return left
  return `${left.trimEnd()} ${right}`
}

/** Readable message for a `SpeechRecognitionErrorEvent.error` code. */
export function speechErrorMessage(code) {
  switch (code) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'Microphone or speech recognition permission was denied. Allow access, or type your query instead.'
    case 'no-speech':
      return 'No speech was detected. Try again, or type your query.'
    case 'audio-capture':
      return 'No microphone was found. You can still type your query.'
    case 'network':
      return 'Speech recognition needs a network connection and it was unavailable. Type your query instead.'
    case 'language-not-supported':
      return 'The selected language is not supported by this browser’s recognition service.'
    case 'aborted':
      return ''
    default:
      return 'Speech recognition stopped unexpectedly. You can still type your query.'
  }
}
