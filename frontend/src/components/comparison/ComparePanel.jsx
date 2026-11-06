import { useEffect, useRef, useState } from 'react'
import Icon from '../Icon.jsx'
import MicButton from '../MicButton.jsx'
import { API_BASE } from '../../services/apiBase.js'
import {
  LEGAL_DEMO_EXAMPLES,
  CORPUS_SNAPSHOT,
  exampleFormValues,
  matchPresetCases,
} from '../../data/legalDemoExamples.js'
import './comparison.css'

const EMPTY = {
  legal_issue: '',
  case_facts: '',
  provisions: '',
  court: '',
  year_from: '',
  year_to: '',
  a_label: 'Party A',
  a_position: '',
  b_label: 'Party B',
  b_position: '',
}

const LIMITS = {
  issue: 2000,
  facts: 8000,
  position: 6000,
  label: 120,
}

const MODE_META = {
  two_scenarios: {
    label: 'Compare Two Cases',
    description:
      'Compare two different case situations and see what is similar, what is different, and what legal judgments support each side.',
    example: 'Example: Compare two cases involving personal liberty.',
    action: 'Compare Two Cases',
    icon: 'compare',
  },
  single_scenario: {
    label: 'Analyse One Case',
    description:
      'Enter one legal situation and explore relevant judgments, legal arguments, and supporting legal information.',
    example: 'Example: Research whether a particular action falls under private defence.',
    action: 'Analyse One Case',
    icon: 'scale',
  },
}

const STEPS = {
  two_scenarios: [
    { key: 'question', title: 'What legal question do you want to explore?', short: 'Legal question' },
    { key: 'background', title: 'Add the common background', short: 'Background' },
    { key: 'caseA', title: 'Describe the first case', short: 'Case A' },
    { key: 'caseB', title: 'Describe the second case', short: 'Case B' },
    { key: 'filters', title: 'Add legal details', short: 'Legal details' },
    { key: 'review', title: 'Review and compare', short: 'Review' },
  ],
  single_scenario: [
    { key: 'question', title: 'What legal issue do you want to research?', short: 'Legal issue' },
    { key: 'situation', title: 'Describe the situation', short: 'Situation' },
    { key: 'provisions', title: 'Add legal provisions', short: 'Provisions' },
    { key: 'filters', title: 'Additional filters', short: 'Filters' },
  ],
}

const EVIDENCE_TONE = {
  SUFFICIENT_EVIDENCE_FOR_ANALYSIS: 'green',
  LIMITED_EVIDENCE: 'gold',
  INSUFFICIENT_EVIDENCE: 'neutral',
}

const EVIDENCE_LABEL = {
  SUFFICIENT_EVIDENCE_FOR_ANALYSIS: 'Enough material to compare',
  LIMITED_EVIDENCE: 'Limited material found',
  INSUFFICIENT_EVIDENCE: 'Not enough material found',
}

const RESEARCH_STATEMENT =
  'VIDHIVEDA supports legal research. It does not decide which party is legally right or replace professional legal judgment.'

function Badge({ children, tone = 'neutral' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

function FieldTools({ value, label, onClear, micValue, onMicChange }) {
  return (
    <div className="cmp-field-tools">
      {value ? (
        <button
          type="button"
          className="cmp-field-clear"
          onClick={onClear}
          aria-label={`Clear ${label}`}
        >
          Clear
        </button>
      ) : null}
      <MicButton value={micValue} onChange={onMicChange} title={`Dictate ${label}`} />
    </div>
  )
}

function PrecedentSource({ precedent }) {
  const meta =
    [precedent.court, precedent.judgment_date || precedent.year].filter(Boolean).join(' · ') ||
    'Court/date not recorded upstream'

  return (
    <article className="cmp-source-card">
      <div className="cmp-source-head">
        <strong>{precedent.case_name || 'Unnamed document'}</strong>
        {precedent.verified && <Badge tone="green">From indexed corpus</Badge>}
      </div>
      <span className="cmp-meta">{meta}</span>
      {precedent.excerpt && <p className="cmp-source-excerpt">{precedent.excerpt}</p>}
      <div className="cmp-source-foot">
        {precedent.chunk_id ? <span className="cmp-meta">Chunk {precedent.chunk_id}</span> : null}
        {precedent.source_url ? (
          <a
            className="cmp-source-link"
            href={precedent.source_url}
            target="_blank"
            rel="noreferrer"
          >
            Open source <Icon name="arrow" size={12} />
          </a>
        ) : precedent.source ? (
          <span className="cmp-meta">Source: {precedent.source}</span>
        ) : (
          <span className="cmp-meta">No source link recorded</span>
        )}
      </div>
    </article>
  )
}

function SupportColumn({ scenario, title }) {
  if (!scenario) return null
  return (
    <article className="cmp-support">
      <header className="cmp-support-head">
        <h4>{scenario.label || title}</h4>
        <span className="cmp-meta">
          {scenario.supporting_count} supporting · {scenario.contrary_count} contrary
        </span>
      </header>

      <div className="cmp-support-group">
        <span className="answer-label">Retrieved sources supporting this case</span>
        {scenario.supporting_precedents?.length > 0 ? (
          scenario.supporting_precedents.map((precedent, index) => (
            <PrecedentSource key={`${precedent.chunk_id || index}-support`} precedent={precedent} />
          ))
        ) : (
          <p className="cmp-empty">
            No retrieved source was topically aligned with this case in this run.
          </p>
        )}
      </div>

      {scenario.contrary_precedents?.length > 0 && (
        <details className="cmp-subdetails">
          <summary>Retrieved sources cutting against this case ({scenario.contrary_count})</summary>
          <div className="cmp-subdetails-body">
            {scenario.contrary_precedents.map((precedent, index) => (
              <PrecedentSource key={`${precedent.chunk_id || index}-contrary`} precedent={precedent} />
            ))}
          </div>
        </details>
      )}

      {(scenario.weaknesses?.length > 0 || scenario.missing_evidence?.length > 0) && (
        <details className="cmp-subdetails">
          <summary>What VIDHIVEDA noted as weak or missing</summary>
          <div className="cmp-subdetails-body">
            {scenario.weaknesses?.length > 0 && (
              <ul className="cmp-list">
                {scenario.weaknesses.map((item, index) => (
                  <li key={`w-${index}`}>{item}</li>
                ))}
              </ul>
            )}
            {scenario.missing_evidence?.length > 0 && (
              <ul className="cmp-list">
                {scenario.missing_evidence.map((item, index) => (
                  <li key={`m-${index}`}>{item}</li>
                ))}
              </ul>
            )}
          </div>
        </details>
      )}
    </article>
  )
}

function OutcomePredictionCard({ outcome, scenarioA, scenarioB }) {
  if (!outcome) return null

  if (!outcome.available) {
    return (
      <div className="cmp-outcome-box cmp-outcome-box--unavailable">
        <div className="cmp-outcome-head">
          <Badge tone="neutral">Outcome Prediction Unavailable</Badge>
          <span className="cmp-meta">Statistical Model</span>
        </div>
        <p className="cmp-outcome-reason">
          {outcome.reason || 'No trained, evaluated outcome classifier is available.'}
        </p>
        <span className="cmp-meta">
          Retrieval similarity indicates document overlap, never a judicial verdict probability.
        </span>
      </div>
    )
  }

  const perScenario = outcome.per_scenario || {}
  const items = [
    { key: 'scenario_a', label: scenarioA?.label || 'Case A', pred: perScenario.scenario_a },
    ...(scenarioB ? [{ key: 'scenario_b', label: scenarioB?.label || 'Case B', pred: perScenario.scenario_b }] : []),
  ].filter((item) => item.pred)

  const percent = (value) => (typeof value === 'number' ? Math.round(value * 100) : null)
  const metrics = outcome.model_metrics || null
  const sameClass =
    items.length === 2 && items[0].pred.label && items[0].pred.label === items[1].pred.label

  return (
    <div className="cmp-outcome-box cmp-outcome-box--experimental">
      <div className="cmp-outcome-head">
        <div className="cmp-outcome-head-group">
          <Badge tone="gold">Experimental model output — not validated</Badge>
          {outcome.model_version && (
            <span className="cmp-outcome-version">Model {outcome.model_version}</span>
          )}
        </div>
        <span className="cmp-meta">
          {outcome.calibration ? `${outcome.calibration} classifier output` : 'classifier output'}
        </span>
      </div>

      <p className="cmp-outcome-reason">
        This is a statistical classification of a historical disposition, computed from the account
        you supplied. It is not a verdict, and it is not a validated forecast of how a court would
        decide. The retrieved precedents above are the primary research evidence.
      </p>

      {metrics && (
        <div className="cmp-outcome-metrics">
          <span className="cmp-meta">
            Held-out test partition: {metrics.test_size ?? '—'} record(s)
            {metrics.test_class_distribution
              ? ` · ${Object.entries(metrics.test_class_distribution)
                  .map(([label, count]) => `${label} ${count}`)
                  .join(', ')}`
              : ''}
          </span>
          <span className="cmp-meta">
            Accuracy {percent(metrics.accuracy) ?? '—'}% · macro F1 {percent(metrics.macro_f1) ?? '—'}%
            {' '}· validation macro F1 {percent(metrics.val_macro_f1) ?? '—'}%
            {' '}· trained on {metrics.n_train ?? '—'} cases
          </span>
        </div>
      )}

      {sameClass && (
        <div className="cmp-low-conf-badge">
          Both accounts were assigned the same class. This model does not distinguish between them
          on the evidence supplied — read the precedent comparison instead.
        </div>
      )}

      <details className="cmp-outcome-details">
        <summary>Show raw model output for each account</summary>
        <div className="cmp-outcome-grid">
          {items.map(({ key, label, pred }) => {
            const isConvicted = pred.label === 'convicted'
            const pct = Math.round((pred.confidence || 0) * 100)
            const probAcquitted = Math.round((pred.probabilities?.acquitted || 0) * 100)
            const probConvicted = Math.round((pred.probabilities?.convicted || 0) * 100)

            return (
              <div key={key} className="cmp-outcome-card">
                <div className="cmp-outcome-card-header">
                  <strong>{label}</strong>
                  <Badge tone={isConvicted ? 'gold' : 'green'}>
                    Model class: {pred.label ? pred.label.toUpperCase() : 'UNKNOWN'}
                  </Badge>
                </div>

                <div className="cmp-outcome-score">
                  <span className="cmp-score-number">{pct}%</span>
                  <span className="cmp-score-label">Model probability (experimental)</span>
                </div>

                <div className="cmp-prob-bar-container">
                  <div className="cmp-prob-bar">
                    <div
                      className="cmp-prob-fill cmp-prob-fill--acquitted"
                      style={{ width: `${probAcquitted}%` }}
                      title={`Acquitted: ${probAcquitted}%`}
                    />
                    <div
                      className="cmp-prob-fill cmp-prob-fill--convicted"
                      style={{ width: `${probConvicted}%` }}
                      title={`Convicted: ${probConvicted}%`}
                    />
                  </div>
                  <div className="cmp-prob-labels">
                    <span>Acquittal: {probAcquitted}%</span>
                    <span>Conviction: {probConvicted}%</span>
                  </div>
                </div>

                {pred.low_confidence && (
                  <div className="cmp-low-conf-badge">
                    Lower model confidence (&lt;60%) — rely primarily on precedent analysis.
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </details>

      {outcome.limitations?.length > 0 && (
        <ul className="answer-limitations">
          {outcome.limitations.map((limitation, index) => (
            <li key={index}>{limitation}</li>
          ))}
        </ul>
      )}

      {outcome.validation && <span className="cmp-meta">{outcome.validation}</span>}

      <div className="cmp-outcome-disclaimer">
        <strong>Research notice:</strong> this estimate comes from an experimental supervised
        classifier trained on a small, curated set of pre-judgment Indian case facts. It is not a
        legal verdict or a judicial forecast.
      </div>
    </div>
  )
}

function ComparativeAnalysisCard({ analysis }) {
  if (!analysis) return null

  return (
    <div className="cmp-analysis-box">
      <div className="cmp-analysis-header">
        <span className="answer-label">Comparative Legal Argument Analysis</span>
        <Badge tone="blue">Research Synthesis</Badge>
      </div>

      {analysis.executive_summary && (
        <p className="cmp-analysis-summary">{analysis.executive_summary}</p>
      )}

      {analysis.key_findings?.length > 0 && (
        <div className="cmp-analysis-section">
          <strong>Key Precedent &amp; Argument Findings</strong>
          <ul className="cmp-findings-list">
            {analysis.key_findings.map((finding, index) => (
              <li key={index}>{finding}</li>
            ))}
          </ul>
        </div>
      )}

      {analysis.outcome_insights?.length > 0 && (
        <div className="cmp-analysis-section">
          <strong>Historical Outcome Insights</strong>
          <ul className="cmp-insights-list">
            {analysis.outcome_insights.map((insight, index) => (
              <li key={index}>{insight}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function ReviewItem({ label, children, onEdit }) {
  return (
    <div className="cmp-review-item">
      <div className="cmp-review-head">
        <span className="answer-label">{label}</span>
        <button type="button" className="cmp-link-btn" onClick={onEdit}>
          Edit
        </button>
      </div>
      <div className="cmp-review-body">{children}</div>
    </div>
  )
}

function SourceTrail({ result }) {
  const merged = new Map()
  for (const precedent of result.precedents || []) {
    const key = precedent.chunk_id || precedent.document_id || precedent.case_name
    if (!key) continue
    merged.set(key, precedent)
  }
  for (const citation of result.citations || []) {
    const key = citation.chunk_id || citation.document_id || citation.case_name
    if (!key || merged.has(key)) continue
    merged.set(key, citation)
  }
  const sources = [...merged.values()]

  if (sources.length === 0) {
    return <p className="cmp-empty">No source passages were retrieved for this request.</p>
  }

  return (
    <div className="cmp-source-list">
      {sources.map((source, index) => (
        <PrecedentSource key={source.chunk_id || source.document_id || index} precedent={source} />
      ))}
    </div>
  )
}

export default function ComparePanel() {
  const [analysisMode, setAnalysisMode] = useState('two_scenarios')
  const [form, setForm] = useState(EMPTY)
  const [step, setStep] = useState(0)
  const [stepError, setStepError] = useState('')
  const [activeExampleId, setActiveExampleId] = useState('')
  const [presetDirty, setPresetDirty] = useState(false)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const wizardRef = useRef(null)
  const resultsRef = useRef(null)
  const legalIssueRef = useRef(null)
  const inFlight = useRef(false)

  const steps = STEPS[analysisMode]
  const activeStep = steps[Math.min(step, steps.length - 1)]
  const isSingle = analysisMode === 'single_scenario'
  const activeExample = LEGAL_DEMO_EXAMPLES.find((item) => item.id === activeExampleId) || null

  const markEdited = () => {
    if (activeExampleId) setPresetDirty(true)
  }

  const setField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }))
    markEdited()
    setStepError('')
  }

  const update = (key) => (event) => setField(key, event.target.value)

  const changeMode = (mode) => {
    if (mode === analysisMode) {
      wizardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      legalIssueRef.current?.focus({ preventScroll: true })
      return
    }
    setAnalysisMode(mode)
    setStep(0)
    setStepError('')
    setResult(null)
    setError('')
    setActiveExampleId('')
    setPresetDirty(false)
  }

  const valuesComplete = (values, mode) =>
    values.legal_issue.trim().length >= 2 &&
    values.a_position.trim().length >= 2 &&
    (mode === 'single_scenario' || values.b_position.trim().length >= 2)

  /** Per-step validation. Returns '' when the step can be left. */
  const validateStep = (index, values = form, mode = analysisMode) => {
    const key = STEPS[mode][index]?.key
    if (key === 'question' && values.legal_issue.trim().length < 2) {
      return 'Enter a legal question of at least 2 characters.'
    }
    if (key === 'caseA' && values.a_position.trim().length < 2) {
      return 'Describe the first case in at least 2 characters.'
    }
    if (key === 'situation' && values.a_position.trim().length < 2) {
      return 'Describe the situation in at least 2 characters.'
    }
    if (key === 'caseB' && values.b_position.trim().length < 2) {
      return 'Describe the second case in at least 2 characters.'
    }
    if (key === 'filters') {
      const from = values.year_from.trim()
      const to = values.year_to.trim()
      if (from && !/^\d{4}$/.test(from)) return 'Enter the start year as four digits, for example 1950.'
      if (to && !/^\d{4}$/.test(to)) return 'Enter the end year as four digits, for example 1951.'
      if (from && to && Number(from) > Number(to)) return 'The start year cannot be later than the end year.'
      if ((from && Number(from) < 1800) || (to && Number(to) < 1800)) {
        return 'Enter a year between 1800 and 2100.'
      }
    }
    return ''
  }

  const goNext = () => {
    const message = validateStep(step)
    if (message) {
      setStepError(message)
      return
    }
    setStepError('')
    setStep((current) => Math.min(current + 1, steps.length - 1))
  }

  const goBack = () => {
    setStepError('')
    setStep((current) => Math.max(current - 1, 0))
  }

  const goToStep = (index) => {
    if (index > step) {
      const message = validateStep(step)
      if (message) {
        setStepError(message)
        return
      }
    }
    setStepError('')
    setStep(index)
  }

  const runComparison = async (values, mode) => {
    if (inFlight.current || !valuesComplete(values, mode)) return
    const single = mode === 'single_scenario'
    inFlight.current = true
    setLoading(true)
    setError('')
    try {
      const payload = {
        legal_issue: values.legal_issue.trim(),
        case_facts: values.case_facts.trim() || undefined,
        provisions: values.provisions
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean)
          .slice(0, 40),
        court: values.court.trim() || undefined,
        year_from: values.year_from.trim() ? parseInt(values.year_from, 10) : undefined,
        year_to: values.year_to.trim() ? parseInt(values.year_to, 10) : undefined,
        scenario_a: {
          label: values.a_label.trim() || (single ? 'Claimant / Accused' : 'Party A'),
          position: values.a_position.trim(),
        },
        scenario_b: single
          ? undefined
          : { label: values.b_label.trim() || 'Party B', position: values.b_position.trim() },
        top_k: 8,
      }
      const res = await fetch(`${API_BASE}/api/comparison`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail.detail || `Comparison request failed (${res.status})`)
      }
      setResult(await res.json())
    } catch (err) {
      setResult(null)
      setError(
        err instanceof TypeError
          ? 'Could not reach the backend. Check that the API is running, then try again.'
          : err.message || 'The comparison could not be completed.',
      )
    } finally {
      inFlight.current = false
      setLoading(false)
    }
  }

  const submit = (event) => {
    event?.preventDefault()
    if (!valuesComplete(form, analysisMode)) {
      const first = STEPS[analysisMode].findIndex((_, index) => validateStep(index))
      if (first >= 0) {
        setStep(first)
        setStepError(validateStep(first))
      }
      return
    }
    for (let index = 0; index < steps.length; index += 1) {
      const message = validateStep(index)
      if (message) {
        setStep(index)
        setStepError(message)
        return
      }
    }
    runComparison(form, analysisMode)
  }

  const clearForm = () => {
    if (!window.confirm('Clear all fields and start again?')) return
    setForm(EMPTY)
    setStep(0)
    setStepError('')
    setActiveExampleId('')
    setPresetDirty(false)
    setResult(null)
    setError('')
  }

  const startNew = () => {
    if (!window.confirm('Start a new comparison? Your current form entries will be cleared.')) return
    setForm(EMPTY)
    setStep(0)
    setStepError('')
    setActiveExampleId('')
    setPresetDirty(false)
    setResult(null)
    setError('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const scrollToResults = () =>
    resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  const loadExample = (example) => {
    if (presetDirty && !window.confirm('Replace your edited fields with this example?')) return
    const values = exampleFormValues(example, EMPTY)
    setAnalysisMode(example.mode)
    setForm(values)
    setStep(0)
    setStepError('')
    setActiveExampleId(example.id)
    setPresetDirty(false)
    setError('')
    setResult(null)
    window.requestAnimationFrame(() => {
      wizardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      legalIssueRef.current?.focus({ preventScroll: true })
    })
  }

  const restoreExample = () => {
    if (!activeExample) return
    if (presetDirty && !window.confirm('Discard your edits and restore the example fields?')) return
    const values = exampleFormValues(activeExample, EMPTY)
    setForm(values)
    setStep(0)
    setStepError('')
    setPresetDirty(false)
    setError('')
    setResult(null)
  }

  useEffect(() => {
    if (result) resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [result])

  const outcome = result?.outcome_prediction
  const quality = result?.evidence_quality
  const presetMatches = result && activeExample ? matchPresetCases(result, activeExample) : []
  const presetFound = presetMatches.some((match) => match.retrievedAs)
  const evidence = result?.evidence_comparison
  const bothCount = evidence?.retrieved_for_both?.length || 0
  const onlyACount = evidence?.retrieved_for_scenario_a_only?.length || 0
  const onlyBCount = evidence?.retrieved_for_scenario_b_only?.length || 0
  const precedentCount = result?.precedents?.length || 0
  const resultLabels = {
    a: result?.scenario_a?.label || 'Case A',
    b: result?.scenario_b?.label || 'Case B',
  }

  const filterSummary = () => {
    const parts = []
    if (form.provisions.trim()) parts.push(`Provisions: ${form.provisions.trim()}`)
    if (form.court.trim()) parts.push(`Court: ${form.court.trim()}`)
    if (form.year_from.trim() || form.year_to.trim()) {
      const from = form.year_from.trim() || 'earliest'
      const to = form.year_to.trim() || 'latest'
      parts.push(`Year: ${from} to ${to}`)
    }
    return parts.length > 0 ? parts : ['No extra filters — the search covers the whole indexed corpus.']
  }

  return (
    <section className="page-section section-container cmp-page">
      <div className="section-heading cmp-intro">
        <div>
          <span className="eyebrow">Legal research</span>
          <h2>Compare Legal Cases</h2>
        </div>
        <p>
          Explore how two cases are similar or different, find legal support for each side, and
          understand the relevant judgments.
        </p>
      </div>

      <section className="cmp-modes-section" aria-labelledby="cmp-modes-title">
        <h3 id="cmp-modes-title" className="cmp-section-title">
          How would you like to begin?
        </h3>
        <div className="cmp-modes" role="group" aria-label="Choose a comparison mode">
          {Object.entries(MODE_META).map(([mode, meta]) => {
            const selected = analysisMode === mode
            return (
              <article
                key={mode}
                className={`cmp-mode-card ${selected ? 'cmp-mode-card--active' : ''}`}
              >
                <div className="cmp-mode-card__top">
                  <span className="cmp-mode-card__icon" aria-hidden="true">
                    <Icon name={meta.icon} size={20} />
                  </span>
                  {selected && (
                    <span className="cmp-mode-selected">
                      <Icon name="check" size={12} /> Selected
                    </span>
                  )}
                </div>
                <h4>{meta.label}</h4>
                <p>{meta.description}</p>
                <span className="cmp-mode-card__example">{meta.example}</span>
                <button
                  type="button"
                  className={`cmp-mode-btn ${selected ? 'cmp-mode-btn--selected' : ''}`}
                  onClick={() => changeMode(mode)}
                  aria-pressed={selected}
                >
                  <Icon name={meta.icon} size={15} /> {meta.action}
                </button>
              </article>
            )
          })}
        </div>
      </section>

      <section className="cmp-examples" aria-labelledby="cmp-examples-title">
        <div className="cmp-examples-head">
          <div>
            <h3 id="cmp-examples-title">Try Real Indian Court Cases</h3>
            <p>
              Not sure what to enter? Select a real published judgment and we will fill in the
              research form for you.
            </p>
          </div>
        </div>

        <div className="cmp-example-grid">
          {LEGAL_DEMO_EXAMPLES.map((example) => {
            const isActive = example.id === activeExampleId
            return (
              <article
                key={example.id}
                className={`cmp-example ${isActive ? 'cmp-example--active' : ''}`}
              >
                <div className="cmp-example-top">
                  <Badge tone={example.mode === 'two_scenarios' ? 'gold' : 'neutral'}>
                    {example.mode === 'two_scenarios' ? 'Two cases' : 'One case'}
                  </Badge>
                  <span className="cmp-meta">{example.year_label}</span>
                </div>
                <h4>{example.title}</h4>
                <span className="cmp-example-topic">
                  {example.court} · {example.topic}
                </span>
                <p className="cmp-example-summary">{example.demonstrates}</p>

                <a
                  className="cmp-source-link"
                  href={example.sources[0].url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Read the published judgment <Icon name="arrow" size={12} />
                </a>

                <div className="cmp-example-actions">
                  <button
                    type="button"
                    className="cmp-example-btn cmp-example-btn--primary"
                    onClick={() => loadExample(example)}
                    aria-pressed={isActive}
                  >
                    <Icon name="check" size={14} /> Use Example
                  </button>
                </div>

                <details className="cmp-example-details">
                  <summary>View Details</summary>
                  <div className="cmp-example-details-body">
                    <span className="answer-label">Applicable provisions</span>
                    <p className="cmp-meta">{example.provisions_display}</p>
                    <span className="answer-label">What this example shows</span>
                    <p className="cmp-meta">{example.scope_note}</p>
                    <span className="answer-label">Published judgment links (external)</span>
                    <div className="cmp-example-links">
                      {example.sources.map((source) => (
                        <a key={source.url} href={source.url} target="_blank" rel="noreferrer">
                          {source.label} <Icon name="arrow" size={12} />
                        </a>
                      ))}
                    </div>
                    <span className="answer-label">Indexed corpus status</span>
                    <ul className="cmp-preset-cases">
                      {example.cases.map((item) => (
                        <li key={item.name}>
                          <span>
                            {item.name} ({item.year})
                          </span>
                          <Badge tone={item.corpus.present ? 'green' : 'neutral'}>
                            {item.corpus.present ? 'In indexed corpus' : 'External reference only'}
                          </Badge>
                        </li>
                      ))}
                    </ul>
                    <p className="cmp-meta">
                      External links open the published judgment. Only passages marked “From
                      indexed corpus” come from VIDHIVEDA’s ChromaDB index.
                    </p>
                  </div>
                </details>
              </article>
            )
          })}
        </div>

        <p className="cmp-examples-note">
          Sources checked {CORPUS_SNAPSHOT.checked_at}. {CORPUS_SNAPSHOT.note} An example fills the
          form below; it never supplies a prepared answer. Results always come from a real request.
        </p>
      </section>

      {activeExample && (
        <div className="cmp-loaded" role="status" aria-live="polite">
          <div className="cmp-loaded-main">
            <strong className="cmp-loaded-title">
              <Icon name="check" size={16} /> Example loaded successfully
              {presetDirty ? ' (edited)' : ''}
            </strong>
            <p className="cmp-meta">
              {activeExample.title} · {activeExample.court} · {activeExample.year_label}
            </p>
            <p className="cmp-meta">{activeExample.scope_note}</p>
            <div className="cmp-loaded-sources">
              <span className="answer-label">Published judgment links (external)</span>
              <div className="cmp-example-links">
                {activeExample.sources.map((source) => (
                  <a key={source.url} href={source.url} target="_blank" rel="noreferrer">
                    {source.label} <Icon name="arrow" size={12} />
                  </a>
                ))}
              </div>
            </div>
            <ul className="cmp-preset-cases">
              {activeExample.cases.map((item) => (
                <li key={item.name}>
                  <span>
                    {item.name} ({item.year})
                  </span>
                  <Badge tone={item.corpus.present ? 'green' : 'neutral'}>
                    {item.corpus.present ? 'In indexed corpus' : 'External reference only'}
                  </Badge>
                </li>
              ))}
            </ul>
          </div>
          <div className="cmp-loaded-actions">
            {presetDirty && (
              <button type="button" className="cmp-btn cmp-btn--ghost" onClick={restoreExample}>
                <Icon name="refresh" size={14} /> Reset to example
              </button>
            )}
            {result && (
              <button type="button" className="cmp-btn cmp-btn--ghost" onClick={scrollToResults}>
                Show results <Icon name="arrow" size={14} />
              </button>
            )}
          </div>
        </div>
      )}

      <div className="cmp-wizard" ref={wizardRef}>
        <div className="cmp-wizard-head">
          <div>
            <span className="eyebrow">{MODE_META[analysisMode].label}</span>
            <h3>{activeStep.title}</h3>
          </div>
          <span className="cmp-step-count" aria-live="polite">
            Step {step + 1} of {steps.length}
          </span>
        </div>

        <ol className="cmp-stepper" aria-label="Form steps">
          {steps.map((item, index) => {
            const state = index === step ? 'active' : index < step ? 'done' : 'upcoming'
            return (
              <li key={item.key}>
                <button
                  type="button"
                  className={`cmp-step-chip cmp-step-chip--${state}`}
                  onClick={() => goToStep(index)}
                  aria-current={index === step ? 'step' : undefined}
                >
                  <span className="cmp-step-num">
                    {index < step ? <Icon name="check" size={12} /> : index + 1}
                  </span>
                  <span className="cmp-step-label">{item.short}</span>
                </button>
              </li>
            )
          })}
        </ol>

        <form className="cmp-form" onSubmit={submit} noValidate>
          {activeStep.key === 'question' && (
            <div className="cmp-step">
              <p className="cmp-step-help">
                {isSingle
                  ? 'Start with the legal issue you want to understand. VIDHIVEDA will look for judgments about it.'
                  : 'Start with the legal issue that connects the two cases. Keep it as a question if you can.'}
              </p>
              <div className="cmp-field">
                <div className="cmp-field-header">
                  <label className="cmp-label" htmlFor="cmp-legal-issue">
                    What is the main legal question? <span className="cmp-req">Required</span>
                  </label>
                  <FieldTools
                    value={form.legal_issue}
                    label="the legal question"
                    onClear={() => setField('legal_issue', '')}
                    micValue={form.legal_issue}
                    onMicChange={(value) => setField('legal_issue', value)}
                  />
                </div>
                <p className="cmp-help" id="cmp-legal-issue-help">
                  Write the legal issue you want to understand or compare.
                </p>
                <textarea
                  id="cmp-legal-issue"
                  value={form.legal_issue}
                  onChange={update('legal_issue')}
                  ref={legalIssueRef}
                  rows={3}
                  maxLength={LIMITS.issue}
                  aria-describedby="cmp-legal-issue-help"
                  aria-invalid={Boolean(stepError)}
                  placeholder={
                    isSingle
                      ? 'Example: What legal principles apply to anticipatory bail?'
                      : 'Example: How does the right to personal liberty apply under Article 21?'
                  }
                />
                <span className="cmp-counter">
                  {form.legal_issue.length}/{LIMITS.issue}
                </span>
              </div>
            </div>
          )}

          {activeStep.key === 'background' && (
            <div className="cmp-step">
              <p className="cmp-step-help">
                Shared facts give both cases the same starting point. This step is optional.
              </p>
              <div className="cmp-field">
                <div className="cmp-field-header">
                  <label className="cmp-label" htmlFor="cmp-case-facts">
                    Are there any facts common to both cases? <span className="cmp-opt">Optional</span>
                  </label>
                  <FieldTools
                    value={form.case_facts}
                    label="the common background"
                    onClear={() => setField('case_facts', '')}
                    micValue={form.case_facts}
                    onMicChange={(value) => setField('case_facts', value)}
                  />
                </div>
                <p className="cmp-help" id="cmp-case-facts-help">
                  Enter facts that apply to both sides. You can leave this empty when the cases have
                  different backgrounds.
                </p>
                <textarea
                  id="cmp-case-facts"
                  value={form.case_facts}
                  onChange={update('case_facts')}
                  rows={4}
                  maxLength={LIMITS.facts}
                  aria-describedby="cmp-case-facts-help"
                  placeholder="Enter the common facts, if any."
                />
                <span className="cmp-counter">
                  {form.case_facts.length}/{LIMITS.facts}
                </span>
              </div>
            </div>
          )}

          {(activeStep.key === 'caseA' || activeStep.key === 'situation') && (
            <div className="cmp-step">
              <p className="cmp-step-help">
                {isSingle
                  ? 'Explain the situation in your own words. You do not need legal language.'
                  : 'Describe the first situation. Keep it to what this side says happened and what it argues.'}
              </p>
              <div className="cmp-scenario-card">
                <h4>{isSingle ? 'The situation' : 'Case A — First situation'}</h4>
                <div className="cmp-field">
                  <div className="cmp-field-header">
                    <label className="cmp-label" htmlFor="cmp-a-label">
                      {isSingle ? 'Who or what is involved?' : 'Who or what is the first side?'}{' '}
                      <span className="cmp-opt">Optional</span>
                    </label>
                    <MicButton
                      value={form.a_label}
                      onChange={(value) => setField('a_label', value)}
                      title="Dictate a name for this side"
                    />
                  </div>
                  <input
                    id="cmp-a-label"
                    value={form.a_label}
                    onChange={update('a_label')}
                    maxLength={LIMITS.label}
                    placeholder={
                      isSingle
                        ? 'Example: The applicant'
                        : 'Example: The petitioner challenged the restriction imposed on personal liberty.'
                    }
                  />
                </div>
                <div className="cmp-field">
                  <div className="cmp-field-header">
                    <label className="cmp-label" htmlFor="cmp-a-position">
                      {isSingle ? 'What happened?' : 'What are the facts or arguments for this side?'}{' '}
                      <span className="cmp-req">Required</span>
                    </label>
                    <FieldTools
                      value={form.a_position}
                      label="the first case description"
                      onClear={() => setField('a_position', '')}
                      micValue={form.a_position}
                      onMicChange={(value) => setField('a_position', value)}
                    />
                  </div>
                  <p className="cmp-help" id="cmp-a-position-help">
                    {isSingle
                      ? 'Explain what happened, who was involved, and any relevant facts you know.'
                      : 'Describe the first case in plain language. Focus on the facts and the argument.'}
                  </p>
                  <textarea
                    id="cmp-a-position"
                    value={form.a_position}
                    onChange={update('a_position')}
                    rows={6}
                    maxLength={LIMITS.position}
                    aria-describedby="cmp-a-position-help"
                    aria-invalid={Boolean(stepError)}
                    placeholder={
                      isSingle
                        ? 'Explain what happened, who was involved, and any relevant facts you know.'
                        : 'Example: The petitioner challenged the restriction imposed on personal liberty.'
                    }
                  />
                  <span className="cmp-counter">
                    {form.a_position.length}/{LIMITS.position}
                  </span>
                </div>
              </div>
            </div>
          )}

          {activeStep.key === 'caseB' && (
            <div className="cmp-step">
              <p className="cmp-step-help">
                Now describe the second situation, keeping its facts separate from the first.
              </p>
              <div className="cmp-scenario-card">
                <h4>Case B — Second situation</h4>
                <div className="cmp-field">
                  <div className="cmp-field-header">
                    <label className="cmp-label" htmlFor="cmp-b-label">
                      Who or what is the second side? <span className="cmp-opt">Optional</span>
                    </label>
                    <MicButton
                      value={form.b_label}
                      onChange={(value) => setField('b_label', value)}
                      title="Dictate a name for the second side"
                    />
                  </div>
                  <input
                    id="cmp-b-label"
                    value={form.b_label}
                    onChange={update('b_label')}
                    maxLength={LIMITS.label}
                    placeholder="Example: The government defended the restriction under the applicable law."
                  />
                </div>
                <div className="cmp-field">
                  <div className="cmp-field-header">
                    <label className="cmp-label" htmlFor="cmp-b-position">
                      What are the facts or arguments for this side?{' '}
                      <span className="cmp-req">Required</span>
                    </label>
                    <FieldTools
                      value={form.b_position}
                      label="the second case description"
                      onClear={() => setField('b_position', '')}
                      micValue={form.b_position}
                      onMicChange={(value) => setField('b_position', value)}
                    />
                  </div>
                  <p className="cmp-help" id="cmp-b-position-help">
                    Describe the second case in plain language. Do not merge it with Case A.
                  </p>
                  <textarea
                    id="cmp-b-position"
                    value={form.b_position}
                    onChange={update('b_position')}
                    rows={6}
                    maxLength={LIMITS.position}
                    aria-describedby="cmp-b-position-help"
                    aria-invalid={Boolean(stepError)}
                    placeholder="Example: The government defended the restriction under the applicable law."
                  />
                  <span className="cmp-counter">
                    {form.b_position.length}/{LIMITS.position}
                  </span>
                </div>
              </div>
            </div>
          )}

          {activeStep.key === 'provisions' && (
            <div className="cmp-step">
              <p className="cmp-step-help">
                Add the sections or articles you already know. This step is optional; skip it if you
                are not sure.
              </p>
              <div className="cmp-field">
                <div className="cmp-field-header">
                  <label className="cmp-label" htmlFor="cmp-provisions">
                    Applicable legal provisions <span className="cmp-opt">Optional</span>
                  </label>
                  <MicButton
                    value={form.provisions}
                    onChange={(value) => setField('provisions', value)}
                    title="Dictate applicable provisions"
                  />
                </div>
                <p className="cmp-help" id="cmp-provisions-help">
                  Separate multiple provisions with commas, for example “Article 21, Section 302
                  IPC”.
                </p>
                <input
                  id="cmp-provisions"
                  value={form.provisions}
                  onChange={update('provisions')}
                  aria-describedby="cmp-provisions-help"
                  placeholder="Example: Section 482 BNSS, Article 21"
                />
              </div>
            </div>
          )}

          {activeStep.key === 'filters' && (
            <div className="cmp-step">
              <p className="cmp-step-help">
                {isSingle
                  ? 'Narrow the search if you know the court or the years involved. You can skip this step.'
                  : 'These filters can help narrow the search. You can skip this section and continue.'}
              </p>
              <details className="cmp-optional" open>
                <summary>Additional Legal Filters (Optional)</summary>
                <div className="cmp-optional-body">
                  {!isSingle && (
                    <div className="cmp-field">
                      <div className="cmp-field-header">
                        <label className="cmp-label" htmlFor="cmp-provisions">
                          Applicable legal provisions <span className="cmp-opt">Optional</span>
                        </label>
                        <FieldTools
                          value={form.provisions}
                          label="the applicable provisions"
                          onClear={() => setField('provisions', '')}
                          micValue={form.provisions}
                          onMicChange={(value) => setField('provisions', value)}
                        />
                      </div>
                      <p className="cmp-help" id="cmp-provisions-help">
                        Separate multiple provisions with commas. These help VIDHIVEDA check
                        statutory alignment.
                      </p>
                      <input
                        id="cmp-provisions"
                        value={form.provisions}
                        onChange={update('provisions')}
                        aria-describedby="cmp-provisions-help"
                        placeholder="Example: Article 21, Section 302 IPC"
                      />
                    </div>
                  )}

                  <div className="cmp-form-row cmp-form-row--filters">
                    <div className="cmp-field">
                      <div className="cmp-field-header">
                        <label className="cmp-label" htmlFor="cmp-court">
                          Court <span className="cmp-opt">Optional</span>
                        </label>
                        <FieldTools
                          value={form.court}
                          label="the court"
                          onClear={() => setField('court', '')}
                          micValue={form.court}
                          onMicChange={(value) => setField('court', value)}
                        />
                      </div>
                      <input
                        id="cmp-court"
                        value={form.court}
                        onChange={update('court')}
                        placeholder="e.g. Supreme Court of India"
                      />
                    </div>
                    <div className="cmp-field">
                      <label className="cmp-label" htmlFor="cmp-year-from">
                        Year from <span className="cmp-opt">Optional</span>
                      </label>
                      <input
                        id="cmp-year-from"
                        value={form.year_from}
                        onChange={update('year_from')}
                        inputMode="numeric"
                        maxLength={4}
                        placeholder="e.g. 1950"
                      />
                    </div>
                    <div className="cmp-field">
                      <label className="cmp-label" htmlFor="cmp-year-to">
                        Year to <span className="cmp-opt">Optional</span>
                      </label>
                      <input
                        id="cmp-year-to"
                        value={form.year_to}
                        onChange={update('year_to')}
                        inputMode="numeric"
                        maxLength={4}
                        placeholder="e.g. 1951"
                      />
                    </div>
                  </div>

                  <p className="cmp-help">
                    {CORPUS_SNAPSHOT.note} A year range outside those years may return no results.
                  </p>
                </div>
              </details>
            </div>
          )}

          {activeStep.key === 'review' && (
            <div className="cmp-step">
              <p className="cmp-step-help">
                Check what will be sent. You can edit any part before starting.
              </p>

              <div className="cmp-review">
                <ReviewItem
                  label="Main legal question"
                  onEdit={() => goToStep(0)}
                >
                  <p>{form.legal_issue.trim() || 'Not entered yet.'}</p>
                </ReviewItem>

                {form.case_facts.trim() && (
                  <ReviewItem label="Common background" onEdit={() => goToStep(1)}>
                    <p>{form.case_facts.trim()}</p>
                  </ReviewItem>
                )}

                <ReviewItem
                  label={`Case A — ${form.a_label.trim() || 'Party A'}`}
                  onEdit={() => goToStep(2)}
                >
                  <p>{form.a_position.trim() || 'Not entered yet.'}</p>
                </ReviewItem>

                <ReviewItem
                  label={`Case B — ${form.b_label.trim() || 'Party B'}`}
                  onEdit={() => goToStep(3)}
                >
                  <p>{form.b_position.trim() || 'Not entered yet.'}</p>
                </ReviewItem>

                <ReviewItem label="Legal filters" onEdit={() => goToStep(4)}>
                  <ul className="cmp-review-filters">
                    {filterSummary().map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </ReviewItem>
              </div>

              {!valuesComplete(form, analysisMode) && (
                <p className="cmp-field-error" role="alert">
                  Add the main legal question and a description for each case before comparing.
                </p>
              )}
            </div>
          )}

          {stepError && (
            <p className="cmp-field-error" role="alert" id="cmp-step-error">
              {stepError}
            </p>
          )}

          <div className="cmp-wizard-actions">
            <button
              type="button"
              className="cmp-btn cmp-btn--ghost"
              onClick={goBack}
              disabled={step === 0 || loading}
            >
              Back
            </button>

            {step < steps.length - 1 && (
              <button type="button" className="cmp-btn cmp-btn--primary" onClick={goNext}>
                Next step <Icon name="arrow" size={15} />
              </button>
            )}

            {step === steps.length - 1 && (
              <button
                type="submit"
                className="cmp-submit-btn"
                disabled={loading || !valuesComplete(form, analysisMode)}
              >
                <Icon name="compare" size={18} />
                {isSingle ? 'Analyse This Case' : 'Compare Cases'}
              </button>
            )}

            <button
              type="button"
              className="cmp-link-btn cmp-clear-btn"
              onClick={clearForm}
              disabled={loading}
            >
              Clear form
            </button>
          </div>

          {isSingle && step === steps.length - 1 && (
            <div className="cmp-after-action">
              <p>
                VIDHIVEDA will search its available legal documents, find relevant passages, and
                organize the results for you to review.
              </p>
              <ol className="cmp-workflow" aria-label="What happens after you start">
                {['Your Details', 'Legal Document Search', 'Relevant Judgments', 'Evidence Review', 'Comparison Results'].map(
                  (label, index) => (
                    <li key={label}>
                      <span>{label}</span>
                      {index < 4 && <span className="cmp-workflow-arrow" aria-hidden="true">→</span>}
                    </li>
                  ),
                )}
              </ol>
            </div>
          )}

          {!isSingle && step === steps.length - 1 && (
            <div className="cmp-after-action">
              <p>
                VIDHIVEDA will search its available legal documents, find relevant passages, and
                organize the results for you to review.
              </p>
              <ol className="cmp-workflow" aria-label="What happens after you start">
                {['Your Details', 'Legal Document Search', 'Relevant Judgments', 'Evidence Review', 'Comparison Results'].map(
                  (label, index) => (
                    <li key={label}>
                      <span>{label}</span>
                      {index < 4 && <span className="cmp-workflow-arrow" aria-hidden="true">→</span>}
                    </li>
                  ),
                )}
              </ol>
            </div>
          )}
        </form>
      </div>

      {loading && (
        <div className="empty-card cmp-loading" role="status" aria-live="polite">
          <div className="spinner" aria-hidden="true"></div>
          <h3>Searching the indexed legal corpus…</h3>
          <p>Looking for the passages that best match the details you supplied.</p>
        </div>
      )}

      {error && !loading && (
        <div className="empty-card cmp-error" role="alert">
          <h3>Research unavailable</h3>
          <p>{error}</p>
          <button
            type="button"
            className="cmp-btn cmp-btn--primary"
            onClick={() => runComparison(form, analysisMode)}
          >
            <Icon name="refresh" size={15} /> Try again
          </button>
        </div>
      )}

      {result && !loading && (
        <div className="cmp-result" ref={resultsRef}>
          <div className="cmp-result-head">
            <div>
              <span className="eyebrow">Comparison results</span>
              <h3>What the retrieved material shows</h3>
            </div>
            <div className="cmp-result-head-actions">
              <Badge tone={EVIDENCE_TONE[quality?.status] || 'neutral'}>
                {EVIDENCE_LABEL[quality?.status] || 'Material retrieved'}
              </Badge>
              <button type="button" className="cmp-btn cmp-btn--ghost" onClick={startNew}>
                <Icon name="refresh" size={14} /> Start a new comparison
              </button>
            </div>
          </div>

          <section className="cmp-result-section" aria-labelledby="cmp-results-overview">
            <div className="cmp-result-section-head">
              <span className="cmp-result-index">A</span>
              <h3 id="cmp-results-overview">Quick overview</h3>
            </div>
            <p className="cmp-result-text">
              {result.scenario_b
                ? `VIDHIVEDA searched its indexed legal corpus and found ${precedentCount} retrieved document(s) relevant to this question. ${bothCount} were retrieved for both cases, ${onlyACount} only for ${resultLabels.a}, and ${onlyBCount} only for ${resultLabels.b}.`
                : `VIDHIVEDA searched its indexed legal corpus and found ${precedentCount} retrieved document(s) relevant to this question. ${result.scenario_a?.supporting_count || 0} are topically aligned with the situation you described.`}
            </p>
            <p className="cmp-meta">
              “Enough material” means relevant passages were found. It does not mean either side is
              legally right.
            </p>
          </section>

          {result.scenario_b ? (
            <>
              <section className="cmp-result-section" aria-labelledby="cmp-results-similar">
                <div className="cmp-result-section-head">
                  <span className="cmp-result-index">B</span>
                  <h3 id="cmp-results-similar">What is similar?</h3>
                </div>
                <div className="cmp-result-subsection">
                  <strong>Documents retrieved for both cases ({bothCount})</strong>
                  {bothCount > 0 ? (
                    <ul className="cmp-plain-list">
                      {evidence.retrieved_for_both.map((item, index) => (
                        <li key={item.chunk_id || index}>
                          <span>{item.case_name || 'Unnamed document'}</span>
                          {item.chunk_id && <span className="cmp-meta">Chunk {item.chunk_id}</span>}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="cmp-empty">
                      No single judgment was retrieved for both cases in this run.
                    </p>
                  )}
                </div>
                {result.legal_issues?.length > 0 && (
                  <div className="cmp-result-subsection">
                    <strong>Legal questions identified in your wording</strong>
                    <ul className="cmp-plain-list">
                      {result.legal_issues.map((issue, index) => (
                        <li key={index}>{issue}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </section>

              <section className="cmp-result-section" aria-labelledby="cmp-results-different">
                <div className="cmp-result-section-head">
                  <span className="cmp-result-index">C</span>
                  <h3 id="cmp-results-different">What is different?</h3>
                </div>
                <div className="cmp-two-col">
                  <div className="cmp-position-card">
                    <span className="answer-label">Case A — {resultLabels.a}</span>
                    <p>{result.scenario_a?.position}</p>
                    <span className="cmp-meta">
                      {result.scenario_a?.supporting_count || 0} supporting ·{' '}
                      {result.scenario_a?.contrary_count || 0} contrary
                    </span>
                  </div>
                  <div className="cmp-position-card">
                    <span className="answer-label">Case B — {resultLabels.b}</span>
                    <p>{result.scenario_b?.position}</p>
                    <span className="cmp-meta">
                      {result.scenario_b?.supporting_count || 0} supporting ·{' '}
                      {result.scenario_b?.contrary_count || 0} contrary
                    </span>
                  </div>
                </div>
                <div className="cmp-two-col">
                  <div className="cmp-result-subsection">
                    <strong>Documents retrieved only for {resultLabels.a} ({onlyACount})</strong>
                    {onlyACount > 0 ? (
                      <ul className="cmp-plain-list">
                        {evidence.retrieved_for_scenario_a_only.map((item, index) => (
                          <li key={item.chunk_id || index}>{item.case_name || 'Unnamed document'}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="cmp-empty">None in this run.</p>
                    )}
                  </div>
                  <div className="cmp-result-subsection">
                    <strong>Documents retrieved only for {resultLabels.b} ({onlyBCount})</strong>
                    {onlyBCount > 0 ? (
                      <ul className="cmp-plain-list">
                        {evidence.retrieved_for_scenario_b_only.map((item, index) => (
                          <li key={item.chunk_id || index}>{item.case_name || 'Unnamed document'}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="cmp-empty">None in this run.</p>
                    )}
                  </div>
                </div>
                <p className="cmp-meta">
                  Different retrieved judgments show different subject matter. They do not show
                  which side is legally stronger.
                </p>
              </section>
            </>
          ) : (
            <section className="cmp-result-section" aria-labelledby="cmp-results-covered">
              <div className="cmp-result-section-head">
                <span className="cmp-result-index">B</span>
                <h3 id="cmp-results-covered">What the retrieved material covers</h3>
              </div>
              {result.scenario_a?.supporting_precedents?.length > 0 ? (
                <div className="cmp-source-list">
                  {result.scenario_a.supporting_precedents.map((precedent, index) => (
                    <PrecedentSource key={precedent.chunk_id || index} precedent={precedent} />
                  ))}
                </div>
              ) : (
                <p className="cmp-empty">
                  No retrieved judgment was topically aligned with this situation in this run.
                </p>
              )}
              {result.legal_issues?.length > 0 && (
                <div className="cmp-result-subsection">
                  <strong>Legal questions identified in your wording</strong>
                  <ul className="cmp-plain-list">
                    {result.legal_issues.map((issue, index) => (
                      <li key={index}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          )}

          <section className="cmp-result-section" aria-labelledby="cmp-results-support">
            <div className="cmp-result-section-head">
              <span className="cmp-result-index">D</span>
              <h3 id="cmp-results-support">Legal support</h3>
            </div>
            <div className={`cmp-support-grid ${result.scenario_b ? '' : 'cmp-support-grid--single'}`}>
              <SupportColumn title="Case A" scenario={result.scenario_a} />
              {result.scenario_b && <SupportColumn title="Case B" scenario={result.scenario_b} />}
            </div>
          </section>

          <section className="cmp-result-section" aria-labelledby="cmp-results-provisions">
            <div className="cmp-result-section-head">
              <span className="cmp-result-index">E</span>
              <h3 id="cmp-results-provisions">Relevant legal provisions</h3>
            </div>
            {result.applicable_law?.length > 0 ? (
              <ul className="cmp-provision-list">
                {result.applicable_law.map((law, index) => (
                  <li key={`${law.label}-${index}`}>
                    <strong>{law.label}</strong>
                    <span className="cmp-meta">
                      {law.origin === 'query'
                        ? 'Named in your legal question'
                        : law.origin === 'requested'
                          ? 'Supplied by you'
                          : 'Found in a retrieved judgment'}
                      {law.statute ? ` · ${law.statute}` : ''}
                      {law.chunk_id ? ` · chunk ${law.chunk_id}` : ''}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="cmp-empty">
                No provision was supplied, inferred from your wording, or found in the retrieved
                passages.
              </p>
            )}
          </section>

          <section className="cmp-result-section" aria-labelledby="cmp-results-sources">
            <div className="cmp-result-section-head">
              <span className="cmp-result-index">F</span>
              <h3 id="cmp-results-sources">Sources to read</h3>
            </div>
            <p className="cmp-meta">
              Every passage below was returned by the indexed corpus. Chunk ids let you check the
              stored passage directly.
            </p>
            <SourceTrail result={result} />
          </section>

          <section className="cmp-result-section" aria-labelledby="cmp-results-limits">
            <div className="cmp-result-section-head">
              <span className="cmp-result-index">G</span>
              <h3 id="cmp-results-limits">What the evidence does not establish</h3>
            </div>
            {result.scenario_a?.missing_evidence?.length > 0 || result.scenario_b?.missing_evidence?.length > 0 ? (
              <div className="cmp-result-subsection">
                <strong>Missing facts or sources</strong>
                <ul className="cmp-list">
                  {(result.scenario_a?.missing_evidence || []).map((item, index) => (
                    <li key={`a-${index}`}>{item}</li>
                  ))}
                  {(result.scenario_b?.missing_evidence || []).map((item, index) => (
                    <li key={`b-${index}`}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            <ul className="cmp-list">
              {(quality?.reasons || []).map((reason, index) => (
                <li key={`q-${index}`}>{reason}</li>
              ))}
              {(result.limitations || []).map((limitation, index) => (
                <li key={`l-${index}`}>{limitation}</li>
              ))}
            </ul>
            <div className="cmp-research-note">
              <Icon name="info" size={16} />
              <p>{RESEARCH_STATEMENT}</p>
            </div>
            {result.disclaimer && <p className="cmp-disclaimer">{result.disclaimer}</p>}
          </section>

          {activeExample && (
            <section className="cmp-result-section cmp-preset-provenance">
              <span className="answer-label">Example judgments in the retrieved evidence</span>
              <ul className="cmp-preset-result-cases">
                {presetMatches.map((match) => (
                  <li key={match.name}>
                    <strong>
                      {match.name} ({match.year})
                    </strong>
                    <span className="cmp-meta">
                      {match.retrievedAs
                        ? `Retrieved from the indexed corpus as “${match.retrievedAs}”.`
                        : 'Not found in the indexed corpus — the external judgment link is the published source.'}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="cmp-meta">
                {presetFound
                  ? 'Only the judgments marked as retrieved came from the index; the other cases in this example remain external references.'
                  : 'None of this example’s judgments appears in the retrieved evidence. The comparison below uses related material from the indexed corpus, shown with its own case names and chunk ids — it is not the selected judgment.'}
              </p>
            </section>
          )}

          <details className="cmp-tech">
            <summary>Technical Details</summary>
            <div className="cmp-tech-body">
              <p>
                <strong>Relevance score:</strong> An indication of how closely a retrieved passage
                matches your search. It is not the probability that a legal conclusion is correct.
              </p>
              <ul className="cmp-plain-list">
                <li>
                  <span>Evidence status</span>
                  <span className="cmp-meta">
                    {quality?.status || 'not reported'}
                    {quality?.best_similarity != null
                      ? ` · best similarity ${Math.round(quality.best_similarity * 100)}%`
                      : ''}
                  </span>
                </li>
                <li>
                  <span>Case A retrieval</span>
                  <span className="cmp-meta">
                    {result.retrieval?.scenario_a?.precedent_count ?? 0} document(s) · similarity{' '}
                    {Math.round((result.retrieval?.scenario_a?.best_similarity || 0) * 100)}%
                  </span>
                </li>
                {result.retrieval?.scenario_b && (
                  <li>
                    <span>Case B retrieval</span>
                    <span className="cmp-meta">
                      {result.retrieval.scenario_b.precedent_count ?? 0} document(s) · similarity{' '}
                      {Math.round((result.retrieval.scenario_b.best_similarity || 0) * 100)}%
                    </span>
                  </li>
                )}
                <li>
                  <span>Precedent documents</span>
                  <span className="cmp-meta">{precedentCount}</span>
                </li>
              </ul>
              <ComparativeAnalysisCard analysis={result.comparative_analysis} />
              <OutcomePredictionCard
                outcome={outcome}
                scenarioA={result.scenario_a}
                scenarioB={result.scenario_b}
              />
            </div>
          </details>

          <div className="cmp-result-actions">
            <button type="button" className="cmp-btn cmp-btn--primary" onClick={startNew}>
              <Icon name="refresh" size={15} /> Start a new comparison
            </button>
            <button type="button" className="cmp-btn cmp-btn--ghost" onClick={scrollToResults}>
              Back to top of results
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
