import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { writeClipboard, recordToText } from '../utils/clipboard.js'
import { toParagraphs } from '../utils/readerText.js'

/**
 * Reading view for a single corpus record.
 *
 * Built for long-form legal text: the whole point is that a user can sit and
 * read a retrieved chunk without squinting. Everything here is presentation
 * only — the text, source trail and confidence come straight from the record
 * the backend returned, and nothing is derived or invented.
 */

/** Reader preferences are user-visible settings, so keep the bounds generous. */
export const SCALE_MIN = 0.8
export const SCALE_MAX = 2.4
export const SCALE_STEP = 0.1

export const DEFAULT_READER_PREFS = {
  scale: 1,
  lineHeight: 'normal',
  measure: 'standard',
  font: 'serif',
  theme: 'light',
}

export const LINE_HEIGHTS = { compact: 1.5, normal: 1.75, relaxed: 2.05 }
export const MEASURES = { narrow: '58ch', standard: '76ch', wide: '96ch', full: 'none' }

const PREFS_KEY = 'vidhiveda.reader'

const clampScale = (value) =>
  Math.min(SCALE_MAX, Math.max(SCALE_MIN, Math.round(value * 100) / 100))

/**
 * Preferences are read once at start-up and written back on change. A bad or
 * partial stored value must never break the reader, so every field is
 * validated against the known option sets.
 */
export function loadReaderPrefs() {
  if (typeof window === 'undefined') return { ...DEFAULT_READER_PREFS }
  try {
    const raw = window.localStorage.getItem(PREFS_KEY)
    if (!raw) return { ...DEFAULT_READER_PREFS }
    const stored = JSON.parse(raw)
    return {
      scale: clampScale(Number(stored.scale) || 1),
      lineHeight: LINE_HEIGHTS[stored.lineHeight] ? stored.lineHeight : DEFAULT_READER_PREFS.lineHeight,
      measure: MEASURES[stored.measure] ? stored.measure : DEFAULT_READER_PREFS.measure,
      font: stored.font === 'sans' ? 'sans' : 'serif',
      theme: ['light', 'sepia', 'dark'].includes(stored.theme) ? stored.theme : 'light',
    }
  } catch {
    return { ...DEFAULT_READER_PREFS }
  }
}

export function saveReaderPrefs(prefs) {
  try {
    window.localStorage.setItem(PREFS_KEY, JSON.stringify(prefs))
  } catch {
    /* private-mode browsers: preferences simply do not persist */
  }
}

function ToolButton({ active, onClick, children, title, ariaLabel }) {
  return (
    <button
      type="button"
      className={`reader-tool ${active ? 'is-active' : ''}`}
      onClick={onClick}
      title={title}
      aria-label={ariaLabel || title}
      aria-pressed={active ? 'true' : undefined}
    >
      {children}
    </button>
  )
}

function ReaderView({ record, index, total, prefs, onPrefsChange, onClose, onPrev, onNext }) {
  const panelRef = useRef(null)
  const [copyStatus, setCopyStatus] = useState(null)

  // Functional update: several controls can be pressed in the same tick, and a
  // spread of the captured `prefs` would let the later one undo the earlier.
  const update = (patch) => onPrefsChange((previous) => ({ ...previous, ...patch }))

  // Move focus into the reader on open and hand it back to whatever was focused
  // before on close, so keyboard users are never dropped at the top of the page.
  useEffect(() => {
    const previous = document.activeElement
    panelRef.current?.focus()
    return () => previous?.focus?.()
  }, [])

  // Escape closes; +/-/0 resize the text; arrows step through the result set.
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) return
      if (event.key === '+' || event.key === '=') {
        event.preventDefault()
        update({ scale: clampScale(prefs.scale + SCALE_STEP) })
      } else if (event.key === '-' || event.key === '_') {
        event.preventDefault()
        update({ scale: clampScale(prefs.scale - SCALE_STEP) })
      } else if (event.key === '0') {
        event.preventDefault()
        update({ scale: 1 })
      } else if (event.key === 'ArrowLeft' && onPrev) {
        event.preventDefault()
        onPrev()
      } else if (event.key === 'ArrowRight' && onNext) {
        event.preventDefault()
        onNext()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [prefs, onClose, onPrev, onNext])

  const paragraphs = useMemo(() => toParagraphs(record?.summary), [record?.summary])

  // Corpus records carry sections as an array, browse-mode sample records as a
  // comma-joined string. Normalising here keeps both shapes safe to render.
  const sections = useMemo(() => {
    const raw = record?.sections
    if (!raw) return []
    const list = Array.isArray(raw) ? raw : String(raw).split(',')
    return list.map((item) => String(item).trim()).filter(Boolean)
  }, [record?.sections])

  const articles = useMemo(() => {
    const raw = record?.articles
    if (!raw) return []
    const list = Array.isArray(raw) ? raw : String(raw).split(',')
    return list.map((item) => String(item).trim()).filter(Boolean)
  }, [record?.articles])
  const zoomPercent = Math.round(prefs.scale * 100)
  const sourceLines = useMemo(() => {
    if (!record) return []
    const lines = []
    if (record.source) lines.push({ icon: 'file', label: 'Source file', value: record.source })
    if (record.citation) lines.push({ icon: 'book', label: 'Reported citation', value: record.citation })
    if (record.chunkId) lines.push({ icon: 'book', label: 'Chunk', value: `${record.chunkId}${record.chunkIndex != null ? ` (index ${record.chunkIndex})` : ''}` })
    if (record.judgmentDate) lines.push({ icon: 'book', label: 'Judgment date', value: record.judgmentDate })
    if (record.recordType) lines.push({ icon: 'info', label: 'Record type', value: record.recordType })
    return lines
  }, [record])

  const copyText = async () => {
    const copied = await writeClipboard(recordToText(record))
    setCopyStatus(copied ? 'copied' : 'failed')
    window.setTimeout(() => setCopyStatus(null), 2200)
  }

  if (!record) return null

  // Rendered into <body> rather than in place: a transform or filter on any
  // ancestor would otherwise become the containing block for this fixed
  // overlay and the panel would size against the page instead of the viewport.
  return createPortal(
    <div className="reader-backdrop" onClick={onClose}>
      <div
        className={`reader-panel reader-theme-${prefs.theme} reader-font-${prefs.font}`}
        role="dialog"
        aria-modal="true"
        aria-label={`Reading view: ${record.title || 'source record'}`}
        tabIndex={-1}
        ref={panelRef}
        onClick={(event) => event.stopPropagation()}
        style={{
          '--reader-scale': prefs.scale,
          '--reader-line': LINE_HEIGHTS[prefs.lineHeight] || LINE_HEIGHTS.normal,
          '--reader-measure': MEASURES[prefs.measure] || MEASURES.standard,
        }}
      >
        <header className="reader-head">
          <div className="reader-head-copy">
            <span className="eyebrow">
              Reading view{total > 1 ? ` · record ${index + 1} of ${total}` : ''}
            </span>
            <div className="reader-badges">
              {record.area && <span className="badge">{record.area}</span>}
              {record.court && record.court !== 'Court not recorded' && <span className="badge">{record.court}</span>}
              {record.year && <span className="badge">{record.year}</span>}
              {typeof record.score === 'number' && <span className="badge badge-green">Match {record.score}%</span>}
            </div>
          </div>
          <div className="reader-actions">
            <button type="button" className="reader-action" onClick={copyText} aria-live="polite">
              {copyStatus === 'copied' ? 'Copied ✓' : copyStatus === 'failed' ? 'Copy unavailable' : 'Copy text'}
            </button>
            <button type="button" className="reader-action" onClick={() => window.print()}>Print</button>
            <button type="button" className="reader-close" onClick={onClose} aria-label="Close reading view">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
                <path d="m6 6 12 12M18 6 6 18" />
              </svg>
            </button>
          </div>
        </header>

        <div className="reader-tools" role="group" aria-label="Reading settings">
          <div className="reader-tool-group" aria-label="Text size">
            <span className="reader-tool-label">Text size</span>
            <ToolButton title="Decrease text size (−)" onClick={() => update({ scale: clampScale(prefs.scale - SCALE_STEP) })}>A−</ToolButton>
            <span className="reader-zoom" aria-live="polite">{zoomPercent}%</span>
            <ToolButton title="Increase text size (+)" onClick={() => update({ scale: clampScale(prefs.scale + SCALE_STEP) })}>A+</ToolButton>
            <ToolButton title="Reset text size (0)" onClick={() => update({ scale: 1 })}>Reset</ToolButton>
            <ToolButton title="Fit text to the window" onClick={() => update({ scale: 1.6, measure: 'full' })}>Fit</ToolButton>
          </div>

          <div className="reader-tool-group" aria-label="Line spacing">
            <span className="reader-tool-label">Spacing</span>
            <ToolButton active={prefs.lineHeight === 'compact'} title="Compact line spacing" onClick={() => update({ lineHeight: 'compact' })}>Compact</ToolButton>
            <ToolButton active={prefs.lineHeight === 'normal'} title="Normal line spacing" onClick={() => update({ lineHeight: 'normal' })}>Normal</ToolButton>
            <ToolButton active={prefs.lineHeight === 'relaxed'} title="Relaxed line spacing" onClick={() => update({ lineHeight: 'relaxed' })}>Relaxed</ToolButton>
          </div>

          <div className="reader-tool-group" aria-label="Column width">
            <span className="reader-tool-label">Width</span>
            <ToolButton active={prefs.measure === 'narrow'} title="Narrow column" onClick={() => update({ measure: 'narrow' })}>Narrow</ToolButton>
            <ToolButton active={prefs.measure === 'standard'} title="Standard column" onClick={() => update({ measure: 'standard' })}>Standard</ToolButton>
            <ToolButton active={prefs.measure === 'wide'} title="Wide column" onClick={() => update({ measure: 'wide' })}>Wide</ToolButton>
            <ToolButton active={prefs.measure === 'full'} title="Full width" onClick={() => update({ measure: 'full' })}>Full</ToolButton>
          </div>

          <div className="reader-tool-group" aria-label="Typeface and theme">
            <span className="reader-tool-label">Type</span>
            <ToolButton active={prefs.font === 'serif'} title="Serif typeface" onClick={() => update({ font: 'serif' })}>Serif</ToolButton>
            <ToolButton active={prefs.font === 'sans'} title="Sans-serif typeface" onClick={() => update({ font: 'sans' })}>Sans</ToolButton>
            <span className="reader-tool-divider" aria-hidden="true" />
            <ToolButton active={prefs.theme === 'light'} title="Light theme" onClick={() => update({ theme: 'light' })}>Light</ToolButton>
            <ToolButton active={prefs.theme === 'sepia'} title="Sepia theme" onClick={() => update({ theme: 'sepia' })}>Sepia</ToolButton>
            <ToolButton active={prefs.theme === 'dark'} title="Dark theme" onClick={() => update({ theme: 'dark' })}>Dark</ToolButton>
          </div>
        </div>

        <div className="reader-scroll">
          <article className="reader-article">
            <h1 className="reader-title">{record.title}</h1>
            <p className="reader-byline">
              {[record.court, record.year, record.chunkId && `chunk ${record.chunkId}`].filter(Boolean).join(' · ')}
            </p>

            {[...sections, ...articles].length > 0 && (
              <p className="reader-tags">
                {[...sections, ...articles].map((section, i) => <span key={`${section}-${i}`}>§ {section}</span>)}
              </p>
            )}

            <div className="reader-text">
              {paragraphs.length
                ? paragraphs.map((paragraph, i) => <p key={i}>{paragraph}</p>)
                : <p className="reader-empty">No text was stored for this chunk.</p>}
            </div>

            {sourceLines.length > 0 && (
              <section className="reader-source" aria-label="Source trail">
                <h2>Source trail</h2>
                <ul>
                  {sourceLines.map((line) => (
                    <li key={`${line.label}-${line.value}`}>
                      <span>{line.label}</span>
                      <strong>{line.value}</strong>
                    </li>
                  ))}
                  {record.sourceUrl && (
                    <li>
                      <span>Link</span>
                      <a href={record.sourceUrl} target="_blank" rel="noreferrer noopener">{record.sourceUrl}</a>
                    </li>
                  )}
                </ul>
              </section>
            )}

            <p className="reader-disclaimer">
              Retrieved from the indexed legal corpus (ChromaDB) with the source filename and chunk id it was
              stored under. Verify against the original judgment before relying on it.
            </p>
          </article>
        </div>

        <footer className="reader-nav">
          <button type="button" onClick={onPrev} disabled={!onPrev} aria-label="Previous record">
            ← Previous
          </button>
          <span className="reader-hint">Esc closes · +/− resizes · ←/→ moves between records</span>
          <button type="button" onClick={onNext} disabled={!onNext} aria-label="Next record">
            Next →
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  )
}

export default ReaderView
