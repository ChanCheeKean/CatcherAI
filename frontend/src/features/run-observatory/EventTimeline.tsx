import { useInspector } from '../../app/InspectorContext'
import { eventAccent } from '../../components/eventColor'
import type { EventEnvelope } from '../../api/types'

const DOT: Record<ReturnType<typeof eventAccent>, string> = {
  cyan: 'bg-cyan',
  violet: 'bg-violet',
  amber: 'bg-amber',
  emerald: 'bg-emerald',
  rose: 'bg-rose',
  slate: 'bg-slate',
}

export function EventTimeline({ events }: { events: EventEnvelope[] }) {
  const { selected, select } = useInspector()

  if (events.length === 0) {
    return <p className="p-4 text-sm text-ink-faint">No events yet.</p>
  }

  return (
    <ol role="list" aria-label="Run event timeline" className="flex flex-col">
      {events.map((event) => {
        const isSelected = selected?.event_id === event.event_id
        return (
          <li key={event.event_id}>
            <button
              type="button"
              onClick={() => select(event)}
              aria-pressed={isSelected}
              className={`flex w-full items-start gap-3 border-b border-border px-4 py-2 text-left transition-colors hover:bg-surface-2 ${
                isSelected ? 'bg-surface-2' : ''
              }`}
            >
              <span
                className={`mt-1.5 size-1.5 shrink-0 rounded-full ${DOT[eventAccent(event)]}`}
                aria-hidden
              />
              <span className="w-12 shrink-0 font-mono text-xs text-ink-faint">{event.seq}</span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="flex items-baseline gap-2">
                  <span className="font-mono text-xs text-ink-muted">{event.type}</span>
                  <span className="truncate text-xs text-ink-faint">{event.actor.name}</span>
                </span>
                <span className="truncate text-sm text-ink">{event.summary}</span>
              </span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}
