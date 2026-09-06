import { useState } from 'react';
import { BookOpen, Calendar, Building2, ChevronDown, ChevronUp, Scale, FileText, Bell, BookCheck, ExternalLink } from 'lucide-react';
import { DOC_TYPE_BADGE_CLASS, DOC_TYPE_LABELS } from '../../utils/constants';

const typeIcons = {
  case_law: Scale,
  statute: BookCheck,
  notification: Bell,
  regulation: FileText,
};

export default function DocumentCard({ document, index }) {
  const [expanded, setExpanded] = useState(false);

  const {
    doc_id, title, document_type, jurisdiction, court, year,
    full_text, sections, summary, outcome, relevance_score, source_url,
  } = document;

  const TypeIcon = typeIcons[document_type] || FileText;
  const badgeClass = DOC_TYPE_BADGE_CLASS[document_type] || 'badge-case-law';
  const typeLabel = DOC_TYPE_LABELS[document_type] || document_type;

  return (
    <div
      className="glass-card glass-card-hover"
      style={{
        padding: 24,
        animation: `fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) ${(index || 0) * 80}ms forwards`,
        opacity: 0,
        border: '1px solid rgba(255, 255, 255, 0.04)',
      }}
    >
      {/* Header row */}
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 12,
        marginBottom: 16,
      }}>
        <div style={{ flex: 1 }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            marginBottom: 8,
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: 8,
              background: 'rgba(212, 175, 55, 0.08)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              border: '1px solid rgba(212, 175, 55, 0.2)',
            }}>
              <TypeIcon size={14} color="#d4af37" />
            </div>
            <h4 className="font-display" style={{ fontSize: 16, fontWeight: 700, color: '#f8fafc' }}>
              {title}
            </h4>
          </div>

          {/* Meta info */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            flexWrap: 'wrap',
          }}>
            <span className={`badge ${badgeClass}`} style={{ fontSize: 10.5, padding: '3px 10px' }}>
              {typeLabel}
            </span>
            <span style={{
              display: 'flex', alignItems: 'center', gap: 4,
              fontSize: 12, color: '#47557a', fontWeight: 500
            }}>
              <Calendar size={12} />
              {year}
            </span>
            {court && (
              <span className="badge badge-court" style={{ fontSize: 10.5, padding: '3px 10px' }}>
                <Building2 size={10} />
                {court}
              </span>
            )}
            {jurisdiction && (
              <span className="badge badge-jurisdiction" style={{ fontSize: 10.5, padding: '3px 10px' }}>
                {jurisdiction}
              </span>
            )}
            {outcome && (
              <span className="badge" style={{
                fontSize: 10.5,
                padding: '3px 10px',
                background: outcome === 'conviction' ? 'rgba(239,68,68,0.06)' : 'rgba(34,197,94,0.06)',
                color: outcome === 'conviction' ? '#f87171' : '#34d399',
                border: `1px solid ${outcome === 'conviction' ? 'rgba(239,68,68,0.15)' : 'rgba(34,197,94,0.15)'}`,
              }}>
                {outcome}
              </span>
            )}
          </div>
        </div>

        {/* Relevance badge */}
        {relevance_score > 0 && (
          <div className="badge badge-relevance" style={{
            fontSize: 14, fontWeight: 800, padding: '6px 14px', flexShrink: 0,
          }}>
            {(relevance_score * 100).toFixed(0)}% Match
          </div>
        )}
      </div>

      {/* Sections */}
      {sections && sections.length > 0 && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
          {sections.map((s) => (
            <span key={s} className="badge badge-section" style={{ fontSize: 10.5, padding: '3px 10px' }}>
              § {s}
            </span>
          ))}
        </div>
      )}

      {/* Text excerpt */}
      <div style={{
        fontSize: 13, color: '#94a3b8', lineHeight: 1.6, marginBottom: 12,
      }}>
        {expanded ? full_text : (full_text?.slice(0, 250) + (full_text?.length > 250 ? '...' : ''))}
      </div>

      {/* Summary (expanded) */}
      {expanded && summary && (
        <div style={{
          padding: 16,
          background: 'rgba(212, 175, 55, 0.04)',
          borderRadius: 12,
          border: '1px solid rgba(212, 175, 55, 0.12)',
          marginBottom: 14,
        }}>
          <div style={{
            fontSize: 11, fontWeight: 700, color: '#f5d77f', marginBottom: 8,
            textTransform: 'uppercase', letterSpacing: '0.08em',
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <BookOpen size={12} />
            AI Summary
          </div>
          <div style={{ fontSize: 13, color: '#cbd5e1', lineHeight: 1.7 }}>
            {summary}
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            display: 'flex', alignItems: 'center', gap: 4,
            fontSize: 12, color: '#d4af37', background: 'none',
            border: 'none', cursor: 'pointer', padding: '4px 0',
            fontWeight: 600,
            transition: 'color 0.2s',
          }}
          onMouseEnter={(e) => e.currentTarget.style.color = '#f5d77f'}
          onMouseLeave={(e) => e.currentTarget.style.color = '#d4af37'}
        >
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          {expanded ? 'Show less' : 'Show full details'}
        </button>
        {source_url && (
          <a
            href={source_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'flex', alignItems: 'center', gap: 4,
              fontSize: 12, color: '#64748b', textDecoration: 'none',
            }}
          >
            <ExternalLink size={12} />
            Source
          </a>
        )}
      </div>
    </div>
  );
}
