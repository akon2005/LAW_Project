#!/usr/bin/env node
/**
 * Generate `src/styles/palettes.generated.css` from `src/theme/palettes.js`.
 *
 * Runs automatically before `npm run dev` / `npm run build`, so the CSS and the
 * data the gallery renders can never drift apart. The output is committed so a
 * fresh checkout works without running anything.
 *
 * Only the eight palette primitives are authored. The whole semantic token
 * vocabulary is derived from them below, which is what makes every palette
 * complete: pick a palette and background, surfaces, text tiers, borders,
 * accents, panels and shadows all follow.
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { MODE_TOKENS, PALETTES, TEXT_MIX } from '../src/theme/palettes.js'

const here = dirname(fileURLToPath(import.meta.url))
const target = resolve(here, '../src/styles/palettes.generated.css')

const ORDER = ['bg', 'surface', 'text', 'primary', 'accent', 'border', 'panel', 'panelText']

const primitives = (mode, palette) =>
  ORDER.map((key) => `  --p-${key}: ${palette[mode][key]};`).join('\n')

/** mix(text, bg, pct) — the tier ladder that keeps text readable on every palette. */
const tier = (key, mode) =>
  `color-mix(in srgb, var(--p-text) ${TEXT_MIX[mode][key]}%, var(--p-bg))`

function derivation(mode) {
  const m = TEXT_MIX[mode]
  const t = MODE_TOKENS[mode]
  return `  color-scheme: ${t.scheme};

  /* ── Semantic tokens (interface-mode independent names) ───────────── */
  --background: var(--p-bg);
  --foreground: var(--p-text);
  --surface: var(--p-surface);
  --surface-secondary: color-mix(in srgb, var(--p-surface) 92%, var(--p-bg));
  --surface-elevated: var(--p-surface);
  --card: var(--p-surface);
  --card-foreground: var(--p-text);
  --primary: var(--p-primary);
  --primary-foreground: ${t.onInk};
  --secondary: var(--p-accent);
  --secondary-foreground: var(--p-text);
  --accent: var(--p-accent);
  --accent-foreground: var(--p-text);
  /* --muted is the muted *foreground* in this codebase; the muted surface is
     --surface-secondary / --muted-surface. */
  --muted-foreground: ${tier('muted', mode)};
  --muted-surface: color-mix(in srgb, var(--p-surface) 88%, var(--p-bg));
  --border: var(--p-border);
  --input: color-mix(in srgb, var(--p-surface) 96%, var(--p-bg));
  --input-bg: color-mix(in srgb, var(--p-surface) 96%, var(--p-bg));
  --input-foreground: var(--p-text);
  --ring: color-mix(in srgb, var(--p-accent) 45%, transparent);
  --sidebar-background: color-mix(in srgb, var(--p-surface) 74%, var(--p-bg));
  --sidebar-foreground: var(--p-text);
  --sidebar-accent: var(--p-accent);
  --sidebar-accent-foreground: var(--p-text);
  --success: ${t.success};
  --warning: ${t.warning};
  --error: ${t.error};

  /* ── Backgrounds & surfaces ──────────────────────────────────────── */
  --bg: var(--p-bg);
  --bg-2: color-mix(in srgb, var(--p-bg) 88%, var(--p-surface));
  --paper: var(--p-bg);
  --paper-2: var(--p-surface);
  --surface-2: color-mix(in srgb, var(--p-surface) 92%, var(--p-bg));
  --surface-3: color-mix(in srgb, var(--p-surface) 86%, var(--p-bg));
  --surface-translucent: color-mix(in srgb, var(--p-surface) 62%, transparent);
  --topbar-bg: color-mix(in srgb, var(--p-bg) 88%, transparent);
  --strip-bg: color-mix(in srgb, var(--p-surface) 58%, var(--p-bg));
  --footer-bg: color-mix(in srgb, var(--p-surface) 38%, var(--p-bg));
  --notice-bg: var(--p-surface);
  --notice-border: color-mix(in srgb, var(--p-border) 86%, var(--p-text));
  --notice-text: ${tier('t3', mode)};
  --drawer-bg: var(--p-surface);
  --drawer-border: var(--p-border);
  --overlay: color-mix(in srgb, var(--p-primary) 58%, transparent);
  --art-bg: color-mix(in srgb, var(--p-surface) 68%, var(--p-bg));
  --meter-track: color-mix(in srgb, var(--p-border) 70%, var(--p-surface));
  --white: #ffffff;

  /* ── Borders ─────────────────────────────────────────────────────── */
  --line: var(--p-border);
  --line-2: color-mix(in srgb, var(--p-border) 62%, var(--p-surface));
  --input-border: color-mix(in srgb, var(--p-border) 76%, var(--p-text));
  --border-strong: color-mix(in srgb, var(--p-accent) 52%, var(--p-text));
  --border-hover: color-mix(in srgb, var(--p-border) 58%, var(--p-text));
  --placeholder: ${tier('muted2', mode)};

  /* ── Text tiers ──────────────────────────────────────────────────── */
  --ink: var(--p-text);
  --ink-2: ${tier('ink2', mode)};
  --muted: ${tier('muted', mode)};
  --muted-2: ${tier('muted2', mode)};
  --text-2: ${tier('t2', mode)};
  --text-3: ${tier('t3', mode)};
  --text-4: ${tier('t4', mode)};
  --text-5: ${tier('muted2', mode)};
  --heading: var(--p-text);
  --icon-muted: ${tier('t3', mode)};
  --on-ink: ${t.onInk};
  --brand-bg: var(--p-primary);
  /* Kept light enough to clear 3:1 on every palette's (always dark) primary. */
  --brand-fg: color-mix(in srgb, var(--p-accent) 50%, #ffffff);

  /* ── Accents & feedback ──────────────────────────────────────────── */
  --gold: color-mix(in srgb, var(--p-accent) ${m.gold}%, var(--p-text));
  --gold-soft: color-mix(in srgb, var(--p-accent) 16%, var(--p-surface));
  --green: var(--success);
  --green-soft: color-mix(in srgb, var(--success) 16%, var(--p-surface));
  --success-soft: color-mix(in srgb, var(--success) 16%, var(--p-surface));
  --warning-soft: color-mix(in srgb, var(--warning) 16%, var(--p-surface));
  --error-soft: color-mix(in srgb, var(--error) 14%, var(--p-surface));
  --error-border: color-mix(in srgb, var(--error) 42%, var(--p-border));
  --hover-bg: color-mix(in srgb, var(--p-text) 6%, var(--p-surface));
  --focus-ring: color-mix(in srgb, var(--p-accent) 26%, transparent);

  /* ── Inverted panel (grounded answer card, brand panels) ─────────── */
  --panel-ink-bg: var(--p-panel);
  --panel-ink-text: var(--p-panelText);
  --panel-ink-text-2: color-mix(in srgb, var(--p-panelText) 78%, var(--p-panel));
  --panel-ink-text-3: color-mix(in srgb, var(--p-panelText) 64%, var(--p-panel));
  --panel-ink-accent: color-mix(in srgb, var(--p-accent) 86%, var(--p-panelText));
  --panel-ink-border: color-mix(in srgb, var(--p-panelText) 18%, transparent);
  --panel-ink-surface: color-mix(in srgb, var(--p-panelText) 7%, transparent);
  --panel-ink-hover: color-mix(in srgb, var(--p-panelText) 11%, transparent);

  /* ── Elevation ───────────────────────────────────────────────────── */
  --shadow: ${t.shadow};
  --card-shadow: ${t.cardShadow};
  --card-shadow-hover: ${t.cardShadowHover};`
}

const block = (mode, palette) =>
  `/* ${palette.name} — ${mode} */\n[data-mode='${mode}'][data-palette='${palette.id}'] {\n${primitives(mode, palette)}\n}`

const fallback = PALETTES.find((palette) => palette.id === 'ivory')

const header = `/*
 * AUTO-GENERATED by scripts/generate-palette-css.js — do not edit by hand.
 * Edit src/theme/palettes.js and run: npm run generate:palettes
 *
 * Authored: the eight palette primitives per (palette, mode).
 * Derived:  every semantic token, so a palette can never be half-applied.
 */`

const rootBlock = `/* Fallback before the provider sets attributes: ivory, light. */
:root {
${primitives('light', fallback)}
${derivation('light')}
}`

const darkBlock = `/* Default dark (ivory). A palette block below overrides the primitives. */
[data-mode='dark'] {
${primitives('dark', fallback)}
${derivation('dark')}
}`

const paletteBlocks = PALETTES.map(
  (palette) => block('light', palette) + '\n\n' + block('dark', palette),
).join('\n\n')

const output = `${header}\n\n${rootBlock}\n\n${darkBlock}\n\n${paletteBlocks}\n`

mkdirSync(dirname(target), { recursive: true })
writeFileSync(target, output, 'utf8')

console.log(
  `palettes: ${PALETTES.length} palettes × 2 modes — wrote ${output.length} bytes to ${target}`,
)
