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
    <div style={{ minHeight: '100vh', backgroundColor: '#282c34', color: '#f8f8f2', padding: '20px' }}>
      <nav style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: '40px', paddingBottom: '20px', borderBottom: '1px solid #4b566a',
      }}>
        <Link to="/" style={{ textDecoration: 'none' }}>
          <h1 style={{ margin: 0, fontSize: '24px', color: '#f8f8f2', fontWeight: 800 }}>
            Suburb Intelligence
          </h1>
        </Link>
        <nav aria-label="Main Navigation" style={{ display: 'flex', gap: '4px' }}>
          {NAV_LINKS.map(({ path, label }) => {
            const active = location.pathname === path
            return (
              <Link key={path} to={path} style={{
                color: active ? '#282c34' : '#d1d5da',
                textDecoration: 'none',
                padding: '8px 18px',
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: active ? 700 : 400,
                backgroundColor: active ? '#f8f8f2' : 'transparent',
                transition: 'all 0.15s',
              }}>
                {label}
              </Link>
            )
          })}
        </nav>
      </nav>

      <main style={{ maxWidth: '1200px', margin: '0 auto' }}>
        {children}
      </main>
    </div>
  )
}
