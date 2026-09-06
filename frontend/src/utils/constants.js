/**
 * VIDHIVEDA constants — commercial court focused.
 */
export const DOCUMENT_TYPES = [
  { value: 'case_law', label: 'Case Law', color: '#e4b96a' },
  { value: 'statute', label: 'Statute', color: '#60a5fa' },
  { value: 'notification', label: 'Notification', color: '#c084fc' },
  { value: 'regulation', label: 'Regulation', color: '#5eead4' },
];

export const JURISDICTIONS = [
  'India',
  'Delhi',
  'Maharashtra',
  'Tamil Nadu',
  'Karnataka',
  'West Bengal',
  'Kerala',
  'Uttar Pradesh',
  'Gujarat',
  'Telangana',
  'Punjab and Haryana',
  'Bihar',
];

export const COURTS = [
  'Supreme Court of India',
  'Delhi High Court',
  'Bombay High Court',
  'Madras High Court',
  'Calcutta High Court',
  'Karnataka High Court',
  'Kerala High Court',
  'Allahabad High Court',
  'Gujarat High Court',
  'Punjab and Haryana High Court',
  'Telangana High Court',
  'Patna High Court',
];

export const SUGGESTED_QUERIES = [
  {
    title: 'Commercial Courts Jurisdiction',
    query: 'What types of disputes fall under the jurisdiction of Commercial Courts under the Commercial Courts Act, 2015?',
    icon: '⚖️',
  },
  {
    title: 'Specified Value Threshold',
    query: 'What is the specified value threshold for commercial disputes and how is it determined?',
    icon: '💰',
  },
  {
    title: 'Pre-Institution Mediation',
    query: 'When is pre-institution mediation mandatory in commercial disputes under Section 12A?',
    icon: '🤝',
  },
  {
    title: 'Arbitration Award Challenge',
    query: 'What are the grounds for setting aside an arbitral award under Section 34 of the Arbitration Act?',
    icon: '📜',
  },
  {
    title: 'Breach of Contract Compensation',
    query: 'How is compensation determined in cases of breach of commercial contracts under Indian law?',
    icon: '📋',
  },
  {
    title: 'Transfer of Pending Cases',
    query: 'What is the procedure for transfer of pending cases to Commercial Courts under Section 15?',
    icon: '🔄',
  },
];

export const DOC_TYPE_BADGE_CLASS = {
  case_law: 'badge-case-law',
  statute: 'badge-statute',
  notification: 'badge-notification',
  regulation: 'badge-regulation',
};

export const DOC_TYPE_LABELS = {
  case_law: 'Case Law',
  statute: 'Statute',
  notification: 'Notification',
  regulation: 'Regulation',
};
