#!/usr/bin/env node
/**
 * Audit every colour palette in both interface modes.
 *
 * Two things are checked, numerically, with no browser involved:
 *
 *   1. Contrast — WCAG 2.2 AA for the pairs the design system actually uses
 *      (body text, card text, accent, the inverted panel, the brand button).
 *      The derived text tiers are recomputed with the same TEXT_MIX weights
 *      the CSS generator uses, so a passing audit means the generated CSS
 *      passes.
 *   2. Completeness — palettes.generated.css contains a block for every
 *      palette × mode and defines the full semantic token vocabulary, so no
 *      component can be left on a stale hard-coded colour.
 *
 * Exits non-zero when a check fails, so it can gate a build.
 */
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { MODE_TOKENS, PALETTES, TEXT_MIX, CUSTOM_PALETTE } from '../src/theme/palettes.js'
import {
  auditPrimitives,
  contrastRatio,
  deriveCustomPrimitives,
  mix,
  readableForeground,
  round2,
} from '../src/theme/color.js'

const here = dirname(fileURLToPath(import.meta.url))
const cssPath = resolve(here, '../src/styles/palettes.generated.css')

const AA = 4.5
const AA_LARGE = 3
const NON_TEXT = 1.2

const failures = []
const record = (label, ratio, min) => {
  if (ratio + 1e-9 < min) {
    failures.push(`${label} — ${round2(ratio)}:1 (needs ${min}:1)`)
  }
}

/**
 * Contrast pairs the interface relies on, per palette/mode primitives.
 *
 * `onInkOverride` mirrors reality for the custom palette, where the provider
 * derives --on-ink from the palette's own text colour rather than the mode.
 */
function checkPrimitives(label, p, mode, onInkOverride = null) {
  record(`${label} · body text on page`, contrastRatio(p.text, p.bg), AA)
  record(`${label} · body text on card`, contrastRatio(p.text, p.surface), AA)
  record(`${label} · accent on page`, contrastRatio(p.accent, p.bg), AA_LARGE)
  record(`${label} · accent on card`, contrastRatio(p.accent, p.surface), AA_LARGE)
  record(`${label} · panel text on panel`, contrastRatio(p.panelText, p.panel), AA)
  record(`${label} · border on page`, contrastRatio(p.border, p.bg), NON_TEXT)

  // --ink background with --on-ink text (reader tool active state, search submit).
  const onInk = MODE_TOKENS[mode].onInk
  const onInkColor = onInkOverride || (onInk.startsWith('var(') ? p.primary : onInk)
  record(`${label} · control text on ink`, contrastRatio(onInkColor, p.text), AA)

  // Secondary text tiers, recomputed exactly as the CSS generator does.
  const tiers = TEXT_MIX[mode]
  const tier = (key) => mix(p.text, p.bg, tiers[key] / 100)
  record(`${label} · ink-2`, contrastRatio(tier('ink2'), p.bg), AA)
  record(`${label} · text-3`, contrastRatio(tier('t3'), p.bg), AA_LARGE)
  record(`${label} · text-4`, contrastRatio(tier('t4'), p.bg), 2.5)

  // Palette-derived audit (the one the custom-theme UI runs live).
  const audit = auditPrimitives(p)
  for (const issue of audit.issues) {
    failures.push(`${label} · ${issue.label} — ${issue.ratio}:1 (needs ${issue.min}:1)`)
  }
}

/** Tokens the generator derives rather than authors. */
function checkDerivedTokens(label, p) {
  const brandFg = mix(p.accent, '#ffffff', 0.5)
  const panelAccent = mix(p.accent, p.panelText, 0.86)
  record(`${label} · brand mark on brand panel`, contrastRatio(brandFg, p.primary), AA_LARGE)
  record(`${label} · panel accent on panel`, contrastRatio(panelAccent, p.panel), AA_LARGE)
}

for (const palette of PALETTES) {
  checkPrimitives(`${palette.name} (${palette.id}) / light`, palette.light, 'light')
  checkPrimitives(`${palette.name} (${palette.id}) / dark`, palette.dark, 'dark')
  checkDerivedTokens(`${palette.name} (${palette.id}) / light`, palette.light)
  checkDerivedTokens(`${palette.name} (${palette.id}) / dark`, palette.dark)
}

// The custom palette must stay readable for a range of user choices, including
// deliberately awkward ones (very dark background, very light background).
const customSamples = [
  { background: '#f7f4ec', accent: '#b38b3e', highlight: '#14283b' },
  { background: '#0b1220', accent: '#c9a45c', highlight: '#1b3047' },
  { background: '#000000', accent: '#888888', highlight: '#333333' },
  { background: '#ffffff', accent: '#dddddd', highlight: '#eeeeee' },
  { background: '#2a0d3a', accent: '#e0b544', highlight: '#7a35bf' },
]
for (const mode of ['light', 'dark']) {
  customSamples.forEach((sample, index) => {
    const p = deriveCustomPrimitives(sample, mode)
    checkPrimitives(`Custom sample ${index + 1} (${mode})`, p, mode, readableForeground(p.text))
    // Text and panel text are machine-derived, so they must always pass AA.
    record(`Custom ${index + 1} (${mode}) · derived text`, contrastRatio(p.text, p.bg), AA)
    record(`Custom ${index + 1} (${mode}) · derived panel text`, contrastRatio(p.panelText, p.panel), AA)
  })
}

// ── Generated CSS completeness ────────────────────────────────────────────
let css = ''
try {
  css = readFileSync(cssPath, 'utf8')
} catch {
  failures.push(`palettes.generated.css is missing (run npm run generate:palettes)`)
}

if (css) {
  for (const palette of PALETTES) {
    for (const mode of ['light', 'dark']) {
      const selector = `[data-mode='${mode}'][data-palette='${palette.id}']`
      if (!css.includes(selector)) failures.push(`generated CSS has no block for ${selector}`)
    }
  }
  const requiredTokens = [
    '--background', '--foreground', '--surface', '--surface-secondary', '--surface-elevated',
    '--card', '--card-foreground', '--primary', '--primary-foreground', '--secondary',
    '--secondary-foreground', '--accent', '--accent-foreground', '--muted-foreground',
    '--border', '--input', '--input-bg', '--ring', '--sidebar-background',
    '--sidebar-foreground', '--sidebar-accent', '--success', '--warning', '--error',
    '--panel-ink-bg', '--panel-ink-text', '--topbar-bg', '--footer-bg', '--drawer-bg',
    '--overlay', '--shadow', '--card-shadow', '--card-shadow-hover',
  ]
  for (const token of requiredTokens) {
    if (!css.includes(`${token}:`)) failures.push(`generated CSS is missing token ${token}`)
  }
  // The custom palette is applied inline, so it must NOT have a static block.
  if (css.includes(`data-palette='${CUSTOM_PALETTE}'`)) {
    failures.push(`generated CSS should not define a static block for '${CUSTOM_PALETTE}'`)
  }
  console.log(`palettes.generated.css: ${(css.length / 1024).toFixed(1)} kB, 12 palettes × 2 modes`)
}

// ── Report ────────────────────────────────────────────────────────────────
const combinations = PALETTES.length * 2
if (failures.length) {
  console.error(`\n${failures.length} contrast/coverage failure(s):`)
  for (const failure of failures) console.error(`  - ${failure}`)
  process.exit(1)
}

console.log(
  `OK: ${combinations} palette/mode combinations passed WCAG AA checks ` +
    `(plus ${customSamples.length * 2} custom-palette samples).`,
)
