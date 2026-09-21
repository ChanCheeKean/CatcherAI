import { describe, expect, it } from 'vitest'
import { event } from './fixtures'
import { deriveFlow, layout } from './flow'
import type { TrajectoryEvent } from '../api/types'

const at = (visit: number, turn: number, parent_id: string | null = null) => ({ visit, turn, parent_id })
const enter = (actor: string, visit: number, turn: number, parent: string | null = null) =>
  event('node_entered', actor, { input: { of: actor } }, at(visit, turn, parent))
const exit = (actor: string, visit: number, turn: number, parent: string | null = null) =>
  event('node_exited', actor, { output: { by: actor } }, at(visit, turn, parent))
const edge = (source: string, target: string, visit: number, turn: number, reason: string, parent: string | null = null) =>
  event('edge_taken', source, { source, target, reason }, at(visit, turn, parent))
const delegate = (role: string, turn: number, parent: string, instructions: string | null = null) =>
  event('delegation_started', role, { task: { role, objective: `Look into ${role}`, instructions } }, at(1, turn, parent))
const toolCall = (caller: string, tool: string, callId: string, v: number, turn: number, parent: string | null, ids: string[]) => [
  event('tool_call', tool, { caller, tool, call_id: callId, args: { q: 1 } }, { ...at(v, turn, parent), actor: { kind: 'tool', name: tool } }),
  event(
    'tool_result',
    tool,
    { caller, tool, call_id: callId, result: { rows: [] }, node_ids: ids, edge_ids: [] },
    { ...at(v, turn, parent), actor: { kind: 'tool', name: tool } },
  ),
]

const plan = [{ id: 'P1', question: 'Who?', status: 'open', evidence_refs: [], waiver_reason: null }]

/** triage, a rejected Decide, two parallel workers (one invented), then decision and memory. */
function stream(): TrajectoryEvent[] {
  return [
    enter('triage', 1, 0),
    event('triage', 'triage', { plan }, at(1, 0)),
    exit('triage', 1, 0),
    edge('triage', 'supervisor', 1, 0, 'triage complete'),
    enter('supervisor', 1, 1),
    exit('supervisor', 1, 1),
    edge('supervisor', 'supervisor', 1, 1, 'Decide rejected'),
    enter('supervisor', 2, 2),
    delegate('graph_analyst', 2, 'dlg-a'),
    delegate('ring_mapper', 2, 'dlg-b', 'Map the ring'),
    edge('supervisor', 'graph_analyst', 2, 2, 'decided by supervisor', 'dlg-a'),
    edge('supervisor', 'ring_mapper', 2, 2, 'decided by supervisor', 'dlg-b'),
    exit('supervisor', 2, 2),
    enter('graph_analyst', 1, 2, 'dlg-a'),
    event('skill_loaded', 'graph_analyst', { skill: 'graph-investigation' }, at(1, 2, 'dlg-a')),
    ...toolCall('graph_analyst', 'graph_query', 'c1', 1, 2, 'dlg-a', ['ADR-1', 'CUS-1']),
    ...toolCall('graph_analyst', 'graph_query', 'c2', 1, 2, 'dlg-a', ['CUS-2']),
    event('model_call', 'graph_analyst', { input_tokens: 100, output_tokens: 20 }, at(1, 2, 'dlg-a')),
    enter('ring_mapper', 1, 2, 'dlg-b'),
    ...toolCall('ring_mapper', 'graph_neighbors', 'c3', 1, 2, 'dlg-b', ['ADR-1']),
    exit('graph_analyst', 1, 2, 'dlg-a'),
    edge('graph_analyst', 'supervisor', 1, 2, 'findings returned', 'dlg-a'),
    exit('ring_mapper', 1, 2, 'dlg-b'),
    edge('ring_mapper', 'supervisor', 1, 2, 'findings returned', 'dlg-b'),
    event('plan_updated', 'supervisor', { plan: [{ ...plan[0], status: 'done' }] }, at(3, 3)),
    enter('supervisor', 3, 3),
    exit('supervisor', 3, 3),
    edge('supervisor', 'adjudicator', 3, 3, 'forced: max_turns'),
    enter('adjudicator', 1, 3),
    ...toolCall('adjudicator', 'graph_query', 'c4', 1, 3, null, ['TXN-1']),
    exit('adjudicator', 1, 3),
    edge('adjudicator', 'consolidate_memory', 1, 3, 'decision complete'),
    enter('consolidate_memory', 1, 3),
    ...toolCall('memory_keeper', 'memory_write', 'c5', 1, 3, null, ['MEM-1']),
    exit('consolidate_memory', 1, 3),
    edge('consolidate_memory', 'end', 1, 3, 'decided'),
  ]
}

const byId = (flow: ReturnType<typeof deriveFlow>, id: string) => flow.nodes.find((n) => n.id === id)!

describe('deriveFlow', () => {
  const flow = deriveFlow(stream())

  it('places each actor in its region, in order of first appearance', () => {
    expect(flow.nodes.map((n) => [n.id, n.region, n.order])).toEqual([
      ['triage', 'planning', 0],
      ['supervisor', 'planning', 1],
      ['graph_analyst', 'investigation', 0],
      ['ring_mapper', 'investigation', 1],
      ['graph_query', 'tools', 0],
      ['graph_neighbors', 'tools', 1],
      ['adjudicator', 'decision', 0],
      ['consolidate_memory', 'decision', 1],
      ['memory_write', 'tools', 2],
    ])
  })

  it('counts visits and tags roles the supervisor invented', () => {
    expect(byId(flow, 'supervisor').visits).toBe(3)
    expect(byId(flow, 'graph_analyst').adHoc).toBe(false)
    expect(byId(flow, 'ring_mapper').adHoc).toBe(true)
    expect(byId(flow, 'graph_query').visits).toBe(3)
  })

  it('draws loops as return and self edges, and the final hand-off as a decision edge', () => {
    const kinds = Object.fromEntries(flow.edges.map((e) => [e.id, [e.kind, e.count]]))
    expect(kinds['supervisor>supervisor']).toEqual(['self', 1])
    expect(kinds['graph_analyst>supervisor']).toEqual(['return', 1])
    expect(kinds['supervisor>ring_mapper']).toEqual(['forward', 1])
    expect(kinds['graph_analyst>graph_query']).toEqual(['tool', 2])
    expect(kinds['supervisor>adjudicator']).toEqual(['decision', 1])
    expect(flow.edges.find((e) => e.id === 'supervisor>graph_analyst')?.decidedBy).toBe('supervisor')
    expect(flow.edges.find((e) => e.id === 'supervisor>adjudicator')?.reason).toBe('forced: max_turns')
    expect(flow.edges.some((e) => e.target === 'end')).toBe(false)
  })

  it('files tool calls under the visit that made them, including the memory step', () => {
    const analyst = flow.visits.get('graph_analyst')![0]
    expect(analyst.tools.map((c) => c.callId)).toEqual(['c1', 'c2'])
    expect(analyst.tools[0].nodeIds).toEqual(['ADR-1', 'CUS-1'])
    expect(analyst.skills).toEqual(['graph-investigation'])
    expect(analyst.tokens).toBe(120)
    expect(flow.visits.get('consolidate_memory')![0].tools.map((c) => c.tool)).toEqual(['memory_write'])
    expect(flow.visits.has('memory_keeper')).toBe(false)
  })

  it('keeps the plan as it stood after each supervisor turn', () => {
    expect(flow.visits.get('triage')![0].plan?.[0].status).toBe('open')
    expect(flow.visits.get('supervisor')![0].plan?.[0].status).toBe('open')
    expect(flow.visits.get('supervisor')![2].plan?.[0].status).toBe('done')
  })

  it('reports which agents are still working and the last edge taken', () => {
    const partial = deriveFlow(stream().slice(0, 21))
    expect([...partial.active].sort()).toEqual(['graph_analyst', 'ring_mapper'])
    expect(partial.lastEdge).toBe('supervisor>ring_mapper')
    expect(flow.active.size).toBe(0)
  })

  it('collects every call of a tool with its caller and graph ids', () => {
    const calls = flow.toolCalls.get('graph_query')!
    expect(calls.map((c) => [c.caller, c.callId])).toEqual([
      ['graph_analyst', 'c1'],
      ['graph_analyst', 'c2'],
      ['adjudicator', 'c4'],
    ])
    expect(calls.flatMap((c) => c.nodeIds)).toEqual(['ADR-1', 'CUS-1', 'CUS-2', 'TXN-1'])
  })
})

describe('layout', () => {
  it('is deterministic and never moves a placed node when others arrive', () => {
    const events = stream()
    const early = deriveFlow(events.slice(0, 21))
    const late = deriveFlow(events)
    for (const { id } of early.nodes)
      expect(layout(late.nodes).position(byId(late, id))).toEqual(layout(early.nodes).position(byId(early, id)))
  })

  it('wraps Investigation into a further slot and shifts only the regions to its right', () => {
    const roles = Array.from({ length: 7 }, (_, i) => enter(`role_${i}`, 1, 1, `dlg-${i}`))
    const base = deriveFlow([...roles.slice(0, 6), enter('adjudicator', 1, 1)])
    const wrapped = deriveFlow([...roles, enter('adjudicator', 1, 1)])
    const a = layout(base.nodes)
    const b = layout(wrapped.nodes)
    expect(b.position(byId(wrapped, 'role_6')).x).toBeGreaterThan(b.position(byId(wrapped, 'role_0')).x)
    expect(b.position(byId(wrapped, 'role_0'))).toEqual(a.position(byId(base, 'role_0')))
    expect(b.position(byId(wrapped, 'adjudicator')).x).toBeGreaterThan(a.position(byId(base, 'adjudicator')).x)
  })
})
