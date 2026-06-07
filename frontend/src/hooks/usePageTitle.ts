import { useEffect } from 'react'

const BASE = 'Suburb Intelligence'

/**
 * Sets document.title to "<title> — Suburb Intelligence".
 * Pass null/undefined to reset to just the base title.
 */
export function usePageTitle(title?: string | null) {
  useEffect(() => {
    document.title = title ? `${title} — ${BASE}` : BASE
    return () => { document.title = BASE }
  }, [title])
}
