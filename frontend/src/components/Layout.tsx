import { ReactNode } from 'react'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#282c34',
      color: '#f8f8f2',
      padding: '20px'
    }}>
      <nav style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '40px',
        paddingBottom: '20px',
        borderBottom: '1px solid #4b566a'
      }}>
        <h1 style={{ margin: 0, fontSize: '28px', color: '#f8f8f2' }}>
          Suburb Intelligence
        </h1>
        <nav aria-label="Main Navigation">
          <a href="/" style={linkStyle}>Search</a>
          <a href="/rankings" style={linkStyle}>Rankings</a>
        </nav>
      </nav>
      
      <main style={{ maxWidth: '1200px', margin: '0 auto' }}>
        {children}
      </main>
    </div>
  )
}

const linkStyle = {
  color: '#d1d5da',
  textDecoration: 'none',
  padding: '10px 20px',
  borderRadius: '6px',
  transition: 'all 0.2s'
}
