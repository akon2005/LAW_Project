import { useState, useEffect, useCallback } from 'react';
import { FileText, Filter, X, ChevronLeft, ChevronRight, Search, AlertTriangle } from 'lucide-react';
import DocumentCard from '../components/Results/DocumentCard';
import { browseDocuments, getFilterOptions } from '../api/client';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pagination, setPagination] = useState({ page: 1, total: 0, totalPages: 1, limit: 10 });
  const [showFilters, setShowFilters] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [filters, setFilters] = useState({
    document_type: '',
    jurisdiction: '',
    court: '',
    year_from: '',
    year_to: '',
  });

  // Dynamic filter options from the backend
  const [filterOptions, setFilterOptions] = useState({
    courts: [],
    legal_domains: [],
    record_types: [],
    year_range: { min: 1900, max: 2026 },
  });

  // Fetch filter options once on mount
  useEffect(() => {
    async function loadFilterOptions() {
      try {
        const opts = await getFilterOptions();
        setFilterOptions(opts);
      } catch (err) {
        console.error('Failed to load filter options:', err);
      }
    }
    loadFilterOptions();
  }, []);

  const fetchDocuments = useCallback(async (page = 1) => {
    setLoading(true);
    setError(null);
    try {
      const params = { page, limit: 10 };
      if (filters.document_type) params.document_type = filters.document_type;
      if (filters.jurisdiction) params.jurisdiction = filters.jurisdiction;
      if (filters.court) params.court = filters.court;
      if (filters.year_from) params.year_from = parseInt(filters.year_from);
      if (filters.year_to) params.year_to = parseInt(filters.year_to);
      if (searchText.trim()) params.query = searchText.trim();

      const data = await browseDocuments(params);
      setDocuments(data.documents || []);
      setPagination({
        page: data.page,
        total: data.total,
        totalPages: data.total_pages,
        limit: data.limit,
      });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load documents');
    } finally {
      setLoading(false);
    }
  }, [filters, searchText]);

  useEffect(() => {
    fetchDocuments(1);
  }, [fetchDocuments]);

  const handleSearch = (e) => {
    e.preventDefault();
    fetchDocuments(1);
  };

  const clearFilters = () => {
    setFilters({ document_type: '', jurisdiction: '', court: '', year_from: '', year_to: '' });
    setSearchText('');
  };

  const hasFilters = Object.values(filters).some(Boolean) || searchText;

  // Build a human-readable description of active filters for the empty state
  const activeFilterDesc = () => {
    const parts = [];
    if (filters.document_type) parts.push(`type "${filters.document_type}"`);
    if (filters.court) parts.push(`court "${filters.court}"`);
    if (filters.year_from || filters.year_to) {
      const from = filters.year_from || filterOptions.year_range.min;
      const to = filters.year_to || filterOptions.year_range.max;
      parts.push(`years ${from}–${to}`);
    }
    if (searchText) parts.push(`search "${searchText}"`);
    return parts.length > 0 ? parts.join(', ') : null;
  };

  return (
    <div className="animated-bg" style={{ flex: 1 }}>
      <div style={{ maxWidth: 1000, margin: '0 auto', padding: '32px 24px 60px' }}>
        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <FileText size={24} color="#d4a44c" />
            <h1 style={{ fontSize: 28, fontWeight: 800, color: '#f1f5f9' }}>Legal Documents</h1>
          </div>
          <p style={{ fontSize: 14, color: '#64748b' }}>
            Browse and search across case laws, statutes, notifications, and regulations in the knowledge base.
          </p>
        </div>

        {/* Search + Filter toggle */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          <form onSubmit={handleSearch} style={{ flex: 1, position: 'relative' }}>
            <input
              className="input-field"
              type="text"
              placeholder="Search in document text..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              style={{ paddingRight: 44 }}
            />
            <button type="submit" style={{
              position: 'absolute', right: 4, top: '50%', transform: 'translateY(-50%)',
              width: 36, height: 36, borderRadius: 8, background: 'rgba(212,164,76,0.15)',
              border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Search size={14} color="#d4a44c" />
            </button>
          </form>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="btn-secondary"
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: showFilters ? 'rgba(212,164,76,0.12)' : undefined,
              borderColor: showFilters ? 'rgba(212,164,76,0.3)' : undefined,
              color: showFilters ? '#d4a44c' : undefined,
            }}
          >
            <Filter size={14} />
            Filters
          </button>
        </div>

        {/* Filters — dynamic options from backend */}
        {showFilters && (
          <div className="glass-card animate-fade-in-up" style={{ padding: 16, marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#94a3b8' }}>Filter Documents</span>
              {hasFilters && (
                <button onClick={clearFilters} style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  fontSize: 12, color: '#f87171', display: 'flex', alignItems: 'center', gap: 4,
                }}>
                  <X size={12} /> Clear all
                </button>
              )}
            </div>
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12,
            }}>
              {/* Legal Domain (Type) */}
              <div>
                <label style={{ fontSize: 11, color: '#64748b', marginBottom: 4, display: 'block' }}>Legal Domain</label>
                <select className="input-field" value={filters.document_type}
                  onChange={(e) => setFilters({ ...filters, document_type: e.target.value })}
                  style={{ padding: '8px 12px' }}>
                  <option value="">All domains</option>
                  {filterOptions.legal_domains.map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>

              {/* Court — from DB */}
              <div>
                <label style={{ fontSize: 11, color: '#64748b', marginBottom: 4, display: 'block' }}>Court</label>
                <select className="input-field" value={filters.court}
                  onChange={(e) => setFilters({ ...filters, court: e.target.value })}
                  style={{ padding: '8px 12px' }}>
                  <option value="">All courts</option>
                  {filterOptions.courts.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>

              {/* Year From */}
              <div>
                <label style={{ fontSize: 11, color: '#64748b', marginBottom: 4, display: 'block' }}>Year From</label>
                <input className="input-field" type="number"
                  placeholder={String(filterOptions.year_range.min)}
                  value={filters.year_from}
                  onChange={(e) => setFilters({ ...filters, year_from: e.target.value })}
                  style={{ padding: '8px 12px' }}
                  min={filterOptions.year_range.min}
                  max={filterOptions.year_range.max} />
              </div>

              {/* Year To */}
              <div>
                <label style={{ fontSize: 11, color: '#64748b', marginBottom: 4, display: 'block' }}>Year To</label>
                <input className="input-field" type="number"
                  placeholder={String(filterOptions.year_range.max)}
                  value={filters.year_to}
                  onChange={(e) => setFilters({ ...filters, year_to: e.target.value })}
                  style={{ padding: '8px 12px' }}
                  min={filterOptions.year_range.min}
                  max={filterOptions.year_range.max} />
              </div>
            </div>
          </div>
        )}

        {/* Results count */}
        <div style={{ marginBottom: 16, fontSize: 13, color: '#64748b' }}>
          Showing {documents.length} of {pagination.total} documents
          (page {pagination.page} of {pagination.totalPages})
        </div>

        {/* Loading */}
        {loading && (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <div className="spinner" style={{ width: 32, height: 32, margin: '0 auto 12px' }} />
            <p style={{ fontSize: 13, color: '#94a3b8' }}>Loading documents...</p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="glass-card" style={{
            padding: 20, borderColor: 'rgba(239, 68, 68, 0.3)', textAlign: 'center',
          }}>
            <span style={{ fontSize: 18 }}>⚠️</span>
            <p style={{ color: '#f87171', marginTop: 8 }}>{error}</p>
          </div>
        )}

        {/* Documents list */}
        {!loading && !error && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {documents.length === 0 ? (
              <div className="glass-card" style={{ padding: 40, textAlign: 'center' }}>
                <AlertTriangle size={40} color="#f5d77f" style={{ margin: '0 auto 12px', display: 'block' }} />
                <p style={{ color: '#f1f5f9', fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
                  No documents found
                </p>
                {activeFilterDesc() ? (
                  <p style={{ color: '#64748b', fontSize: 13, lineHeight: 1.6 }}>
                    No results for {activeFilterDesc()}.
                    Try broadening your filters or clearing them to see all {pagination.total || 'available'} documents.
                  </p>
                ) : (
                  <p style={{ color: '#64748b', fontSize: 13 }}>
                    No documents are currently available in the database.
                  </p>
                )}
                {hasFilters && (
                  <button onClick={clearFilters} className="btn-secondary" style={{ marginTop: 16 }}>
                    <X size={12} /> Clear all filters
                  </button>
                )}
              </div>
            ) : (
              documents.map((doc, i) => (
                <DocumentCard key={doc.doc_id} document={doc} index={i} />
              ))
            )}
          </div>
        )}

        {/* Pagination */}
        {pagination.totalPages > 1 && (
          <div style={{
            display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, marginTop: 24,
          }}>
            <button
              className="btn-secondary"
              disabled={pagination.page <= 1}
              onClick={() => fetchDocuments(pagination.page - 1)}
              style={{ display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <ChevronLeft size={14} /> Previous
            </button>
            <span style={{ fontSize: 13, color: '#94a3b8' }}>
              Page {pagination.page} of {pagination.totalPages}
            </span>
            <button
              className="btn-secondary"
              disabled={pagination.page >= pagination.totalPages}
              onClick={() => fetchDocuments(pagination.page + 1)}
              style={{ display: 'flex', alignItems: 'center', gap: 4 }}
            >
              Next <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
