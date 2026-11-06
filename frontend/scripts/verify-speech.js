#!/usr/bin/env node
/**
 * Verify the voice-input helpers without a browser.
 *
 * The Web Speech API is feature-detected, so these checks inject a mock window
 * and exercise the pure functions the microphone control relies on:
 * feature detection (incl. the `webkit` fallback), transcript extraction
 * (interim vs final), merging into the existing search input, and the readable
 * error mapping. Exits non-zero on failure so it can gate a build.
 */
import {
  SPEECH_LANGUAGES,
  extractTranscript,
  getSpeechRecognitionCtor,
  isSpeechRecognitionSupported,
  mergeTranscript,
  speechErrorMessage,
} from '../src/utils/speech.js'

const failures = []
const check = (label, condition) => {
  if (!condition) failures.push(label)
}

// ── Feature detection ─────────────────────────────────────────────────────
check('no scope → no constructor', getSpeechRecognitionCtor(null) === null)
check('unsupported window reported unsupported', !isSpeechRecognitionSupported({}))
check(
  'standard SpeechRecognition detected',
  isSpeechRecognitionSupported({ SpeechRecognition: function SR() {} }),
)
check(
  'webkit fallback detected',
  isSpeechRecognitionSupported({ webkitSpeechRecognition: function WSR() {} }),
)

// ── Transcript extraction ─────────────────────────────────────────────────
const mockEvent = {
  resultIndex: 0,
  results: [
    Object.assign({ 0: { transcript: 'breach of ' }, length: 1 }, { isFinal: true }),
    Object.assign({ 0: { transcript: 'contract damages' }, length: 1 }, { isFinal: false }),
  ],
}
const extracted = extractTranscript(mockEvent)
check('final transcript extracted', extracted.final === 'breach of ')
check('interim transcript extracted', extracted.interim === 'contract damages')
check('missing event is safe', extractTranscript(undefined).final === '')
check('result list without length is safe', extractTranscript({ results: {} }).final === '')

// Only results from resultIndex onward are read.
const afterIndex = extractTranscript({
  resultIndex: 1,
  results: [
    Object.assign({ 0: { transcript: 'ignored' }, length: 1 }, { isFinal: true }),
    Object.assign({ 0: { transcript: 'kept' }, length: 1 }, { isFinal: true }),
  ],
})
check('resultIndex is honoured', afterIndex.final === 'kept')

// ── Merging into the existing input ───────────────────────────────────────
check('empty base takes transcript', mergeTranscript('', 'self defence') === 'self defence')
check('typed text is preserved', mergeTranscript('IPC 302', 'self defence') === 'IPC 302 self defence')
check('no duplicate append', mergeTranscript('self defence', 'self defence') === 'self defence')
check('empty addition is a no-op', mergeTranscript('typed query', '') === 'typed query')

// ── Error mapping ─────────────────────────────────────────────────────────
check('permission error is readable', /permission/i.test(speechErrorMessage('not-allowed')))
check('no-speech is readable', /no speech/i.test(speechErrorMessage('no-speech')))
check('network error is readable', /network/i.test(speechErrorMessage('network')))
check('aborted is silent', speechErrorMessage('aborted') === '')
check('unknown error still returns text', speechErrorMessage('weird').length > 0)

// ── Language options ──────────────────────────────────────────────────────
check('languages offered', Array.isArray(SPEECH_LANGUAGES) && SPEECH_LANGUAGES.length >= 1)
check(
  'every language has value+label',
  SPEECH_LANGUAGES.every((l) => l.value && l.label),
)

if (failures.length) {
  console.error(`\n${failures.length} voice-input check(s) failed:`)
  for (const failure of failures) console.error(`  - ${failure}`)
  process.exit(1)
}
console.log('OK: voice-input helpers (feature detection, transcript merge, error mapping) verified.')
