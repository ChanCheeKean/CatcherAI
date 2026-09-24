import { expect, it } from 'vitest'
import { event } from './fixtures'
import { deriveFlow } from './flow'
import { axisTicks, swimlanes } from './lanes'

const t = (seconds: number) => ({ ts_wall: new Date(Date.UTC(2026, 8, 24, 10, 0, seconds)).toISOString() })

it('lays the run out as lanes over time with tool ticks, Notebook marks and sent-back rules', () => {
  const entry = { entry_id: 'NBK-1', seq: 1, author: 'graph_analyst', kind: 'fact', text: 'Found it.', node_ids: ['CHG-1'], edge_ids: [] }
  const events = [
    event('node_entered', 'supervisor', {}, { ...t(0), visit: 1 }),
    event('node_exited', 'supervisor', {}, { ...t(2), visit: 1 }),
    event('edge_taken', 'supervisor', { source: 'supervisor', target: 'supervisor', reason: 'Decide rejected' }, t(2)),
    event('node_entered', 'graph_analyst', {}, { ...t(3), parent_id: 'dlg-a' }),
    event('tool_call', 'graph_query', { caller: 'graph_analyst', tool: 'graph_query', call_id: 'c1', args: {} }, { ...t(5), parent_id: 'dlg-a' }),
    event('notebook_write', 'notebook_write', { entry }, t(6)),
  ]
  const { lanes, sentBack, now } = swimlanes(deriveFlow(events), events)
  expect(lanes.map((lane) => lane.actor)).toEqual(['supervisor', 'graph_analyst'])
  expect(lanes[0].spans).toEqual([{ visit: 1, start: 0, end: 2000, calls: [] }])
  expect(lanes[0].notes).toEqual([])
  // Still running: the span stays open and ends at the latest event.
  expect(lanes[1].spans).toEqual([{ visit: 1, start: 3000, end: null, calls: [{ at: 5000, tool: 'graph_query' }] }])
  expect(lanes[1].notes).toEqual([{ at: 6000, entry }])
  expect(sentBack).toEqual([2000])
  expect(now).toBe(6000)
})

it('spaces the time axis so a long run keeps its labels apart', () => {
  const minute = 60_000
  expect(axisTicks(5 * minute)).toEqual([0, 1, 2, 3, 4, 5].map((m) => m * minute))
  const long = axisTicks(39 * minute)
  expect(long.length).toBeLessThanOrEqual(8)
  expect(long.slice(0, 3)).toEqual([0, 5 * minute, 10 * minute])
})
