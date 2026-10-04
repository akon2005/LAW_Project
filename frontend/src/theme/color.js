/**
 * Colour utilities for custom themes and contrast validation.
 *
 * Used to (a) derive a complete, readable palette from the three colours a user
 * picks and (b) refuse/warn on combinations that would fail WCAG AA. Pure
 * functions — unit-checked by `scripts/verify-themes.js`.
 */

const HEX_PATTERN = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i

/** Parse `#rgb` / `#rrggbb` into `{r,g,b}` (0–255), or null when invalid. */
export function parseHex(value) {
  const match = HEX_PATTERN.exec(String(value || '').trim())
  if (!match) return null
  let hex = match[1]
  if (hex.length === 3) {
    hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2]
  }
  return {
    r: parseInt(hex.slice(0, 2), 16),
    g: parseInt(hex.slice(2, 4), 16),
    b: parseInt(hex.slice(4, 6), 16),
  }
}

export function isValidHex(value) {
  return parseHex(value) !== null
}

const clamp = (value) => Math.max(0, Math.min(255, Math.round(value)))

/** `{r,g,b}` → `#rrggbb`. */
export function toHex({ r, g, b }) {
  return `#${[r, g, b].map((channel) => clamp(channel).toString(16).padStart(2, '0')).join('')}`
}

/** Normalise any accepted hex string to `#rrggbb`, or null. */
export function normalizeHex(value) {
  const rgb = parseHex(value)
  return rgb ? toHex(rgb) : null
}

/**
 * Mix two colours. `weight` is how much of `a` to keep (0–1).
 * Matches the sRGB behaviour of CSS `color-mix`, so previews agree with output.
 */
export function mix(a, b, weight) {
  const first = parseHex(a)
  const second = parseHex(b)
  if (!first || !second) return a
  const w = Math.max(0, Math.min(1, weight))
  return toHex({
    r: first.r * w + second.r * (1 - w),
    g: first.g * w + second.g * (1 - w),
    b: first.b * w + second.b * (1 - w),
  })
}

/** WCAG relative luminance (0–1). */
export function relativeLuminance(color) {
  const rgb = parseHex(color)
  if (!rgb) return 0
  const channel = (value) => {
    const c = value / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(rgb.r) + 0.7152 * channel(rgb.g) + 0.0722 * channel(rgb.b)
}

/** WCAG contrast ratio between two colours (1–21). */
export function contrastRatio(a, b) {
  const la = relativeLuminance(a)
  const lb = relativeLuminance(b)
  const lighter = Math.max(la, lb)
  const darker = Math.min(la, lb)
  return (lighter + 0.05) / (darker + 0.05)
}

export function isDarkColor(color) {
  return relativeLuminance(color) < 0.4
}

/** Round to 2dp for display. */
export function round2(value) {
  return Math.round(value * 100) / 100
}

const AA_NORMAL = 4.5
const AA_LARGE = 3

/**
 * Pick a foreground that clears WCAG AA on `background`, preferring the tinted
 * candidate but falling back to near-black/near-white when it does not.
 */
export function readableForeground(background, preferred = null) {
  const dark = '#0b1220'
  const light = '#ffffff'
  const candidates = [preferred, isDarkColor(background) ? light : dark, dark, light].filter(Boolean)
  for (const candidate of candidates) {
    if (contrastRatio(candidate, background) >= AA_NORMAL) return normalizeHex(candidate)
  }
  return toHex({ r: 11, g: 18, b: 32 })
}

/**
 * Derive the eight palette primitives from the three colours a user chooses.
 *
 * Readability is derived from the *actual* background, not from the interface
 * mode: a user who picks a dark background in light mode still gets light text.
 * Surfaces are lifted from the background on the same side of the luminance
 * divide, so the text colour derived for the page also reads on every card.
 *
 * `mode` is accepted for API stability and future tuning; the derivation is
 * intentionally mode-independent because a custom palette defines its own
 * light/dark character through the background the user picked.
 */
export function deriveCustomPrimitives({ background, accent, highlight }, mode = 'light') {
  void mode
  const bg = normalizeHex(background) || '#ffffff'
  const acc = normalizeHex(accent) || '#b38b3e'
  const hi = normalizeHex(highlight) || acc
  const dark = isDarkColor(bg)

  const text = readableForeground(bg, mix(dark ? '#ffffff' : '#0b1220', bg, 0.88))
  const surface = dark ? mix(bg, '#ffffff', 0.9) : mix(bg, '#ffffff', 0.32)
  const border = mix(text, bg, dark ? 0.18 : 0.16)
  const panel = dark ? mix(bg, '#ffffff', 0.84) : mix(hi, '#0b1220', 0.3)
  const panelText = readableForeground(panel, '#ffffff')

  return {
    bg,
    surface,
    text,
    primary: dark ? mix(bg, '#000000', 0.6) : hi,
    accent: acc,
    border,
    panel,
    panelText,
  }
}

/**
 * Audit a derived palette. Returns `{ ok, issues[] }`; a failing pair is
 * surfaced in the UI instead of being applied silently.
 */
export function auditPrimitives(primitives) {
  const issues = []
  const check = (label, fg, bgn, min) => {
    const ratio = contrastRatio(fg, bgn)
    if (ratio < min) {
      issues.push({ label, ratio: round2(ratio), min })
    }
  }
  check('Body text', primitives.text, primitives.bg, AA_NORMAL)
  check('Body text on cards', primitives.text, primitives.surface, AA_NORMAL)
  check('Accent on background', primitives.accent, primitives.bg, AA_LARGE)
  check('Accent on cards', primitives.accent, primitives.surface, AA_LARGE)
  check('Panel text', primitives.panelText, primitives.panel, AA_NORMAL)
  check('Borders on background', primitives.border, primitives.bg, 1.2)
  return { ok: issues.length === 0, issues }
}

export const CONTRAST = { AA_NORMAL, AA_LARGE }
