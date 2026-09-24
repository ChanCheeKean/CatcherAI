import type { NotebookEntry, TrajectoryEvent } from '../api/types'
import type { Flow } from './flow'
import { isSentBack } from './replay'

/** One visit of an agent as a span of run time, in ms from the start of the run. */
export interface Span {
  visit: number
  start: number
  /** Null while the visit is still running. */
  end: number | null
  /** When each tool call was made, and which tool. */
  calls: { at: number; tool: string }[]
}

export interface Lane {
  actor: string
  spans: Span[]
  /** Case Notebook entries this agent wrote, at the moment each was written. */
  notes: { at: number; entry: NotebookEntry }[]
}

export interface Swimlanes {
  lanes: Lane[]
  /** Moments the supervisor's Decide was sent back because plan items were still open. */
  sentBack: number[]
  /** Run time of the latest event shown. */
  now: number
}

/** The run as lanes over time: one lane per agent in order of first appearance, built from the same events as the map. */
export function swimlanes(flow: Flow, events: TrajectoryEvent[]): Swimlanes {
  const start = events.length ? Date.parse(events[0].ts_wall) : 0
  const time = (ts: string) => Date.parse(ts) - start
  const notes = events
    .filter((event) => event.type === 'notebook_write')
    .map((event) => ({ at: time(event.ts_wall), entry: event.payload.entry as NotebookEntry }))
  const lanes = [...flow.visits].map(([actor, visits]) => ({
    actor,
    spans: visits.map((visit) => ({
      visit: visit.visit,
      start: time(visit.startedAt),
      end: visit.durationMs === null ? null : time(visit.startedAt) + visit.durationMs,
      calls: visit.tools.map((call) => ({ at: time(call.at), tool: call.tool })),
    })),
    notes: notes.filter(({ entry }) => entry.author === actor),
  }))
  const sentBack = events
    .filter(isSentBack)
    .map((event) => time(event.ts_wall))
  return { lanes, sentBack, now: events.length ? time(events[events.length - 1].ts_wall) : 0 }
}

const MINUTE = 60_000

/** Axis marks for a run of `length` ms: whole minutes, spaced so no more than eight are drawn. */
export function axisTicks(length: number): number[] {
  const step = [1, 2, 5, 10, 15, 30].map((m) => m * MINUTE).find((s) => length / s < 8) ?? 60 * MINUTE
  return Array.from({ length: Math.floor(length / step) + 1 }, (_, i) => i * step)
}
