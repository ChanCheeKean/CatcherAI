import type { EventEnvelope } from '../../api/types'
import { useInspector } from '../../app/InspectorContext'
import { eventAccent } from '../../components/eventColor'

const COLOR = { cyan: 'bg-cyan', violet: 'bg-violet', amber: 'bg-amber', emerald: 'bg-emerald', rose: 'bg-rose', slate: 'bg-slate' }

export function ActorSwimlanes({ events }: { events: EventEnvelope[] }) {
  const { select } = useInspector()
  const actors = [...new Set(events.map((event) => `${event.actor.kind}:${event.actor.name}`))]
  const min = events[0]?.seq ?? 0
  const range = Math.max((events.at(-1)?.seq ?? min) - min, 1)
  return <div className="min-w-[680px] p-3" aria-label="Actor swimlanes">
    {actors.map((actor) => <div key={actor} className="grid grid-cols-[170px_1fr] border-b border-border/60 py-2">
      <span className="truncate pr-3 font-mono text-[11px] text-ink-faint">{actor}</span>
      <div className="relative h-5 rounded bg-surface-1">
        {events.filter((event) => `${event.actor.kind}:${event.actor.name}` === actor).map((event) => <button key={event.event_id} type="button" title={`${event.seq} ${event.summary}`} aria-label={`Inspect sequence ${event.seq}`} onClick={() => select(event)} className={`absolute top-1 size-3 rounded-full ${COLOR[eventAccent(event)]}`} style={{ left: `calc(${((event.seq - min) / range) * 100}% - 6px)` }} />)}
      </div>
    </div>)}
  </div>
}
