import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

interface LayoutProps {
  children: ReactNode
}

const NAV_LINKS = [
  { path: '/',         label: 'Search'   },
  { path: '/rankings', label: 'Rankings' },
  { path: '/map',      label: 'Map'      },
  { path: '/compare',  label: 'Compare'  },
]

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#0d1117', color: '#cdd8e8' }}>
      {/* Top nav bar */}
      <header style={{
        position: 'sticky',
        top: 0,
        zIndex: 50,
        backgroundColor: 'rgba(13,17,23,0.88)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid #28334a',
      }}>
        <div style={{
          maxWidth: '1280px',
          margin: '0 auto',
          padding: '0 24px',
          height: '60px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          {/* Wordmark */}
          <Link to="/" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{
              width: '28px', height: '28px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #2dd4bf 0%, #38bdf8 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '14px', fontWeight: 800, color: '#0d1117', flexShrink: 0,
            }}>
              SI
            </span>
            <span style={{ fontSize: '16px', fontWeight: 700, color: '#cdd8e8', letterSpacing: '-0.02em' }}>
              Suburb Intelligence
            </span>
          </Link>

          {/* Nav links */}
          <nav aria-label="Main Navigation" style={{ display: 'flex', gap: '2px' }}>
            {NAV_LINKS.map(({ path, label }) => {
              const active = location.pathname === path
              return (
                <Link
                  key={path}
                  to={path}
                  style={{
                    color: active ? '#2dd4bf' : '#9aafc8',
                    textDecoration: 'none',
                    padding: '6px 14px',
                    borderRadius: '8px',
                    fontSize: '14px',
                    fontWeight: active ? 600 : 400,
                    backgroundColor: active ? 'rgba(45,212,191,0.1)' : 'transparent',
                    transition: 'all 0.15s',
                  }}
                >
                  {label}
                </Link>
              )
            })}
          </nav>
        </div>
      </header>

      {/* Page content */}
      <main style={{ maxWidth: '1280px', margin: '0 auto', padding: '40px 24px' }}>
        {children}
      </main>
    </div>
  )
}
