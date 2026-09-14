import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import { EntityGraph } from './EntityGraph'

export function GraphLabPage() {
  const [caseId, setCaseId] = useState('DSP-2026-90011')
  const [depth, setDepth] = useState(2)
  const graph = useQuery({ queryKey: ['case-graph', caseId, depth], queryFn: () => api.getCaseGraph(caseId, depth), enabled: Boolean(caseId) })
  return <div className="p-6"><div className="mb-4 flex flex-wrap items-end justify-between gap-3"><div><h1 className="text-lg font-bold text-ink">Graph Lab</h1><p className="text-sm text-ink-muted">Bounded operational entity neighborhoods; no inferred nodes.</p></div><div className="flex gap-2"><label className="text-xs text-ink-faint">Case ID<input value={caseId} onChange={(event) => setCaseId(event.target.value)} className="ml-2 rounded border border-border bg-surface-1 px-2 py-1 font-mono text-ink" /></label><label className="text-xs text-ink-faint">Depth<select value={depth} onChange={(event) => setDepth(Number(event.target.value))} className="ml-2 rounded border border-border bg-surface-1 px-2 py-1 text-ink"><option>1</option><option>2</option><option>3</option></select></label></div></div>{graph.isLoading && <p className="text-sm text-ink-faint">Loading graph…</p>}{graph.isError && <p className="text-sm text-rose">This case is not available in the operational graph.</p>}{graph.data && <><p className="mb-2 font-mono text-xs text-ink-faint">{graph.data.nodes.length} nodes · {graph.data.edges.length} persisted edges</p><EntityGraph graph={graph.data} /></>}</div>
}
