/**
 * Ready-to-Demonstrate legal examples for the Compare page.
 *
 * Every entry is a real Indian judgment. Nothing here is generated: the case
 * summaries, questions and provision lists are written from the judgments
 * themselves, and each `sources[].url` was opened and checked against the
 * published judgment title recorded in `sources[].verified_title`.
 *
 * `corpus` records what the ACTIVE ChromaDB index actually contains, checked by
 * querying `POST /api/research` with the case name and comparing the returned
 * `case_name` metadata (see `corpus.checked_at`). Examples whose judgment is not
 * in the index say so on the card and in the result provenance panel — the
 * comparison then reports related retrieved material, not the selected judgment.
 *
 * `citation` is left null wherever no citation string could be verified from the
 * source; it is never invented.
 *
 * `form.year` is deliberately left blank for every preset. The shared year field
 * is a *retrieval filter* over the indexed corpus, and the active index holds
 * 1950–1951 judgments only; entering 2015 or 1973 would silently return nothing.
 * The judgment year is carried as metadata instead (`years`), and the filter
 * stays under the user's control.
 */

/** Active index snapshot at `checked_at`: 9,375 chunks, judgments from 1950–1951. */
const CORPUS_CHECKED_AT = '2026-10-28'
const CORPUS_SCOPE_NOTE =
  'The active index holds 9,375 chunks of Indian Supreme Court judgments from 1950–1951.'

export const LEGAL_DEMO_EXAMPLES = [
  {
    id: 'gopalan-v-maneka',
    featured: true,
    mode: 'two_scenarios',
    title: 'A.K. Gopalan (1950) vs Maneka Gandhi (1978)',
    court: 'Supreme Court of India',
    years: [1950, 1978],
    year_label: '1950 and 1978',
    topic: 'Personal liberty · Article 21',
    demonstrates:
      'How the Supreme Court\'s approach to personal liberty and "procedure established by law" developed between two landmark judgments.',
    provisions_display:
      'Constitution of India: Articles 14, 19, 21 and 22 · Preventive Detention Act, 1950 · Passports Act, 1967',
    scope_note:
      'Two judgments with different facts. The comparison treats them as two separate accounts of the personal-liberty question — the underlying events are not identical and the year filter is left blank so retrieval is not restricted to one year.',
    form: {
      legal_issue:
        'How did the Supreme Court interpret personal liberty and "procedure established by law" under Article 21 in A.K. Gopalan and Maneka Gandhi, including the relationship between Articles 14, 19, 21 and 22?',
      case_facts:
        'Compare two real Supreme Court judgments concerning personal liberty and constitutional safeguards. The cases involve different facts and legal settings; compare their legal reasoning without treating the underlying events as identical.',
      // Comma-separated because the form splits provisions on commas; each token
      // stays self-contained so nothing is mangled.
      provisions:
        'Constitution of India Article 14, Constitution of India Article 19, Constitution of India Article 21, Constitution of India Article 22, Preventive Detention Act 1950, Passports Act 1967',
      court: 'Supreme Court of India',
      year: '',
      a_label: 'A.K. Gopalan v. State of Madras (1950)',
      a_position:
        "A.K. Gopalan challenged his preventive detention under the Preventive Detention Act, 1950. The constitutional issues included personal liberty and the safeguards applicable to preventive detention. Examine the judgment's treatment of Articles 19, 21 and 22.",
      b_label: 'Maneka Gandhi v. Union of India (1978)',
      b_position:
        'Maneka Gandhi challenged the impounding of her passport under the Passports Act, 1967. The case raised constitutional questions involving Articles 14, 19 and 21, including the fairness of the procedure affecting personal liberty.',
    },
    cases: [
      {
        name: 'A.K. Gopalan v. State of Madras',
        year: 1950,
        match_tokens: ['gopalan'],
        corpus: {
          present: true,
          matched_titles: ['A.K. GOPALAN v. THE STATE OF MADRAS.UNION OF INDIA: INTERVENER'],
          note: 'Retrieved from the indexed corpus.',
        },
      },
      {
        name: 'Maneka Gandhi v. Union of India',
        year: 1978,
        match_tokens: ['maneka'],
        corpus: {
          present: false,
          matched_titles: [],
          note: 'Not found in the indexed corpus. The external judgment link is provided for source verification.',
        },
      },
    ],
    sources: [
      {
        label: 'A.K. Gopalan v. State of Madras — Indian Kanoon',
        url: 'https://indiankanoon.org/doc/1857950/',
        verified_title: 'A.K. Gopalan vs The State Of Madras.Union Of India: ... on 19 May, 1950',
      },
      {
        label: 'Maneka Gandhi v. Union of India — Indian Kanoon',
        url: 'https://indiankanoon.org/doc/1766147/',
        verified_title: 'Maneka Gandhi vs Union Of India on 25 January, 1978',
      },
    ],
    citation: null,
  },
  {
    id: 'shreya-singhal-2015',
    mode: 'single_scenario',
    title: 'Shreya Singhal v. Union of India (2015)',
    court: 'Supreme Court of India',
    years: [2015],
    year_label: '2015',
    topic: 'Freedom of speech · Section 66A IT Act',
    demonstrates:
      'Why Section 66A of the Information Technology Act, 2000 was held unconstitutional in relation to freedom of speech and expression.',
    provisions_display:
      'Constitution of India: Articles 19(1)(a) and 19(2) · Information Technology Act, 2000, Section 66A',
    scope_note:
      'Section 66A is discussed only as the provision struck down by this 2015 judgment. It is not current law.',
    form: {
      legal_issue:
        'Why did the Supreme Court hold Section 66A of the Information Technology Act, 2000 unconstitutional in relation to freedom of speech and expression?',
      case_facts:
        'The petitions challenged Section 66A of the Information Technology Act, 2000, which criminalised specified categories of messages sent through communication services. The Supreme Court considered the provision in relation to the constitutional guarantee of freedom of speech and expression.',
      provisions:
        'Constitution of India Article 19(1)(a), Constitution of India Article 19(2), Information Technology Act 2000 Section 66A',
      court: 'Supreme Court of India',
      year: '',
      a_label: 'Petitioners',
      a_position:
        'The petitioners challenged Section 66A of the Information Technology Act, 2000, which criminalised specified categories of messages sent through communication services, as inconsistent with the freedom of speech and expression guaranteed by Article 19(1)(a).',
      b_label: 'Union of India',
      b_position: '',
    },
    cases: [
      {
        name: 'Shreya Singhal v. Union of India',
        year: 2015,
        match_tokens: ['shreya'],
        corpus: {
          present: false,
          matched_titles: [],
          note: 'Not found in the indexed corpus. The external judgment link is provided for source verification.',
        },
      },
    ],
    sources: [
      {
        label: 'Shreya Singhal v. U.O.I. — Indian Kanoon',
        url: 'https://indiankanoon.org/doc/76238264/',
        verified_title: 'Shreya Singhal vs U.O.I. on 24 March, 2015',
      },
    ],
    citation: null,
  },
  {
    id: 'vishaka-1997',
    mode: 'single_scenario',
    title: 'Vishaka v. State of Rajasthan (1997)',
    court: 'Supreme Court of India',
    years: [1997],
    year_label: '1997',
    topic: 'Workplace sexual harassment · gender equality',
    demonstrates:
      'How the Court addressed workplace sexual harassment and constitutional protection in the absence of specific legislation at the time.',
    provisions_display:
      'Constitution of India: Articles 14, 15, 19(1)(g), 21 and 32',
    scope_note:
      'The guidelines in this 1997 judgment are the historic position; later legislation is outside this judgment and is not relied on here.',
    form: {
      legal_issue:
        'How did the Supreme Court address workplace sexual harassment and constitutional protection in the absence of specific legislation at the time?',
      case_facts:
        'Vishaka and other petitioners brought a public-interest case seeking effective safeguards against workplace sexual harassment. The Supreme Court considered gender equality, dignity, and constitutional rights, and issued guidelines to address the legislative gap.',
      provisions:
        'Constitution of India Article 14, Constitution of India Article 15, Constitution of India Article 19(1)(g), Constitution of India Article 21, Constitution of India Article 32',
      court: 'Supreme Court of India',
      year: '',
      a_label: 'Vishaka and other petitioners',
      a_position:
        'The petitioners sought effective safeguards against workplace sexual harassment, relying on the constitutional guarantees of gender equality, dignity and personal liberty, in the absence of specific legislation at the time.',
      b_label: 'State of Rajasthan and other respondents',
      b_position: '',
    },
    cases: [
      {
        name: 'Vishaka v. State of Rajasthan',
        year: 1997,
        match_tokens: ['vishaka'],
        corpus: {
          present: false,
          matched_titles: [],
          note: 'Not found in the indexed corpus. The external judgment link is provided for source verification.',
        },
      },
    ],
    sources: [
      {
        label: 'Vishaka & Ors v. State Of Rajasthan & Ors — Indian Kanoon',
        url: 'https://indiankanoon.org/doc/1031794/',
        verified_title: 'Vishaka & Ors vs State Of Rajasthan & Ors on 13 August, 1997',
      },
    ],
    citation: null,
  },
  {
    id: 'puttaswamy-2017',
    mode: 'single_scenario',
    title: 'Justice K.S. Puttaswamy (Retd.) v. Union of India (2017)',
    court: 'Supreme Court of India',
    years: [2017],
    year_label: '2017',
    topic: 'Fundamental right to privacy · Part III',
    demonstrates:
      'Whether the Constitution protects privacy as a fundamental right, and how that right relates to personal liberty and other fundamental rights.',
    provisions_display:
      'Constitution of India, Part III, including Articles 14, 19 and 21 where relevant to the judgment',
    scope_note:
      'This preset is about the constitutional question decided in this judgment; it does not decide later disputes involving privacy.',
    form: {
      legal_issue:
        'Does the Constitution of India protect privacy as a fundamental right, and how does that right relate to personal liberty and other fundamental rights?',
      case_facts:
        'A nine-judge bench of the Supreme Court considered whether privacy is protected as a fundamental right under the Constitution of India. Analyse the reasoning in that decision and distinguish this constitutional question from the merits of other privacy-related disputes.',
      provisions:
        'Constitution of India Part III, Constitution of India Article 14, Constitution of India Article 19, Constitution of India Article 21',
      court: 'Supreme Court of India',
      year: '',
      a_label: 'Justice K.S. Puttaswamy (Retd.) and another petitioner',
      a_position:
        'The petitioners asked the nine-judge bench to hold that privacy is protected as a fundamental right under the Constitution of India and to explain how that right relates to personal liberty and the other fundamental rights.',
      b_label: 'Union of India and other respondents',
      b_position: '',
    },
    cases: [
      {
        name: 'Justice K.S. Puttaswamy (Retd.) v. Union of India',
        year: 2017,
        match_tokens: ['puttaswamy'],
        corpus: {
          present: false,
          matched_titles: [],
          note: 'Not found in the indexed corpus. The external judgment link is provided for source verification.',
        },
      },
    ],
    sources: [
      {
        label: 'Justice K.S. Puttaswamy (Retd) v. Union Of India — Indian Kanoon',
        url: 'https://indiankanoon.org/doc/91938676/',
        verified_title: 'Justice K.S.Puttaswamy(Retd) And Anr. vs Union Of India And Ors. on 24 August, 2017',
      },
    ],
    citation: null,
  },
  {
    id: 'kesavananda-1973',
    mode: 'single_scenario',
    title: 'Kesavananda Bharati v. State of Kerala (1973)',
    court: 'Supreme Court of India',
    years: [1973],
    year_label: '1973',
    topic: 'Basic structure doctrine · Article 368',
    demonstrates:
      'What limits the Court placed on Parliament\'s power to amend the Constitution under Article 368.',
    provisions_display:
      'Constitution of India: Article 368 and the constitutional provisions discussed in the judgment',
    scope_note:
      'Source verification links to the official eCourts Basic Structure judgment portal rather than a third-party copy.',
    form: {
      legal_issue:
        "What limits did the Supreme Court place on Parliament's power to amend the Constitution under Article 368?",
      case_facts:
        "The Supreme Court considered the scope of Parliament's constitutional amendment power in a landmark constitutional case. Examine the reasoning behind the basic structure doctrine using the judgment itself and its documented legal context.",
      provisions:
        'Constitution of India Article 368',
      court: 'Supreme Court of India',
      year: '',
      a_label: 'Kesavananda Bharati',
      a_position:
        "The case concerned the scope of Parliament's power to amend the Constitution under Article 368, including whether any features of the Constitution lie beyond that amending power.",
      b_label: 'State of Kerala and other respondents, as recorded in the source judgment',
      b_position: '',
    },
    cases: [
      {
        name: 'Kesavananda Bharati v. State of Kerala',
        year: 1973,
        match_tokens: ['kesavananda'],
        corpus: {
          present: false,
          matched_titles: [],
          note: 'Not found in the indexed corpus. The external judgment link is provided for source verification.',
        },
      },
    ],
    sources: [
      {
        label: 'Kesavananda Bharati judgment — eCourts official portal',
        url: 'https://judgments.ecourts.gov.in/KBJ/?p=home',
        verified_title: 'The Basic Structure Judgment - Kesavananda Bharati Judgment - Home',
      },
    ],
    citation: null,
  },
]

export const CORPUS_SNAPSHOT = {
  checked_at: CORPUS_CHECKED_AT,
  note: CORPUS_SCOPE_NOTE,
}

export function getDemoExample(id) {
  return LEGAL_DEMO_EXAMPLES.find((example) => example.id === id) || null
}

/** Form state for a preset, merged over the empty form so no field is missing. */
export function exampleFormValues(example, emptyForm) {
  return { ...emptyForm, ...(example?.form || {}) }
}

/**
 * Which of the preset's judgments the backend actually returned, compared by the
 * case-name tokens recorded per case. This runs on the real response; nothing is
 * assumed about what the index contains.
 */
export function matchPresetCases(result, example) {
  if (!example) return []
  const names = [
    ...((result?.citations || []).map((item) => item.case_name)),
    ...((result?.precedents || []).map((item) => item.case_name)),
  ].filter(Boolean)

  return example.cases.map((item) => {
    const tokens = (item.match_tokens || []).map((token) => token.toLowerCase())
    const retrievedAs =
      names.find((name) => tokens.every((token) => name.toLowerCase().includes(token))) || null
    return { ...item, retrievedAs }
  })
}
