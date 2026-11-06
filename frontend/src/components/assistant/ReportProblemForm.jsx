import { useState } from 'react'
import { supportApi } from '../../services/supportApi.js'
import { SUPPORT_PAGES } from '../../utils/supportChat.js'

/**
 * Problem-report form for the support assistant.
 *
 * It posts to the real /api/support/report endpoint and only shows a reference
 * number after the backend confirms the record was written. There is no
 * external ticketing integration, and the component says so instead of
 * pretending a remote ticket exists.
 */

// Must match backend REPORT_CATEGORIES.
const CATEGORIES = [
  { value: 'research', label: 'Legal research / results' },
  { value: 'comparison', label: 'Compare' },
  { value: 'documents', label: 'Documents' },
  { value: 'statutes', label: 'Statutes & Articles' },
  { value: 'knowledge', label: 'Knowledge bundle' },
  { value: 'guides', label: 'Guides' },
  { value: 'assistant', label: 'This support assistant' },
  { value: 'account', label: 'Sign-in / account' },
  { value: 'performance', label: 'Speed or page loading' },
  { value: 'other', label: 'Something else' },
]

const PAGE_LABELS = {
  research: 'Research',
  statutes: 'Statutes & Articles',
  documents: 'Documents',
  comparison: 'Compare',
  knowledge: 'Knowledge',
  guide: 'Guides',
  settings: 'Settings',
}

const LIMITS = { title: 120, description: 2000, steps: 1000, contact: 120 }

export default function ReportProblemForm({ page, sessionId, onClose }) {
  const [form, setForm] = useState({
    category: CATEGORIES.some((item) => item.value === page) ? page : 'other',
    title: '',
    description: '',
    steps: '',
    page: SUPPORT_PAGES.includes(page) ? page : '',
    contact: '',
  })
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [stored, setStored] = useState(null)
  const [touched, setTouched] = useState(false)

  const update = (key) => (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }))

  const titleOk = form.title.trim().length >= 4
  const descriptionOk = form.description.trim().length >= 20
  const canSubmit = titleOk && descriptionOk && !pending

  const submit = async (event) => {
    event.preventDefault()
    setTouched(true)
    if (!canSubmit) return
    setPending(true)
    setError('')
    try {
      const data = await supportApi.report(
        {
          category: form.category,
          title: form.title.trim(),
          description: form.description.trim(),
          steps: form.steps.trim(),
          page: form.page,
          contact: form.contact.trim(),
        },
        { sessionId },
      )
      setStored(data)
    } catch (err) {
      const status = err?.status ?? 0
      const detail = typeof err?.message === 'string' ? err.message : ''
      setError(
        status === 0
          ? 'Network error: the report was NOT sent because the support backend could not be reached. Check that the API is running and try again.'
          : status === 429
            ? 'Too many reports were submitted just now. Wait a few minutes and try again.'
            : status === 503
              ? 'The server could not store the report (its support log is not writable). Nothing was saved.'
              : detail || `The report could not be submitted (HTTP ${status}). Nothing was saved.`,
      )
    } finally {
      setPending(false)
    }
  }

  const reset = () => {
    setForm({
      category: CATEGORIES.some((item) => item.value === page) ? page : 'other',
      title: '',
      description: '',
      steps: '',
      page: SUPPORT_PAGES.includes(page) ? page : '',
      contact: '',
    })
    setStored(null)
    setError('')
    setTouched(false)
  }

  if (stored) {
    return (
      <section className="assistant-panel assistant-report" aria-label="Problem report recorded">
        <header>
          <h4>Report recorded</h4>
          <button type="button" className="assistant-mini-btn" onClick={onClose}>Close</button>
        </header>
        <p className="assistant-panel-note">
          Reference <strong>{stored.ticket_id}</strong>. {stored.message}
        </p>
        <p className="assistant-panel-note">
          Your report is stored with this deployment&apos;s support log for the maintainers to review.
          No external ticket, email or notification was created.
        </p>
        <div className="assistant-report-actions">
          <button type="button" className="assistant-mini-btn" onClick={reset}>File another issue</button>
        </div>
      </section>
    )
  }

  return (
    <section className="assistant-panel assistant-report" aria-label="Report a problem">
      <header>
        <h4>Report a problem</h4>
        <button type="button" className="assistant-mini-btn" onClick={onClose}>Cancel</button>
      </header>
      <p className="assistant-panel-note">
        Describe a product or technical issue. Do not include confidential case facts, passwords or
        API keys. Reports are written to this deployment&apos;s support log; there is no external
        ticketing service.
      </p>

      <form className="assistant-report-form" onSubmit={submit} noValidate>
        <label className="assistant-report-field">
          <span>Issue category</span>
          <select value={form.category} onChange={update('category')}>
            {CATEGORIES.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </label>

        <label className="assistant-report-field">
          <span>Short title <em>required</em></span>
          <input
            value={form.title}
            onChange={update('title')}
            maxLength={LIMITS.title}
            aria-invalid={touched && !titleOk}
          />
          {touched && !titleOk && <small className="assistant-report-hint">At least 4 characters.</small>}
        </label>

        <label className="assistant-report-field">
          <span>What happened? <em>required</em></span>
          <textarea
            value={form.description}
            onChange={update('description')}
            rows={4}
            maxLength={LIMITS.description}
            aria-invalid={touched && !descriptionOk}
            placeholder="What you did, what you expected, and what happened instead."
          />
          <small className="assistant-report-hint">
            {form.description.trim().length}/{LIMITS.description}
            {!descriptionOk ? ' · at least 20 characters' : ''}
          </small>
        </label>

        <label className="assistant-report-field">
          <span>Steps to reproduce <em>optional</em></span>
          <textarea
            value={form.steps}
            onChange={update('steps')}
            rows={3}
            maxLength={LIMITS.steps}
            placeholder="For example: open Compare, fill both positions, press Analyze."
          />
        </label>

        <div className="assistant-report-row">
          <label className="assistant-report-field">
            <span>Page you were on</span>
            <select value={form.page} onChange={update('page')}>
              <option value="">Not sure / other</option>
              {SUPPORT_PAGES.map((value) => (
                <option key={value} value={value}>{PAGE_LABELS[value] || value}</option>
              ))}
            </select>
          </label>

          <label className="assistant-report-field">
            <span>Contact <em>optional</em></span>
            <input
              value={form.contact}
              onChange={update('contact')}
              maxLength={LIMITS.contact}
              placeholder="Email or handle, if you want a reply"
            />
          </label>
        </div>

        {error && <p className="assistant-error-inline" role="alert">{error}</p>}

        <div className="assistant-report-actions">
          <button type="submit" className="assistant-mini-btn assistant-mini-btn--primary" disabled={!canSubmit}>
            {pending ? 'Submitting…' : 'Submit report'}
          </button>
          <span className="assistant-panel-note">Stored only if the server confirms the write.</span>
        </div>
      </form>
    </section>
  )
}
