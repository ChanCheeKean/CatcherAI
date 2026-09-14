import { useInspector } from './InspectorContext'

export function Inspector() {
  const { selected } = useInspector()

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
        <h3 className="text-xs font-medium text-ink-faint">Payload</h3>
        <pre className="mt-2 overflow-x-auto rounded-md bg-surface-1 p-3 font-mono text-xs text-ink-muted">
          {JSON.stringify(selected.payload, null, 2)}
        </pre>
      </div>
    </div>
  )
}
