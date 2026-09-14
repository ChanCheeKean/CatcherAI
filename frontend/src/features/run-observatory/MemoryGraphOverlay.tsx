import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { useInspector } from '../../app/InspectorContext'

export function MemoryGraphOverlay({ runId }: { runId: string }) {
  const { select } = useInspector()
  const memory = useQuery({ queryKey: ['run-memory', runId], queryFn: () => api.getRunMemory(runId) })
  const graph = useQuery({ queryKey: ['run-graph', runId], queryFn: () => api.getRunGraph(runId) })
  const operations = [...(memory.data?.operations ?? []), ...(graph.data?.operations ?? [])].sort((a, b) => a.seq - b.seq)
  return <div className="p-4"><div className="mb-3 flex flex-wrap gap-2">{Object.entries(memory.data?.groups ?? {}).map(([store, count]) => <span key={store} className="rounded bg-surface-2 px-2 py-1 font-mono text-[10px] text-ink-muted">{store} · {count}</span>)}{graph.data && <span className="rounded bg-cyan/10 px-2 py-1 font-mono text-[10px] text-cyan">graph · {graph.data.operations.length}</span>}</div><div className="grid gap-2 md:grid-cols-2">{operations.map((event) => <button type="button" key={event.event_id} onClick={() => select(event)} className="rounded-lg border border-border bg-surface-2 p-3 text-left"><span className="font-mono text-[10px] text-ink-faint">seq {event.seq} · {event.type}</span><p className="mt-1 text-xs text-ink">{event.summary}</p><p className="mt-1 truncate font-mono text-[10px] text-ink-faint">{event.refs.join(', ')}</p></button>)}</div>{operations.length === 0 && !memory.isLoading && !graph.isLoading && <p className="text-sm text-ink-faint">No memory or graph operations were recorded.</p>}</div>
}
