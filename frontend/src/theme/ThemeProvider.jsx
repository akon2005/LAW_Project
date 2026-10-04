/**
 * VIDHIVEDA appearance system.
 *
 * A single provider owns two *independent* choices:
 *
 *   mode     'light' | 'dark' | 'system'   — the interface mode
 *   palette  one of the 12 palette ids, or 'custom'
 *
 * They compose freely: Lavender + Dark is a dark interface with lavender
 * accents; Lavender + Light is a lavender-tinted light interface. The palette
 * never forces a mode.
 *
 * How it reaches the CSS: the provider writes `data-mode` (always the *resolved*
 * light/dark, never 'system') and `data-palette` on <html>. Those two attributes
 * select a block in styles/palettes.generated.css, which turns eight primitives
 * into the whole semantic token vocabulary. A custom palette has no generated
 * block, so its primitives are injected as inline `--p-*` custom properties,
 * which win over the stylesheet and inherit the resolved mode's derived tokens.
 *
 * Components never touch document.documentElement or localStorage — they read
 * `useTheme()` and call the setters.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import {
  CUSTOM_PALETTE,
  DEFAULT_PALETTE,
  MODES,
  PALETTE_IDS,
  getPalette,
  palettePrimitives,
} from './palettes.js'
import { deriveCustomPrimitives, normalizeHex, readableForeground } from './color.js'

/** Interface-mode preference. Kept under the original key so existing choices survive. */
export const THEME_STORAGE_KEY = 'vidhiveda.theme'
/** Colour-palette id. */
export const PALETTE_STORAGE_KEY = 'vidhiveda.palette'
/** The three colours behind a custom palette. */
export const CUSTOM_STORAGE_KEY = 'vidhiveda.custom'
/**
 * The derived custom primitives, cached per mode so the pre-paint script in
 * index.html can apply them without re-running the colour maths (and thus
 * without a flash of the default palette on reload).
 */
export const PAINTED_STORAGE_KEY = 'vidhiveda.custom.painted'

export const THEME_PREFERENCES = MODES

export const DEFAULT_CUSTOM = { background: '#f7f4ec', accent: '#a1792f', highlight: '#14283b' }

const ThemeContext = createContext(null)

/** OS appearance preference, treated as light when unavailable. */
function systemPrefersDark() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  } catch {
    return false
  }
}

function readStored(key, fallback) {
  if (typeof window === 'undefined') return fallback
  try {
    const raw = window.localStorage.getItem(key)
    return raw == null ? fallback : raw
  } catch {
    return fallback
  }
}

function writeStored(key, value) {
  try {
    window.localStorage.setItem(key, value)
  } catch {
    /* private mode: the choice still applies for this session */
  }
}

/** Stored mode preference, or 'system' when absent/invalid/storage-blocked. */
function readMode() {
  const raw = readStored(THEME_STORAGE_KEY, 'system')
  return MODES.includes(raw) ? raw : 'system'
}

/** Stored palette id, or the default when absent/invalid. */
function readPalette() {
  const raw = readStored(PALETTE_STORAGE_KEY, DEFAULT_PALETTE)
  return raw === CUSTOM_PALETTE || PALETTE_IDS.includes(raw) ? raw : DEFAULT_PALETTE
}

/**
 * Stored custom colours. Each channel is validated independently; a partially
 * corrupt value degrades to the default rather than breaking the interface.
 */
export function readCustom() {
  const raw = readStored(CUSTOM_STORAGE_KEY, '')
  if (!raw) return { ...DEFAULT_CUSTOM }
  try {
    const parsed = JSON.parse(raw)
    return {
      background: normalizeHex(parsed?.background) || DEFAULT_CUSTOM.background,
      accent: normalizeHex(parsed?.accent) || DEFAULT_CUSTOM.accent,
      highlight: normalizeHex(parsed?.highlight) || DEFAULT_CUSTOM.highlight,
    }
  } catch {
    return { ...DEFAULT_CUSTOM }
  }
}

/** Every `--p-*` property the stylesheet understands. */
const PRIMITIVE_KEYS = ['bg', 'surface', 'text', 'primary', 'accent', 'border', 'panel', 'panelText']

export function ThemeProvider({ children }) {
  const [mode, setModeState] = useState(readMode)
  const [palette, setPaletteState] = useState(readPalette)
  const [custom, setCustomState] = useState(readCustom)
  const [systemDark, setSystemDark] = useState(systemPrefersDark)

  const resolvedMode = mode === 'system' ? (systemDark ? 'dark' : 'light') : mode
  const isCustom = palette === CUSTOM_PALETTE

  const customPrimitives = useMemo(
    () => (isCustom ? deriveCustomPrimitives(custom, resolvedMode) : null),
    [isCustom, custom, resolvedMode],
  )

  // Follow OS appearance changes only while the preference is 'system'. An
  // explicit light/dark choice is never overwritten by an OS change.
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return undefined
    }
    let query
    try {
      query = window.matchMedia('(prefers-color-scheme: dark)')
    } catch {
      return undefined
    }
    const handler = (event) => setSystemDark(event.matches)
    setSystemDark(query.matches)
    if (typeof query.addEventListener === 'function') {
      query.addEventListener('change', handler)
      return () => query.removeEventListener('change', handler)
    }
    if (typeof query.addListener === 'function') {
      query.addListener(handler)
      return () => query.removeListener(handler)
    }
    return undefined
  }, [])

  // Publish mode + palette to <html> so the token blocks cascade everywhere.
  useEffect(() => {
    if (typeof document === 'undefined') return
    const root = document.documentElement
    root.setAttribute('data-mode', resolvedMode)
    root.setAttribute('data-palette', palette)
    try {
      root.style.colorScheme = resolvedMode
    } catch {
      /* older engines: the attribute alone still drives the token block */
    }

    // A custom palette has no generated block, so supply its primitives inline.
    // --on-ink is bound to the *interface mode* in the stylesheet, which is
    // wrong for a palette whose own background decides its readability, so it
    // is derived from the custom text colour too.
    if (customPrimitives) {
      for (const key of PRIMITIVE_KEYS) {
        root.style.setProperty(`--p-${key}`, customPrimitives[key])
      }
      root.style.setProperty('--on-ink', readableForeground(customPrimitives.text))
    } else {
      for (const key of PRIMITIVE_KEYS) {
        root.style.removeProperty(`--p-${key}`)
      }
      root.style.removeProperty('--on-ink')
    }

    const meta = document.querySelector('meta[name="theme-color"]')
    if (meta) {
      const bg =
        (customPrimitives ? customPrimitives.bg : palettePrimitives(palette, resolvedMode)?.bg) ||
        (resolvedMode === 'dark' ? '#0e1a26' : '#f6f2ea')
      meta.setAttribute('content', bg)
    }

    // Cache the custom primitives for the pre-paint script.
    if (customPrimitives) {
      try {
        const cached = JSON.parse(window.localStorage.getItem(PAINTED_STORAGE_KEY) || '{}')
        cached[resolvedMode] = customPrimitives
        window.localStorage.setItem(PAINTED_STORAGE_KEY, JSON.stringify(cached))
      } catch {
        /* non-fatal: worst case the next reload starts from the default palette */
      }
    }
  }, [resolvedMode, palette, customPrimitives])

  const setMode = useCallback((next) => {
    const value = MODES.includes(next) ? next : 'system'
    setModeState(value)
    writeStored(THEME_STORAGE_KEY, value)
    return value
  }, [])

  const setPalette = useCallback((next) => {
    const value = next === CUSTOM_PALETTE || PALETTE_IDS.includes(next) ? next : DEFAULT_PALETTE
    setPaletteState(value)
    writeStored(PALETTE_STORAGE_KEY, value)
    return value
  }, [])

  const setCustom = useCallback((next) => {
    setCustomState((prev) => {
      const merged = {
        background: normalizeHex(next?.background) || prev.background,
        accent: normalizeHex(next?.accent) || prev.accent,
        highlight: normalizeHex(next?.highlight) || prev.highlight,
      }
      writeStored(CUSTOM_STORAGE_KEY, JSON.stringify(merged))
      return merged
    })
  }, [])

  const resetCustom = useCallback(() => {
    setCustomState({ ...DEFAULT_CUSTOM })
    writeStored(CUSTOM_STORAGE_KEY, JSON.stringify(DEFAULT_CUSTOM))
  }, [])

  const value = useMemo(
    () => ({
      mode,
      palette,
      custom,
      resolvedMode,
      isDark: resolvedMode === 'dark',
      isCustom,
      customPrimitives,
      paletteDefinition: isCustom ? null : getPalette(palette),
      setMode,
      setPalette,
      setCustom,
      resetCustom,
      // Back-compat aliases for the original single-choice API.
      preference: mode,
      setPreference: setMode,
      resolved: resolvedMode,
    }),
    [mode, palette, custom, resolvedMode, isCustom, customPrimitives, setMode, setPalette, setCustom, resetCustom],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used inside <ThemeProvider>')
  }
  return context
}

export default ThemeProvider
