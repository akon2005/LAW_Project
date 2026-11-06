#!/usr/bin/env node
/**
 * Verify the Ready-to-Demonstrate legal examples.
 *
 * Two layers:
 *   1. Structural checks — every preset is complete enough to launch without
 *      typing, has a real https source, and records its corpus status honestly.
 *   2. Live checks — each preset is submitted to the running comparison API with
 *      exactly the payload the Compare panel builds, and the response is checked
 *      for the preset's judgments by case name.
 *
 * Usage:
 *   npm run verify:examples              # structural + live (API must be running)
 *   npm run verify:examples -- --offline # structural only
 */
import {
  LEGAL_DEMO_EXAMPLES,
  CORPUS_SNAPSHOT,
  exampleFormValues,
  matchPresetCases,
} from '../src/data/legalDemoExamples.js'

const EMPTY = {
  legal_issue: '',
  case_facts: '',
  provisions: '',
  court: '',
  year: '',
  a_label: 'Party A',
  a_position: '',
  b_label: 'Party B',
  b_position: '',
}

const API_BASE = process.env.API_BASE || 'http://localhost:8000'
const OFFLINE = process.argv.includes('--offline')

let failures = 0
const results = []

function check(label, ok, detail = '') {
  if (!ok) {
    failures += 1
    console.log(`FAIL  ${label}${detail ? ` — ${detail}` : ''}`)
  }
  return ok
}

function payloadFor(example) {
  const values = exampleFormValues(example, EMPTY)
  const single = example.mode === 'single_scenario'
  return {
    legal_issue: values.legal_issue.trim(),
    case_facts: values.case_facts.trim() || undefined,
    provisions: values.provisions.split(',').map((p) => p.trim()).filter(Boolean),
    court: values.court.trim() || undefined,
    year: values.year.trim() ? parseInt(values.year, 10) : undefined,
    scenario_a: {
      label: values.a_label.trim() || (single ? 'Claimant / Accused' : 'Party A'),
      position: values.a_position.trim(),
    },
    scenario_b: single
      ? undefined
      : { label: values.b_label.trim() || 'Party B', position: values.b_position.trim() },
    top_k: 8,
  }
}

console.log(`Legal examples: ${LEGAL_DEMO_EXAMPLES.length}`)
console.log(`Corpus snapshot recorded: ${CORPUS_SNAPSHOT.checked_at}\n`)

// ── Structural checks ──────────────────────────────────────────────────
for (const example of LEGAL_DEMO_EXAMPLES) {
  const values = exampleFormValues(example, EMPTY)
  const single = example.mode === 'single_scenario'
  const label = example.id

  check(`${label}: id/title/mode`, Boolean(example.id && example.title && ['two_scenarios', 'single_scenario'].includes(example.mode)))
  check(`${label}: court and years`, Boolean(example.court && example.years?.length && example.year_label))
  check(`${label}: legal question`, values.legal_issue.trim().length >= 20)
  check(`${label}: scenario A position`, values.a_position.trim().length >= 20)
  check(`${label}: scenario B position`, single || values.b_position.trim().length >= 20)
  check(`${label}: shared year filter blank`, values.year === '', 'the shared year is a retrieval filter; presets must not restrict it')
  check(`${label}: case metadata`, example.cases.length > 0 && example.cases.every((item) => item.name && item.year && item.corpus))
  check(`${label}: every source is https`, example.sources.length > 0 && example.sources.every((source) => /^https:\/\//.test(source.url)))
  check(`${label}: sources are verified`, example.sources.every((source) => Boolean(source.verified_title)))
  check(`${label}: no invented citation`, example.citation === null || typeof example.citation === 'string')
}

// ── Live checks ────────────────────────────────────────────────────────
if (!OFFLINE) {
  for (const example of LEGAL_DEMO_EXAMPLES) {
    const payload = payloadFor(example)
    let response
    try {
      response = await fetch(`${API_BASE}/api/comparison`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    } catch (err) {
      check(`${example.id}: backend reachable`, false, `${err.message}. Start the API on ${API_BASE} or run with --offline.`)
      continue
    }

    if (!check(`${example.id}: HTTP 200`, response.ok, `HTTP ${response.status}`)) continue
    const data = await response.json()
    check(`${example.id}: response has scenario_a`, Boolean(data.scenario_a))
    const modeOk =
      example.mode === 'single_scenario'
        ? data.mode === 'single_scenario' && !data.scenario_b
        : Boolean(data.scenario_b)
    check(`${example.id}: response matches mode`, modeOk, `response mode ${data.mode}`)

    const matches = matchPresetCases(data, example)
    const retrieved = matches.filter((item) => item.retrievedAs)
    const citedIds = (data.citations || []).map((citation) => citation.chunk_id).filter(Boolean)
    check(`${example.id}: no fabricated citations`, (data.citations || []).every((citation) => citation.chunk_id && citation.case_name))

    results.push({
      title: example.title,
      status: response.status,
      evidence: data.evidence_quality?.status || 'unknown',
      entries: (data.precedents || []).length,
      citations: (data.citations || []).length,
      citedIds: citedIds.slice(0, 3),
      matches: matches.map((item) => `${item.name} (${item.year}): ${item.retrievedAs ? 'retrieved' : 'not in index'}`),
      retrievedCount: retrieved.length,
    })
  }

  console.log('\nLive comparison results:')
  for (const item of results) {
    console.log(`\n${item.title}`)
    console.log(`  HTTP ${item.status} · evidence ${item.evidence} · ${item.entries} precedent document(s) · ${item.citations} citation(s)`)
    console.log(`  preset judgments: ${item.matches.join(' | ') || 'none recorded'}`)
    if (item.citedIds.length) console.log(`  sample chunk ids: ${item.citedIds.join(', ')}`)
  }
} else {
  console.log('\nLive checks skipped (--offline).')
}

console.log(`\n${failures === 0 ? 'verify-legal-examples: all checks passed' : `verify-legal-examples: ${failures} check(s) failed`}`)
process.exit(failures === 0 ? 0 : 1)
