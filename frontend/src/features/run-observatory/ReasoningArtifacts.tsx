import type { RunProjection } from '../../projections/runProjection'
import { useInspector } from '../../app/InspectorContext'

export function ReasoningArtifacts({ projection }: { projection: RunProjection }) {
  const { select } = useInspector()
  const artifacts = [...projection.plans, ...projection.hypotheses, ...projection.verifier, ...projection.panel].sort((a, b) => a.seq - b.seq)
  return <div className="grid gap-3 p-4 md:grid-cols-2">
    <div className="rounded-lg border border-border bg-surface-2 p-3"><h3 className="text-xs font-semibold uppercase tracking-wider text-violet">Plans & hypotheses</h3><div className="mt-2 space-y-2">{artifacts.filter((event) => ['plan_created','plan_updated','todo_updated','hypothesis_updated','contradiction_detected'].includes(event.type)).map((event) => <button key={event.event_id} onClick={() => select(event)} className="block w-full rounded border border-border bg-surface-1 p-2 text-left"><span className="font-mono text-[10px] text-ink-faint">v{event.seq} · {event.type}</span><p className="text-xs text-ink">{event.summary}</p>{typeof event.payload.diff === 'object' && <pre className="mt-1 max-h-20 overflow-auto font-mono text-[10px] text-ink-muted">{JSON.stringify(event.payload.diff, null, 2)}</pre>}</button>)}</div></div>
    <div className="rounded-lg border border-border bg-surface-2 p-3"><h3 className="text-xs font-semibold uppercase tracking-wider text-emerald">Verification & panel</h3><div className="mt-2 space-y-2">{artifacts.filter((event) => ['verifier_check','panel_position','adjudication'].includes(event.type)).map((event) => <button key={event.event_id} onClick={() => select(event)} className="flex w-full items-start justify-between gap-2 rounded border border-border bg-surface-1 p-2 text-left"><span className="text-xs text-ink">{event.summary}</span><span className={`font-mono text-[10px] ${event.payload.passed === false ? 'text-rose' : 'text-emerald'}`}>{event.payload.passed === false ? 'FAIL' : event.type === 'verifier_check' ? 'PASS' : 'RECORDED'}</span></button>)}</div></div>
  </div>
}
