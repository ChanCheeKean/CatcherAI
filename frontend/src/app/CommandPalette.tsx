import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

const COMMANDS = [
  { label: 'Mission control', path: '/' },
  { label: 'Memory explorer', path: '/memory' },
  { label: 'Graph Lab', path: '/graph' },
  { label: 'Evaluation coverage', path: '/evaluation' },
]

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const navigate = useNavigate()
  useEffect(() => { const handler = (event: KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setOpen((value) => !value) } if (event.key === 'Escape') setOpen(false) }; window.addEventListener('keydown', handler); return () => window.removeEventListener('keydown', handler) }, [])
  const commands = useMemo(() => COMMANDS.filter((item) => item.label.toLowerCase().includes(query.toLowerCase())), [query])
  if (!open) return <button type="button" onClick={() => setOpen(true)} className="rounded border border-border px-2 py-1 font-mono text-xs text-ink-faint">⌘K</button>
  return <div role="dialog" aria-modal="true" aria-label="Command palette" className="fixed inset-0 z-50 flex items-start justify-center bg-canvas/80 px-4 pt-[15vh]" onMouseDown={() => setOpen(false)}><div className="w-full max-w-lg rounded-xl border border-border-strong bg-surface-1 p-2 shadow-2xl" onMouseDown={(event) => event.stopPropagation()}><input autoFocus aria-label="Search commands" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Go to…" className="w-full rounded-md border border-border bg-canvas px-3 py-2 text-sm text-ink" /><ul className="mt-2">{commands.map((item) => <li key={item.path}><button type="button" onClick={() => { navigate(item.path); setOpen(false); setQuery('') }} className="w-full rounded-md px-3 py-2 text-left text-sm text-ink-muted hover:bg-surface-3 hover:text-ink">{item.label}</button></li>)}</ul></div></div>
}
