import { useCallback } from 'react'
import Icon from './Icon.jsx'
import { useSpeechRecognition } from '../utils/useSpeechRecognition.js'
import { mergeTranscript } from '../utils/speech.js'

/**
 * Reusable microphone dictation control for inputs and textareas.
 *
 * Supported modes:
 * 1. Controlled: pass `value` and `onChange` — speech is automatically merged
 *    with existing typed content without overwriting previous text.
 * 2. Raw: pass `onTranscript(text)` to handle finalized recognition directly.
 *
 * Feature-detects browser speech recognition. When active, pulses visually and
 * displays live listening feedback with interim transcript preview.
 */
export default function MicButton({
  value,
  onChange,
  onTranscript,
  lang = 'en-IN',
  size = 14,
  title = 'Dictate with voice',
  className = '',
  variant = 'field', // 'field' | 'bar' | 'chat' | 'compact'
  showStatus = true,
  disabled = false,
}) {
  const handleFinal = useCallback(
    (text) => {
      if (onTranscript) {
        onTranscript(text)
      } else if (onChange) {
        onChange(mergeTranscript(value, text))
      }
    },
    [value, onChange, onTranscript],
  )

  const speech = useSpeechRecognition({
    lang,
    onFinal: handleFinal,
  })

  const tooltip = !speech.supported
    ? 'Speech recognition is not supported in this browser'
    : speech.listening
      ? 'Listening… Click to stop dictation'
      : title

  const handleClick = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled && speech.supported) {
      speech.toggle()
    }
  }

  return (
    <div className={`mic-ctrl mic-ctrl--${variant} ${speech.listening ? 'is-listening' : ''} ${className}`}>
      <button
        type="button"
        className={`mic-btn mic-btn--${variant} ${speech.listening ? 'mic-btn--listening' : ''} ${!speech.supported ? 'mic-btn--unsupported' : ''}`}
        onClick={handleClick}
        disabled={disabled || !speech.supported}
        aria-pressed={speech.listening}
        aria-label={tooltip}
        title={tooltip}
      >
        <Icon name={speech.listening ? 'micOff' : 'mic'} size={size} />
      </button>

      {showStatus && (speech.listening || speech.error) && (
        <span className="mic-pill-wrap" role="status" aria-live="polite">
          {speech.listening && (
            <span className="mic-pill mic-pill--live">
              <span className="mic-dot" />
              <span className="mic-pill-label">Listening…</span>
              {speech.interim && <span className="mic-pill-text">"{speech.interim}"</span>}
            </span>
          )}
          {speech.error && (
            <span className="mic-pill mic-pill--error" title={speech.error}>
              {speech.error}
            </span>
          )}
        </span>
      )}
    </div>
  )
}
