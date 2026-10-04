import { Scale, AlertTriangle } from 'lucide-react';

export default function Footer() {
  return (
    <footer style={{
      borderTop: '1px solid rgba(51, 65, 85, 0.3)',
      padding: '24px',
      textAlign: 'center',
      marginTop: 'auto',
    }}>
      <div style={{
        maxWidth: 1200,
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        color: '#475569',
        fontSize: 13,
      }}>
        <Scale size={14} />
        <span>VIDHIVEDA — AI-Powered Legal Research Engine</span>
        <span style={{ margin: '0 8px' }}>•</span>
        <span>SIH1701 · Department of Justice</span>
      </div>
      <div style={{
        marginTop: 10,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
        color: '#92400e',
        fontSize: 11,
        background: 'rgba(245, 158, 11, 0.06)',
        padding: '6px 16px',
        borderRadius: 8,
        maxWidth: 600,
        margin: '10px auto 0',
      }}>
        <AlertTriangle size={12} />
        <span>Research support only — not legal advice. All outputs must be independently verified.</span>
      </div>
    </footer>
  );
}
