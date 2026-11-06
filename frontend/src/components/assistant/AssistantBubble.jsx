import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from '../Icon.jsx'
import MicButton from '../MicButton.jsx'
import './assistant.css'
import ReportProblemForm from './ReportProblemForm.jsx'
import { supportApi, getSessionId } from '../../services/supportApi.js'
import { writeClipboard } from '../../utils/clipboard.js'
import {
  KIND_LABELS,
  WELCOME,
  buildChatPayload,
  clientCommand,
  describeError,
  exampleBadge,
  groupExamples,
  healthRows,
  healthTone,
  kindLabel,
  mergeHistory,
  normalizeMessage,
  originLabel,
  resolveAction,
} from '../../utils/supportChat.js'

/**
 * VIDHIVEDA User Guide & Support Assistant.
 *
 * This bubble is the *support* assistant: it explains how the product works from
 * the project's own documentation, shows labelled demo examples and troubleshoots
 * problems. It is not the legal research assistant — legal questions are handed
 * to the Research workspace through an allowlisted quick action, and the answer
 * says so.
 *
 * Every control here has real behaviour: navigation switches real tabs, examples
 * load or run real prompts, feedback posts to the real endpoint, and the status
 * panel reads the real readiness check. Model output is escaped before it is
 * rendered; no raw HTML from the backend is injected.
 */

/** Escape, then apply a small markdown subset. Model/back-end text is never raw HTML. */
function renderText(text) {
  const escaped = String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  const html = escaped
    .replace(/^#{2,3} (.+)$/gm, '<strong>$1</strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^&gt; (.+)$/gm, '<em>$1</em>')
    .replace(/^\s*[-*] (.+)$/gm, '• $1')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br/>')
  return <div dangerouslySetInnerHTML={{ __html: html }} />
}

function CopyButton({ text }) {
  const [state, setState] = useState('')
  return (
    <button
      type="button"
      className="assistant-mini-btn"
      onClick={async () => {
        const ok = await writeClipboard(text)
        setState(ok ? 'Copied' : 'Unavailable')
        window.setTimeout(() => setState(''), 1600)
      }}
      aria-label="Copy this response"
    >
      {state || 'Copy'}
    </button>
  )
}

function FeedbackControls({ messageId, sessionId, page, onDone }) {
  const [sent, setSent] = useState('')
  const [showComment, setShowComment] = useState(false)
  const [comment, setComment] = useState('')
  const [pending, setPending] = useState(false)

  const submit = async (rating) => {
    setPending(true)
    try {
      await supportApi.feedback(rating, { comment, messageId, sessionId, page })
      setSent(rating)
      setShowComment(false)
      onDone?.(rating)
    } catch (err) {
      setSent('error')
    } finally {
      setPending(false)
    }
  }

  if (sent === 'helpful') return <p className="assistant-feedback-note">Thanks — recorded as helpful.</p>
  if (sent === 'not_helpful') return <p className="assistant-feedback-note">Thanks — recorded. A short note helps most.</p>
  if (sent === 'error') return <p className="assistant-feedback-note assistant-feedback-note--error">Feedback could not be stored right now.</p>

  return (
    <div className="assistant-feedback">
      <span>Was this helpful?</span>
      <button type="button" className="assistant-mini-btn" disabled={pending} onClick={() => submit('helpful')}>Yes</button>
      <button type="button" className="assistant-mini-btn" disabled={pending} onClick={() => setShowComment((v) => !v)}>Not quite</button>
      {showComment && (
        <span className="assistant-feedback-comment">
          <label htmlFor={`fb-${messageId}`} className="assistant-sr">Optional comment</label>
          <input
            id={`fb-${messageId}`}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="Anything missing? (optional)"
            maxLength={500}
          />
          <button type="button" className="assistant-mini-btn" disabled={pending} onClick={() => submit('not_helpful')}>Send</button>
        </span>
      )}
    </div>
  )
}

function ExampleList({ data, onLoad, onRun }) {
  const groups = useMemo(() => groupExamples(data?.examples || [], data?.categories || []), [data])
  if (!groups.length) return <p className="assistant-empty">No examples are available right now.</p>

  return (
    <div className="assistant-examples">
      {groups.map((group) => (
        <section key={group.id}>
          <h5>{group.letter ? `${group.letter} · ` : ''}{group.label}</h5>
          {group.examples.map((example) => {
            const badge = exampleBadge(example)
            return (
              <article className="assistant-example" key={example.id}>
                <div className="assistant-example-top">
                  <strong>{example.title}</strong>
                  <span className={`assistant-tag assistant-tag--${badge.tone}`}>{badge.label}</span>
                </div>
                <p className="assistant-example-prompt">“{example.prompt}”</p>
                <p className="assistant-example-objective">{example.learning_objective}</p>
                {example.illustrative_notice && (
                  <p className="assistant-example-notice">{example.illustrative_notice}</p>
                )}
                <div className="assistant-example-actions">
                  <button type="button" className="assistant-mini-btn" onClick={() => onLoad(example.prompt)}>Load into chat</button>
                  <button type="button" className="assistant-mini-btn assistant-mini-btn--primary" onClick={() => onRun(example.prompt)}>Try this example</button>
                </div>
              </article>
            )
          })}
        </section>
      ))}
    </div>
  )
}

export default function AssistantBubble({
  page = null,
  onNavigate,
  onOpenGuides,
  openRequest = null,
  demoMode = false,
}) {
  const [isOpen, setIsOpen] = useState(false)
  const [isClosing, setIsClosing] = useState(false)
  const [messages, setMessages] = useState([{ id: 'welcome', role: 'assistant', content: WELCOME.content, suggestions: WELCOME.suggestions }])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [retryText, setRetryText] = useState('')
  const [notice, setNotice] = useState('')
  const [showExamples, setShowExamples] = useState(false)
  const [examples, setExamples] = useState(null)
  const [examplesError, setExamplesError] = useState('')
  const [health, setHealth] = useState(null)
  const [healthError, setHealthError] = useState('')
  const [showHealth, setShowHealth] = useState(false)
  const [showReport, setShowReport] = useState(false)

  const bodyRef = useRef(null)
  const inputRef = useRef(null)
  const sessionId = useRef(getSessionId())
  const handledRequest = useRef(null)
  const noticeTimer = useRef(null)

  const flash = useCallback((text) => {
    setNotice(text)
    window.clearTimeout(noticeTimer.current)
    noticeTimer.current = window.setTimeout(() => setNotice(''), 2600)
  }, [])

  useEffect(() => () => window.clearTimeout(noticeTimer.current), [])

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [messages, isLoading, showExamples, showHealth, showReport])

  const toggleOpen = useCallback(() => {
    setIsOpen((open) => {
      if (open) return false
      window.requestAnimationFrame(() => inputRef.current?.focus())
      return true
    })
  }, [])

  const close = useCallback(() => {
    setIsClosing(true)
    window.setTimeout(() => {
      setIsOpen(false)
      setIsClosing(false)
    }, 200) // matches the pop-out animation
  }, [])

  // ── Sending ────────────────────────────────────────────────────────────
  const send = useCallback(
    async (rawText, { retry = false } = {}) => {
      const text = normalizeMessage(rawText)
      if (!text || isLoading) return

      const history = mergeHistory(
        messages.filter((msg) => msg.id !== 'welcome' && !msg.pending),
      )
      const userMessage = { id: `u-${Date.now()}`, role: 'user', content: text }
      const placeholder = { id: `a-${Date.now()}`, role: 'assistant', content: '', pending: true }

      setMessages((prev) => [...prev, userMessage, placeholder])
      setInput('')
      setIsLoading(true)
      setRetryText('')

      try {
        const payload = buildChatPayload({
          message: text,
          sessionId: sessionId.current,
          page,
          demoMode,
          history,
        })
        const data = await supportApi.chat(payload)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === placeholder.id
              ? {
                  id: placeholder.id,
                  role: 'assistant',
                  content: data.answer || 'The assistant returned an empty answer.',
                  data,
                }
              : msg,
          ),
        )
      } catch (err) {
        const { message, retryable } = describeError(err?.status ?? 0, err?.payload)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === placeholder.id
              ? {
                  id: placeholder.id,
                  role: 'assistant',
                  content: message,
                  error: true,
                  retryable,
                }
              : msg,
          ),
        )
        setRetryText(retryable ? text : '')
        if (!retryable) flash('That request cannot be retried — see the message for what to change.')
      } finally {
        setIsLoading(false)
      }
    },
    [demoMode, flash, isLoading, messages, page],
  )

  // ── Examples / health panels ───────────────────────────────────────────
  const loadExamples = useCallback(async () => {
    if (examples || examplesError) return
    try {
      setExamples(await supportApi.examples())
    } catch (err) {
      setExamplesError(describeError(err?.status ?? 0, err?.payload).message)
    }
  }, [examples, examplesError])

  const toggleExamples = useCallback(() => {
    setShowExamples((open) => {
      if (!open) {
        setShowHealth(false)
        setShowReport(false)
        loadExamples()
      }
      return !open
    })
  }, [loadExamples])

  const loadHealth = useCallback(async () => {
    setHealthError('')
    try {
      setHealth(await supportApi.health())
    } catch (err) {
      setHealthError(describeError(err?.status ?? 0, err?.payload).message)
    }
  }, [])

  const toggleHealth = useCallback(() => {
    setShowHealth((open) => {
      if (!open) {
        setShowExamples(false)
        setShowReport(false)
        loadHealth()
      }
      return !open
    })
  }, [loadHealth])

  const toggleReport = useCallback(() => {
    setShowReport((open) => {
      if (!open) {
        setShowExamples(false)
        setShowHealth(false)
      }
      return !open
    })
  }, [])

  const restart = useCallback(async () => {
    try {
      await supportApi.resetSession(sessionId.current)
    } catch {
      // A reset that cannot reach the server still clears this view; the server
      // session expires on its own.
    }
    setMessages([{ id: `welcome-${Date.now()}`, role: 'assistant', content: WELCOME.content, suggestions: WELCOME.suggestions }])
    setRetryText('')
    flash('Conversation restarted.')
  }, [flash])

  // ── Quick actions ──────────────────────────────────────────────────────
  const runAction = useCallback(
    (action) => {
      const resolved = resolveAction(action)
      if (!resolved) {
        flash('That action is not available.')
        return
      }
      if (resolved.mode === 'navigate') {
        if (resolved.tab === 'guide' && onOpenGuides) {
          onOpenGuides()
        } else if (onNavigate) {
          onNavigate(resolved.tab)
        } else {
          flash('That section is not reachable from here.')
          return
        }
        flash(`Opened ${resolved.label || resolved.tab}.`)
        return
      }
      const command = clientCommand(resolved.command)
      if (!command) return
      if (command.restart) return void restart()
      if (command.report) {
        setShowExamples(false)
        setShowHealth(false)
        setShowReport(true)
        return
      }
      if (resolved.command === 'demo') {
        setShowExamples(true)
        void loadExamples()
        return
      }
      if (command.note) flash(command.note)
      void send(command.message)
    },
    [flash, loadExamples, onNavigate, onOpenGuides, restart, send],
  )

  // The workspace can ask the assistant to open with a specific example prompt.
  useEffect(() => {
    if (!openRequest || handledRequest.current === openRequest.id) return
    handledRequest.current = openRequest.id
    setIsOpen(true)
    if (openRequest.mode === 'send') {
      void send(openRequest.prompt)
    } else {
      setInput(openRequest.prompt)
      window.requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [openRequest, send])

  useEffect(() => {
    if (!isOpen) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') close()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [close, isOpen])

  const panel = (
    <div className="assistant-bubble-container">
      {!isOpen && !isClosing && (
        <button
          className="assistant-bubble-btn"
          onClick={toggleOpen}
          aria-label="Open the VIDHIVEDA support assistant"
          aria-expanded={false}
        >
          <Icon name="sparkles" size={24} />
          <div className="assistant-tooltip">Ask VIDHIVEDA</div>
        </button>
      )}

      {(isOpen || isClosing) && (
        <div
          className={`assistant-window ${isClosing ? 'closing' : ''}`}
          role="dialog"
          aria-label="VIDHIVEDA support assistant"
        >
          <header className="assistant-header">
            <div className="assistant-header-title">
              <div className="status-dot"></div>
              <div>
                <h3>VIDHIVEDA Support</h3>
                <small>
                  User guide &amp; support assistant
                  {demoMode ? ' · demo mode' : ''}
                </small>
              </div>
            </div>
            <div className="assistant-header-actions">
              <button className="assistant-icon-btn" onClick={restart} title="Restart conversation" aria-label="Restart conversation">
                <Icon name="refresh" size={16} />
              </button>
              <button className="assistant-icon-btn" onClick={close} title="Close" aria-label="Close assistant">
                <Icon name="close" size={18} />
              </button>
            </div>
          </header>

          <div className="assistant-toolbar" role="toolbar" aria-label="Assistant shortcuts">
            <button type="button" className={`assistant-chip ${showExamples ? 'active' : ''}`} onClick={toggleExamples}>
              Explore Examples
            </button>
            <button type="button" className={`assistant-chip ${showHealth ? 'active' : ''}`} onClick={toggleHealth}>
              System Status
            </button>
            <button type="button" className={`assistant-chip ${showReport ? 'active' : ''}`} onClick={toggleReport}>
              Report a Problem
            </button>
            <button type="button" className="assistant-chip" onClick={() => runAction({ kind: 'navigate', target: 'research', label: 'Open Legal Research' })}>
              Open Legal Research
            </button>
            <button type="button" className="assistant-chip" onClick={() => runAction({ kind: 'navigate', target: 'settings', label: 'Open Theme Settings' })}>
              Theme Settings
            </button>
          </div>

          <div className="assistant-body" ref={bodyRef} aria-live="polite">
            {showExamples && (
              <section className="assistant-panel" aria-label="Example gallery">
                <header>
                  <h4>Explore examples</h4>
                  {onOpenGuides && (
                    <button type="button" className="assistant-mini-btn" onClick={onOpenGuides}>Open full gallery</button>
                  )}
                </header>
                {examplesError ? (
                  <p className="assistant-error-inline">{examplesError}</p>
                ) : examples ? (
                  <>
                    <p className="assistant-panel-note">
                      Every example is labelled <strong>verified project data</strong> or an{' '}
                      <strong>illustrative teaching example</strong>. Nothing here stages a fake search, citation or prediction.
                    </p>
                    <ExampleList
                      data={examples}
                      onLoad={(prompt) => { setInput(prompt); inputRef.current?.focus(); flash('Prompt loaded — review it, then send.') }}
                      onRun={(prompt) => send(prompt)}
                    />
                  </>
                ) : (
                  <p className="assistant-empty">Loading examples…</p>
                )}
              </section>
            )}

            {showReport && (
              <ReportProblemForm
                page={page}
                sessionId={sessionId.current}
                onClose={() => setShowReport(false)}
              />
            )}

            {showHealth && (
              <section className="assistant-panel" aria-label="Support system status">
                <header>
                  <h4>Support system status</h4>
                  <button type="button" className="assistant-mini-btn" onClick={loadHealth}>Re-check</button>
                </header>
                {healthError ? (
                  <p className="assistant-error-inline">{healthError}</p>
                ) : health ? (
                  <>
                    <p className="assistant-panel-note">
                      Overall: <span className={`assistant-tag assistant-tag--${healthTone(health)}`}>{health.status}</span>
                    </p>
                    <ul className="assistant-health">
                      {healthRows(health).map((row) => (
                        <li key={row.label}><span>{row.label}</span><strong>{row.value}</strong></li>
                      ))}
                    </ul>
                    {health.degraded_reasons?.length > 0 && (
                      <details className="assistant-health-details">
                        <summary>Not fully healthy ({health.degraded_reasons.length})</summary>
                        <ul>{health.degraded_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
                      </details>
                    )}
                  </>
                ) : (
                  <p className="assistant-empty">Running health checks…</p>
                )}
              </section>
            )}

            {messages.map((msg) => {
              const isUser = msg.role === 'user'
              const actions = msg.data?.quick_actions || []
              return (
                <div className={`assistant-msg-wrapper ${isUser ? 'user' : 'ai'}`} key={msg.id}>
                  <div className={`assistant-msg ${msg.error ? 'assistant-msg--error' : ''}`}>
                    {msg.pending ? (
                      <div className="typing-indicator" role="status" aria-label="Assistant is answering">
                        <div className="typing-dot"></div>
                        <div className="typing-dot"></div>
                        <div className="typing-dot"></div>
                      </div>
                    ) : (
                      <>
                        {renderText(msg.content)}
                        {msg.error && (
                          <div className="assistant-msg-actions">
                            {msg.retryable && (
                              <button type="button" className="assistant-mini-btn assistant-mini-btn--primary" onClick={() => send(retryText, { retry: true })}>
                                Retry
                              </button>
                            )}
                            <button type="button" className="assistant-mini-btn" onClick={() => send('What is the system status?')}>
                              Check status
                            </button>
                            {onOpenGuides && (
                              <button type="button" className="assistant-mini-btn" onClick={onOpenGuides}>Troubleshooting articles</button>
                            )}
                          </div>
                        )}
                      </>
                    )}
                  </div>

                  {msg.suggestions && (
                    <div className="assistant-suggestions">
                      {msg.suggestions.map((suggestion) => (
                        <button key={suggestion} className="assistant-suggestion-btn" onClick={() => send(suggestion)}>
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  )}

                  {msg.data && !isUser && (
                    <>
                      <div className="assistant-provenance">
                        <span className={`assistant-tag assistant-tag--${msg.data.generated ? 'green' : 'neutral'}`}>
                          {kindLabel(msg.data.kind)}
                        </span>
                        <span>{originLabel(msg.data.origin, msg.data.generated)}</span>
                        {msg.data.demo && <span className="assistant-tag assistant-tag--gold">demo</span>}
                      </div>

                      {msg.data.degraded?.length > 0 && (
                        <p className="assistant-degraded">Degraded: {msg.data.degraded.join('; ')}</p>
                      )}

                      {msg.data.sources?.length > 0 && (
                        <div className="assistant-sources">
                          <h4>References · support documentation</h4>
                          {msg.data.sources.map((source) => (
                            <div className="assistant-source-item" key={source.id}>
                              <strong>{source.title}</strong>
                              <span>
                                {[source.category, source.match && `match: ${source.match}`, source.updated].filter(Boolean).join(' · ')}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}

                      {msg.data.follow_ups?.length > 0 && (
                        <div className="assistant-suggestions">
                          {msg.data.follow_ups.map((question) => (
                            <button key={question} className="assistant-suggestion-btn" onClick={() => send(question)}>
                              {question}
                            </button>
                          ))}
                        </div>
                      )}

                      {actions.length > 0 && (
                        <div className="assistant-actions">
                          {actions.map((action) => (
                            <button key={action.id} type="button" className="assistant-action-chip" onClick={() => runAction(action)}>
                              {action.label}
                            </button>
                          ))}
                        </div>
                      )}

                      <div className="assistant-msg-actions">
                        <CopyButton text={msg.content} />
                        <FeedbackControls
                          messageId={msg.data.message_id}
                          sessionId={sessionId.current}
                          page={page}
                          onDone={() => {}}
                        />
                      </div>
                    </>
                  )}
                </div>
              )
            })}
          </div>

          <footer className="assistant-footer">
            {notice && <p className="assistant-notice" role="status">{notice}</p>}
            <div className="assistant-input-form">
              <textarea
                className="assistant-input"
                placeholder="Ask how VIDHIVEDA works, or describe a problem…"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    send(input)
                  }
                }}
                disabled={isLoading}
                rows={1}
                aria-label="Support question"
                ref={inputRef}
              />
              <MicButton
                value={input}
                onChange={setInput}
                variant="chat"
                size={16}
                title="Dictate your question"
              />
              <button
                className="assistant-send-btn"
                onClick={() => send(input)}
                disabled={!input.trim() || isLoading}
                title="Send message"
                aria-label="Send message"
              >
                <Icon name="arrow" size={16} />
              </button>
            </div>
            <p className="assistant-disclaimer">
              Support assistant · answers from project documentation, never legal advice.
              {page ? ` Context: ${page}.` : ''}
            </p>
          </footer>
        </div>
      )}
    </div>
  )

  return typeof document !== 'undefined' ? createPortal(panel, document.body) : panel
}
