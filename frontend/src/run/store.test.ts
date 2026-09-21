import { describe, expect, it } from 'vitest'
import { event, report } from './fixtures'
import { emptyRun, openPlanItems, reduceEvent } from './store'
import type { TrajectoryEvent } from '../api/types'

const fold = (events: TrajectoryEvent[]) => events.reduce(reduceEvent, emptyRun())

const plan = [
  { id: 'P1', question: 'Who used the card?', status: 'open', evidence_refs: [], waiver_reason: null },
  { id: 'P2', question: 'Is the IP shared?', status: 'done', evidence_refs: [], waiver_reason: null },
]

describe('reduceEvent', () => {
  it('tracks the plan, supervisor turn and open items', () => {
    const view = fold([
      event('plan_updated', 'triage', { plan }),
      event('supervisor_turn', 'supervisor', {}, { turn: 2, visit: 2 }),
    ])
    expect(view.turn).toBe(2)
    expect(openPlanItems(view).map((item) => item.id)).toEqual(['P1'])
    expect(view.visits.get('supervisor')).toBe(2)
  })

  it('records who first touched each graph item', () => {
    const toolEvent = (caller: string, ids: string[]) =>
      event(
        'tool_result',
        'graph_query',
        { caller, tool: 'graph_query', node_ids: ids, edge_ids: ['E-1'] },
        { actor: { kind: 'tool', name: 'graph_query' }, turn: 1 },
      )
    const view = fold([toolEvent('graph_analyst', ['ADR-1']), toolEvent('critic', ['ADR-1', 'CUS-2'])])
    expect(view.touched.get('ADR-1')).toMatchObject({ actor: 'graph_analyst', tool: 'graph_query', turn: 1 })
    expect(view.touched.get('CUS-2')?.actor).toBe('critic')
    expect(view.touched.size).toBe(3)
    expect(view.visits.size).toBe(0)
  })

  it('ignores an event it has already seen, as after an SSE reconnect', () => {
    const first = event('supervisor_turn', 'supervisor')
    expect(fold([first, first]).events).toHaveLength(1)
  })

  it('completes with the report on the decision event', () => {
    const view = fold([event('decision', 'adjudicator', { report, reason: 'decided' })])
    expect(view.status).toBe('completed')
    expect(view.report?.verdict).toBe('rejected')
  })

  it('fails on an error event', () => {
    const view = fold([event('error', 'runtime', { error: 'boom' })])
    expect(view.status).toBe('failed')
    expect(view.error).toBe('boom')
  })
})
