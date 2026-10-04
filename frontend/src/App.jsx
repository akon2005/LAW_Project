import { useEffect, useMemo, useRef, useState } from 'react'
import { caseRecords, datasetStats } from './data/dataset.js'
import { searchRecords, isVerified, ALL_COURTS, ANY_YEAR } from './utils/search.js'
import { statutes, exampleQueries } from './data/data.js'
import { useAuth } from './auth/AuthProvider.jsx'
import LoginPage from './components/auth/LoginPage.jsx'
import ReaderView, { DEFAULT_READER_PREFS, loadReaderPrefs, saveReaderPrefs, SCALE_MIN, SCALE_MAX, SCALE_STEP } from './components/ReaderView.jsx'
import { API_BASE } from './services/apiBase.js'
import { roleLabel } from './services/authService.js'
import { writeClipboard, recordToText } from './utils/clipboard.js'
import Icon from './components/Icon.jsx'
import AppearancePanel from './components/settings/AppearancePanel.jsx'
import AssistantBubble from './components/assistant/AssistantBubble.jsx'

/** Results rendered before the "show more" control appears. */
const RESULTS_PAGE_SIZE = 8

/**
 * Renders generated/retrieved text safely: HTML is escaped first, then a small
 * subset of markdown (**bold**, ## headings) is applied. Model output must never
 * be injected as raw HTML.
 */
function AnswerText({ text }) {
  const escaped = String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  const html = escaped
    .replace(/^#{2,3} (.+)$/gm, '<strong>$1</strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^&gt; (.+)$/gm, '<em>$1</em>')
    .replace(/\n/g, '<br/>')
  return <div className="answer-text" dangerouslySetInnerHTML={{ __html: html }} />
}

/** Human label for where the answer text came from. */
function originLabel(origin) {
  if (!origin || origin === 'none') return 'Retrieved sources only'
  if (origin === 'retrieval_template') return 'Retrieved sources (no generated summary)'
  if (origin.startsWith('llm:')) return `Grounded summary · ${origin.split(':')[1]}`
  return origin
}

/**
 * Render the inline markdown of an OKF body. Internal `*.md` links open the
 * linked concept, external links open in a new tab, so the knowledge graph is
 * navigable from the explorer itself.
 */
function renderOkfInline(text, onOpenConcept) {
  const pattern = /\[([^\]]+)\]\(([^)\s]+)\)/g
  const parts = []
  let last = 0
  let match
  let key = 0
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index))
    const label = match[1]
    const target = match[2]
    if (/^https?:/i.test(target)) {
      parts.push(<a key={`okf-a-${key++}`} href={target} target="_blank" rel="noreferrer">{label}</a>)
    } else if (target.endsWith('.md')) {
      const conceptId = target.replace(/^\.?\//, '').replace(/\.md$/, '')
      parts.push(
        <button key={`okf-b-${key++}`} type="button" className="okf-link-btn" onClick={() => onOpenConcept?.(conceptId)}>
          {label}
        </button>,
      )
    } else {
      parts.push(label)
    }
    last = match.index + match[0].length
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts.length ? parts : [text]
}

/** Structured, escaping renderer for an OKF markdown body (headings, lists, quotes, tables). */
function OkfBody({ text, onOpenConcept }) {
  const nodes = []
  let list = []
  let table = []
  let key = 0

  const flushList = () => {
    if (list.length) {
      nodes.push(<ul key={`okf-ul-${key++}`}>{list}</ul>)
      list = []
    }
  }
  const flushTable = () => {
    if (table.length) {
      const rows = table
        .filter((row) => !/^\|?[\s|:-]+\|?$/.test(row))
        .map((row) => row.replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim()))
      const [head, ...body] = rows
      nodes.push(
        <table key={`okf-tbl-${key++}`} className="okf-table">
          {head && <thead><tr>{head.map((cell, index) => <th key={index}>{cell}</th>)}</tr></thead>}
          <tbody>
            {body.map((row, rowIndex) => (
              <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex}>{renderOkfInline(cell, onOpenConcept)}</td>)}</tr>
            ))}
          </tbody>
        </table>,
      )
      table = []
    }
  }

  if (!text) {
    nodes.push(<p key={key++} style={{ color: 'var(--muted)' }}>No body content for this concept.</p>)
    return <div className="okf-body">{nodes}</div>
  }

  try {
    String(text).split('\n').forEach((line) => {
      const trimmed = line.trim()
      if (!trimmed) { flushList(); flushTable(); return }
      if (trimmed.startsWith('|')) { flushList(); table.push(trimmed); return }
      flushTable()
      if (trimmed.startsWith('# ')) {
        flushList()
        nodes.push(<h3 key={`okf-h-${key++}`}>{trimmed.slice(2)}</h3>)
        return
      }
      if (trimmed.startsWith('* ')) {
        list.push(<li key={`okf-li-${key++}`}>{renderOkfInline(trimmed.slice(2), onOpenConcept)}</li>)
        return
      }
      if (trimmed.startsWith('> ')) {
        flushList()
        nodes.push(<blockquote key={`okf-q-${key++}`}>{trimmed.slice(2)}</blockquote>)
        return
      }
      flushList()
      nodes.push(<p key={`okf-p-${key++}`}>{renderOkfInline(trimmed, onOpenConcept)}</p>)
    })
    flushList()
    flushTable()
  } catch (err) {
    nodes.push(<p key={key++} style={{ color: 'var(--muted)' }}>Content unavailable.</p>)
  }
  return <div className="okf-body">{nodes}</div>
}

function Badge({ children, tone = 'neutral' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

function Logo() {
  return (
    <div className="brand" aria-label="VIDHIVEDA">
      <div className="brand-mark"><Icon name="scale" size={19} /></div>
      <div>
        <div className="brand-name">VIDHIVEDA</div>
        <div className="brand-sub">LEGAL RESEARCH</div>
      </div>
    </div>
  )
}

function NavButton({ active, icon, children, onClick }) {
  return (
    <button className={`nav-button ${active ? 'active' : ''}`} onClick={onClick}>
      <Icon name={icon} size={16} />
      {children}
    </button>
  )
}

// Six fluted columns centred on x=260: 6 x 18px shafts with 24px gaps => 228px span.
const COURTHOUSE_COLUMNS = [146, 188, 230, 272, 314, 356]

function CourtIllustration() {
  return (
    /* every fill/stroke is a theme token, so the artwork follows the palette */
    <svg className="court-illustration" viewBox="0 0 520 360" role="img" aria-label="Illustration of a courthouse and legal archive">
      <rect x="0" y="0" width="520" height="360" rx="28" fill="var(--art-bg)" />
      <rect x="24" y="24" width="472" height="312" rx="22" fill="var(--surface-2)" stroke="var(--line)" />

      {/* soft ground shadow sitting behind the stylobate */}
      <ellipse cx="260" cy="272" rx="170" ry="16" fill="var(--surface-3)" />

      {/* pediment: outer gold raking cornice + inset tympanum */}
      <path d="M96 152 260 64l164 88z" fill="var(--gold)" stroke="var(--icon-muted)" strokeWidth="3" strokeLinejoin="round" />
      <path d="M126 140 260 78l134 62z" fill="var(--gold-soft)" />
      <circle cx="260" cy="118" r="17" fill="var(--brand-bg)" stroke="var(--gold)" strokeWidth="2" />
      <path d="M260 107v23M251 116h18M254 125h12" stroke="var(--brand-fg)" strokeWidth="2" strokeLinecap="round" />

      {/* entablature */}
      <rect x="112" y="152" width="296" height="18" fill="var(--surface-3)" stroke="var(--icon-muted)" strokeWidth="2" />
      <rect x="112" y="170" width="296" height="6" fill="var(--surface-2)" stroke="var(--icon-muted)" strokeWidth="1" />

      {/* colonnade: capital / shaft / base per column */}
      {COURTHOUSE_COLUMNS.map((x) => (
        <g key={x}>
          <rect x={x - 3} y="176" width="24" height="7" rx="2" fill="var(--surface-3)" stroke="var(--gold)" strokeWidth="1" />
          <rect x={x} y="183" width="18" height="59" fill="var(--surface)" stroke="var(--muted-2)" strokeWidth="1.5" />
          <rect x={x - 3} y="242" width="24" height="6" rx="2" fill="var(--surface-3)" stroke="var(--gold)" strokeWidth="1" />
        </g>
      ))}

      {/* stepped stylobate */}
      <rect x="132" y="248" width="256" height="9" rx="2" fill="var(--surface-2)" stroke="var(--line)" strokeWidth="1" />
      <rect x="120" y="257" width="280" height="9" rx="2" fill="var(--surface-3)" stroke="var(--line)" strokeWidth="1" />
      <rect x="108" y="266" width="304" height="10" rx="3" fill="var(--line-2)" stroke="var(--line)" strokeWidth="1" />

      {/* caption plaque, centred on the building's axis */}
      <rect x="126" y="292" width="268" height="30" rx="8" fill="var(--brand-bg)" />
      <text x="260" y="311" fill="var(--brand-fg)" textAnchor="middle" fontSize="11" letterSpacing="0.6" textLength="240" lengthAdjust="spacingAndGlyphs" fontFamily="Georgia, 'Times New Roman', serif">A RESEARCH-FIRST VIEW OF THE LAW</text>
    </svg>
  )
}

function SectionLabel({ eyebrow, title, text }) {
  return (
    <div className="section-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h2>{title}</h2>
      </div>
      {text && <p>{text}</p>}
    </div>
  )
}

function App() {
  // The session gates the whole workspace: no session, no research interface.
  const { session, logout } = useAuth()
  const displayName = session?.user?.name || session?.user?.email || ''
  const initials =
    displayName
      .split(/[\s@.]+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('') || 'V'

  const [activeTab, setActiveTab] = useState('research')
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')
  const [court, setCourt] = useState(ALL_COURTS)
  const [year, setYear] = useState(ANY_YEAR)
  const [visible, setVisible] = useState(RESULTS_PAGE_SIZE)
  const [selected, setSelected] = useState(null)
  const [showFilters, setShowFilters] = useState(false)
  const [showDisclaimer, setShowDisclaimer] = useState(false)
  // Filters offered in the UI come from the corpus itself, so an option can
  // never be offered that no indexed chunk can satisfy.
  const [facets, setFacets] = useState(null)
  const [readerPrefs, setReaderPrefs] = useState(loadReaderPrefs)
  const [copyState, setCopyState] = useState(null)

  const [results, setResults] = useState([])
  const [explanation, setExplanation] = useState('')
  const [isSearching, setIsSearching] = useState(false)
  // Retrieval confidence (a number 0–1 from the vector store), not a claim
  // about the model's wording. See answerOrigin for how the text was produced.
  const [confidence, setConfidence] = useState(0)
  const [lowConfidence, setLowConfidence] = useState(false)
  const [lowConfidenceReason, setLowConfidenceReason] = useState('')
  const [citations, setCitations] = useState([])
  const [corpus, setCorpus] = useState(null)
  const [answerWarning, setAnswerWarning] = useState('')
  const [answerOrigin, setAnswerOrigin] = useState('')
  const [backendError, setBackendError] = useState('')
  // Structured pipeline fields. A prediction is only rendered when the backend
  // says it is available; otherwise the UI states that plainly.
  const [prediction, setPrediction] = useState(null)
  const [legalProvisions, setLegalProvisions] = useState([])
  const [limitations, setLimitations] = useState([])
  // OKF v0.2 knowledge bundle explorer.
  const [knowledgeStats, setKnowledgeStats] = useState(null)
  const [knowledgeList, setKnowledgeList] = useState(null)
  const [knowledgeType, setKnowledgeType] = useState('')
  const [knowledgeQuery, setKnowledgeQuery] = useState('')
  const [knowledgeConcept, setKnowledgeConcept] = useState(null)
  const [knowledgeError, setKnowledgeError] = useState('')
  const [knowledgeLoading, setKnowledgeLoading] = useState(false)
  const [knowledgeLoadingConcept, setKnowledgeLoadingConcept] = useState(false)

  // Which corpus is actually behind the search box (read from ChromaDB).
  useEffect(() => {
    fetch(`${API_BASE}/api/research/corpus`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => data && setCorpus(data))
      .catch(() => {})
  }, [])

  // Facet values and their counts, taken from the indexed corpus. The old
  // hard-coded 1955–2026 year list offered years no chunk contained, so every
  // year filter returned zero results.
  useEffect(() => {
    fetch(`${API_BASE}/api/research/corpus/facets`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => data && setFacets(data))
      .catch(() => {})
  }, [])

  // Text-size and typography choices survive a reload.
  useEffect(() => {
    saveReaderPrefs(readerPrefs)
  }, [readerPrefs])

  // Bundle summary, loaded the first time the Knowledge tab is opened.
  useEffect(() => {
    if (activeTab !== 'knowledge' || knowledgeStats) return undefined
    let active = true
    fetch(`${API_BASE}/api/knowledge/stats`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => { if (active && data) setKnowledgeStats(data) })
      .catch(() => {})
    return () => { active = false }
  }, [activeTab, knowledgeStats])

  // Concept list, refetched when the type filter or the text query changes.
  useEffect(() => {
    if (activeTab !== 'knowledge') return undefined
    let active = true
    setKnowledgeLoading(true)
    setKnowledgeError('')
    const params = new URLSearchParams({ limit: '400' })
    if (knowledgeType) params.set('type', knowledgeType)
    if (knowledgeQuery.trim()) params.set('q', knowledgeQuery.trim())
    fetch(`${API_BASE}/api/knowledge?${params.toString()}`)
      .then(async (res) => {
        if (!res.ok) {
          const detail = await res.json().catch(() => ({}))
          throw new Error(detail.detail || `Knowledge bundle unavailable (${res.status})`)
        }
        return res.json()
      })
      .then((data) => { if (active) setKnowledgeList(data) })
      .catch((err) => { if (active) { setKnowledgeList(null); setKnowledgeError(err.message) } })
      .finally(() => { if (active) setKnowledgeLoading(false) })
    return () => { active = false }
  }, [activeTab, knowledgeType, knowledgeQuery])

  const courtOptions = useMemo(() => [
    { value: ALL_COURTS, label: 'All courts' },
    ...(facets?.courts || []).map((item) => ({ value: item.value, label: `${item.value} (${item.count.toLocaleString()})` })),
  ], [facets])

  const yearOptions = useMemo(() => [
    { value: ANY_YEAR, label: 'Any year' },
    ...(facets?.years || []).map((item) => ({ value: String(item.value), label: `${item.value} (${item.count.toLocaleString()})` })),
  ], [facets])

  // Fetch results from the FastAPI backend when search params change
  useEffect(() => {
    if (!submitted) {
      // If no query, just show the local full collection for browsing
      const local = searchRecords(caseRecords, { query: '', court, year })
      setResults(local)
      setExplanation('')
      setConfidence(0)
      setLowConfidence(false)
      setLowConfidenceReason('')
      setCitations([])
      setAnswerWarning('')
      setAnswerOrigin('')
      setBackendError('')
      return
    }

    const fetchResults = async () => {
      setIsSearching(true)
      try {
        const payload = {
          query: submitted,
          top_k: 24,
          court: court !== ALL_COURTS ? court : undefined,
          year: year !== ANY_YEAR ? parseInt(year, 10) : undefined,
        }
        const res = await fetch(`${API_BASE}/api/research`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        })
        if (!res.ok) {
          const detail = await res.json().catch(() => ({}))
          throw new Error(detail.detail || `Research request failed (${res.status})`)
        }
        const data = await res.json()

        // Map real corpus chunks to the result card format. Every field comes
        // from stored metadata; missing values are labelled, never invented.
        const mappedResults = (data.sources || []).map((s, index) => ({
          id: s.chunk_id || `${s.document_id || 'chunk'}_${index}`,
          title: s.case_name || s.source || `Corpus chunk ${index + 1}`,
          // Only ever the citation the document itself prints — never derived.
          citation: s.citation || '',
          source: s.source || 'Source not recorded upstream',
          chunkId: s.chunk_id || '',
          chunkIndex: s.chunk_index,
          year: s.year || 'Year not recorded',
          court: s.court || 'Court not recorded',
          judgmentDate: s.judgment_date || '',
          sections: s.sections || [],
          articles: s.articles || [],
          sourceUrl: s.source_url || '',
          area: 'Indexed case law',
          verified: true,
          summary: s.text || '',
          score: Math.round((s.similarity_score || 0) * 100),
          recordType: `ChromaDB · ${data.corpus?.collection || 'legal corpus'}`,
        }))

        setResults(mappedResults)
        setExplanation(data.answer || '')
        setCitations(data.citations || [])
        if (data.corpus) setCorpus(data.corpus)
        setAnswerWarning(data.warning || '')
        setAnswerOrigin(data.answer_origin || '')
        setConfidence(typeof data.confidence === 'number' ? data.confidence : 0)
        setLowConfidence(data.low_confidence || false)
        setLowConfidenceReason(data.low_confidence_reason || '')
        setPrediction(data.prediction || null)
        setLegalProvisions(data.legal_provisions || [])
        setLimitations(data.limitations || [])
        setBackendError('')
      } catch (err) {
        console.error(err)
        // The API is unreachable: say so plainly instead of presenting the
        // bundled sample keywords as if they were corpus results.
        setResults([])
        setExplanation('')
        setCitations([])
        setLowConfidence(false)
        setLowConfidenceReason('')
        setConfidence(0)
        setAnswerOrigin('')
        setAnswerWarning('')
        setPrediction(null)
        setLegalProvisions([])
        setLimitations([])
        setBackendError(
          `${err.message || 'Could not reach the backend'}. Start the API with \`uvicorn app.main:app --port 8000\` and try again.`
        )
      } finally {
        setIsSearching(false)
      }
    }
    fetchResults()
  }, [submitted, court, year])

  const shown = results.slice(0, visible)

  // The reading view steps through whatever is currently on screen.
  const readerIndex = selected ? results.findIndex((record) => record.id === selected.id) : -1
  const readerPrev = readerIndex > 0 ? () => openRecord(results[readerIndex - 1]) : null
  const readerNext = readerIndex >= 0 && readerIndex < results.length - 1 ? () => openRecord(results[readerIndex + 1]) : null

  // Documents tab: newest first, independent of the active search.
  const recentRecords = useMemo(
    () => [...caseRecords].sort((a, b) => (b.year || 0) - (a.year || 0)).slice(0, 25),
    [],
  )

  // Collapse back to the first page whenever the result set changes.
  useEffect(() => {
    setVisible(RESULTS_PAGE_SIZE)
  }, [submitted, court, year])

  // Counting per instrument costs a full scan, so only do it for that tab.
  const statuteCounts = useMemo(() => {
    if (activeTab !== 'statutes') return {}
    return Object.fromEntries(
      statutes.map((item) => [item.title, searchRecords(caseRecords, { query: item.query }).length]),
    )
  }, [activeTab])

  const workspaceRef = useRef(null)

  const submitSearch = (e) => {
    e?.preventDefault()
    setSubmitted(query.trim())
    setActiveTab('research')
  }

  // Submitting a search should land on the results, not leave the user at the
  // top of the hero. The workspace is rendered below the hero on the same tab,
  // so we move focus/scroll to it whenever a new query is submitted.
  useEffect(() => {
    if (!submitted) return undefined
    const node = workspaceRef.current
    if (!node) return undefined
    const frame = window.requestAnimationFrame(() => {
      node.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [submitted])

  const resetFilters = () => {
    setCourt(ALL_COURTS)
    setYear(ANY_YEAR)
  }

  /**
   * Opens the reading view on a result and returns the neighbours it can move
   * to, so the reader's prev/next controls stay inside the current result set.
   */
  const openRecord = (record) => setSelected(record)

  const copyRecord = async (record) => {
    const copied = await writeClipboard(recordToText(record))
    setCopyState({ id: record.id, copied })
    window.setTimeout(() => setCopyState(null), 1800)
  }

  const changeScale = (delta) => {
    setReaderPrefs((prefs) => ({
      ...prefs,
      scale: Math.min(SCALE_MAX, Math.max(SCALE_MIN, Math.round((prefs.scale + delta) * 100) / 100)),
    }))
  }

  /**
   * Examples, library cards and instrument rows all route through here: they
   * clear the facet filters so a curated example can never dead-end on zero
   * results the way the old prompt chips did.
   */
  const applyQuery = (text) => {
    setQuery(text)
    setSubmitted(text)
    resetFilters()
    setActiveTab('research')
  }

  // Opens one OKF concept with its body and resolved relationships.
  const openConcept = (conceptId) => {
    if (!conceptId) return
    setKnowledgeError('')
    setKnowledgeLoadingConcept(true)
    fetch(`${API_BASE}/api/knowledge/${conceptId}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`Concept '${conceptId}' is not in the bundle.`)
        return res.json()
      })
      .then((data) => {
        setKnowledgeConcept(data)
        setKnowledgeLoadingConcept(false)
      })
      .catch((err) => {
        setKnowledgeError(err.message)
        setKnowledgeLoadingConcept(false)
      })
  }

  // Signed out (or session expired): only the sign-in experience is rendered.
  if (!session) {
    return <LoginPage />
  }

  return (
    <div className="app-shell app-shell--enter" style={{ '--reader-scale': readerPrefs.scale }}>
      <header className="topbar">
        <div className="topbar-inner">
          <Logo />
          <nav className="topnav" aria-label="Primary navigation">
            <NavButton active={activeTab === 'research'} icon="search" onClick={() => setActiveTab('research')}>Research</NavButton>
            <NavButton active={activeTab === 'statutes'} icon="book" onClick={() => setActiveTab('statutes')}>Statutes & Articles</NavButton>
            <NavButton active={activeTab === 'documents'} icon="file" onClick={() => setActiveTab('documents')}>Documents</NavButton>
            <NavButton active={activeTab === 'knowledge'} icon="knowledge" onClick={() => setActiveTab('knowledge')}>Knowledge</NavButton>
            <NavButton active={activeTab === 'settings'} icon="settings" onClick={() => setActiveTab('settings')}>Settings</NavButton>
          </nav>
          <div className="topbar-actions">
            <button className="about-link" onClick={() => setShowDisclaimer((v) => !v)}><Icon name="info" size={16}/> About</button>
            <div className="user-chip">
              <span className="user-chip__initial" aria-hidden="true">{initials}</span>
              <span className="user-chip__meta">
                <strong title={displayName}>{displayName}</strong>
                <small>
                  {roleLabel(session.user.role)}
                  {session.mode === 'demo' ? ' · demo' : ''}
                </small>
              </span>
              <button type="button" className="user-chip__signout" onClick={logout}>Sign out</button>
            </div>
          </div>
        </div>
      </header>

      {showDisclaimer && (
        <div className="notice-bar">
          <div><strong>Research support only.</strong> VIDHIVEDA is designed to surface sources and research context; it does not issue judgments or legal opinions.</div>
          <button onClick={() => setShowDisclaimer(false)} aria-label="Close notice"><Icon name="close" size={16}/></button>
        </div>
      )}

      <main key={activeTab} className="page-transition-wrapper">
        {activeTab === 'research' && (
          <>
            <section className="hero">
              <div className="hero-copy">
                <div className="kicker"><span className="dot"/> Research workspace · Indian legal sources</div>
                <h1>Legal research,<br/><em>grounded in the record.</em></h1>
                <p className="hero-lede">Search case law, statutes and notifications in plain language. Follow every result back to the source and keep the research trail visible.</p>
                <form className="searchbar" onSubmit={submitSearch}>
                  <Icon name="search" size={19}/>
                  <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Describe the legal issue or facts you are researching…" aria-label="Legal research query" />
                  <button className="filter-button" type="button" onClick={() => setShowFilters((v) => !v)} aria-label="Open filters"><Icon name="filter" size={18}/></button>
                  <button className="search-submit" type="submit" aria-label="Search"><Icon name="arrow" size={18}/></button>
                </form>
                {showFilters && (
                  <div className="filter-panel">
                    <Select label="Court (indexed corpus)" value={court} options={courtOptions} onChange={setCourt}/>
                    <Select label="Year (indexed corpus)" value={year} options={yearOptions} onChange={setYear}/>
                    <button type="button" className="filter-reset" onClick={resetFilters}>Clear filters</button>
                  </div>
                )}
                <div className="examples">
                  <div className="examples-head">
                    <span className="eyebrow">Example questions</span>
                    <span className="examples-meta">
                      {datasetStats.total.toLocaleString()} records · {datasetStats.areas} areas ·
                      {' '}{datasetStats.yearFrom}–{datasetStats.yearTo} · {datasetStats.courts} courts
                    </span>
                  </div>
                  <div className="example-grid">
                    {exampleQueries.map((example) => (
                      <button
                        key={example.query}
                        type="button"
                        className="example-chip"
                        onClick={() => applyQuery(example.query)}
                      >
                        <Icon name="search" size={14}/>
                        <span>{example.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <div className="hero-art-wrap"><CourtIllustration/></div>
            </section>

            <section className="trust-strip">
              <div><span className="strip-number">01</span><span><strong>Retrieve</strong> precedents by weighted match across case names, sections and principles.</span></div>
              <div><span className="strip-number">02</span><span><strong>Explain</strong> research findings with a visible source trail.</span></div>
              <div><span className="strip-number">03</span><span><strong>Flag</strong> weak matches instead of forcing a result.</span></div>
            </section>

            <section className="workspace section-container" ref={workspaceRef} id="research-results">
              <SectionLabel
                eyebrow="Research workspace"
                title={submitted ? `Researching “${submitted}”` : 'Start with a legal question'}
                text={
                  submitted
                    ? `Semantic search over ${corpus ? `${corpus.chunk_count.toLocaleString()} indexed chunks in ${corpus.collection}` : 'the indexed legal corpus'}. Every result keeps its source file, chunk id and similarity score visible.`
                    : `Browse the bundled sample of ${datasetStats.total.toLocaleString()} records, or ask a question to search the full indexed corpus.`
                }
              />
              <div className="workspace-grid">
                <aside className="side-card">
                  <div className="side-card-head"><span>Filters</span><button onClick={resetFilters}>Reset</button></div>
                  <Select label="Court" value={court} options={courtOptions} onChange={setCourt}/>
                  <Select label="Year" value={year} options={yearOptions} onChange={setYear}/>
                  <div className="side-note"><span className="note-icon"><Icon name="check" size={15}/></span><div><strong>Options come from the corpus</strong><p>Court and year list only values that actually exist in the indexed chunks, with their chunk counts.</p></div></div>
                  <div className="side-note"><span className="note-icon"><Icon name="info" size={15}/></span><div><strong>Area of law is not indexed</strong><p>The corpus metadata carries no area field yet, so no area filter is offered — instead of one that would silently return nothing.</p></div></div>
                  {facets && (
                    <div className="side-coverage">
                      <span className="answer-label">Indexed coverage</span>
                      <p>
                        {facets.chunk_count?.toLocaleString()} chunks · {facets.courts?.length || 0} courts ·
                        {' '}{facets.year_min}–{facets.year_max}
                        {facets.generated_at ? ` · read ${new Date(facets.generated_at).toLocaleTimeString()}` : ''}
                      </p>
                    </div>
                  )}
                </aside>

                <div className="results-column">
                  <div className="results-toolbar">
                    <span className="results-count">
                      {isSearching ? 'Searching the indexed corpus...' : `${results.length.toLocaleString()} match${results.length === 1 ? '' : 'es'}`}
                      {!isSearching && results.length > shown.length ? ` · showing ${shown.length}` : ''}
                    </span>
                    <span className="results-toolbar-right">
                      <Badge tone={submitted ? 'green' : 'neutral'}>
                        {submitted
                          ? `Indexed legal corpus${corpus ? ` · ${corpus.collection}` : ''}`
                          : 'Bundled sample (browse only)'}
                      </Badge>
                      <span className="text-size" role="group" aria-label="Reading text size">
                        <button type="button" onClick={() => changeScale(-SCALE_STEP)} disabled={readerPrefs.scale <= SCALE_MIN} aria-label="Decrease reading text size" title="Decrease reading text size">A−</button>
                        <span aria-live="polite">{Math.round(readerPrefs.scale * 100)}%</span>
                        <button type="button" onClick={() => changeScale(SCALE_STEP)} disabled={readerPrefs.scale >= SCALE_MAX} aria-label="Increase reading text size" title="Increase reading text size">A+</button>
                        <button type="button" onClick={() => setReaderPrefs((prefs) => ({ ...DEFAULT_READER_PREFS, theme: prefs.theme, font: prefs.font }))} aria-label="Reset reading text size" title="Reset reading text size">↺</button>
                      </span>
                    </span>
                  </div>
                  {isSearching && (
                    <div className="empty-card" style={{ padding: '40px', textAlign: 'center' }}>
                      <div className="spinner"></div>
                      <h3>Analyzing legal precedents...</h3>
                      <p>Searching the database and synthesizing an answer.</p>
                    </div>
                  )}
                  {!isSearching && shown.map((result, i) => (
                    <article
                      className="result-card"
                      key={result.id}
                      onClick={() => openRecord(result)}
                      tabIndex={0}
                      role="button"
                      aria-label={`Open reading view for ${result.title || 'source record'}`}
                      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), openRecord(result))}
                      style={{ animationDelay: `${i * 0.06}s` }}
                    >
                      <div className="result-topline">
                        <span className="result-tags">
                          <Badge>{result.area}</Badge>
                          <Badge tone={result.verified ? 'green' : 'neutral'}>{result.verified ? 'Real corpus record' : 'Unverified'}</Badge>
                        </span>
                        <span>{result.court} · {result.year}</span>
                      </div>
                      <h3>{result.title}</h3>
                      <p>{result.summary}</p>
                      <div className="result-footer">
                        <span className="citation"><Icon name="file" size={14}/>{submitted ? (result.source || result.citation) : result.citation}</span>
                        <span className="result-read">
                          {submitted
                            ? <span className="similarity"><span>{result.chunkId ? `chunk ${result.chunkId} · similarity` : 'Similarity'}</span><strong>{result.score}%</strong></span>
                            : <span className="similarity"><span>Record</span><strong>{result.id}</strong></span>}
                          <button
                            type="button"
                            className="card-action"
                            onClick={(e) => { e.stopPropagation(); copyRecord(result) }}
                            aria-label={`Copy text of ${result.title || 'record'}`}
                          >
                            {copyState?.id === result.id
                              ? copyState.copied ? 'Copied ✓' : 'Copy unavailable'
                              : 'Copy'}
                          </button>
                          <button
                            type="button"
                            className="card-action card-action--primary"
                            onClick={(e) => { e.stopPropagation(); openRecord(result) }}
                            aria-label={`Read ${result.title || 'record'} in the reading view`}
                          >
                            Read
                          </button>
                        </span>
                      </div>
                    </article>
                  ))}
                  {!results.length && (
                    <div className="empty-card">
                      <h3>No records match the current filters.</h3>
                      <p>
                        {submitted ? `“${submitted}” returned nothing across ` : 'No records found across '}
                        {datasetStats.total.toLocaleString()} records. Try a broader phrase, or clear the facet filters.
                      </p>
                      <button className="ghost-btn" onClick={resetFilters}>Reset filters <Icon name="arrow" size={16}/></button>
                    </div>
                  )}
                  {results.length > shown.length && (
                    <button className="ghost-btn show-more" onClick={() => setVisible((v) => v + RESULTS_PAGE_SIZE)}>
                      Show {Math.min(RESULTS_PAGE_SIZE, results.length - shown.length)} more of {results.length.toLocaleString()} <Icon name="arrow" size={16}/>
                    </button>
                  )}
                </div>

                <aside className="answer-card">
                  <div className="answer-header">
                    <span className="eyebrow">{submitted ? 'Grounded research answer' : 'Leading authority'}</span>
                    <Badge tone={lowConfidence ? "neutral" : "gold"}>{lowConfidence ? "Low confidence" : "Sources verified"}</Badge>
                  </div>
                  {isSearching ? (
                     <div style={{ padding: '20px 0', opacity: 0.6 }}>Searching the indexed corpus...</div>
                  ) : backendError ? (
                    <>
                      <h3>Backend unavailable</h3>
                      <p className="answer-lede">{backendError}</p>
                    </>
                  ) : submitted && lowConfidence ? (
                    <>
                      <h3>Insufficient supporting precedent</h3>
                      <p className="answer-lede">{lowConfidenceReason || 'The retrieved sources are too weak to support an answer.'}</p>
                      <div className="answer-block">
                        <span className="answer-label">Best retrieval confidence</span>
                        <p>{Math.round(confidence * 100)}% similarity — no answer was generated for this query.</p>
                      </div>
                      {limitations.length > 0 && (
                        <div className="answer-block">
                          <span className="answer-label">Limitations</span>
                          <ul className="answer-limitations">
                            {limitations.map((limitation, index) => (
                              <li key={index}>{limitation}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      <div className="answer-meta"><span>Sources retrieved</span><strong>{results.length.toLocaleString()}</strong></div>
                      {results[0] && (
                        <button className="outline-btn" onClick={() => setSelected(results[0])}>View closest record <Icon name="arrow" size={16}/></button>
                      )}
                    </>
                  ) : submitted && explanation ? (
                    <>
                      <div className="answer-block" style={{ marginTop: '16px' }}>
                        <AnswerText text={explanation} />
                      </div>

                      <div className="answer-meta">
                        <span>Retrieval confidence</span>
                        <strong>{Math.round(confidence * 100)}%</strong>
                      </div>
                      <div className="answer-meta">
                        <span>Answer source</span>
                        <strong>{originLabel(answerOrigin)}</strong>
                      </div>
                      <div className="answer-meta">
                        <span>Corpus</span>
                        <strong>{corpus ? `${corpus.collection} · ${corpus.chunk_count.toLocaleString()}` : 'indexed legal corpus'}</strong>
                      </div>

                      {answerWarning && <div className="answer-warning">⚠️ {answerWarning}</div>}

                      {prediction?.available ? (
                        <div className="answer-block">
                          <span className="answer-label">Predicted outcome (research model, not a court decision)</span>
                          <p>
                            <strong>{prediction.label}</strong>
                            {' · '}{Math.round((prediction.confidence || 0) * 100)}% confidence
                            {prediction.low_confidence ? ' · low confidence' : ''}
                          </p>
                          <span className="citation-meta">
                            Model {prediction.model_version || 'untrained'}
                            {prediction.calibration ? ` · ${prediction.calibration}` : ''}
                            {' — '}a statistical estimate from case facts, not a verdict.
                          </span>
                        </div>
                      ) : (
                        <div className="answer-block">
                          <span className="answer-label">Outcome prediction</span>
                          <p>Prediction unavailable{prediction?.reason ? ` — ${prediction.reason}` : ''}.</p>
                        </div>
                      )}

                      {legalProvisions.length > 0 && (
                        <div className="answer-block">
                          <span className="answer-label">Relevant provisions</span>
                          <div className="citation-list">
                            {legalProvisions.slice(0, 12).map((provision, index) => (
                              <div className="citation-item" key={`${provision.label}-${index}`}>
                                <strong>{provision.label}</strong>
                                <span className="citation-meta">
                                  {provision.origin === 'query' ? 'requested in the query' : 'found in retrieved evidence'}
                                  {provision.statute ? ` · ${provision.statute}` : ''}
                                  {provision.chunk_id ? ` · chunk ${provision.chunk_id}` : ''}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {limitations.length > 0 && (
                        <div className="answer-block">
                          <span className="answer-label">Limitations</span>
                          <ul className="answer-limitations">
                            {limitations.map((limitation, index) => (
                              <li key={index}>{limitation}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {citations.length > 0 && (
                        <div className="answer-block">
                          <span className="answer-label">Verified citations ({citations.length})</span>
                          <div className="citation-list">
                            {citations.map((citation, index) => (
                              <div className="citation-item" key={`${citation.chunk_id}-${index}`}>
                                <strong>{index + 1}. {citation.case_name}</strong>
                                <span>{[citation.court, citation.judgment_date || citation.year].filter(Boolean).join(' · ') || 'Court/date not recorded upstream'}</span>
                                <span className="citation-source">{citation.source || 'Source filename not recorded upstream'}</span>
                                <span className="citation-meta">chunk {citation.chunk_id} · similarity {Math.round((citation.similarity_score || 0) * 100)}%</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : results[0] ? (
                    <>
                      <h3>{results[0].title}</h3>
                      <p className="answer-lede">{results[0].citation} · {results[0].court} · {results[0].year}</p>
                      <div className="answer-block">
                        <span className="answer-label">Corpus excerpt</span>
                        <p>{results[0].summary}</p>
                      </div>
                      <div className="answer-meta"><span>Match</span><strong>{submitted ? `${results[0].score}%` : '—'}</strong></div>
                      <div className="answer-meta"><span>Records retrieved</span><strong>{results.length.toLocaleString()}</strong></div>
                      <button className="outline-btn" onClick={() => setSelected(results[0])}>View supporting record <Icon name="arrow" size={16}/></button>
                    </>
                  ) : submitted ? (
                    <>
                      <h3>No corpus record matched</h3>
                      <p className="answer-lede">No chunk in the indexed corpus matched this query with the current filters.</p>
                      <button className="outline-btn" onClick={resetFilters}>Reset filters <Icon name="arrow" size={16}/></button>
                    </>
                  ) : (
                    <>
                      <h3>Ask a research question</h3>
                      <p className="answer-lede">Answers are built only from chunks in the indexed legal corpus, and every citation is checked against the retrieved sources.</p>
                    </>
                  )}
                </aside>
              </div>
            </section>

            <section className="library section-container">
              <SectionLabel eyebrow="Legal library" title="Browse the building blocks of research" text={`The first eight of ${statutes.length} instruments referenced in the dataset. Open Statutes & Articles for the full list, or click any card to search it.`} />
              <div className="library-grid">
                {statutes.slice(0, 8).map((item, index) => (
                  <button className="library-card" key={item.title} onClick={() => applyQuery(item.query)} style={{ animationDelay: `${index * 0.05}s` }}>
                    <div className="library-index">0{index + 1}</div>
                    <div><h3>{item.title}</h3><p>{item.category}</p></div>
                    <Icon name="arrow" size={18}/>
                  </button>
                ))}
              </div>
            </section>

            <section className="ethics section-container">
              <div className="ethics-card">
                <div><span className="eyebrow">Research, not judgment</span><h2>Keep the source trail visible.</h2></div>
                <p>VIDHIVEDA is positioned as a decision-support and research aid. Human judicial authority remains outside the system, while generated claims are designed to stay connected to source material.</p>
                <div className="ethics-points"><span><Icon name="check" size={15}/> Source-backed responses</span><span><Icon name="check" size={15}/> Low-confidence handling</span><span><Icon name="check" size={15}/> Human decision-making retained</span></div>
              </div>
            </section>
          </>
        )}

        {activeTab === 'statutes' && (
          <section className="page-section section-container">
            <SectionLabel eyebrow="Reference library" title="Statutes & Articles" text="A browsable shell for the statute and article collection described in the project architecture." />
            <div className="library-grid large">
              {statutes.map((item, i) => (
                <div className="statute-row" key={item.title} style={{ animationDelay: `${i * 0.04}s` }}>
                  <div className="library-index">{String(i + 1).padStart(2, '0')}</div>
                  <div>
                    <h3>{item.title}</h3>
                    <p>{item.category} · {(statuteCounts[item.title] ?? 0).toLocaleString()} records</p>
                  </div>
                  <button className="text-btn" onClick={() => applyQuery(item.query)}>Search <Icon name="arrow" size={15}/></button>
                </div>
              ))}
            </div>
          </section>
        )}

        {activeTab === 'documents' && (
          <section className="page-section section-container">
            <SectionLabel eyebrow="Document collection" title="Documents" text={`The 25 most recent of ${datasetStats.total.toLocaleString()} records in the dataset. Preview any record to see its citation and source.`} />
            <div className="document-list">
              {recentRecords.map((item, i) => (
                <div className="document-row" key={item.id} style={{ animationDelay: `${i * 0.04}s` }}>
                  <div className="doc-icon"><Icon name="file" size={18}/></div>
                  <div className="doc-main"><h3>{item.title}</h3><p>{item.court} · {item.year} · {item.area}</p></div>
                  <Badge>{item.id}</Badge>
                  <Badge tone={isVerified(item) ? 'green' : 'neutral'}>{isVerified(item) ? 'Verified' : 'Synthetic'}</Badge>
                  <button className="text-btn" onClick={() => setSelected(item)}>Preview <Icon name="arrow" size={15}/></button>
                </div>
              ))}
            </div>
          </section>
        )}

        {activeTab === 'knowledge' && (
          <section className="page-section section-container okf-page">
            <SectionLabel
              eyebrow="Open Knowledge Format v0.2"
              title="Knowledge bundle"
              text="Curated legal knowledge derived deterministically from the indexed corpus. Every concept records its sources and its trust tier; nothing the corpus does not record is invented."
            />

            {knowledgeStats?.available === false ? (
              <div className="empty-card">
                <h3>Knowledge bundle not built</h3>
                <p>{knowledgeStats.detail || 'Run scripts/build_okf_bundle.py from backend/ to generate it.'}</p>
              </div>
            ) : (
              <>
                {knowledgeStats && (
                  <div className="okf-stats">
                    <div className="okf-stat"><span>Concepts</span><strong>{knowledgeStats.concepts.toLocaleString()}</strong><small>{Object.keys(knowledgeStats.types).length} types</small></div>
                    <div className="okf-stat"><span>Provenance coverage</span><strong>{Math.round((knowledgeStats.provenance?.coverage || 0) * 100)}%</strong><small>{knowledgeStats.provenance?.with_sources?.toLocaleString()} with sources</small></div>
                    <div className="okf-stat"><span>Machine-confirmed</span><strong>{(knowledgeStats.trust?.['machine-confirmed'] || 0).toLocaleString()}</strong><small>not human-reviewed</small></div>
                    <div className="okf-stat"><span>OKF version</span><strong>{knowledgeStats.okf_version}</strong><small>specification</small></div>
                  </div>
                )}

                <div className="okf-toolbar">
                  <form className="searchbar" onSubmit={(event) => event.preventDefault()}>
                    <Icon name="search" size={18} />
                    <input
                      value={knowledgeQuery}
                      onChange={(event) => setKnowledgeQuery(event.target.value)}
                      placeholder="Filter concepts by title, tag or body text…"
                      aria-label="Filter OKF concepts"
                    />
                    {knowledgeQuery && (
                      <button className="filter-button" type="button" onClick={() => setKnowledgeQuery('')} aria-label="Clear filter"><Icon name="close" size={16} /></button>
                    )}
                  </form>
                  {knowledgeStats && (
                    <div className="okf-type-chips">
                      <button type="button" className={`okf-chip ${knowledgeType === '' ? 'active' : ''}`} onClick={() => setKnowledgeType('')}>All</button>
                      {Object.keys(knowledgeStats.types).sort().map((type) => (
                        <button
                          key={type}
                          type="button"
                          className={`okf-chip ${knowledgeType === type ? 'active' : ''}`}
                          onClick={() => setKnowledgeType(type)}
                        >
                          {type} ({knowledgeStats.types[type]})
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {knowledgeError && (
                  <div className="empty-card">
                    <h3>Knowledge bundle unavailable</h3>
                    <p>{knowledgeError}</p>
                  </div>
                )}

                {knowledgeLoading && !knowledgeList && (
                  <div className="empty-card" style={{ padding: '40px', textAlign: 'center' }}>
                    <div className="spinner"></div>
                    <h3>Reading the bundle…</h3>
                  </div>
                )}

                {knowledgeList && knowledgeList.concepts.length > 0 && (
                  <>
                    <div className="results-toolbar">
                      <span className="results-count">{knowledgeList.total.toLocaleString()} concept{knowledgeList.total === 1 ? '' : 's'}</span>
                      <Badge tone="green">OKF v{knowledgeStats?.okf_version || '0.2'}</Badge>
                    </div>
                    <div className="okf-grid">
                      {knowledgeList.concepts.map((concept, index) => (
                        <button
                          type="button"
                          className="okf-card"
                          key={concept.concept_id}
                          style={{ animationDelay: `${Math.min(index, 12) * 0.03}s` }}
                          onClick={() => openConcept(concept.concept_id)}
                        >
                          <div className="okf-card__top">
                            <Badge>{concept.type}</Badge>
                            <span className="okf-tag">{concept.status}</span>
                          </div>
                          <h3>{concept.title}</h3>
                          {concept.description && <p>{concept.description}</p>}
                          <div className="okf-card__tags">
                            {concept.tags.slice(0, 4).map((tag) => <span className="okf-tag" key={tag}>{tag}</span>)}
                          </div>
                        </button>
                      ))}
                    </div>
                  </>
                )}

                {knowledgeList && knowledgeList.concepts.length === 0 && (
                  <div className="empty-card">
                    <h3>No concepts match this filter</h3>
                    <p>Try a different type or clear the text filter.</p>
                    <button className="ghost-btn" onClick={() => { setKnowledgeType(''); setKnowledgeQuery('') }}>Clear filters <Icon name="arrow" size={16} /></button>
                  </div>
                )}
              </>
            )}
          </section>
        )}

        {activeTab === 'settings' && (
          <section className="page-section section-container settings-page">
            <SectionLabel
              eyebrow="Settings"
              title="Preferences"
              text="Customize how VIDHIVEDA looks and feels, and review the account this workspace is signed in with."
            />

            <AppearancePanel />

            <div className="settings-section">
              <div className="settings-section__head">
                <h3>Account</h3>
                <p>The identity this workspace is signed in with.</p>
              </div>
              <dl className="settings-facts">
                <div><dt>Name</dt><dd>{session.user.name || '—'}</dd></div>
                <div><dt>Email</dt><dd>{session.user.email || '—'}</dd></div>
                <div><dt>Role</dt><dd>{roleLabel(session.user.role)}</dd></div>
                <div>
                  <dt>Session</dt>
                  <dd>{session.mode === 'demo' ? 'Local demo session' : 'Verified server session'}</dd>
                </div>
              </dl>
              <button className="ghost-btn settings-signout" type="button" onClick={logout}>
                Sign out <Icon name="arrow" size={16} />
              </button>
            </div>
          </section>
        )}
      </main>

      <footer className="footer">
        <div className="footer-inner">
          <Logo />
          <div className="footer-copy">VIDHIVEDA · legal research interface · {datasetStats.total.toLocaleString()} records indexed</div>
          <button className="text-btn" onClick={() => setShowDisclaimer(true)}>Research support only <Icon name="info" size={14}/></button>
        </div>
      </footer>

      {selected && (
        <ReaderView
          record={selected}
          index={readerIndex}
          total={readerIndex >= 0 ? results.length : 0}
          prefs={readerPrefs}
          onPrefsChange={setReaderPrefs}
          onClose={() => setSelected(null)}
          onPrev={readerPrev}
          onNext={readerNext}
        />
      )}

      {knowledgeConcept && (
        <div className="okf-backdrop" onClick={() => setKnowledgeConcept(null)}>
          {knowledgeLoadingConcept ? (
            <div className="okf-panel okf-panel--loading">
              <div className="okf-panel__head">
                <div>
                  <span className="eyebrow">Loading…</span>
                </div>
                <button type="button" className="reader-close" onClick={() => setKnowledgeConcept(null)} aria-label="Close concept">
                  <Icon name="close" size={18} />
                </button>
              </div>
              <div className="okf-panel__body" style={{ textAlign: 'center', paddingTop: '40px' }}>
                <div className="spinner" style={{ margin: '0 auto' }}></div>
                <p style={{ marginTop: '16px', color: 'var(--muted)' }}>Loading concept…</p>
              </div>
            </div>
          ) : (
            <div
              className="okf-panel"
              role="dialog"
              aria-modal="true"
              aria-label={`OKF concept: ${knowledgeConcept.title}`}
              onClick={(event) => event.stopPropagation()}
            >
              <header className="okf-panel__head">
                <div>
                  <span className="eyebrow">{knowledgeConcept.type} · OKF v0.2</span>
                  <h2>{knowledgeConcept.title}</h2>
                </div>
                <button type="button" className="reader-close" onClick={() => setKnowledgeConcept(null)} aria-label="Close concept">
                  <Icon name="close" size={18} />
                </button>
              </header>
              <div className="okf-panel__body">
                <div className="okf-meta">
                  <div><span>Concept id</span><strong>{knowledgeConcept.concept_id}</strong></div>
                  <div><span>Trust tier</span><strong>{knowledgeConcept.trust_tier}</strong></div>
                  <div><span>Status</span><strong>{knowledgeConcept.status}{knowledgeConcept.stale ? ' · stale' : ''}</strong></div>
                </div>

                <OkfBody text={knowledgeConcept.body} onOpenConcept={openConcept} />

                {knowledgeConcept.sources?.length > 0 && (
                  <>
                    <h3>Sources</h3>
                    <div className="okf-sources">
                      {knowledgeConcept.sources.map((source, index) => (
                        <div className="okf-source" key={`${source.resource}-${index}`}>
                          <strong>{source.title || source.id || 'Source'}</strong>
                          <div>
                            {/^https?:/.test(source.resource || '')
                              ? <a href={source.resource} target="_blank" rel="noreferrer">{source.resource}</a>
                              : source.resource}
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                )}

                {knowledgeConcept.outgoing?.length > 0 && (
                  <>
                    <h3>Related concepts</h3>
                    <div className="okf-link-list">
                      {knowledgeConcept.outgoing.map((link) => (
                        <button type="button" className="okf-link-btn" key={link.concept_id} onClick={() => openConcept(link.concept_id)}>
                          {link.title}
                        </button>
                      ))}
                    </div>
                  </>
                )}

                {knowledgeConcept.backlinks?.length > 0 && (
                  <>
                    <h3>Referenced by</h3>
                    <div className="okf-link-list">
                      {knowledgeConcept.backlinks.map((link) => (
                        <button type="button" className="okf-link-btn" key={link.concept_id} onClick={() => openConcept(link.concept_id)}>
                          {link.title}
                        </button>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      <AssistantBubble />
    </div>
  )
}


/**
 * Dropdown whose options may be plain strings or { value, label } pairs, so
 * corpus facet counts can be shown next to each value without changing how the
 * rest of the app reads from it.
 */
function Select({ label, value, options, onChange }) {
  return (
    <label className="field">
      <span>{label}</span>
      <span className="select-wrap">
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          {options.map((option) => {
            const isObject = option && typeof option === 'object'
            const optionValue = isObject ? option.value : option
            const optionLabel = isObject ? option.label : option
            return <option key={optionValue} value={optionValue}>{optionLabel}</option>
          })}
        </select>
        <Icon name="chevron" size={14}/>
      </span>
    </label>
  )
}

export default App
