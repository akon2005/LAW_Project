/**
 * Text shaping for the reading view.
 *
 * Pure functions only — no React, no I/O — so the paragraph rules can be
 * checked from Node, the same way `utils/search.js` is.
 *
 * Chunks are stored as plain text extracted from judgment PDFs. Two problems
 * have to be solved before the text is readable:
 *
 *   1. Hard wraps. A "paragraph" is separated by blank lines, but within one
 *      the PDF's line breaks are meaningless and are joined back into prose.
 *   2. Walls of text. Some chunks are a single block with no blank lines at
 *      all. Those are re-broken at sentence boundaries.
 *
 * Only whitespace is ever added: no word is changed, reordered or dropped.
 */

/** A block longer than this is re-broken at sentence boundaries. */
export const MAX_BLOCK_CHARS = 1400

export function splitLongBlock(block) {
  if (block.length <= MAX_BLOCK_CHARS) return [block]

  const out = []
  let current = ''
  const flush = () => {
    if (current.trim()) out.push(current.trim())
    current = ''
  }

  for (const sentence of block.split(/(?<=[.!?])\s+/)) {
    if (sentence.length > MAX_BLOCK_CHARS * 2) {
      // A run with no sentence punctuation at all: fall back to word wrapping.
      flush()
      let line = ''
      for (const word of sentence.split(/\s+/)) {
        if (line && line.length + word.length > MAX_BLOCK_CHARS) {
          out.push(line)
          line = word
        } else {
          line = line ? `${line} ${word}` : word
        }
      }
      if (line) out.push(line)
      continue
    }
    if (current && (current + ' ' + sentence).length > MAX_BLOCK_CHARS) flush()
    current = current ? `${current} ${sentence}` : sentence
  }
  flush()
  return out
}

/** Paragraphs ready to render, with PDF hard wraps removed. */
export function toParagraphs(text) {
  return String(text || '')
    .split(/\n\s*\n/)
    .map((block) => block.replace(/\s*\n\s*/g, ' ').trim())
    .filter(Boolean)
    .flatMap(splitLongBlock)
}
