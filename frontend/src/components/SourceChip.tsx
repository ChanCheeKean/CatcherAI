import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'

export function SourceChip({ sourceId }: { sourceId: string }) {
  const [open, setOpen] = useState(false)
  const source = useQuery({ queryKey: ['source', sourceId], queryFn: () => api.getSource(sourceId), enabled: open })
  return <span className="relative inline-block"><button type="button" onClick={() => setOpen((value) => !value)} className="rounded bg-surface-1 px-1.5 py-0.5 font-mono text-ink-faint hover:text-cyan">{sourceId}</button>{open && <span className="absolute right-0 top-6 z-30 block w-80 rounded-lg border border-border bg-surface-2 p-3 shadow-2xl"><span className="block text-xs font-semibold text-ink">{source.data?.title ?? 'Resolving source…'}</span>{source.isError && <span className="mt-1 block text-xs text-rose">Source is not available through the allowlisted resolver.</span>}{source.data && <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap font-mono text-[10px] text-ink-muted">{JSON.stringify(source.data.data, null, 2)}</pre>}</span>}</span>
}
