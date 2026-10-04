/**
 * Client-side retrieval over the bundled sample dataset.
 *
 * The dataset has no embedding vectors available in the browser, so this is a
 * weighted keyword/field match rather than true semantic search. It is a pure
 * function module: no React, no I/O — which keeps it testable from Node.
 *
 * Ranking, in order of precedence:
 *   1. weighted field match      (title & sections > summary > area & court > citation)
 *   2. exact-phrase bonus        ("natural justice" beats two scattered tokens)
 *   3. verified records first    (curated cases outrank synthetic templates)
 *   4. most recent year
 */
import { ALL_AREAS, ALL_COURTS, ANY_YEAR } from '../data/dataset.js';

export { ALL_AREAS, ALL_COURTS, ANY_YEAR };

const STOPWORDS = new Set([
  'the', 'a', 'an', 'of', 'and', 'or', 'to', 'in', 'on', 'for', 'with', 'under',
  'is', 'are', 'was', 'be', 'by', 'as', 'at', 'from', 'that', 'this', 'it',
  'its', 'his', 'her', 'their', 'what', 'which', 'when', 'who', 'how', 'about',
  'regarding', 'case', 'law', 'legal', 'court', 'judgment',
]);

/** Field importance when scoring a match. Fields absent here are not searched. */
const FIELD_WEIGHTS = {
  title: 4,
  sections: 4,
  summary: 3,
  area: 2,
  court: 2,
  citation: 1,
  source: 1,
};

const MAX_TOKEN_WEIGHT = Math.max(...Object.values(FIELD_WEIGHTS));
const PHRASE_BONUS = 0.25;

/**
 * Synthetic records are dataset-scale filler whose templated summaries match
 * common phrases verbatim, so they would otherwise outrank real judgments.
 * They keep their true match score but sort at half weight.
 */
const SYNTHETIC_RANK_FACTOR = 0.5;

/** Lowercase word tokens with punctuation and stopwords removed. */
export function tokenize(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter((token) => token.length > 1 && !STOPWORDS.has(token));
}

/**
 * Maps each token in a record to its highest field weight. Built once per
 * record and memoised, since a single query re-scans all ~1,600 records.
 */
const weightCache = new Map();

function tokenWeights(record) {
  const cached = weightCache.get(record.id);
  if (cached) return cached;

  const weights = new Map();
  for (const [field, weight] of Object.entries(FIELD_WEIGHTS)) {
    for (const token of tokenize(record[field])) {
      if ((weights.get(token) || 0) < weight) weights.set(token, weight);
    }
  }
  weightCache.set(record.id, weights);
  return weights;
}

/** Weight for a query token, tolerating simple singular/plural differences. */
function weightForToken(weights, token) {
  if (weights.has(token)) return weights.get(token);
  if (token.endsWith('s') && weights.has(token.slice(0, -1))) return weights.get(token.slice(0, -1));
  if (weights.has(`${token}s`)) return weights.get(`${token}s`);
  return 0;
}

/** How well a single record satisfies a query, as a 0–1 fraction. */
export function scoreRecord(record, tokens, phrase = '') {
  if (!tokens.length) return 0;

  const weights = tokenWeights(record);
  let matched = 0;
  for (const token of tokens) matched += weightForToken(weights, token);
  const base = matched / (tokens.length * MAX_TOKEN_WEIGHT);

  // An exact phrase counts on its own: short instrument names such as
  // "IT Act" or "Sale of Goods Act" carry a stopword that tokenising drops.
  let phraseHit = false;
  if (phrase) {
    const haystack = `${record.title} ${record.summary} ${record.sections}`.toLowerCase();
    phraseHit = haystack.includes(phrase);
  }
  if (base === 0 && !phraseHit) return 0;

  return Math.min(base + (phraseHit ? PHRASE_BONUS : 0), 1);
}

export function isVerified(record) {
  return /^verified/i.test(record.recordType || '');
}

/**
 * Filter by faceted dropdowns, then rank by relevance.
 * With no query text this returns the whole (filtered) collection, newest first.
 */
export function searchRecords(records, options = {}) {
  const {
    query = '',
    area = ALL_AREAS,
    court = ALL_COURTS,
    year = ANY_YEAR,
  } = options;

  const tokens = tokenize(query);
  const phrase = query.toLowerCase().trim().replace(/\s+/g, ' ');
  const scored = [];

  for (const record of records) {
    if (area !== ALL_AREAS && record.area !== area) continue;
    if (court !== ALL_COURTS && record.court !== court) continue;
    if (year !== ANY_YEAR && String(record.year) !== String(year)) continue;

    const score = scoreRecord(record, tokens, tokens.length ? phrase : '');
    if (tokens.length && score === 0) continue;

    const verified = isVerified(record);
    // Ordering only: the displayed percentage stays an honest match score,
    // while synthetic templates are pushed below curated sources.
    const rank = score * (verified ? 1 : SYNTHETIC_RANK_FACTOR);
    scored.push({ record, score, verified, rank });
  }

  scored.sort((a, b) => {
    if (b.rank !== a.rank) return b.rank - a.rank;
    if (a.verified !== b.verified) return Number(b.verified) - Number(a.verified);
    return (b.record.year || 0) - (a.record.year || 0);
  });

  return scored.map(({ record, score, verified }) => ({
    ...record,
    // With no query there is nothing to match against, so leave the score off
    // entirely rather than publishing a 0% that the UI would render as a
    // meaningless "Match 0%" badge.
    score: tokens.length ? Math.round(score * 100) : undefined,
    verified,
  }));
}
