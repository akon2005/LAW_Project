/**
 * VIDHIVEDA colour palettes.
 *
 * Single source of truth. `scripts/generate-palette-css.js` turns these into
 * `src/styles/palettes.generated.css` (run automatically by `npm run dev` /
 * `npm run build`, and asserted by `scripts/verify-themes.js`), so the CSS can
 * never drift from the data the gallery renders.
 *
 * Each palette defines eight primitives per interface mode. Everything else in
 * the design system is *derived* from these in CSS (`color-mix`), which is why
 * a palette can never be half-applied: change a primitive and the whole
 * interface follows.
 *
 *   bg         page background
 *   surface    card / input surface
 *   text       primary text
 *   primary    strongest brand colour (nav-active, brand mark, inverted panels)
 *   accent     accent colour (eyebrows, links, meters, focus)
 *   border     hairline borders
 *   panel      inverted "answer" panel background
 *   panelText  text on that panel
 */

export const MODES = ['light', 'dark', 'system']

export const PALETTES = [
  {
    id: 'ivory',
    name: 'Classic Ivory',
    group: 'Neutral',
    description: 'Warm ivory, navy text, muted gold.',
    light: { bg: '#f7f4ec', surface: '#ffffff', text: '#14283b', primary: '#14283b', accent: '#a1792f', border: '#ded7ca', panel: '#172d43', panelText: '#eef3f6' },
    dark: { bg: '#0e1a26', surface: '#16232f', text: '#e8eef3', primary: '#0d1b28', accent: '#c9a45c', border: '#2a3d4e', panel: '#1b3047', panelText: '#eaf1f6' },
  },
  {
    id: 'midnight',
    name: 'Midnight Navy',
    group: 'Neutral',
    description: 'Cool navy character with soft white text and gold.',
    light: { bg: '#eef1f6', surface: '#ffffff', text: '#0f2440', primary: '#0f2440', accent: '#a8802f', border: '#d3dae6', panel: '#0f2440', panelText: '#eef3f8' },
    dark: { bg: '#0b1220', surface: '#131c2e', text: '#e6edf7', primary: '#080f1b', accent: '#c9a45c', border: '#263349', panel: '#17233a', panelText: '#e9f0fa' },
  },
  {
    id: 'slate',
    name: 'Slate Grey',
    group: 'Neutral',
    description: 'Cool grey surfaces, charcoal text, blue accents.',
    light: { bg: '#f2f4f7', surface: '#ffffff', text: '#1f2933', primary: '#1f2933', accent: '#1f6fb0', border: '#d5dbe3', panel: '#22303d', panelText: '#eef2f6' },
    dark: { bg: '#12161c', surface: '#1a2029', text: '#e6eaf0', primary: '#0c1014', accent: '#5aa0e0', border: '#2b333f', panel: '#1f2733', panelText: '#e8edf4' },
  },
  {
    id: 'lavender',
    name: 'Lavender Dream',
    group: 'Colour',
    description: 'Soft lavender surfaces, deep purple text, violet accents.',
    light: { bg: '#f4f1fb', surface: '#ffffff', text: '#241a45', primary: '#4c3a86', accent: '#6b4fc4', border: '#ddd6ef', panel: '#372a63', panelText: '#f1eefb' },
    dark: { bg: '#141029', surface: '#1e1838', text: '#e9e4f9', primary: '#0f0b21', accent: '#a98cf0', border: '#332b56', panel: '#241d44', panelText: '#ece7fb' },
  },
  {
    id: 'purple',
    name: 'Soft Purple',
    group: 'Colour',
    description: 'Pale purple surfaces with rich purple accents.',
    light: { bg: '#f7f2fb', surface: '#ffffff', text: '#2c1a4a', primary: '#5b2f96', accent: '#7a35bf', border: '#e0d4ef', panel: '#3d2168', panelText: '#f3edfb' },
    dark: { bg: '#170f2b', surface: '#221739', text: '#ece5fa', primary: '#0f0a1e', accent: '#b478f0', border: '#372a56', panel: '#291c45', panelText: '#efe8fc' },
  },
  {
    id: 'royal-purple',
    name: 'Royal Purple',
    group: 'Colour',
    description: 'Deeper violet with elegant lavender highlights.',
    light: { bg: '#f0eef8', surface: '#ffffff', text: '#211845', primary: '#2e1f66', accent: '#5a45b8', border: '#d8d2ec', panel: '#2a1d5c', panelText: '#edeaf9' },
    dark: { bg: '#100c2a', surface: '#1a1438', text: '#e8e4fb', primary: '#0a0720', accent: '#8f7bf0', border: '#2e2755', panel: '#201a44', panelText: '#eae6fc' },
  },
  {
    id: 'yellow',
    name: 'Butter Yellow',
    group: 'Colour',
    description: 'Warm pale yellow with dark brown text, golden accents.',
    light: { bg: '#fdf7e3', surface: '#fffef9', text: '#3a2f14', primary: '#4a3a12', accent: '#9c7614', border: '#ece0bd', panel: '#2f2810', panelText: '#fdf7e3' },
    dark: { bg: '#1a1508', surface: '#262013', text: '#f5ecd8', primary: '#100d05', accent: '#e0b544', border: '#3a311a', panel: '#2b2314', panelText: '#f7efdc' },
  },
  {
    id: 'cream',
    name: 'Soft Cream',
    group: 'Colour',
    description: 'Creamy background, warm brown text, bronze accents.',
    light: { bg: '#faf5ec', surface: '#fffdf8', text: '#3b2f22', primary: '#4a3826', accent: '#8a5f24', border: '#e8ddca', panel: '#3a2c1d', panelText: '#f7f0e4' },
    dark: { bg: '#1a1510', surface: '#262019', text: '#f2e9de', primary: '#100d09', accent: '#d09a4e', border: '#3a3128', panel: '#2b231a', panelText: '#f5eee4' },
  },
  {
    id: 'ocean',
    name: 'Ocean Blue',
    group: 'Colour',
    description: 'Pale blue background, deep navy text, blue accents.',
    light: { bg: '#eef6fb', surface: '#ffffff', text: '#0e2b46', primary: '#0f4b78', accent: '#15689e', border: '#cfe2f0', panel: '#0d3350', panelText: '#eaf4fb' },
    dark: { bg: '#081a28', surface: '#0f2637', text: '#e2eefa', primary: '#061320', accent: '#4aa8e0', border: '#1e3b52', panel: '#123047', panelText: '#e6f2fc' },
  },
  {
    id: 'sage',
    name: 'Sage Green',
    group: 'Colour',
    description: 'Muted green background, forest-green text, green accents.',
    light: { bg: '#f1f6f0', surface: '#ffffff', text: '#1e3a2b', primary: '#23553a', accent: '#357a52', border: '#d3e2d6', panel: '#1d4230', panelText: '#ecf5ef' },
    dark: { bg: '#0c1a12', surface: '#14261b', text: '#e4f0e8', primary: '#08120c', accent: '#6cbf8e', border: '#23402e', panel: '#17301f', panelText: '#e8f3ec' },
  },
  {
    id: 'rose',
    name: 'Rose Pink',
    group: 'Colour',
    description: 'Soft pink background, dark burgundy text, rose accents.',
    light: { bg: '#fdf2f4', surface: '#ffffff', text: '#4a1d2b', primary: '#7a2338', accent: '#a83c58', border: '#f0d3da', panel: '#5b1c2c', panelText: '#fbeef2' },
    dark: { bg: '#1c0f16', surface: '#281721', text: '#f7e6ec', primary: '#120a0e', accent: '#e08aa6', border: '#3d2531', panel: '#321c28', panelText: '#f9ebf0' },
  },
  {
    id: 'peach',
    name: 'Peach',
    group: 'Colour',
    description: 'Warm peach background, dark brown text, coral accents.',
    light: { bg: '#fdf3ec', surface: '#ffffff', text: '#4a2c1c', primary: '#8a4a2a', accent: '#bf6238', border: '#f0dccb', panel: '#5c301c', panelText: '#fbeee6' },
    dark: { bg: '#1c120c', surface: '#281a12', text: '#f7e9e0', primary: '#120b07', accent: '#e89a70', border: '#3d2a20', panel: '#322015', panelText: '#f9ede6' },
  },
]

/**
 * How strongly each text tier keeps the palette's text colour (percent) when
 * mixed with the background. Kept here so the CSS generator and the numeric
 * contrast audit in scripts/verify-themes.js use the same numbers.
 */
export const TEXT_MIX = {
  light: { ink2: 82, t2: 82, t3: 76, t4: 72, muted: 72, muted2: 66, gold: 58 },
  dark: { ink2: 86, t2: 86, t3: 78, t4: 70, muted: 70, muted2: 62, gold: 94 },
}

/** Per-mode literals that are semantic rather than palette-specific. */
export const MODE_TOKENS = {
  light: {
    scheme: 'light',
    onInk: '#ffffff',
    success: '#2f6b52',
    warning: '#8a6a1f',
    error: '#a8402f',
    shadowColor: 'color-mix(in srgb, var(--p-primary) 14%, transparent)',
    shadow: '0 18px 50px color-mix(in srgb, var(--p-primary) 12%, transparent)',
    cardShadow: '0 10px 28px color-mix(in srgb, var(--p-primary) 9%, transparent)',
    cardShadowHover: '0 16px 36px color-mix(in srgb, var(--p-primary) 16%, transparent)',
  },
  dark: {
    scheme: 'dark',
    onInk: 'var(--p-primary)',
    success: '#73c2a4',
    warning: '#e0c58a',
    error: '#f0a89c',
    shadowColor: 'color-mix(in srgb, #000000 55%, transparent)',
    shadow: '0 18px 50px color-mix(in srgb, #000000 60%, transparent)',
    cardShadow: '0 10px 28px color-mix(in srgb, #000000 45%, transparent)',
    cardShadowHover: '0 16px 36px color-mix(in srgb, #000000 58%, transparent)',
  },
}

export const DEFAULT_PALETTE = 'ivory'
export const CUSTOM_PALETTE = 'custom'

export const PALETTE_IDS = PALETTES.map((palette) => palette.id)

export function getPalette(id) {
  return PALETTES.find((palette) => palette.id === id) || null
}

/** The eight primitives for one palette in one mode, or null when unknown. */
export function palettePrimitives(id, mode) {
  const palette = getPalette(id)
  if (!palette) return null
  return mode === 'dark' ? palette.dark : palette.light
}
