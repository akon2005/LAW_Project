import { useEffect, useMemo, useRef, useState } from 'react'
import Icon from '../Icon.jsx'
import { CUSTOM_PALETTE, PALETTES, getPalette } from '../../theme/palettes.js'
import { DEFAULT_CUSTOM, useTheme } from '../../theme/ThemeProvider.jsx'
import {
  auditPrimitives,
  deriveCustomPrimitives,
  normalizeHex,
  round2,
} from '../../theme/color.js'

/**
 * Appearance & Personalization.
 *
 * Two independent choices — interface mode and colour palette — plus an
 * optional custom palette. Everything here reads and writes the single
 * ThemeProvider; no second source of theme state exists.
 */

/** Interface mode options. Order defines keyboard arrow order. */
const MODE_OPTIONS = [
  { value: 'light', label: 'Light', icon: 'sun', blurb: 'A clean, bright workspace.' },
  { value: 'dark', label: 'Dark', icon: 'moon', blurb: 'Easy on the eyes in low light.' },
  { value: 'system', label: 'System default', icon: 'monitor', blurb: 'Follows your device appearance.' },
]

/** Gallery groups, in display order. */
const PALETTE_GROUPS = [
  { id: 'Neutral', label: 'Neutral & professional' },
  { id: 'Colour', label: 'Colourful' },
]

/** The three colours a user picks for a custom palette. */
const CUSTOM_FIELDS = [
  { key: 'background', label: 'Main background', hint: 'The page behind everything.' },
  { key: 'accent', label: 'Accent colour', hint: 'Links, meters and highlights.' },
  { key: 'highlight', label: 'Primary highlight', hint: 'Brand marks and inverted panels.' },
]

const MODE_VALUES = MODE_OPTIONS.map((option) => option.value)

/** Roving-focus arrow-key handling shared by the radiogroups. */
function moveFocus(event, values, current, idPrefix, select) {
  const keys = ['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End']
  if (!keys.includes(event.key)) return
  event.preventDefault()
  const index = values.indexOf(current)
  let next = index
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % values.length
  else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index - 1 + values.length) % values.length
  else if (event.key === 'End') next = values.length - 1
  else next = 0
  select(values[next])
  document.getElementById(`${idPrefix}-${values[next]}`)?.focus()
}

export default function AppearancePanel() {
  const {
    mode,
    palette,
    custom,
    resolvedMode,
    isCustom,
    setMode,
    setPalette,
    setCustom,
    resetCustom,
  } = useTheme()

  const [draft, setDraft] = useState(custom)
  const [toast, setToast] = useState('')
  const toastTimer = useRef(null)

  // Re-sync the draft when the provider's custom colours change (save/reset).
  useEffect(() => setDraft(custom), [custom])

  useEffect(() => () => window.clearTimeout(toastTimer.current), [])

  const notify = (message) => {
    setToast(message)
    window.clearTimeout(toastTimer.current)
    toastTimer.current = window.setTimeout(() => setToast(''), 2400)
  }

  /** Colours live in the gallery use — derive them for the active mode. */
  const primitivesFor = (paletteId, modeValue) => {
    if (paletteId === CUSTOM_PALETTE) return deriveCustomPrimitives(custom, modeValue)
    return getPalette(paletteId)?.[modeValue] || null
  }

  // ── Interface mode ──────────────────────────────────────────────────────
  const modePreview = (modeValue) => {
    if (modeValue === 'system') {
      const light = primitivesFor(palette, 'light') || {}
      const dark = primitivesFor(palette, 'dark') || {}
      return {
        style: { background: `linear-gradient(105deg, ${light.bg} 0 50%, ${dark.bg} 50% 100%)` },
        bar: { background: `linear-gradient(180deg, ${light.primary} 0 50%, ${dark.accent} 50% 100%)` },
        block: { background: `linear-gradient(105deg, ${light.surface} 0 50%, ${dark.surface} 50% 100%)` },
      }
    }
    const p = primitivesFor(palette, modeValue) || {}
    return {
      style: { background: p.bg },
      bar: { background: p.primary },
      block: { background: p.surface },
    }
  }

  const chooseMode = (value) => {
    setMode(value)
    notify(`Interface mode — ${MODE_OPTIONS.find((o) => o.value === value)?.label || value}`)
  }

  const choosePalette = (paletteId) => {
    setPalette(paletteId)
    const name = getPalette(paletteId)?.name || paletteId
    notify(`Colour theme — ${name}`)
  }

  // ── Custom palette ──────────────────────────────────────────────────────
  const sanitized = useMemo(
    () => ({
      background: normalizeHex(draft.background),
      accent: normalizeHex(draft.accent),
      highlight: normalizeHex(draft.highlight),
    }),
    [draft],
  )

  const fieldErrors = {
    background: sanitized.background ? '' : 'Enter a hex colour such as #f7f4ec.',
    accent: sanitized.accent ? '' : 'Enter a hex colour such as #b38b3e.',
    highlight: sanitized.highlight ? '' : 'Enter a hex colour such as #14283b.',
  }
  const allValid = Boolean(sanitized.background && sanitized.accent && sanitized.highlight)

  const derived = useMemo(
    () =>
      deriveCustomPrimitives(
        {
          background: sanitized.background || custom.background,
          accent: sanitized.accent || custom.accent,
          highlight: sanitized.highlight || custom.highlight,
        },
        resolvedMode,
      ),
    [sanitized, custom, resolvedMode],
  )

  const audit = useMemo(() => auditPrimitives(derived), [derived])
  const canSave = allValid && audit.ok

  const changeField = (key, value) => setDraft((prev) => ({ ...prev, [key]: value }))

  const saveCustom = () => {
    if (!canSave) return
    setCustom(sanitized)
    setPalette(CUSTOM_PALETTE)
    notify('Custom theme applied')
  }

  const doReset = () => {
    resetCustom()
    setDraft({ ...DEFAULT_CUSTOM })
    notify('Custom theme reset')
  }

  return (
    <div className="settings-section">
      <div className="settings-section__head">
        <h3>Appearance &amp; Personalization</h3>
        <p>Customize your workspace with themes and colours that suit your preferences.</p>
      </div>

      {/* ── A. Interface mode ─────────────────────────────────────────── */}
      <section className="appearance-block" aria-labelledby="appearance-mode-title">
        <div className="appearance-block__head">
          <h4 id="appearance-mode-title">Interface mode</h4>
          <p>Choose how bright the interface is. This is independent of the colour theme below.</p>
        </div>

        <div className="theme-grid" role="radiogroup" aria-label="Interface mode">
          {MODE_OPTIONS.map((option, index) => {
            const active = mode === option.value
            const preview = modePreview(option.value)
            return (
              <button
                key={option.value}
                id={`theme-option-${option.value}`}
                type="button"
                role="radio"
                aria-checked={active}
                tabIndex={active ? 0 : -1}
                className={`theme-card${active ? ' is-active' : ''}`}
                onClick={() => chooseMode(option.value)}
                onKeyDown={(event) => moveFocus(event, MODE_VALUES, mode, 'theme-option', chooseMode)}
              >
                <span className="theme-card__top">
                  <span className="theme-card__icon"><Icon name={option.icon} size={17} /></span>
                  <span className="theme-card__label">{option.label}</span>
                  <span className="theme-card__check" aria-hidden="true">
                    {active ? <Icon name="check" size={13} /> : null}
                  </span>
                </span>

                <span className="theme-preview" style={{ ...preview.style, borderColor: 'var(--line)' }} aria-hidden="true">
                  <span className="theme-preview__bar" style={preview.bar} />
                  <span className="theme-preview__block" style={preview.block} />
                  <span className="theme-preview__block theme-preview__block--short" style={preview.block} />
                </span>

                <span className="theme-card__blurb">{option.blurb}</span>
                <span className="theme-card__state">
                  {active
                    ? 'Selected'
                    : option.value === 'system'
                      ? `Currently ${resolvedMode}`
                      : 'Select'}
                </span>
              </button>
            )
          })}
        </div>
      </section>

      {/* ── B. Colour theme ───────────────────────────────────────────── */}
      <section className="appearance-block" aria-labelledby="appearance-palette-title">
        <div className="appearance-block__head">
          <h4 id="appearance-palette-title">Colour theme</h4>
          <p>
            Pick a palette. Every theme works in both interface modes — the accent and surfaces follow
            your choice, the light or dark mode stays yours.
          </p>
        </div>

        {PALETTE_GROUPS.map((group) => {
          const groupPalettes = PALETTES.filter((entry) => entry.group === group.id)
          const ids = groupPalettes.map((entry) => entry.id)
          const groupActive = ids.includes(palette)
          return (
            <div className="palette-group" key={group.id}>
              <span className="palette-group__label">{group.label}</span>
              <div className="palette-grid" role="radiogroup" aria-label={`${group.label} colour themes`}>
                {groupPalettes.map((entry) => {
                  const active = palette === entry.id
                  const p = entry[resolvedMode]
                  return (
                    <button
                      key={entry.id}
                      id={`palette-option-${entry.id}`}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      tabIndex={active || (!groupActive && entry.id === ids[0]) ? 0 : -1}
                      className={`palette-card${active ? ' is-active' : ''}`}
                      onClick={() => choosePalette(entry.id)}
                      onKeyDown={(event) => moveFocus(event, ids, palette, 'palette-option', choosePalette)}
                    >
                      <span className="palette-card__head">
                        <span className="palette-card__name">{entry.name}</span>
                        <span className="palette-card__check" aria-hidden="true">
                          {active ? <Icon name="check" size={12} /> : null}
                        </span>
                      </span>

                      <span
                        className="palette-card__preview"
                        style={{ background: p.bg, borderColor: p.border }}
                        aria-hidden="true"
                      >
                        <span className="palette-card__bar" style={{ background: p.primary }} />
                        <span className="palette-card__body">
                          <span className="palette-card__chip" style={{ background: p.surface, borderColor: p.border }} />
                          <span className="palette-card__line" style={{ background: p.text }} />
                          <span className="palette-card__line palette-card__line--short" style={{ background: p.accent }} />
                        </span>
                      </span>

                      <span className="palette-card__swatches">
                        <span className="palette-swatch" role="img" aria-label={`Background ${p.bg}`} style={{ background: p.bg }} />
                        <span className="palette-swatch" role="img" aria-label={`Card surface ${p.surface}`} style={{ background: p.surface }} />
                        <span className="palette-swatch" role="img" aria-label={`Primary text ${p.text}`} style={{ background: p.text }} />
                        <span className="palette-swatch" role="img" aria-label={`Accent ${p.accent}`} style={{ background: p.accent }} />
                      </span>

                      <span className="palette-card__desc">{entry.description}</span>
                      <span className="palette-card__state">{active ? 'Selected' : 'Select'}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </section>

      {/* ── C. Custom theme ───────────────────────────────────────────── */}
      <section className="appearance-block" aria-labelledby="appearance-custom-title">
        <div className="appearance-block__head">
          <h4 id="appearance-custom-title">Custom theme</h4>
          <p>
            Build your own palette from three colours. Text and surfaces are derived automatically so
            long documents stay readable.
          </p>
        </div>

        <div className="custom-theme">
          <div className="custom-theme__fields">
            {CUSTOM_FIELDS.map((field) => {
              const error = fieldErrors[field.key]
              return (
                <div className="custom-field" key={field.key}>
                  <label htmlFor={`custom-${field.key}`}>{field.label}</label>
                  <div className="custom-field__row">
                    <input
                      type="color"
                      className="custom-field__picker"
                      aria-label={`${field.label} colour picker`}
                      value={sanitized[field.key] || '#000000'}
                      onChange={(event) => changeField(field.key, event.target.value)}
                    />
                    <input
                      id={`custom-${field.key}`}
                      className={`custom-field__hex${error ? ' is-invalid' : ''}`}
                      type="text"
                      spellCheck="false"
                      autoComplete="off"
                      value={draft[field.key]}
                      aria-invalid={Boolean(error)}
                      aria-describedby={`custom-${field.key}-note`}
                      onChange={(event) => changeField(field.key, event.target.value)}
                    />
                  </div>
                  <p id={`custom-${field.key}-note`} className={`custom-field__note${error ? ' is-error' : ''}`}>
                    {error || field.hint}
                  </p>
                </div>
              )
            })}
          </div>

          <div className="custom-theme__preview" aria-label="Live preview of your custom theme">
            <span className="custom-preview" style={{ background: derived.bg, borderColor: derived.border }}>
              <span className="custom-preview__bar" style={{ background: derived.primary, color: derived.panelText }}>
                VIDHIVEDA
              </span>
              <span className="custom-preview__card" style={{ background: derived.surface, borderColor: derived.border, color: derived.text }}>
                <span className="custom-preview__line" style={{ background: derived.text }} />
                <span className="custom-preview__line custom-preview__line--short" style={{ background: derived.accent }} />
                <span className="custom-preview__chip" style={{ background: derived.accent }} />
              </span>
              <span className="custom-preview__panel" style={{ background: derived.panel, color: derived.panelText }}>
                Retrieved answer
              </span>
            </span>
            <span className="custom-theme__preview-label">
              Live preview — {resolvedMode} mode
            </span>
          </div>
        </div>

        <div className={`contrast-report${audit.ok ? ' is-ok' : ' is-warning'}`} role="status">
          {audit.ok ? (
            <p className="contrast-report__ok">
              <Icon name="check" size={15} />
              Contrast passes WCAG AA for body text, headings and accents.
            </p>
          ) : (
            <>
              <p className="contrast-report__title">
                Not applied — some combinations are too low-contrast:
              </p>
              <ul className="contrast-report__list">
                {audit.issues.map((issue) => (
                  <li key={issue.label}>
                    {issue.label}: <strong>{round2(issue.ratio)}:1</strong> — needs {issue.min}:1.
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        <div className="custom-theme__actions">
          <button className="ghost-btn" type="button" onClick={doReset}>
            Reset
          </button>
          <button
            className="custom-theme__save"
            type="button"
            onClick={saveCustom}
            disabled={!canSave}
          >
            Save custom theme
          </button>
          {isCustom ? (
            <span className="custom-theme__active">
              <Icon name="check" size={14} /> Custom theme is active
            </span>
          ) : null}
        </div>

        <p className="settings-note">
          Your interface mode and colour theme are saved on this device and restored on your next
          visit — including after signing out and back in. <strong>System</strong> follows your
          operating system and updates automatically when it changes.
        </p>
      </section>

      {toast && (
        <div className="theme-toast" role="status" aria-live="polite">
          <Icon name="check" size={15} />
          {toast}
        </div>
      )}
    </div>
  )
}
