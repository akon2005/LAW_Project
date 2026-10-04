#!/usr/bin/env node
/**
 * Smoke test for the bundled dataset + search pipeline.
 *
 * Guards the promise made in the UI: every example query under the search bar
 * and every card in the reference library must return at least one record.
 * Run it after editing src/data.js or src/dataset.js.
 *
 * Usage: npm run verify:search
 */
import { caseRecords, datasetStats } from '../src/data/dataset.js';
import { searchRecords, isVerified } from '../src/utils/search.js';
import { exampleQueries, statutes } from '../src/data/data.js';
import { toParagraphs, splitLongBlock } from '../src/utils/readerText.js';
import { recordToText } from '../src/utils/clipboard.js';

let failures = 0;

function report(label, query, ok, detail) {
  const mark = ok ? 'PASS' : 'FAIL';
  if (!ok) failures += 1;
  console.log(`  [${mark}] ${label.padEnd(46)} ${detail}`);
}

console.log('DATASET');
console.log(
  `  ${datasetStats.total} records · ${datasetStats.areas} areas · ` +
    `${datasetStats.courts} courts · ${datasetStats.yearFrom}-${datasetStats.yearTo}`,
);
console.log(
  `  verified: ${caseRecords.filter(isVerified).length} · ` +
    `synthetic: ${caseRecords.filter((r) => !isVerified(r)).length}`,
);

console.log('\nEXAMPLE QUERIES (must each return results)');
for (const example of exampleQueries) {
  const hits = searchRecords(caseRecords, { query: example.query });
  const verifiedInTop5 = hits.slice(0, 5).filter(isVerified).length;
  const top = hits[0];
  report(
    example.label,
    example.query,
    hits.length > 0,
    `${String(hits.length).padStart(4)} hits · top: ${top ? top.title.slice(0, 38) : '—'} · ` +
      `${verifiedInTop5}/5 verified in top 5`,
  );
}

console.log('\nREFERENCE LIBRARY (each card must return results)');
for (const statute of statutes) {
  const hits = searchRecords(caseRecords, { query: statute.query });
  const top = hits[0];
  report(statute.title.slice(0, 44), statute.query, hits.length > 0, `${String(hits.length).padStart(4)} hits · top: ${top ? top.title.slice(0, 34) : '—'}`);
}

console.log('\nFACET FILTERS');
const filtered = searchRecords(caseRecords, { query: '', area: 'Criminal', court: 'Supreme Court of India' });
report('Criminal + Supreme Court of India', '', filtered.length > 0, `${filtered.length} records`);
const combined = searchRecords(caseRecords, { query: 'natural justice', area: 'Administrative' });
report('query + area facet', 'natural justice', combined.length > 0, `${combined.length} records`);
const none = searchRecords(caseRecords, { query: 'zzzzzznomatch' });
report('nonsense query returns nothing', 'zzzzzznomatch', none.length === 0, `${none.length} records`);

console.log('\nRANKING');
const justice = searchRecords(caseRecords, { query: 'natural justice' });
report('verified case outranks synthetic on tie', 'natural justice', isVerified(justice[0] || {}), justice[0]?.title || '—');
const arbitration = searchRecords(caseRecords, { query: 'arbitration clause' });
report('verified case outranks paraphrasing synthetic', 'arbitration clause', isVerified(arbitration[0] || {}), arbitration[0]?.title || '—');
const itAct = searchRecords(caseRecords, { query: 'it act' });
report('short instrument name matches by phrase', 'it act', itAct.length > 0, `${itAct.length} records · top: ${itAct[0]?.title.slice(0, 34) || '—'}`);
const empty = searchRecords(caseRecords, {});
report('no query returns full dataset', '', empty.length === datasetStats.total, `${empty.length} records`);

// The reading view shapes chunk text before rendering it, so the guarantees it
// depends on are checked here too: no word is lost, and no block is a wall.
console.log('\nREADER TEXT SHAPING');
const longBlock = caseRecords
  .map((record) => String(record.summary || ''))
  .sort((a, b) => b.length - a.length)[0] || '';
const shaped = toParagraphs(longBlock);
const sameWords = (a, b) => a.replace(/\s+/g, ' ').trim() === b.replace(/\s+/g, ' ').trim();
report(
  'longest bundled record survives shaping',
  '',
  shaped.length > 0 && sameWords(shaped.join(' '), longBlock),
  `${longBlock.length} chars → ${shaped.length} paragraph(s)`,
);
const wall = Array.from({ length: 120 }, (_, i) => `Sentence ${i} describing the facts of the matter.`).join(' ');
const wallParts = splitLongBlock(wall);
report(
  'unbroken wall of text is split',
  '',
  wallParts.length > 1 && sameWords(wallParts.join(' '), wall),
  `${wall.length} chars → ${wallParts.length} parts, longest ${Math.max(...wallParts.map((p) => p.length))}`,
);
const copied = recordToText(caseRecords[0] || {});
report(
  'record copy includes title, source trail and text',
  '',
  copied.includes(String(caseRecords[0]?.title || '\u0000')) && copied.includes(String(caseRecords[0]?.summary || '\u0000')),
  `${copied.length} chars`,
);

console.log(failures === 0 ? '\nAll checks passed.' : `\n${failures} check(s) FAILED.`);
process.exit(failures === 0 ? 0 : 1);
