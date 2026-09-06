import { useState, useEffect, useRef } from 'react';
import { Scale, Search, BookOpen, Sparkles } from 'lucide-react';
import SearchBar from '../components/CaseInput/CaseInputForm';
import ResearchAnswer from '../components/Results/ResearchAnswer';
import { useSearch } from '../hooks/useSearch';
import { browseDocuments, healthCheck } from '../api/client';
import MarqueeTrack from '../components/Home/MarqueeTrack';
import EcosystemDiagram from '../components/Home/EcosystemDiagram';

const AshokaChakra = ({ size = 20, color = "#0B3D91" }) => (
  <svg width={size} height={size} viewBox="0 0 100 100" style={{ flexShrink: 0, animation: 'spin 25s linear infinite' }}>
    <circle cx="50" cy="50" r="44" fill="none" stroke={color} strokeWidth="5" />
    <circle cx="50" cy="50" r="10" fill="none" stroke={color} strokeWidth="4" />
    {Array.from({ length: 24 }).map((_, i) => {
      const angle = (i * 360) / 24;
      const x2 = 50 + 34 * Math.sin((angle * Math.PI) / 180);
      const y2 = 50 - 34 * Math.cos((angle * Math.PI) / 180);
      return (
        <line
          key={i}
          x1="50"
          y1="50"
          x2={x2}
          y2={y2}
          stroke={color}
          strokeWidth="3"
        />
      );
    })}
  </svg>
);

export default function HomePage() {
  const { result, loading, error, search } = useSearch();
  const resultsRef = useRef(null);
  const [stats, setStats] = useState({
    caseLaws: '1,631',
    statutes: '180',
    vectorChunks: '1,631',
  });

  useEffect(() => {
    async function loadStats() {
      try {
        const [docsRes, healthRes] = await Promise.all([
          browseDocuments({ limit: 1 }),
          healthCheck(),
        ]);
        const count = docsRes.total || 1631;
        setStats({
          caseLaws: count.toLocaleString(),
          statutes: '180',
          vectorChunks: (healthRes.components?.document_count || count).toLocaleString(),
        });
      } catch (err) {
        console.error("Failed to fetch stats", err);
      }
    }
    loadStats();
  }, []);

  useEffect(() => {
    if (result && resultsRef.current) {
      resultsRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [result]);

  return (
    <div className="hero" style={{ flex: 1, position: 'relative' }}>
      {/* Premium Background Mesh Glow (Tricolor) */}
      <div className="mesh-gradient">
        <div className="mesh-orb-saffron"></div>
        <div className="mesh-orb-blue"></div>
        <div className="mesh-orb-green"></div>
      </div>

      <div style={{ maxWidth: 1000, margin: '0 auto', padding: '60px 24px 80px', position: 'relative', zIndex: 10 }}>

        {/* Asymmetric Hero Grid */}
        <div className="hero-grid-layout">
          {/* Left Hero Section (60% width) */}
          <div>
            <div 
              className="gradient-border-pill"
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 10,
                padding: '8px 20px',
                marginBottom: 24,
                boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)',
                transform: 'rotate(-2.5deg)',
                transformOrigin: 'left center',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <AshokaChakra size={16} color="#0B3D91" />
                <Sparkles size={12} color="#FF9933" />
              </div>
              <span style={{ fontSize: 11, fontWeight: 800, color: '#f5d77f', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                AI-Powered Legal Research Engine · SIH1701
              </span>
            </div>

            <h1 className="font-display" style={{
              fontSize: 66,
              fontWeight: 300,
              letterSpacing: '-2px',
              lineHeight: 1.12,
              marginBottom: 20,
              fontFamily: "'Fraunces', Georgia, serif",
            }}>
              <span style={{ fontWeight: 300, color: '#ffffff' }}>Legal </span>
              <span style={{ fontWeight: 850, color: '#ffffff', textShadow: '0 2px 12px rgba(255, 255, 255, 0.12)' }}>Research,</span>
              <br />
              <div style={{ position: 'relative', display: 'inline-block', marginTop: 4 }}>
                <span className="headline-highlight" style={{ fontWeight: 900 }}>Reimagined.</span>
                {/* Hand-drawn SVG squiggle underline */}
                <svg 
                  viewBox="0 0 100 20" 
                  preserveAspectRatio="none" 
                  style={{
                    position: 'absolute',
                    bottom: '-14px',
                    left: 0,
                    width: '105%',
                    height: '14px',
                    zIndex: 1,
                    pointerEvents: 'none',
                  }}
                >
                  <path 
                    d="M 2,12 Q 25,2 50,10 T 98,12" 
                    fill="none" 
                    stroke="url(#squiggle-gradient)" 
                    strokeWidth="4.5" 
                    strokeLinecap="round" 
                  />
                  <defs>
                    <linearGradient id="squiggle-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" stopColor="#FF9933" />
                      <stop offset="50%" stopColor="#F4C430" />
                      <stop offset="100%" stopColor="#046A38" />
                    </linearGradient>
                  </defs>
                </svg>
              </div>
            </h1>

            <p style={{
              fontSize: 16, color: '#cbd5e1', maxWidth: 520, margin: '24px 0 0',
              lineHeight: 1.8,
              fontWeight: 400,
              textShadow: '0 1px 3px rgba(0,0,0,0.5)',
            }}>
              Ask questions in natural language. Get citation-backed answers from Indian case laws,
              statutes, and notifications — powered by Retrieval-Augmented Generation.
            </p>
          </div>

          {/* Right Hero Section (Asymmetric Vertical Accent Line + Seal) */}
          <div 
            className="hero-accent-right"
            style={{
              position: 'relative',
              height: '320px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              overflow: 'hidden',
              borderRadius: 16,
              background: 'rgba(10, 13, 26, 0.15)',
              border: '1px solid rgba(255,255,255,0.02)',
            }}
          >
            {/* Vertical glowing accent line */}
            <div style={{
              position: 'absolute',
              left: '15%',
              top: '0',
              bottom: '0',
              width: '1px',
              background: 'linear-gradient(180deg, transparent, #FF9933 30%, #0B3D91 60%, transparent)',
              boxShadow: '0 0 15px rgba(255, 153, 51, 0.3)',
            }} />
            
            {/* Bleeding Ashoka Chakra motif */}
            <div style={{
              position: 'absolute',
              right: '-30%',
              width: '320px',
              height: '320px',
              opacity: 0.08,
              transform: 'rotate(12deg)',
              pointerEvents: 'none',
            }}>
              <AshokaChakra size={320} color="#0B3D91" />
            </div>
            
            {/* Hand-drawn ink-stamp circular seal graphic */}
            <div style={{
              position: 'absolute',
              left: '25%',
              top: '30%',
              transform: 'rotate(-6deg)',
              opacity: 0.28,
              pointerEvents: 'none',
            }}>
              <svg width="130" height="130" viewBox="0 0 100 100" style={{ fill: 'none', stroke: '#F4C430', strokeWidth: 1.5 }}>
                <circle cx="50" cy="50" r="45" strokeDasharray="3 3 2 1" />
                <circle cx="50" cy="50" r="41" strokeDasharray="5 2 1 4" />
                <path d="M 50, 25 L 50, 75 M 30, 75 L 70, 75 M 35, 38 L 65, 38" strokeWidth="2" strokeDasharray="1.5 0.5" />
                <path d="M 35, 38 L 28, 55 M 35, 38 L 42, 55 M 28, 55 Q 35, 60 42, 55" />
                <path d="M 65, 38 L 58, 55 M 65, 38 L 72, 55 M 58, 55 Q 65, 60 72, 55" />
                <path id="seal-text-path-home" d="M 15,50 A 35,35 0 0,1 85,50" fill="none" stroke="none" />
                <text style={{ fontSize: '6.5px', fill: '#F4C430', fontWeight: 'bold', letterSpacing: '1.8px' }}>
                  <textPath href="#seal-text-path-home" startOffset="50%" textAnchor="middle">
                    VIDHIVEDA JUSTICE
                  </textPath>
                </text>
              </svg>
            </div>
          </div>
        </div>

        {/* Search Bar */}
        <div style={{ marginBottom: 40, marginTop: 12 }}>
          <SearchBar onSearch={search} loading={loading} />
        </div>

        {/* Asymmetric grid stat cards */}
        <div className="stats-grid-layout" style={{ marginBottom: 48 }}>
          {/* Stat Card 1 */}
          <div 
            className="stat-card" 
            onClick={() => search({ query: "show me recent case laws", top_k: 8 })}
            style={{ 
              padding: '30px', 
              textAlign: 'left',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              height: '100%',
              cursor: 'pointer',
              '--accent-color': '#FF9933',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{
                width: 44, height: 44, borderRadius: '50%',
                background: 'rgba(255, 153, 51, 0.12)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: '0 0 16px rgba(255, 153, 51, 0.45)',
              }}>
                <Scale size={20} color="#FF9933" />
              </div>
              <span style={{ fontSize: 10, color: '#f5d77f', fontWeight: 800, letterSpacing: '0.12em', textTransform: 'uppercase' }}>Primary Corpus</span>
            </div>
            <div style={{ marginTop: 24 }}>
              <div style={{ fontSize: 44, fontWeight: 900, color: '#ffffff', lineHeight: 1 }}>{stats.caseLaws}</div>
              <div style={{ fontSize: 13, color: '#cbd5e1', fontWeight: 700, marginTop: 8, letterSpacing: '0.02em', textTransform: 'uppercase' }}>Case Laws & Judicial Precedents</div>
            </div>
          </div>

          {/* Stat Card 2 */}
          <div 
            className="stat-card" 
            onClick={() => search({ query: "list important statutes", top_k: 8 })}
            style={{ 
              padding: '30px', 
              textAlign: 'left',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              height: '100%',
              cursor: 'pointer',
              '--accent-color': '#0B3D91',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{
                width: 44, height: 44, borderRadius: '50%',
                background: 'rgba(11, 61, 145, 0.25)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: '0 0 16px rgba(11, 61, 145, 0.55)',
              }}>
                <BookOpen size={20} color="#60a5fa" />
              </div>
              <span style={{ fontSize: 10, color: '#93c5fd', fontWeight: 800, letterSpacing: '0.12em', textTransform: 'uppercase' }}>Legislation</span>
            </div>
            <div style={{ marginTop: 24 }}>
              <div style={{ fontSize: 44, fontWeight: 900, color: '#f8fafc', lineHeight: 1 }}>{stats.statutes}</div>
              <div style={{ fontSize: 13, color: '#cbd5e1', fontWeight: 700, marginTop: 8, letterSpacing: '0.02em', textTransform: 'uppercase' }}>Central Acts & Commercial Codes</div>
            </div>
          </div>

          {/* Stat Card 3 */}
          <div 
            className="stat-card" 
            onClick={() => search({ query: "explain semantic search", top_k: 8 })}
            style={{ 
              padding: '30px', 
              textAlign: 'left',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              height: '100%',
              cursor: 'pointer',
              '--accent-color': '#046A38',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{
                width: 44, height: 44, borderRadius: '50%',
                background: 'rgba(4, 106, 56, 0.25)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: '0 0 16px rgba(4, 106, 56, 0.55)',
              }}>
                <Search size={20} color="#34d399" />
              </div>
              <span style={{ fontSize: 10, color: '#6ee7b7', fontWeight: 800, letterSpacing: '0.12em', textTransform: 'uppercase' }}>Technology</span>
            </div>
            <div style={{ marginTop: 24 }}>
              <div style={{ fontSize: 32, fontWeight: 900, color: '#f8fafc', lineHeight: 1 }}>{stats.vectorChunks} Vectors</div>
              <div style={{ fontSize: 13, color: '#cbd5e1', fontWeight: 700, marginTop: 8, letterSpacing: '0.02em', textTransform: 'uppercase' }}>ChromaDB Semantic Chunks</div>
            </div>
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div style={{
            textAlign: 'center', padding: 48, marginTop: 32,
          }}>
            <div className="spinner" style={{ width: 36, height: 36, margin: '0 auto 20px' }} />
            <p style={{ fontSize: 14, color: '#f5d77f', fontWeight: 500 }}>
              Searching legal knowledge base and generating analysis...
            </p>
            <div className="loading-bar" style={{ maxWidth: 300, margin: '18px auto 0' }} />
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="glass-card animate-fade-in-up" style={{
            padding: 24, marginTop: 32,
            borderColor: 'rgba(239, 68, 68, 0.2)',
            background: 'rgba(239, 68, 68, 0.03)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#f87171' }}>
              <span style={{ fontSize: 20 }}>⚠️</span>
              <span style={{ fontWeight: 700, fontSize: 15 }}>System Error</span>
            </div>
            <p style={{ fontSize: 13, color: '#cbd5e1', marginTop: 10, lineHeight: 1.6 }}>{error}</p>
          </div>
        )}

        {/* Results */}
        {result && (
          <div ref={resultsRef} style={{ marginTop: 40, scrollMarginTop: '20px' }}>
            <ResearchAnswer result={result} />
          </div>
        )}
      </div>

      {/* FreeAPI Inspired Animations */}
      <div style={{ position: 'relative', zIndex: 5 }}>
        <MarqueeTrack />
        <EcosystemDiagram />
      </div>
    </div>
  );
}
