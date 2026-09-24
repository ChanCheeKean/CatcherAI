import { useMemo } from 'react'
import { noteTone, words } from './format'
import { clock } from './replay'
import { useRunPanels } from './RunContext'
import { axisTicks, swimlanes } from './lanes'

/**
 * The agent flow over time: one lane per agent, a bar per visit with a tick per tool call, a
 * diamond per Case Notebook entry, and a dashed rule wherever the supervisor's Decide was sent back.
 * Lanes that overlap in time are agents working in parallel.
 */
export function Swimlanes() {
  const { flow, view, runLength, select, selection, showEvidence } = useRunPanels()
  const { lanes, sentBack, now } = useMemo(() => swimlanes(flow, view.events), [flow, view.events])
  if (!lanes.length) return <p className="p-4 text-graphite">Waiting for the first agent to start…</p>

  const length = Math.max(runLength, now, 1)
  const x = (ms: number) => `${(ms / length) * 100}%`
  const ticks = axisTicks(length)
  const selected = selection?.kind === 'actor' ? selection.name : null

  return (
    <section aria-label="Agents over time" className="flex h-full flex-col overflow-auto p-4">
      <div className="flex min-w-[36rem]">
        <ol className="w-36 shrink-0 pt-6">
          {lanes.map(({ actor }) => (
            <li key={actor} className="flex h-10 items-center">
              <button
                type="button"
                onClick={() => select({ kind: 'actor', name: actor })}
                className={`cursor-pointer truncate text-left text-sm hover:underline ${actor === selected ? 'font-semibold' : ''}`}
              >
                {words(actor)}
              </button>
            </li>
          ))}
        </ol>
        <div className="relative min-w-0 flex-1">
          <div aria-hidden className="relative h-6 border-b text-xs text-graphite">
            {ticks.map((ms) => (
              <span key={ms} className="absolute top-0 -translate-x-1/2 tabular-nums first:translate-x-0" style={{ left: x(ms) }}>
                {clock(ms)}
              </span>
            ))}
          </div>
          <ol>
            {lanes.map(({ actor, spans, notes }) => (
              <li key={actor} className="relative h-10 border-b border-rule/50">
                {spans.map((span) => {
                  const end = span.end ?? now
                  return (
                    <button
                      key={span.visit}
                      type="button"
                      onClick={() => select({ kind: 'actor', name: actor })}
                      title={`${words(actor)}, visit ${span.visit}: ${clock(span.start)}–${clock(end)}, ${span.calls.length} tool calls`}
                      className={`absolute top-2 h-6 min-w-1 cursor-pointer rounded-sm border border-agent/50 bg-agent/15 hover:bg-agent/25 ${span.end === null ? 'pulse' : ''}`}
                      style={{ left: x(span.start), width: x(end - span.start) }}
                    />
                  )
                })}
                {spans.flatMap((span) =>
                  span.calls.map((call, index) => (
                    <span
                      key={`${span.visit}-${index}`}
                      aria-hidden
                      title={call.tool}
                      className="pointer-events-none absolute top-3 h-4 w-px bg-agent"
                      style={{ left: x(call.at) }}
                    />
                  )),
                )}
                {notes.map(({ at, entry }) => (
                  <button
                    key={entry.entry_id}
                    type="button"
                    onClick={() => showEvidence(entry)}
                    title={`${words(entry.kind)}: ${entry.text}`}
                    aria-label={`Notebook ${words(entry.kind)} by ${words(actor)}`}
                    className={`absolute top-0 size-2.5 -translate-x-1/2 rotate-45 cursor-pointer border border-vellum hover:scale-150 ${noteTone[entry.kind]}`}
                    style={{ left: x(at) }}
                  />
                ))}
              </li>
            ))}
          </ol>
          {sentBack.map((at) => (
            <div key={at} className="pointer-events-none absolute top-0 bottom-0 border-l-2 border-dashed border-partial" style={{ left: x(at) }}>
              <span className="absolute top-0 left-1 rounded-sm bg-vellum px-1 text-xs whitespace-nowrap text-partial">↻ sent back</span>
            </div>
          ))}
          <div aria-hidden className="pointer-events-none absolute top-0 bottom-0 w-px bg-ink" style={{ left: x(now) }} />
        </div>
      </div>
      <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-graphite">
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-5 rounded-sm border border-agent/50 bg-agent/15" /> a visit
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-px bg-agent" /> a tool call
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2 rotate-45 bg-facts" /> a Case Notebook entry (click to show its evidence)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 border-l-2 border-dashed border-partial" /> Decide sent back
        </span>
      </p>
    </section>
  )
}
