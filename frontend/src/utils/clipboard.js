/**
 * Copy text to the clipboard.
 *
 * Three things are handled here rather than at each call site:
 *
 *   - `navigator.clipboard` is unavailable on insecure origins, which includes
 *     a plain-http deployment on a non-localhost host.
 *   - `writeText` can stay pending indefinitely in embedded and headless
 *     contexts, so the wait is bounded and the fallback is used instead.
 *   - Callers need to know whether the copy actually happened, because a
 *     "Copied" label shown after a failed copy is a lie.
 *
 * Resolves with true only when a copy really was performed. Never throws.
 */

const CLIPBOARD_TIMEOUT_MS = 1200

/** Selection-based fallback, used when the async API is missing or stalled. */
function copyViaSelection(value) {
  try {
    const area = document.createElement('textarea')
    area.value = value
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.top = '-1000px'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const ok = document.execCommand ? document.execCommand('copy') : false
    document.body.removeChild(area)
    return Boolean(ok)
  } catch {
    return false
  }
}

export async function writeClipboard(text) {
  const value = String(text ?? '')
  const api = typeof navigator !== 'undefined' ? navigator.clipboard : null

  if (api?.writeText) {
    const settled = await Promise.race([
      api.writeText(value).then(() => true, () => false),
      new Promise((resolve) => setTimeout(() => resolve('timeout'), CLIPBOARD_TIMEOUT_MS)),
    ])
    if (settled === true) return true
  }

  return copyViaSelection(value)
}

/** The plain-text payload copied for a corpus record. */
export function recordToText(record) {
  if (!record) return ''
  return [
    record.title,
    record.court || '',
    record.year || '',
    record.source ? `Source: ${record.source}` : '',
    record.chunkId ? `Chunk: ${record.chunkId}` : '',
    '',
    record.summary || '',
  ]
    .filter((line, index) => line !== '' || index === 5)
    .join('\n')
}
