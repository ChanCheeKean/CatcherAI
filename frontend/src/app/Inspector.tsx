import { useInspector } from './InspectorContext'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

function text(value: unknown): string { return typeof value === 'string' ? value : JSON.stringify(value) }

function highlights(type: string, payload: Record<string, unknown>): Array<[string, unknown]> {
  const keys = type === 'route_decision' ? ['route_id', 'depth', 'agents', 'skills', 'budget']
    : type.startsWith('tool_') ? ['tool', 'call_id', 'rationale', 'arguments', 'status', 'duration_ms', 'source_ids']
      : type.startsWith('llm_') ? ['call_id', 'model', 'role', 'attempt', 'stop_reason', 'request_blob', 'response_blob']
        : type.startsWith('subagent_') ? ['subagent', 'subagent_id', 'task_id', 'role', 'status', 'result']
          : type === 'skill_loaded' ? ['skill', 'version', 'why', 'content_blob']
            : type.startsWith('memory_') || type.startsWith('graph_') ? ['store', 'operation', 'target_id', 'result_ids', 'used_ids', 'discarded', 'before', 'after']
              : type === 'computation' ? ['helper', 'inputs', 'output', 'status', 'runtime_ms']
                : type.startsWith('wait_') ? ['wait_id', 'reason', 'awaited_ref', 'available_at', 'resume_at']
                  : type === 'clock_advanced' ? ['from', 'to', 'reason']
                    : type === 'verifier_check' ? ['check', 'name', 'passed', 'findings', 'remediation']
                      : type === 'panel_position' || type === 'adjudication' ? ['role', 'position', 'outcome', 'confidence', 'flip_fact']
                        : []
  return keys.filter((key) => payload[key] !== undefined).map((key) => [key, payload[key]])
}

export function Inspector() {
  const { selected } = useInspector()
  const blobRef = selected ? Object.values(selected.payload).find((value) => typeof value === 'string' && value.startsWith('sha256:')) as string | undefined : undefined
  const blob = useQuery({ queryKey: ['blob', selected?.run_id, blobRef], queryFn: () => api.getBlob(selected!.run_id, blobRef!), enabled: Boolean(selected && blobRef) })
  const eventHighlights = selected ? highlights(selected.type, selected.payload) : []

  if (!selected) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-ink-faint">
        Select an event on the timeline to inspect its rationale, arguments and references.
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <header className="border-b border-border px-4 py-3">
        <p className="text-xs text-ink-faint">seq {selected.seq}</p>
        <h2 className="text-sm font-semibold text-ink">{selected.type}</h2>
        <p className="mt-1 text-sm text-ink-muted">{selected.summary}</p>
      </header>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-2 px-4 py-3 text-xs">
        <dt className="text-ink-faint">Actor</dt>
        <dd className="font-mono text-ink">
          {selected.actor.kind} · {selected.actor.name}
        </dd>
        <dt className="text-ink-faint">Virtual time</dt>
        <dd className="font-mono text-ink">{selected.ts_virtual}</dd>
        <dt className="text-ink-faint">Wall time</dt>
        <dd className="font-mono text-ink">{selected.ts_wall}</dd>
        {selected.refs.length > 0 && (
          <>
            <dt className="text-ink-faint">References</dt>
            <dd className="font-mono text-ink">{selected.refs.join(', ')}</dd>
          </>
        )}
      </dl>
      <div className="flex-1 border-t border-border px-4 py-3">
        {Boolean(selected.payload.rationale) && <div className="mb-3 rounded-md border border-violet/30 bg-violet/5 p-3"><h3 className="text-xs font-medium text-violet">Recorded rationale</h3><p className="mt-1 text-xs text-ink">{text(selected.payload.rationale)}</p></div>}
        {selected.type.startsWith('wait_') && <div className="mb-3 rounded-md border border-amber/30 bg-amber/5 p-3 text-xs text-amber">External wait lifecycle · playback remains independent of agent execution.</div>}
        {selected.type === 'verifier_check' && <div className={`mb-3 rounded-md border p-3 text-xs ${selected.payload.passed === false ? 'border-rose/30 text-rose' : 'border-emerald/30 text-emerald'}`}>Verifier {selected.payload.passed === false ? 'failed' : 'passed'} · {text(selected.payload.check ?? selected.payload.name ?? '')}</div>}
        {eventHighlights.length > 0 && <dl className="mb-3 grid grid-cols-[90px_1fr] gap-x-2 gap-y-1 rounded-md border border-border bg-surface-1 p-3 text-xs">{eventHighlights.map(([key, value]) => <div key={key} className="contents"><dt className="text-ink-faint">{key.replaceAll('_', ' ')}</dt><dd className="break-all font-mono text-ink-muted">{text(value)}</dd></div>)}</dl>}
        <h3 className="text-xs font-medium text-ink-faint">Payload</h3>
        <pre className="mt-2 overflow-x-auto rounded-md bg-surface-1 p-3 font-mono text-xs text-ink-muted">
          {JSON.stringify(selected.payload, null, 2)}
        </pre>
        {blobRef && <div className="mt-3"><h3 className="text-xs font-medium text-ink-faint">Redacted blob · {blobRef.slice(0, 18)}…</h3>{blob.isLoading && <p className="text-xs text-ink-faint">Loading artifact…</p>}{blob.data && <pre className="mt-2 max-h-72 overflow-auto rounded-md bg-surface-1 p-3 font-mono text-xs text-ink-muted">{JSON.stringify(blob.data.content, null, 2)}</pre>}</div>}
      </div>
    </div>
  )
}
