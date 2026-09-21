import type { TrajectoryEvent } from '../api/types'
import { useRunPanels } from './RunContext'

const MAX_EVENTS = 100

/** Selection-driven side panel. For now it shows the raw events behind the selection. */
export function Inspector() {
  const { view, selection } = useRunPanels()

  let heading = 'Inspector'
  let events: TrajectoryEvent[] = []
  let note = 'Select an agent or a graph item to see what happened.'

  if (selection?.kind === 'actor') {
    heading = selection.name
    events = view.events.filter(
      (e) => e.actor.name === selection.name || e.payload.caller === selection.name,
    )
    note = ''
  } else if (selection?.kind === 'node') {
    heading = selection.id
    const found = view.touched.get(selection.id)
    events = view.events.filter((e) => e.refs.includes(selection.id))
    note = found ? `Found by ${found.actor} with ${found.tool} in turn ${found.turn}.` : ''
  }

  return (
    <aside aria-label="Inspector" className="min-h-0 overflow-auto bg-vellum p-4">
      <h2 className={`mb-2 font-semibold ${selection?.kind === 'node' ? 'id-chip text-sm' : ''}`}>
        {heading}
      </h2>
      {note && <p className="mb-3 text-sm text-graphite">{note}</p>}
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
