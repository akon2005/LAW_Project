import { useCallback, useEffect, useRef, useState } from 'react'
import {
  extractTranscript,
  getSpeechRecognitionCtor,
  isSpeechRecognitionSupported,
  mergeTranscript,
  speechErrorMessage,
} from './speech.js'

/**
 * Voice input for an existing text field.
 *
 * Feature-detects the browser API, exposes start/stop/toggle, streams the live
 * interim transcript and hands finalized text to `onFinal`. Handlers are always
 * detached and the recognizer aborted on unmount, and a fresh recognizer is
 * created per session, so listeners can never accumulate or double-fire.
 *
 * Typed input keeps working whether or not recognition is available.
 */
export function useSpeechRecognition({ onFinal, lang = 'en-IN', continuous = false } = {}) {
  const [supported] = useState(() => isSpeechRecognitionSupported())
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState('')

  const recognitionRef = useRef(null)
  const onFinalRef = useRef(onFinal)
  const interimRef = useRef('')

  onFinalRef.current = onFinal

  const detach = useCallback(() => {
    const recognition = recognitionRef.current
    if (!recognition) return
    recognition.onresult = null
    recognition.onerror = null
    recognition.onend = null
    recognition.onstart = null
    try {
      recognition.abort()
    } catch {
      /* already stopped */
    }
    recognitionRef.current = null
  }, [])

  const stop = useCallback(() => {
    const recognition = recognitionRef.current
    if (interimRef.current) {
      onFinalRef.current?.(mergeTranscript('', interimRef.current))
      interimRef.current = ''
    }
    setListening(false)
    setInterim('')
    if (recognition) {
      try {
        recognition.stop()
      } catch {
        /* ignore */
      }
    }
  }, [])

  const start = useCallback(() => {
    setError('')
    const Ctor = getSpeechRecognitionCtor()
    if (!Ctor) {
      setError('Speech recognition is not supported by this browser. You can still type your query.')
      return
    }

    detach()
    const recognition = new Ctor()
    recognition.lang = lang
    recognition.continuous = continuous
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onresult = (event) => {
      const { final, interim: interimText } = extractTranscript(event)
      interimRef.current = interimText
      setInterim(interimText)
      if (final) {
        interimRef.current = ''
        onFinalRef.current?.(mergeTranscript('', final))
      }
    }
    recognition.onerror = (event) => {
      if (event?.error === 'aborted') return
      const message = speechErrorMessage(event?.error)
      if (message) setError(message)
      setListening(false)
      setInterim('')
      interimRef.current = ''
    }
    recognition.onend = () => {
      if (interimRef.current) {
        onFinalRef.current?.(mergeTranscript('', interimRef.current))
        interimRef.current = ''
      }
      setListening(false)
      setInterim('')
    }

    recognitionRef.current = recognition
    try {
      recognition.start()
      setListening(true)
    } catch {
      setError('Could not start speech recognition. You can still type your query.')
      setListening(false)
    }
  }, [detach, lang, continuous])

  const toggle = useCallback(() => {
    if (listening) stop()
    else start()
  }, [listening, start, stop])

  // Cleanup on unmount: remove handlers and abort so nothing fires later.
  useEffect(() => detach, [detach])

  const clearError = useCallback(() => setError(''), [])

  return { supported, listening, interim, error, start, stop, toggle, clearError }
}

export default useSpeechRecognition
