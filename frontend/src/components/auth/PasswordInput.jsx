/**
 * Password field with a show/hide control.
 *
 * The two eye icons are stacked and cross-faded rather than swapped, so the
 * toggle reads as one smooth state change instead of a flicker.
 */
import { useState } from 'react'
import { EyeIcon, EyeOffIcon, LockIcon } from './icons.jsx'

export default function PasswordInput({
  id,
  label,
  value,
  onChange,
  onBlur,
  error,
  disabled = false,
  autoComplete = 'current-password',
  autoFocus = false,
}) {
  const [visible, setVisible] = useState(false)
  const errorId = `${id}-error`

  return (
    <div className={`login-field${error ? ' has-error' : ''}`}>
      <label htmlFor={id}>{label}</label>

      <div className="login-input-wrap">
        <span className="login-input-icon" aria-hidden="true">
          <LockIcon size={17} />
        </span>

        <input
          id={id}
          name="password"
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onBlur={onBlur}
          disabled={disabled}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          spellCheck="false"
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={error ? errorId : undefined}
          placeholder="Enter your password"
        />

        <button
          type="button"
          className="login-password-toggle"
          onClick={() => setVisible((current) => !current)}
          disabled={disabled}
          aria-label={visible ? 'Hide password' : 'Show password'}
          aria-pressed={visible}
          title={visible ? 'Hide password' : 'Show password'}
        >
          <span className="login-toggle-icons" data-visible={visible ? 'true' : 'false'}>
            <EyeIcon size={17} className="login-toggle-eye" />
            <EyeOffIcon size={17} className="login-toggle-eye-off" />
          </span>
        </button>
      </div>

      {error && (
        <p className="login-error" id={errorId} role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
