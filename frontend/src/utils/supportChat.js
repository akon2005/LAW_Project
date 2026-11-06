/**
 * Pure helpers for the support assistant.
 *
 * Nothing here touches the DOM, `fetch` or storage, so the whole module can be
 * checked from Node by `npm run verify:support`. The component keeps only the
 * React state; the logic that decides what gets sent, what a response means and
 * which action is safe to run lives here where it can be tested.
 */

/** Workspace pages the assistant may be told about (must match backend ALLOWED_PAGES). */
export const SUPPORT_PAGES = ['research', 'statutes', 'documents', 'comparison', 'knowledge', 'settings', 'guide']

/** Navigation targets an action may point at (must match the backend allowlist). */
export const NAVIGATION_TABS = ['research', 'comparison', 'settings', 'knowledge', 'documents', 'statutes', 'guide']

export const MAX_MESSAGE_LENGTH = 2000

/** How the response was produced, in words a user can act on. */
export const KIND_LABELS = {
  knowledge_base: 'Project documentation',
  troubleshooting: 'Troubleshooting guide',
  demo: 'Demo example',
  status: 'Live system status',
  greeting: 'Support assistant',
  fallback: 'Not in the documentation',
}

export const WELCOME = {
  role: 'assistant',
  content:
    "Hello — I'm the VIDHIVEDA support assistant. I explain how this site works, walk you through " +
    "features, show demo examples and help when something breaks.\n\n" +
    "I don't run legal research myself: the Research tab does that, and I can open it for you.",
  suggestions: [
    'What is VIDHIVEDA, and how should I use it?',
    'Explain how VIDHIVEDA uses RAG.',
    'The legal search returned no results. What should I do?',
    'Which features are currently implemented?',
  ],
}

export function kindLabel(kind) {
  return KIND_LABELS[kind] || 'Support assistant'
}

/** Trim, collapse whitespace and cap length the way the API expects. */
export function normalizeMessage(text) {
  return String(text ?? '').split(/\s+/).filter(Boolean).join(' ').slice(0, MAX_MESSAGE_LENGTH)
}

export function createSessionId(random = Math.random) {
  const part = () => Math.floor(random() * 1e9).toString(36)
  return `sup-${part()}${part()}`.slice(0, 32)
}

export function isAllowedPage(page) {
  return SUPPORT_PAGES.includes(page)
}

export function isAllowedTab(tab) {
  return NAVIGATION_TABS.includes(tab)
}

/**
 * Build the request body. `page` is only sent when it is a page the backend
 * accepts, so an unknown value can never be forwarded.
 */
export function buildChatPayload({ message, sessionId, page, demoMode = false, history = [], feedback = null }) {
  const clean = normalizeMessage(message)
  const payload = { message: clean, demo_mode: Boolean(demoMode) }
  if (sessionId) payload.session_id = sessionId
  if (isAllowedPage(page)) payload.page = page
  if (history.length) payload.history = history.slice(-8)
  if (feedback && (feedback.rating === 'helpful' || feedback.rating === 'not_helpful')) {
    payload.feedback = {
      rating: feedback.rating,
      comment: feedback.comment ? String(feedback.comment).slice(0, 500) : null,
      message_id: feedback.messageId || null,
    }
  }
  return payload
}

/** Turn a transport or HTTP failure into something a user can act on. */
export function describeError(status, payload) {
  const detail = (payload && (payload.detail || payload.message)) || ''
  if (status === 0) {
    return {
      message: 'Network error: the support backend could not be reached. Check that the API is running, then retry.',
      retryable: true,
    }
  }
  const table = {
    422: 'That message was rejected as invalid (for example it was empty or too long). Edit it and send again.',
    429: 'Too many requests just now. Wait a moment and retry.',
    503: 'The support knowledge base is unavailable, so no answer can be grounded in documentation. Retrying will not help until the backend is restored.',
    500: 'The support backend hit an internal error. Retry once; if it repeats, report it with the time it happened.',
  }
  // 503 means a dependency is missing (the knowledge base could not be read),
  // so retrying the same request changes nothing — offering Retry there would
  // be a fake affordance.
  return {
    message: typeof detail === 'string' && detail ? `${detail}` : table[status] || `Support request failed (${status}).`,
    retryable: status === 0 || status === 429 || status === 500 || status === 502 || status === 504,
  }
}

/**
 * Decide what an action does. Navigation is restricted to the known tabs, so a
 * response can never push the UI somewhere that does not exist.
 */
export function resolveAction(action) {
  if (!action || typeof action !== 'object') return null
  if (action.kind === 'navigate') {
    return isAllowedTab(action.target) ? { mode: 'navigate', tab: action.target, label: action.label } : null
  }
  if (action.kind === 'client') return { mode: 'client', command: action.target, label: action.label }
  return null
}

/** Keep only the turns the server will accept, oldest first. */
export function mergeHistory(messages = [], limit = 8) {
  return messages
    .filter((msg) => msg && (msg.role === 'user' || msg.role === 'assistant') && normalizeMessage(msg.content))
    .map((msg) => ({ role: msg.role, content: normalizeMessage(msg.content) }))
    .slice(-limit)
}

/** One-line summary of a source article reference. */
export function sourceLine(source) {
  if (!source) return ''
  const meta = [source.category, source.updated].filter(Boolean).join(' · ')
  return meta ? `${source.title} — ${meta}` : source.title
}

/** Flatten the health payload into rows the panel can render. */
export function healthRows(health) {
  if (!health || !health.components) return []
  const { components } = health
  const rows = [
    { label: 'API process', value: components.api?.status || 'unknown' },
    { label: 'Support knowledge base', value: `${components.knowledge_base?.status || 'unknown'}${components.knowledge_base?.articles ? ` · ${components.knowledge_base.articles} articles` : ''}` },
    {
      label: 'Language model',
      value: components.llm?.configured
        ? `${components.llm.provider} · reachability ${components.llm.checked ? components.llm.reachable : 'not probed'}`
        : 'not configured · answers use documentation only',
    },
    { label: 'Research vector store', value: `${components.vector_store?.status || 'unknown'}${components.vector_store?.chunks ? ` · ${components.vector_store.chunks} chunks` : ''}` },
    { label: 'Outcome prediction', value: components.prediction?.status || 'unknown' },
  ]
  return rows
}

export function healthTone(health) {
  if (!health) return 'neutral'
  if (health.status === 'ok') return 'green'
  if (health.status === 'degraded') return 'gold'
  return 'neutral'
}

/** Group examples by their category, preserving the backend's category order. */
export function groupExamples(examples = [], categories = []) {
  const order = categories.length ? categories.map((item) => item.id) : [...new Set(examples.map((item) => item.category))]
  return order
    .map((id) => {
      const category = categories.find((item) => item.id === id) || { id, label: id, letter: '' }
      return { ...category, examples: examples.filter((item) => item.category === id) }
    })
    .filter((group) => group.examples.length)
}

/** Honest badge for an example: is it backed by the product, or teaching material? */
export function exampleBadge(example) {
  if (!example) return { label: 'Unknown', tone: 'neutral' }
  if (example.evidence === 'illustrative') return { label: 'Illustrative teaching example', tone: 'gold' }
  return { label: 'Verified project data', tone: 'green' }
}

export function exampleRunsLive(example) {
  return Boolean(example && example.invokes_backend)
}

/** Compact label for where an answer came from, including the no-LLM case. */
export function originLabel(origin, generated) {
  if (generated) return origin && origin.startsWith('llm:') ? `Generated · ${origin.split(':')[1]}` : 'Generated'
  if (!origin || origin === 'none') return 'No model used'
  if (origin === 'template:knowledge_base') return 'Documentation text (no model configured)'
  if (origin === 'template:troubleshooting') return 'Troubleshooting data'
  if (origin === 'template:capability_registry') return 'Capability registry'
  if (origin === 'template:examples') return 'Example gallery data'
  if (origin === 'template:status') return 'Live checks'
  if (origin === 'template:fallback') return 'Could not verify'
  if (origin === 'template:greeting') return 'Welcome message'
  return origin
}

/** Build the guided prompts for a client-side action. */
export function clientCommand(command) {
  switch (command) {
    case 'features':
      return { message: 'Which features of VIDHIVEDA are currently implemented?' }
    case 'status':
      return { message: 'Is the system healthy right now?' }
    case 'rag':
      return { message: 'Explain how VIDHIVEDA uses Retrieval-Augmented Generation in simple language.' }
    case 'demo':
      return { message: 'Show me the approved demo examples.' }
    case 'report':
      // Opens the in-app report form; it is a panel action, not a chat message.
      return { report: true }
    case 'restart':
      return { restart: true }
    default:
      return null
  }
}
