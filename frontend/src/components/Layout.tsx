import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const { pathname } = useLocation()

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f8fafc', fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>
      {/* Sticky top nav */}
      <header style={{
        backgroundColor: '#ffffff',
        borderBottom: '1px solid #e2e8f0',
        position: 'sticky',
        top: 0,
        zIndex: 20,
      }}>
        <div style={{
          maxWidth: '1200px',
          margin: '0 auto',
          padding: '0 24px',
          height: '64px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          {/* Logo + nav */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
            <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '9px', textDecoration: 'none' }}>
              <div style={{
                width: '32px',
                height: '32px',
                backgroundColor: '#6366f1',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 1px 3px rgba(99,102,241,0.35)',
                flexShrink: 0,
              }}>
                {/* map-pin icon */}
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 10c0 6-8 13-8 13s-8-7-8-13a8 8 0 0 1 16 0Z"/>
                  <circle cx="12" cy="10" r="3"/>
                </svg>
              </div>
              <span style={{ fontSize: '16px', fontWeight: 700, color: '#0f172a', letterSpacing: '-0.02em' }}>
                Suburb Intel
              </span>
            </Link>

            <nav style={{ display: 'flex', gap: '2px' }} aria-label="Main Navigation">
              <NavLink to="/" active={pathname === '/'}>Search</NavLink>
              <NavLink to="/rankings" active={pathname === '/rankings'}>Rankings</NavLink>
            </nav>
          </div>
        </div>
      </header>

      {/* Page content */}
      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '32px 24px' }}>
        {children}
      </main>
    </div>
  )
}

function NavLink({ to, active, children }: { to: string; active: boolean; children: ReactNode }) {
  return (
    <Link
      to={to}
      style={{
        padding: '6px 12px',
        fontSize: '14px',
        fontWeight: 500,
        borderRadius: '6px',
        textDecoration: 'none',
        color: active ? '#6366f1' : '#64748b',
        backgroundColor: active ? '#eef2ff' : 'transparent',
        transition: 'color 0.15s, background-color 0.15s',
      }}
    >
      {children}
    </Link>
  )
}
