/**
 * Sign-in form.
 *
 * Owns field state, inline validation and the loading/success affordances.
 * The actual credential exchange is delegated to `onSubmit`, which the login
 * page routes through the auth service and then through the session provider.
 *
 * No `alert()` anywhere: every failure surfaces inline, tied to the field or
 * to the form via `role="alert"`.
 */
import { useEffect, useId, useRef, useState } from 'react'
import { DEFAULT_ROLE, AUTH_ERRORS, validateCredentials } from '../../services/authService.js'
import { AlertIcon, ArrowRightIcon, CheckIcon, MailIcon, ShieldCheckIcon, SpinnerIcon } from './icons.jsx'
import PasswordInput from './PasswordInput.jsx'
import RoleSelector from './RoleSelector.jsx'

export default function LoginForm({ onSubmit, leaving = false, disabled = false, isLive = false }) {
  const emailId = useId()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState(DEFAULT_ROLE)
  const [remember, setRemember] = useState(false)

  const [fieldErrors, setFieldErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [phase, setPhase] = useState('idle') // idle | submitting

  // Guards against setting state after the page swaps to the workspace.
  const mounted = useRef(true)
  useEffect(() => () => {
    mounted.current = false
  }, [])

  const busy = phase === 'submitting' || leaving
  const locked = busy || disabled

  const validateField = (field, values = { email, password }) => {
    const errors = validateCredentials(values)
    setFieldErrors((current) => {
      const next = { ...current }
      if (errors[field]) next[field] = errors[field]
      else delete next[field]
      return next
    })
  }

  const handleEmailChange = (value) => {
    setEmail(value)
    setFormError('')
    if (fieldErrors.email) {
      setFieldErrors((current) => ({ ...current, email: undefined }))
    }
  }

  const handlePasswordChange = (value) => {
    setPassword(value)
    setFormError('')
    if (fieldErrors.password) {
      setFieldErrors((current) => ({ ...current, password: undefined }))
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (locked) return

    const errors = validateCredentials({ email, password })
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      setFormError('')
      // Move focus to the first field that needs attention.
      const firstInvalid = errors.email ? emailId : `${emailId}-password`
      document.getElementById(firstInvalid)?.focus()
      return
    }

    setFieldErrors({})
    setFormError('')
    setPhase('submitting')

    try {
      await onSubmit({ email: email.trim(), password, role, remember })
      // On success the login page plays its exit transition and unmounts this
      // form, so phase is intentionally left in "submitting".
    } catch (error) {
      if (!mounted.current) return
      setPhase('idle')
      if (error?.field === 'email' || error?.field === 'password') {
        setFieldErrors({ [error.field]: error.message })
      } else {
        setFormError(error?.message || AUTH_ERRORS.server_error)
      }
    }
  }

  const emailError = fieldErrors.email
  const passwordError = fieldErrors.password

  return (
    <form className="login-card" onSubmit={handleSubmit} noValidate aria-labelledby="login-title">
      <header className="login-card__head">
        <h1 id="login-title">Welcome back</h1>
        <p>Sign in to continue your legal research.</p>
      </header>

      {formError && (
        <div className="login-banner" role="alert">
          <AlertIcon size={17} />
          <span>{formError}</span>
        </div>
      )}

      <RoleSelector value={role} onChange={setRole} disabled={locked} />

      <div className={`login-field${emailError ? ' has-error' : ''}`}>
        <label htmlFor={emailId}>Email address</label>
        <div className="login-input-wrap">
          <span className="login-input-icon" aria-hidden="true">
            <MailIcon size={17} />
          </span>
          <input
            id={emailId}
            name="email"
            type="email"
            value={email}
            onChange={(event) => handleEmailChange(event.target.value)}
            onBlur={() => email && validateField('email')}
            disabled={locked}
            autoComplete="email"
            autoFocus
            inputMode="email"
            spellCheck="false"
            placeholder="name@institution.gov.in"
            aria-invalid={emailError ? 'true' : undefined}
            aria-describedby={emailError ? `${emailId}-error` : undefined}
          />
        </div>
        {emailError && (
          <p className="login-error" id={`${emailId}-error`} role="alert">
            {emailError}
          </p>
        )}
      </div>

      <PasswordInput
        id={`${emailId}-password`}
        label="Password"
        value={password}
        onChange={handlePasswordChange}
        onBlur={() => password && validateField('password')}
        error={passwordError}
        disabled={locked}
      />

      <div className="login-row">
        <label className="login-checkbox">
          <input
            type="checkbox"
            checked={remember}
            onChange={(event) => setRemember(event.target.checked)}
            disabled={locked}
          />
          <span className="login-checkbox__box" aria-hidden="true">
            <CheckIcon size={12} />
          </span>
          <span>Remember me</span>
        </label>

        <button
          type="button"
          className="login-link"
          onClick={() =>
            setFormError(
              isLive
                ? 'Password recovery is handled by your institution’s administrator.'
                : 'Password recovery is unavailable until an authentication service is connected.',
            )
          }
          disabled={locked}
        >
          Forgot password?
        </button>
      </div>

      <button type="submit" className="login-submit" disabled={locked} data-leaving={leaving}>
        <span className="login-submit__content">
          {leaving ? (
            <>
              <CheckIcon size={17} />
              <span>Signed in</span>
            </>
          ) : phase === 'submitting' ? (
            <>
              <SpinnerIcon size={16} />
              <span>Signing in…</span>
            </>
          ) : (
            <>
              <span>Sign In</span>
              <ArrowRightIcon size={17} />
            </>
          )}
        </span>
      </button>

      <p className="login-security" aria-live="polite">
        <ShieldCheckIcon size={15} />
        {isLive
          ? 'Your research workspace is protected with secure authentication.'
          : 'Demo workspace — authentication is not yet connected to a server.'}
      </p>

      {!isLive && (
        <p className="login-demo">
          Any valid email with a password of six or more characters will sign in. No
          credentials are sent anywhere.
        </p>
      )}
    </form>
  )
}
