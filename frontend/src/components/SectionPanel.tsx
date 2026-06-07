import { ReactNode } from 'react'

interface SectionPanelProps {
  title: string
  subtitle?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}

export default function SectionPanel({ title, subtitle, action, children, className = '' }: SectionPanelProps) {
  return (
    <section
      className={className}
      style={{
        backgroundColor: '#151b27',
        border: '1px solid #28334a',
        borderRadius: '12px',
        padding: '28px',
        boxShadow: '0 2px 12px rgba(0,0,0,0.45)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: subtitle ? '4px' : '20px' }}>
        <h2 style={{ margin: 0, fontSize: '17px', fontWeight: 700, color: '#cdd8e8', letterSpacing: '-0.01em' }}>
          {title}
        </h2>
        {action && <div>{action}</div>}
      </div>
      {subtitle && (
        <p style={{ margin: '0 0 20px', fontSize: '13px', color: '#6b7fa0' }}>{subtitle}</p>
      )}
      {children}
    </section>
  )
}
