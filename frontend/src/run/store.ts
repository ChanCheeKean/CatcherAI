import type { CaseReport, PlanItem, RunState, TrajectoryEvent } from '../api/types'

/** Who found a graph item, and where: the frontend's "found by <agent> via <tool>" answer. */
export interface Touch {
  actor: string
  tool: string
  turn: number
  seq: number
}

export interface RunView {
  events: TrajectoryEvent[]
  status: RunState
  error: string | null
  turn: number
  plan: PlanItem[]
  /** Highest visit number per graph actor, in order of first appearance. */
  visits: Map<string, number>
  /** Every node and edge id the run has touched, with its first discovery. */
  touched: Map<string, Touch>
  report: CaseReport | null
  termination: string | null
}

export const emptyRun = (): RunView => ({
  events: [],
  status: 'running',
  error: null,
  turn: 0,
  plan: [],
  visits: new Map(),
  touched: new Map(),
  report: null,
  termination: null,
})

const GRAPH_TYPES = new Set(['tool_result', 'graph_write', 'memory_write'])

/** Fold one event into the view; replays and live streams go through the same path. */
export function reduceEvent(view: RunView, event: TrajectoryEvent): RunView {
  if (view.events.some((seen) => seen.seq === event.seq)) return view
  const next: RunView = {
    ...view,
    events: [...view.events, event],
    turn: Math.max(view.turn, event.turn),
  }
  const { payload } = event

  if (event.actor.kind === 'graph_node' && event.type !== 'run_started' && event.type !== 'error') {
    next.visits = new Map(view.visits).set(
      event.actor.name,
      Math.max(view.visits.get(event.actor.name) ?? 0, event.visit),
    )
  }
  if (event.type === 'plan_updated') next.plan = payload.plan as PlanItem[]
  if (event.type === 'triage' && !view.plan.length) next.plan = payload.plan as PlanItem[]
  if (GRAPH_TYPES.has(event.type)) {
    const touched = new Map(view.touched)
    const found = {
      actor: String(payload.caller ?? event.actor.name),
      tool: String(payload.tool ?? event.actor.name),
      turn: event.turn,
      seq: event.seq,
    }
    for (const id of [...(payload.node_ids as string[]), ...(payload.edge_ids as string[])]) {
      if (!touched.has(id)) touched.set(id, found)
    }
    next.touched = touched
  }
  if (event.type === 'decision') {
    next.report = payload.report as CaseReport
    next.status = 'completed'
  }
  if (event.type === 'termination') next.termination = String(payload.reason)
  if (event.type === 'error') {
    next.status = 'failed'
    next.error = String(payload.error)
  }
  return next
}

export const openPlanItems = (view: RunView) => view.plan.filter((item) => item.status === 'open')
