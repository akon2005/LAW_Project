import React from 'react';
import { Brain, BookOpen, AlertTriangle, Scale, ShieldCheck } from 'lucide-react';

export default function ResearchAnswer({ result }) {
  if (!result) return null;

  const answer = result.answer || result.explanation || "No response generated.";
  const rawSources = result.sources || result.prediction_context || [];
  const key_principles = result.key_principles || [];
  const disclaimer = result.disclaimer || "This is AI-generated research support and does not constitute legal advice.";
  const processing_time_seconds = result.processing_time_seconds || 0.0;
  const confidence = result.confidence || (rawSources.length > 0 ? "High" : "Low");

  const sources = rawSources.map(s => ({
    doc_id: s.doc_id || s.case_id || 'doc',
    title: s.title || s.case_name || 'Judicial Precedent',
    relevance_score: s.relevance_score !== undefined ? s.relevance_score : (s.similarity_score || 0.0),
    document_type: s.document_type || s.legal_domain || s.record_type || 'case_law',
    court: s.court || 'High Court / Supreme Court',
    year: s.year || '',
    snippet: s.snippet || s.retrieval_document || s.full_text || '',
    citation: s.citation || '',
  }));

  return (
    <div className="animate-fade-in-up" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* AI Answer */}
      <div className="glass-card" style={{ padding: '32px' }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: 8, marginBottom: 24, flexWrap: 'wrap'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 40, height: 40, borderRadius: 12,
              background: 'linear-gradient(135deg, rgba(212, 175, 55, 0.15), rgba(212, 175, 55, 0.03))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              border: '1px solid rgba(212, 175, 55, 0.25)',
              boxShadow: '0 0 15px rgba(212, 175, 55, 0.08)',
            }}>
              <Brain size={20} color="#d4af37" />
            </div>
            <div>
              <h3 className="font-display" style={{ fontSize: 20, fontWeight: 700, color: '#f8fafc' }}>
                Research Analysis
              </h3>
              <p style={{ fontSize: 13, color: '#94a3b8', fontWeight: 500, marginTop: 2 }}>
                RAG-generated answer with source citations • {processing_time_seconds ? processing_time_seconds.toFixed(2) : '0.00'}s
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="badge" style={{
              background: confidence === 'High' ? 'rgba(34, 197, 94, 0.12)' : 'rgba(234, 179, 8, 0.12)',
              color: confidence === 'High' ? '#4ade80' : '#facc15',
              border: `1px solid ${confidence === 'High' ? 'rgba(34, 197, 94, 0.25)' : 'rgba(234, 179, 8, 0.25)'}`,
              fontSize: 12, padding: '4px 10px', display: 'flex', alignItems: 'center', gap: 4
            }}>
              <ShieldCheck size={13} />
              {confidence} Confidence
            </span>
            <span className="badge badge-relevance">
              {sources.length} sources cited
            </span>
          </div>
        </div>

        {/* Answer text */}
        <div
          className="markdown-content"
          style={{
            padding: 24,
            background: 'rgba(10, 13, 26, 0.6)',
            borderRadius: 14,
            border: '1px solid rgba(255, 255, 255, 0.05)',
            marginBottom: 24,
            maxHeight: 600,
            overflowY: 'auto',
            lineHeight: 1.8,
            fontSize: 15.5,
            color: '#cbd5e1',
            whiteSpace: 'pre-wrap',
            boxShadow: 'inset 0 2px 10px rgba(0, 0, 0, 0.2)',
          }}
        >
          {answer}
        </div>

        {/* Key principles */}
        {key_principles && key_principles.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <div style={{
              fontSize: 12, fontWeight: 700, color: '#f5d77f', marginBottom: 12,
              textTransform: 'uppercase', letterSpacing: '0.08em',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <Scale size={14} />
              Key Legal Principles & Frameworks
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {key_principles.map((p, i) => (
                <span key={i} className="badge badge-case-law" style={{ fontSize: 12.5, padding: '6px 14px', borderRadius: 20 }}>
                  {p}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Disclaimer */}
        {disclaimer && (
          <div className="disclaimer-banner" style={{ marginTop: 24, fontSize: 13.5 }}>
            <AlertTriangle size={16} color="#d4af37" style={{ flexShrink: 0 }} />
            <span style={{ fontWeight: 500, lineHeight: 1.5 }}>{disclaimer}</span>
          </div>
        )}
      </div>

      {/* Source Documents */}
      {sources && sources.length > 0 && (
        <div className="glass-card animate-fade-in-up animate-delay-200" style={{ padding: 32 }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            marginBottom: 20, flexWrap: 'wrap', gap: 8
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <BookOpen size={20} color="#d4af37" />
              <h3 className="font-display" style={{ fontSize: 20, fontWeight: 700, color: '#f8fafc' }}>
                Cited Judicial Precedents & Sources
              </h3>
            </div>
            <span style={{ fontSize: 13, color: '#94a3b8' }}>
              Ordered by semantic relevance score
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {sources.map((source, i) => (
              <div
                key={source.doc_id || i}
                style={{
                  padding: 24,
                  background: 'rgba(10, 13, 26, 0.4)',
                  borderRadius: 12,
                  border: '1px solid rgba(255, 255, 255, 0.04)',
                  transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'rgba(212, 175, 55, 0.25)';
                  e.currentTarget.style.background = 'rgba(18, 24, 41, 0.6)';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.04)';
                  e.currentTarget.style.background = 'rgba(10, 13, 26, 0.4)';
                  e.currentTarget.style.transform = 'translateY(0)';
                }}
              >
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  gap: 8, marginBottom: 12, flexWrap: 'wrap'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span className="citation-tag" style={{ fontSize: 14, padding: '4px 10px' }}>[{i + 1}]</span>
                    <span className="font-display" style={{ fontSize: 16, fontWeight: 700, color: '#f8fafc' }}>
                      {source.title}
                    </span>
                  </div>
                  <span className="badge badge-relevance" style={{ fontSize: 12, padding: '6px 12px' }}>
                    {(source.relevance_score * 100).toFixed(0)}% Match
                  </span>
                </div>

                <div style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  flexWrap: 'wrap', marginBottom: 14,
                }}>
                  <span className={`badge badge-${source.document_type?.replace(/[\s_]+/g, '-').toLowerCase() || 'case-law'}`}
                    style={{ fontSize: 12, padding: '4px 12px' }}>
                    {source.document_type || 'Case Law'}
                  </span>
                  {source.court && (
                    <span className="badge badge-court" style={{ fontSize: 12, padding: '4px 12px' }}>{source.court}</span>
                  )}
                  {source.year ? (
                    <span style={{ fontSize: 14, color: '#94a3b8', fontWeight: 500 }}>{source.year}</span>
                  ) : null}
                  {source.citation && (
                    <span style={{ fontSize: 12, color: '#64748b', fontStyle: 'italic' }}>Citation: {source.citation}</span>
                  )}
                </div>

                <p style={{ fontSize: 14, color: '#cbd5e1', lineHeight: 1.7 }}>
                  {source.snippet}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
