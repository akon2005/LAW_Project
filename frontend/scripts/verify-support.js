#!/usr/bin/env node
/**
 * Verify the support-assistant helpers without a browser or a backend.
 *
 * These are the decisions that must not drift: what gets sent to the API, how a
 * failure is described, which actions are allowed to navigate, and how an
 * example is labelled. Everything checked here is a pure function, so the checks
 * run in Node and exit non-zero on failure, which lets them gate a build.
 */
import {
  KIND_LABELS,
  MAX_MESSAGE_LENGTH,
  NAVIGATION_TABS,
  SUPPORT_PAGES,
  buildChatPayload,
  clientCommand,
  createSessionId,
  describeError,
  exampleBadge,
  exampleRunsLive,
  groupExamples,
  healthRows,
  healthTone,
  isAllowedPage,
  isAllowedTab,
  kindLabel,
  mergeHistory,
  normalizeMessage,
  originLabel,
  resolveAction,
  sourceLine,
} from '../src/utils/supportChat.js'

const failures = []
const check = (label, condition) => {
  if (!condition) failures.push(label)
}

// ── Message handling ──────────────────────────────────────────────────────
check('whitespace is collapsed', normalizeMessage('  how   do\nI search?  ') === 'how do I search?')
check('null becomes empty', normalizeMessage(null) === '')
check('length is capped', normalizeMessage('x'.repeat(5000)).length === MAX_MESSAGE_LENGTH)
check('legal terminology is never stripped', normalizeMessage('IPC Section 302 self-defence').includes('302'))

// ── Session ids ───────────────────────────────────────────────────────────
const idA = createSessionId(() => 0.5)
const idB = createSessionId(() => 0.5)
check('session id is deterministic from the injected randomness', idA === idB)
check('session id fits the API pattern', /^[A-Za-z0-9_-]{6,64}$/.test(idA))
check('session ids differ when randomness differs', createSessionId(() => 0.1) !== createSessionId(() => 0.9))

// ── Request payload ───────────────────────────────────────────────────────
const payload = buildChatPayload({
  message: '  What is VIDHIVEDA?  ',
  sessionId: 'sup-abc123',
  page: 'research',
  demoMode: true,
  history: [
    { role: 'user', content: 'hello' },
    { role: 'assistant', content: 'hi' },
  ],
})
check('payload trims the message', payload.message === 'What is VIDHIVEDA?')
check('payload keeps demo mode', payload.demo_mode === true)
check('payload passes an allowed page', payload.page === 'research')
check('payload keeps bounded history', payload.history.length === 2)

const unknownPage = buildChatPayload({ message: 'hello there', page: 'admin' })
check('unknown page is dropped, never forwarded', !('page' in unknownPage))
check('page allowlist matches the backend', isAllowedPage('comparison') && !isAllowedPage('dashboard'))
check('tab allowlist matches the workspace', isAllowedTab('guide') && !isAllowedTab('chat'))
check('page and tab lists are consistent', SUPPORT_PAGES.length === NAVIGATION_TABS.length)

const longHistory = buildChatPayload({ message: 'hello there', history: Array.from({ length: 20 }, (_, i) => ({ role: 'user', content: `turn ${i}` })) })
check('history is capped before sending', longHistory.history.length === 8)

const withFeedback = buildChatPayload({ message: 'hello there', feedback: { rating: 'helpful', comment: 'clear' } })
check('valid feedback is included', withFeedback.feedback?.rating === 'helpful')
const badFeedback = buildChatPayload({ message: 'hello there', feedback: { rating: 'amazing' } })
check('invalid feedback is dropped', !('feedback' in badFeedback))

// ── Error description ─────────────────────────────────────────────────────
const network = describeError(0, null)
check('network failure is retryable', network.retryable === true)
check('network failure mentions the backend', /could not be reached/.test(network.message))
const server503 = describeError(503, { detail: 'knowledge base unavailable' })
check('503 reports the real detail', server503.message === 'knowledge base unavailable')
check('503 is not advertised as retryable', server503.retryable === false)
check('429 is retryable', describeError(429, null).retryable === true)
check('422 explains what to change', /invalid/i.test(describeError(422, null).message))
check('500 is retryable once', describeError(500, null).retryable === true)

// ── Action resolution (navigation allowlist) ──────────────────────────────
const nav = resolveAction({ id: 'open_research', label: 'Open Legal Research', kind: 'navigate', target: 'research' })
check('allowed navigation resolves to a tab', nav?.mode === 'navigate' && nav.tab === 'research')
check('off-allowlist navigation is refused', resolveAction({ kind: 'navigate', target: 'https://evil.example' }) === null)
check('unknown kind is refused', resolveAction({ kind: 'run', target: 'research' }) === null)
check('garbage is refused', resolveAction(null) === null)
const client = resolveAction({ id: 'show_status', kind: 'client', target: 'status' })
check('client action resolves to a command', client?.mode === 'client' && client.command === 'status')

// ── Client commands ───────────────────────────────────────────────────────
check('status command asks a real status question', /healthy/i.test(clientCommand('status').message))
check('restart command is a restart', clientCommand('restart').restart === true)
check('report command opens the in-app report form', clientCommand('report').report === true)
check('unknown command does nothing', clientCommand('launch-missiles') === null)

// ── History and labels ────────────────────────────────────────────────────
const merged = mergeHistory([
  { role: 'system', content: 'ignored' },
  { role: 'user', content: '  keep   me  ' },
  { role: 'assistant', content: '' },
])
check('mergeHistory drops unknown roles', merged.length === 1)
check('mergeHistory normalises content', merged[0].content === 'keep me')
check('known kinds have labels', Object.keys(KIND_LABELS).every((kind) => kindLabel(kind) !== 'Support assistant' || kind === 'greeting'))
check('unknown kind falls back to a readable label', kindLabel('nonsense') === 'Support assistant')
check('no-model origin is disclosed', /no model configured/i.test(originLabel('template:knowledge_base', false)))
check('generated origin names the provider', originLabel('llm:openai', true) === 'Generated · openai')
check('fallback origin says it could not verify', /could not verify/i.test(originLabel('template:fallback', false)))
check('source line includes category and date', sourceLine({ title: 'X', category: 'how-to', updated: '2026-10-16' }) === 'X — how-to · 2026-10-16')

// ── Health presentation ───────────────────────────────────────────────────
const health = {
  status: 'degraded',
  components: {
    api: { status: 'up' },
    knowledge_base: { status: 'ready', articles: 23 },
    llm: { configured: false, checked: false, reachable: null },
    vector_store: { status: 'connected', chunks: 9375 },
    prediction: { status: 'experimental' },
  },
  degraded_reasons: ['LLM provider not configured (answers use documentation only)'],
}
const rows = healthRows(health)
check('health rows cover every component', rows.length === 5)
check('unprobed reachability is stated as not probed', rows.some((row) => /not configured/.test(row.value)))
check('degraded health is not painted green', healthTone(health) === 'gold')
check('ok health is green', healthTone({ status: 'ok' }) === 'green')
check('missing health is neutral', healthTone(null) === 'neutral')
check('health rows are empty without components', healthRows(null).length === 0)

// ── Example gallery ───────────────────────────────────────────────────────
const categories = [
  { id: 'a', label: 'First', letter: 'A' },
  { id: 'b', label: 'Second', letter: 'B' },
]
const examples = [
  { id: '1', category: 'b', evidence: 'verified', invokes_backend: true },
  { id: '2', category: 'a', evidence: 'illustrative', invokes_backend: true },
]
const grouped = groupExamples(examples, categories)
check('groups follow the backend category order', grouped[0].id === 'a' && grouped[1].id === 'b')
check('empty categories are dropped', groupExamples(examples, [...categories, { id: 'c', label: 'Third' }]).length === 2)
check('illustrative examples are labelled as teaching material', exampleBadge(examples[1]).label === 'Illustrative teaching example')
check('verified examples are labelled as project data', exampleBadge(examples[0]).label === 'Verified project data')
check('unknown examples are not over-claimed', exampleBadge(null).label === 'Unknown')
check('backend-backed examples are detected', exampleRunsLive(examples[0]) === true && exampleRunsLive({}) === false)

// ── Report ────────────────────────────────────────────────────────────────
if (failures.length) {
  console.error(`verify-support: ${failures.length} check(s) failed`)
  for (const failure of failures) console.error(`  ✗ ${failure}`)
  process.exit(1)
}
console.log('verify-support: all support-assistant helper checks passed')
