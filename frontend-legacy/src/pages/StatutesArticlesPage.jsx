import { useState, useEffect } from 'react';
import { getReferenceData } from '../api/client';
import { FileText, AlertTriangle } from 'lucide-react';
import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="glass-card" style={{ padding: 40, margin: '40px auto', maxWidth: 800, textAlign: 'center', borderColor: 'rgba(239, 68, 68, 0.3)' }}>
          <AlertTriangle size={48} color="#f87171" style={{ margin: '0 auto 16px' }} />
          <h2 style={{ color: '#f87171', fontSize: 24, marginBottom: 12 }}>Something went wrong</h2>
          <p style={{ color: '#cbd5e1', marginBottom: 24 }}>The Statutes & Articles page crashed while rendering.</p>
          <pre style={{ textAlign: 'left', background: 'rgba(0,0,0,0.2)', padding: 16, borderRadius: 8, color: '#f87171', overflowX: 'auto', fontSize: 12 }}>
            {this.state.error?.toString()}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

function StatutesArticlesContent() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const result = await getReferenceData();
        setData(result);
      } catch (err) {
        setError(err.response?.data?.detail || err.message || 'Failed to load reference data');
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <div className="spinner" style={{ width: 40, height: 40, margin: '0 auto 20px' }} />
        <p style={{ color: '#94a3b8', fontSize: 15 }}>Loading reference data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card" style={{ padding: 40, margin: 40, textAlign: 'center', borderColor: 'rgba(239, 68, 68, 0.3)' }}>
        <AlertTriangle size={40} color="#f87171" style={{ margin: '0 auto 12px' }} />
        <h3 style={{ color: '#f87171', fontSize: 20, marginBottom: 8 }}>Failed to Load</h3>
        <p style={{ color: '#cbd5e1' }}>{error}</p>
      </div>
    );
  }

  if (!data || (data.constitution?.length === 0 && data.criminal_law?.length === 0 && data.landmark_cases?.length === 0)) {
    return (
      <div className="glass-card" style={{ padding: 40, margin: 40, textAlign: 'center' }}>
        <FileText size={48} color="#334155" style={{ margin: '0 auto 16px' }} />
        <h3 style={{ color: '#f1f5f9', fontSize: 20, marginBottom: 8 }}>No Data Available</h3>
        <p style={{ color: '#64748b' }}>Reference datasets are currently empty.</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gap: 32 }}>
      {/* Constitution */}
      {data.constitution?.length > 0 && (
        <section>
          <h2 style={{ fontSize: 22, color: '#f5d77f', marginBottom: 16, borderBottom: '1px solid rgba(212, 175, 55, 0.2)', paddingBottom: 8 }}>Constitution</h2>
          <div style={{ display: 'grid', gap: 12 }}>
            {data.constitution.map((item, i) => (
              <div key={i} className="glass-card" style={{ padding: 16 }}>
                <h4 style={{ color: '#f1f5f9', fontSize: 16, marginBottom: 8 }}>{item.title || item.article || 'Article'}</h4>
                <p style={{ color: '#cbd5e1', fontSize: 14 }}>{item.description || item.content}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Criminal Law */}
      {data.criminal_law?.length > 0 && (
        <section>
          <h2 style={{ fontSize: 22, color: '#f5d77f', marginBottom: 16, borderBottom: '1px solid rgba(212, 175, 55, 0.2)', paddingBottom: 8 }}>Criminal Law Mapping</h2>
          <div style={{ display: 'grid', gap: 12 }}>
            {data.criminal_law.map((item, i) => (
              <div key={i} className="glass-card" style={{ padding: 16 }}>
                <h4 style={{ color: '#f1f5f9', fontSize: 16, marginBottom: 8 }}>{item.title || item.offense || item.section || 'Law'}</h4>
                <p style={{ color: '#cbd5e1', fontSize: 14 }}>{item.description || item.content}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Landmark Cases */}
      {data.landmark_cases?.length > 0 && (
        <section>
          <h2 style={{ fontSize: 22, color: '#f5d77f', marginBottom: 16, borderBottom: '1px solid rgba(212, 175, 55, 0.2)', paddingBottom: 8 }}>Landmark Cases</h2>
          <div style={{ display: 'grid', gap: 12 }}>
            {data.landmark_cases.map((item, i) => (
              <div key={i} className="glass-card" style={{ padding: 16 }}>
                <h4 style={{ color: '#f1f5f9', fontSize: 16, marginBottom: 8 }}>{item.title || item.case_name || 'Case'}</h4>
                <p style={{ color: '#cbd5e1', fontSize: 14 }}>{item.description || item.holding || item.content}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default function StatutesArticlesPage() {
  return (
    <div className="animated-bg" style={{ flex: 1 }}>
      <div style={{ maxWidth: 1000, margin: '0 auto', padding: '32px 24px 60px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
          <div style={{ width: 44, height: 44, borderRadius: 12, background: 'rgba(212, 175, 55, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <FileText size={24} color="#d4a44c" />
          </div>
          <div>
            <h1 style={{ fontSize: 28, fontWeight: 800, color: '#f1f5f9', letterSpacing: '-0.02em' }}>Statutes & Articles</h1>
            <p style={{ fontSize: 14, color: '#94a3b8', marginTop: 4 }}>Reference datasets for Indian Law</p>
          </div>
        </div>
        
        <ErrorBoundary>
          <StatutesArticlesContent />
        </ErrorBoundary>
      </div>
    </div>
  );
}
