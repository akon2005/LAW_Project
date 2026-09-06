import { Link, useLocation } from 'react-router-dom';
import { Scale, Search, FileText, Info } from 'lucide-react';

export default function Header() {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Research', icon: Search },
    { path: '/statutes', label: 'Statutes & Articles', icon: FileText },
    { path: '/documents', label: 'Documents', icon: FileText },
    { path: '/about', label: 'About', icon: Info },
  ];

  return (
    <header className="glass-card" style={{
      position: 'sticky',
      top: 0,
      zIndex: 50,
      borderRadius: 0,
      borderTop: 'none',
      borderLeft: 'none',
      borderRight: 'none',
      borderBottom: '1px solid rgba(212, 175, 55, 0.08)',
      boxShadow: '0 4px 30px rgba(0, 0, 0, 0.5), inset 0 -1px 0 rgba(255,255,255,0.02)',
    }}>
      <div style={{
        maxWidth: 1000,
        margin: '0 auto',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 64,
      }}>
        {/* Logo */}
        <Link to="/" style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          textDecoration: 'none',
          color: 'inherit',
        }}>
          <div style={{
            width: 38,
            height: 38,
            borderRadius: 10,
            background: 'linear-gradient(135deg, #d4af37, #b08d25)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 15px rgba(212, 175, 55, 0.45), 0 4px 8px rgba(0, 0, 0, 0.3)',
          }}>
            <Scale size={20} color="#02040a" />
          </div>
          <div>
            <div className="font-display" style={{
              fontSize: 22,
              fontWeight: 850,
              letterSpacing: '-0.04em',
            }}>
              <span className="headline-highlight">VIDHIVEDA</span>
            </div>
            <div style={{
              fontSize: 8.5,
              color: '#94a3b8',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              marginTop: -1,
              fontWeight: 800,
            }}>
              AI LEGAL RESEARCH · VIDHIVEDA
            </div>
          </div>
        </Link>

        {/* Navigation */}
        <nav style={{ display: 'flex', gap: 4 }}>
          {navItems.map(({ path, label, icon: Icon }) => {
            const isActive = location.pathname === path;
            return (
              <Link
                key={path}
                to={path}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '8px 16px',
                  borderRadius: 8,
                  fontSize: 14,
                  fontWeight: isActive ? 600 : 500,
                  color: isActive ? '#f5d77f' : '#94a3b8',
                  background: isActive ? 'rgba(212, 175, 55, 0.08)' : 'transparent',
                  border: isActive ? '1px solid rgba(212, 175, 55, 0.15)' : '1px solid transparent',
                  textDecoration: 'none',
                  transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                }}
              >
                <Icon size={16} />
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
