import { useState, useEffect } from 'react';
import { Search, SlidersHorizontal, X, Scale, DollarSign, Handshake, FileText, ClipboardList, RefreshCw } from 'lucide-react';
import { DOCUMENT_TYPES, JURISDICTIONS, SUGGESTED_QUERIES } from '../../utils/constants';

export default function SearchBar({ onSearch, loading }) {
  const [query, setQuery] = useState('');
  const [placeholder, setPlaceholder] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({
    document_type: '',
    jurisdiction: '',
    year_from: '',
    year_to: '',
  });

  useEffect(() => {
    const prompts = [
      "What defines a commercial dispute under the CCA 2015?",
      "When is pre-institution mediation mandatory under Section 12A?",
      "What are the grounds for setting aside an arbitral award under Section 34?"
    ];
    
    let currentPromptIdx = 0;
    let currentText = '';
    let isDeleting = false;
    let timer;
    
    const type = () => {
      const fullText = prompts[currentPromptIdx];
      if (!isDeleting) {
        currentText = fullText.substring(0, currentText.length + 1);
        setPlaceholder(currentText);
        
        if (currentText === fullText) {
          isDeleting = true;
          timer = setTimeout(type, 3000);
          return;
        }
      } else {
        currentText = fullText.substring(0, currentText.length - 1);
        setPlaceholder(currentText);
        
        if (currentText === '') {
          isDeleting = false;
          currentPromptIdx = (currentPromptIdx + 1) % prompts.length;
          timer = setTimeout(type, 500);
          return;
        }
      }
      
      timer = setTimeout(type, isDeleting ? 25 : 55);
    };
    
    type();
    return () => clearTimeout(timer);
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    const params = { query: query.trim(), top_k: 8 };
    if (filters.document_type) params.document_type = filters.document_type;
    if (filters.jurisdiction) params.jurisdiction = filters.jurisdiction;
    if (filters.year_from) params.year_from = parseInt(filters.year_from);
    if (filters.year_to) params.year_to = parseInt(filters.year_to);
    onSearch(params);
  };

  const handleSuggestion = (suggestion) => {
    setQuery(suggestion.query);
    onSearch({ query: suggestion.query, top_k: 8 });
  };

  const clearFilters = () => {
    setFilters({ document_type: '', jurisdiction: '', year_from: '', year_to: '' });
  };

  const hasFilters = Object.values(filters).some(Boolean);

  return (
    <div>
      {/* Search Form */}
      <form onSubmit={handleSubmit} className="search-bar" style={{ position: 'relative', width: '100%', display: 'flex' }}>
        <input
          className="search-input"
          style={{ width: '100%', boxSizing: 'border-box' }}
          type="text"
          placeholder={placeholder || "Ask a legal research question..."}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={loading}
        />
        <div style={{
          position: 'absolute',
          right: 8,
          top: '50%',
          transform: 'translateY(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}>
          {/* Filter toggle */}
          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            style={{
              width: 44, height: 44, borderRadius: 12,
              background: showFilters ? 'rgba(212, 175, 55, 0.15)' : 'rgba(30, 37, 56, 0.6)',
              border: showFilters ? '1px solid rgba(212, 175, 55, 0.4)' : '1px solid rgba(255, 255, 255, 0.05)',
              color: showFilters ? '#f5d77f' : '#47557a',
              cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
              boxShadow: showFilters ? '0 0 15px rgba(212, 175, 55, 0.1)' : 'none',
            }}
            onMouseEnter={(e) => {
              if(!showFilters) e.currentTarget.style.borderColor = 'rgba(212, 175, 55, 0.2)';
            }}
            onMouseLeave={(e) => {
              if(!showFilters) e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.05)';
            }}
          >
            <SlidersHorizontal size={16} />
          </button>
          {/* Submit */}
          <button
            type="submit"
            disabled={!query.trim() || loading}
            className="btn-gold-glow btn-primary"
            style={{
              width: 44, height: 44, padding: 0, borderRadius: 12,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            {loading ? <span className="spinner" style={{ width: 18, height: 18, borderTopColor: '#02040a' }} /> : <Search size={18} />}
          </button>
        </div>
      </form>

      {/* Filters */}
      {showFilters && (
        <div className="glass-card animate-fade-in-up" style={{
          padding: '20px', marginTop: 14,
          background: 'rgba(10, 13, 26, 0.7)',
          border: '1px solid rgba(255, 255, 255, 0.05)',
        }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14,
          }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#f1f5f9', letterSpacing: '0.02em' }}>Advanced Filters</span>
            {hasFilters && (
              <button
                onClick={clearFilters}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  fontSize: 12, color: '#f87171', display: 'flex', alignItems: 'center', gap: 4,
                  fontWeight: 600,
                }}
              >
                <X size={12} /> Clear all
              </button>
            )}
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 14,
          }}>
            {/* Document Type */}
            <div>
              <label style={{ fontSize: 11, color: '#47557a', marginBottom: 6, display: 'block', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Document Type</label>
              <select
                className="input-field"
                value={filters.document_type}
                onChange={(e) => setFilters({ ...filters, document_type: e.target.value })}
                style={{ padding: '10px 12px' }}
              >
                <option value="">All types</option>
                {DOCUMENT_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            {/* Jurisdiction */}
            <div>
              <label style={{ fontSize: 11, color: '#47557a', marginBottom: 6, display: 'block', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Jurisdiction</label>
              <select
                className="input-field"
                value={filters.jurisdiction}
                onChange={(e) => setFilters({ ...filters, jurisdiction: e.target.value })}
                style={{ padding: '10px 12px' }}
              >
                <option value="">All jurisdictions</option>
                {JURISDICTIONS.map((j) => (
                  <option key={j} value={j}>{j}</option>
                ))}
              </select>
            </div>
            {/* Year Range */}
            <div>
              <label style={{ fontSize: 11, color: '#47557a', marginBottom: 6, display: 'block', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Year From</label>
              <input
                className="input-field"
                type="number"
                placeholder="e.g. 2015"
                value={filters.year_from}
                onChange={(e) => setFilters({ ...filters, year_from: e.target.value })}
                style={{ padding: '10px 12px' }}
                min={1900} max={2030}
              />
            </div>
            <div>
              <label style={{ fontSize: 11, color: '#47557a', marginBottom: 6, display: 'block', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Year To</label>
              <input
                className="input-field"
                type="number"
                placeholder="e.g. 2025"
                value={filters.year_to}
                onChange={(e) => setFilters({ ...filters, year_to: e.target.value })}
                style={{ padding: '10px 12px' }}
                min={1900} max={2030}
              />
            </div>
          </div>
        </div>
      )}

      {/* Suggested Queries */}
      {!loading && (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '12px',
          marginTop: 24,
          justifyContent: 'center',
        }}>
          {SUGGESTED_QUERIES.map((s, i) => {
            const chipIcons = [Scale, DollarSign, Handshake, FileText, ClipboardList, RefreshCw];
            const Icon = chipIcons[i % chipIcons.length];
            return (
              <button
                key={i}
                onClick={() => handleSuggestion(s)}
                className="suggestion-chip"
                style={{
                  borderLeft: 'none', // let nth-child styles handle left border
                }}
              >
                <Icon size={14} className="chip-icon" style={{ flexShrink: 0 }} />
                <span>{s.title}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
