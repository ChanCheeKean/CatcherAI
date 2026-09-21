import { ActorPanel } from './ActorPanel'
import { useRunPanels } from './RunContext'

const MAX_EVENTS = 100
const PANEL = 'min-h-0 overflow-auto bg-vellum p-4'

/** Selection-driven side panel: an agent or tool shows what it did; a graph item shows the raw events that touched it. */
export function Inspector() {
  const { view, flow, selection } = useRunPanels()

  if (selection?.kind === 'actor')
    return (
      <aside aria-label="Inspector" className={PANEL}>
        <ActorPanel name={selection.name} flow={flow} />
      </aside>
    )
  if (!selection)
    return (
      <aside aria-label="Inspector" className={PANEL}>
        <h2 className="mb-2 font-semibold">Inspector</h2>
        <p className="mb-3 text-sm text-graphite">Select an agent or a graph item to see what happened.</p>
      </aside>
    )

  const found = view.touched.get(selection.id)
  const events = view.events.filter((e) => e.refs.includes(selection.id))
  return (
    <aside aria-label="Inspector" className={PANEL}>
      <h2 className="id-chip mb-2 text-sm font-semibold">{selection.id}</h2>
      {found && (
        <p className="mb-3 text-sm text-graphite">
          Found by {found.actor} with {found.tool} in turn {found.turn}.
        </p>
      )}
      <ol className="space-y-1.5">
        {events.slice(-MAX_EVENTS).map((event) => (
          <li key={event.seq}>
            <details className="rounded-sm border bg-paper">
              <summary className="cursor-pointer px-2 py-1 text-sm">
                <span className="text-graphite tabular-nums">{event.seq}</span> {event.summary}
              </summary>
              <pre className="id-chip overflow-x-auto border-t p-2 whitespace-pre-wrap">
                {JSON.stringify(event.payload, null, 2)}
              </pre>
            </details>
          </li>
        ))}
      </ol>
    </aside>
  )
}
