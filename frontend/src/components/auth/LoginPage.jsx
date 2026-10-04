/**
 * Sign-in screen.
 *
 * Split layout: an editorial legal-research panel on the left, the form on the
 * right. On narrow screens the order becomes brand → form → a small legal
 * visual, keeping the form as the primary focus.
 *
 * Sign-in flow: the form calls `onSubmit` → credentials are verified and the
 * session persisted (without touching React state) → this page plays its exit
 * transition → `commit` publishes the session → the workspace fades in.
 */
import { useEffect, useState } from 'react'
import { useAuth } from '../../auth/AuthProvider.jsx'
import { API_BASE } from '../../services/apiBase.js'
import AuthVisual from './AuthVisual.jsx'
import LoginForm from './LoginForm.jsx'
import { ScaleIcon } from './icons.jsx'
import '../../styles/login.css'

/** Must match the exit transition in login.css. */
const TRANSITION_MS = 320

const NOTICES = {
  privacy: [
    'Privacy',
    'Your sign-in session is stored only in this browser, and clearing it signs you out. Research queries are logged server-side with their timings and retrieved chunk ids; credentials and keys are never logged.',
  ],
  terms: [
    'Terms of use',
    'VIDHIVEDA is a research and decision-support tool for judicial officers, lawyers and legal researchers. It does not issue judgments, verdicts or legal advice, and generated text must be checked against the cited sources.',
  ],
  help: [
    'Help',
    'Describe a legal issue in the research workspace and every result will link back to the indexed source it came from. Filters for court and year apply to real corpus metadata.',
  ],
}

function prefersReducedMotion() {
  return (
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  )
}

export default function LoginPage() {
  const { login, commit, isLive } = useAuth()
  const [leaving, setLeaving] = useState(false)
  const [corpus, setCorpus] = useState(null)
  const [notice, setNotice] = useState(null)

  // Real corpus numbers when the API is reachable; neutral wording when it is
  // not. The page never states a figure it has not been told.
  useEffect(() => {
    let active = true
    fetch(`${API_BASE}/api/research/corpus`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (active && data) setCorpus(data)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  const handleSubmit = async (credentials) => {
    const session = await login(credentials)
    setLeaving(true)
    await new Promise((resolve) =>
      window.setTimeout(resolve, prefersReducedMotion() ? 0 : TRANSITION_MS),
    )
    commit(session)
    return session
  }

  const facts = corpus
    ? [
        `${corpus.chunk_count.toLocaleString()} indexed judgment chunks`,
        `Corpus: ${corpus.dataset}`,
        `Semantic search over ${corpus.collection}`,
      ]
    : [
        'Semantic search over an indexed judgment corpus',
        'Every answer cites the source it came from',
        'Research support — never a judicial decision',
      ]

  return (
    <div className={`login-shell${leaving ? ' is-leaving' : ''}`}>
      <section className="login-editorial">
        <AuthVisual imageSrc={import.meta.env.VITE_LOGIN_VISUAL || null} />

        <div className="login-editorial__inner">
          <div className="login-brand">
            <span className="brand-mark" aria-hidden="true">
              <ScaleIcon size={19} />
            </span>
            <span>
              <span className="brand-name">VIDHIVEDA</span>
              <span className="brand-sub">LEGAL RESEARCH</span>
            </span>
          </div>

          <div className="login-editorial__copy">
            <span className="eyebrow">Retrieval-augmented legal research</span>
            <h2 className="login-headline">
              Research the law.
              <br />
              Trace the precedent.
              <br />
              <em>Understand the context.</em>
            </h2>
            <p className="login-statement">
              Judicial knowledge discovery across Indian case law — retrieval over an
              indexed judgment corpus, with every result traceable to its source.
            </p>
          </div>

          <ul className="login-facts">
            {facts.map((fact) => (
              <li key={fact}>{fact}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="login-panel">
        <LoginForm onSubmit={handleSubmit} leaving={leaving} isLive={isLive} />
      </section>

      <section className="login-mobile-visual" aria-hidden="true">
        <AuthVisual compact />
      </section>

      <footer className="login-footer">
        <span className="login-footer__brand">
          VIDHIVEDA <span aria-hidden="true">•</span> Legal Research &amp; Judicial Knowledge
          Discovery
        </span>

        <nav className="login-footer__links" aria-label="Legal and support information">
          {Object.entries(NOTICES).map(([key, [label]]) => (
            <button
              key={key}
              type="button"
              className="login-link"
              onClick={() => setNotice(notice === key ? null : key)}
              aria-expanded={notice === key}
            >
              {label}
            </button>
          ))}
        </nav>

        <span className="login-footer__disclaimer">
          Research support only — not legal advice.
        </span>
      </footer>

      {notice && (
        <div className="login-notice" role="status">
          <strong>{NOTICES[notice][0]}</strong>
          <p>{NOTICES[notice][1]}</p>
          <button
            type="button"
            className="login-link"
            onClick={() => setNotice(null)}
            aria-label="Dismiss"
          >
            Close
          </button>
        </div>
      )}
    </div>
  )
}
