import { Scale, Database, Brain, Shield, Search, FileText, Cpu, AlertTriangle, GitBranch } from 'lucide-react';

export default function AboutPage() {
  return (
    <div className="animated-bg" style={{ flex: 1 }}>
      <div style={{ maxWidth: 900, margin: '0 auto', padding: '40px 24px 60px' }}>
        {/* Hero */}
        <div style={{ textAlign: 'center', marginBottom: 48 }}>
          <div style={{
            width: 60, height: 60, borderRadius: 16, margin: '0 auto 16px',
            background: 'linear-gradient(135deg, #d4a44c, #b8892e)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 8px 24px rgba(212, 164, 76, 0.3)',
          }}>
            <Scale size={28} color="white" />
          </div>
          <h1 style={{ fontSize: 36, fontWeight: 900, marginBottom: 8 }}>
            <span className="headline-highlight">VIDHIVEDA</span>
          </h1>
          <p style={{ fontSize: 18, color: '#94a3b8', marginBottom: 8, fontFamily: "'Crimson Text', serif", fontStyle: 'italic' }}>
            AI-Powered Legal Research Engine for Indian Commercial Courts
          </p>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '6px 14px', borderRadius: 8,
            background: 'rgba(212, 164, 76, 0.08)', border: '1px solid rgba(212, 164, 76, 0.2)',
            fontSize: 12, fontWeight: 600, color: '#d4a44c',
          }}>
            SIH1701 · Department of Justice, Ministry of Law & Justice
          </div>
        </div>

        {/* Problem Statement */}
        <Section icon={AlertTriangle} title="The Problem" color="#f59e0b">
          <p>The <strong>Commercial Courts Act, 2015</strong> was enacted to expedite resolution of
          commercial disputes. However, a massive case backlog persists because judicial officers
          spend excessive time manually researching case laws, statutes, rules, regulations,
          and government notifications.</p>
          <p style={{ marginTop: 12 }}>VIDHIVEDA was built as a <strong>Smart India Hackathon (SIH1701)</strong> solution
          to this problem — providing judges with an AI-powered research assistant that
          dramatically reduces research time while maintaining full judicial authority over decisions.</p>
        </Section>

        {/* Architecture */}
        <Section icon={GitBranch} title="RAG Architecture" color="#14b8a6">
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 16,
          }}>
            {[
              { icon: FileText, title: 'Ingest & Chunk', desc: 'Legal documents are chunked with overlap and stored with metadata (type, jurisdiction, year, sections).' },
              { icon: Database, title: 'Embed & Store', desc: 'Sentence-Transformers encode chunks into vectors. ChromaDB stores them in a persistent, searchable index.' },
              { icon: Search, title: 'Semantic Search', desc: 'User queries are embedded and matched against the vector store with optional metadata filtering.' },
              { icon: Brain, title: 'RAG Generation', desc: 'Retrieved chunks are injected as context into an LLM, which generates citation-backed research answers.' },
            ].map(({ icon: Icon, title, desc }, i) => (
              <div key={i} className="glass-card" style={{ padding: 18 }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10,
                }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: 8,
                    background: 'rgba(20, 184, 166, 0.1)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <Icon size={16} color="#14b8a6" />
                  </div>
                  <span style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9' }}>{title}</span>
                </div>
                <p style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.6 }}>{desc}</p>
              </div>
            ))}
          </div>
        </Section>

        {/* Tech Stack */}
        <Section icon={Cpu} title="Technology Stack" color="#a855f7">
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10,
          }}>
            {[
              { name: 'FastAPI', role: 'Backend API' },
              { name: 'ChromaDB', role: 'Vector Store' },
              { name: 'Sentence-Transformers', role: 'Embeddings' },
              { name: 'OpenAI / Anthropic', role: 'LLM Generation' },
              { name: 'React + Vite', role: 'Frontend' },
              { name: 'SQLite', role: 'Metadata DB' },
            ].map(({ name, role }, i) => (
              <div key={i} style={{
                padding: '12px 14px', borderRadius: 10,
                background: 'rgba(15, 23, 42, 0.5)',
                border: '1px solid rgba(51, 65, 85, 0.3)',
              }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9' }}>{name}</div>
                <div style={{ fontSize: 11, color: '#64748b' }}>{role}</div>
              </div>
            ))}
          </div>
        </Section>

        {/* Principles */}
        <Section icon={Shield} title="Ethical Principles" color="#d4a44c">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              { title: 'Research Only', desc: 'VIDHIVEDA is strictly a research assistant. It never makes legal judgments, predictions, or recommendations.' },
              { title: 'Full Transparency', desc: 'Every response cites its source documents. Users can trace every claim back to verified legal texts.' },
              { title: 'Judicial Authority', desc: 'All decision-making power remains with the judicial officer. LexRAG supports — never supplants — human judgment.' },
              { title: 'Verified Sources Only', desc: 'All ingested data comes from verified legal sources — official gazettes, court records, and authenticated legislation.' },
              { title: 'Neutral & Unbiased', desc: 'The system presents all relevant perspectives from the sources without favouring any party or outcome.' },
            ].map(({ title, desc }, i) => (
              <div key={i} style={{
                display: 'flex', gap: 14, alignItems: 'flex-start',
                padding: '14px 16px', borderRadius: 10,
                background: 'rgba(15, 23, 42, 0.3)',
                border: '1px solid rgba(51, 65, 85, 0.2)',
              }}>
                <span style={{
                  fontSize: 11, fontWeight: 800, color: '#d4a44c',
                  minWidth: 20, textAlign: 'center',
                }}>
                  {i + 1}
                </span>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#f1f5f9', marginBottom: 4 }}>{title}</div>
                  <div style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.5 }}>{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Disclaimer */}
        <div className="disclaimer-banner" style={{
          marginTop: 32, justifyContent: 'center', fontSize: 13,
        }}>
          <AlertTriangle size={16} />
          <span>VIDHIVEDA provides research support only — not legal advice. All outputs must be independently verified by qualified judicial officers.</span>
        </div>
      </div>
    </div>
  );
}

function Section({ icon: Icon, title, color, children }) {
  return (
    <div style={{ marginBottom: 36 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <Icon size={20} color={color} />
        <h2 style={{ fontSize: 22, fontWeight: 800, color: '#f1f5f9' }}>{title}</h2>
      </div>
      <div style={{ fontSize: 14, color: '#cbd5e1', lineHeight: 1.7 }}>
        {children}
      </div>
    </div>
  );
}
