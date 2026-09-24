import type { TrajectoryEvent } from '../api/types'
import { words } from './format'

/** A wait longer than this (the model thinking) is shortened to it, so a replay keeps moving. */
const LONGEST_PAUSE_MS = 2000
/** Replay time per millisecond of shortened run time at 1×: a five-minute run replays in about a minute. */
const PACE = 0.5

/** When each event happens on the replay clock, in ms from the start of the run. */
export function replayTimes(events: TrajectoryEvent[]): number[] {
  let at = 0
  return events.map((event, i) => {
    if (i > 0) {
      const gap = Date.parse(event.ts_wall) - Date.parse(events[i - 1].ts_wall)
      at += Math.min(Math.max(gap, 0), LONGEST_PAUSE_MS) * PACE
    }
    return at
  })
}

/** How many events have happened by `time` on the replay clock. */
export function eventsBy(times: number[], time: number): number {
  let low = 0
  let high = times.length
  while (low < high) {
    const mid = (low + high) >> 1
    if (times[mid] <= time) low = mid + 1
    else high = mid
  }
  return low
}

export type MilestoneKind = 'start' | 'delegation' | 'sent-back' | 'verdict'

export interface Milestone {
  kind: MilestoneKind
  label: string
  /** Index of the event, so the milestone can be jumped to. */
  index: number
}

/** The moments worth marking on the timeline: triage, each delegation, each decision sent back, the verdict. */
export function milestones(events: TrajectoryEvent[]): Milestone[] {
  const marks: Milestone[] = []
  events.forEach((event, index) => {
    const { type, actor, payload } = event
    if (type === 'node_exited' && actor.name === 'triage') marks.push({ kind: 'start', label: 'Triage sets the plan', index })
    else if (type === 'delegation_started') marks.push({ kind: 'delegation', label: `Supervisor delegates to the ${words(actor.name)}`, index })
    else if (type === 'edge_taken' && payload.source === 'supervisor' && payload.target === 'supervisor')
      marks.push({ kind: 'sent-back', label: 'Decision sent back: plan items still open', index })
    else if (type === 'decision') marks.push({ kind: 'verdict', label: 'Verdict', index })
  })
  return marks
}

/** Minutes and seconds of real run time, as a clock reads. */
export function clock(ms: number): string {
  const seconds = Math.max(0, Math.round(ms / 1000))
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}
