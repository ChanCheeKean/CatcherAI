import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { GraphEdge, GraphNode } from '../api/types'
import { citedBy, touchedBy } from './evidence'
import { columnsFor, layoutGraph } from './evidenceLayout'
import { evidence, event, report } from './fixtures'
import { deriveFlow } from './flow'
import { GraphItemPanel } from './GraphItemPanel'
import { fromNeighbor, GRAPH_REGIONS, isAgentWritten, LABELS } from './graphModel'
import { RunPanelsContext, type RunPanels } from './RunContext'
import { emptyRun, reduceEvent } from './store'

const ring = [
  { id: 'ADR-1', region: 'identity' as const },
  { id: 'CUS-1', region: 'identity' as const },
  { id: 'CUS-2', region: 'identity' as const },
  { id: 'TXN-1', region: 'commerce' as const },
  { id: 'DSP-1', region: 'case' as const },
]
const links = [
  { source: 'CUS-1', target: 'ADR-1' },
  { source: 'CUS-2', target: 'ADR-1' },
  { source: 'DSP-1', target: 'TXN-1' },
]

describe('layoutGraph', () => {
  it('is deterministic and keeps each node inside its region band', () => {
    const first = layoutGraph(ring, links, new Map())
    expect([...layoutGraph(ring, links, new Map())]).toEqual([...first])
    const centre = (id: string) => first.get(id)!.x
    expect(centre('DSP-1')).toBeGreaterThan(centre('TXN-1'))
    expect(centre('TXN-1')).toBeGreaterThan(centre('ADR-1'))
    const columns = columnsFor(ring)
    for (const { id, region } of ring) {
      const { centre, width } = columns[region]
      expect(Math.abs(first.get(id)!.x - centre)).toBeLessThanOrEqual(width / 2)
    }
  })

  it('keeps earlier nodes near where they were when the graph grows', () => {
    const first = layoutGraph(ring.slice(0, 3), links.slice(0, 2), new Map())
    const grown = layoutGraph(ring, links, first)
    for (const id of ['ADR-1', 'CUS-1', 'CUS-2']) {
      const moved = Math.hypot(grown.get(id)!.x - first.get(id)!.x, grown.get(id)!.y - first.get(id)!.y)
      expect(moved).toBeLessThan(120)
    }
  })
})

describe('graph model', () => {
  it('assigns every label to a known region', () => {
    const regions = new Set(GRAPH_REGIONS.map((r) => r.id))
    for (const style of Object.values(LABELS)) expect(regions.has(style.region)).toBe(true)
  })

  it('turns a neighbour hit into the node and edge shapes of the lookup endpoint', () => {
    const { node, edge } = fromNeighbor('CUS-1', {
      type: 'LIVES_AT',
      direction: 'out',
      edge: { id: 'E-9', _type: 'LIVES_AT', valid_from: '2026-01-01' },
      node: { id: 'ADR-1', _label: 'Address', street: '100 Amber Street' },
    })
    expect(node).toEqual({ id: 'ADR-1', label: 'Address', properties: { street: '100 Amber Street' } })
    expect(edge).toMatchObject({ id: 'E-9', type: 'LIVES_AT', src: 'CUS-1', dst: 'ADR-1' })
  })

  it('marks agent-written nodes and edges', () => {
    expect(isAgentWritten({ id: 'FND-1', label: 'Finding', properties: {} })).toBe(true)
    expect(isAgentWritten({ id: 'E-1', type: 'SAME_ACTOR', src: 'a', dst: 'b', properties: { run_id: 'run-1' } })).toBe(true)
    expect(isAgentWritten({ id: 'E-2', type: 'LIVES_AT', src: 'a', dst: 'b', properties: { run_id: null } })).toBe(false)
  })
})

describe('evidence helpers', () => {
  const call = (caller: string, tool: string, id: string, ids: string[], parent: string | null) => {
    const actor = { kind: 'tool', name: tool }
    const at = { visit: 1, turn: 1, parent_id: parent, actor }
    return [
      event('tool_call', tool, { caller, tool, call_id: id, args: {} }, at),
      event('tool_result', tool, { caller, tool, call_id: id, result: {}, node_ids: ids, edge_ids: [`E-${id}`] }, at),
    ]
  }
  const flow = deriveFlow([
    event('node_entered', 'graph_analyst', { input: {} }, { parent_id: 'd1' }),
    ...call('graph_analyst', 'graph_query', 'a', ['ADR-1'], 'd1'),
    event('node_entered', 'critic', { input: {} }, { parent_id: 'd2' }),
    ...call('critic', 'graph_neighbors', 'b', ['CUS-9'], 'd2'),
  ])

  it('lists what an agent or a tool touched', () => {
    expect([...touchedBy(flow, 'graph_analyst')].sort()).toEqual(['ADR-1', 'E-a'])
    expect([...touchedBy(flow, 'graph_neighbors')].sort()).toEqual(['CUS-9', 'E-b'])
    expect(touchedBy(flow, 'nobody').size).toBe(0)
  })

  it('collects the evidence a report cites', () => {
    expect(citedBy(null).nodeIds.size).toBe(0)
    const cited = citedBy(report)
    expect([...cited.nodeIds]).toEqual(evidence.node_ids)
    expect([...cited.edgeIds]).toEqual(evidence.edge_ids)
  })
})

describe('GraphItemPanel', () => {
  const address: GraphNode = { id: 'ADR-1', label: 'Address', properties: { street: '100 Amber Street' } }
  const customer: GraphNode = { id: 'CUS-1', label: 'Customer', properties: { name: 'Ada Vega' } }
  const lives: GraphEdge = {
    id: 'E-1',
    type: 'LIVES_AT',
    src: 'CUS-1',
    dst: 'ADR-1',
    properties: { valid_from: '2026-01-01', valid_to: '' },
  }

  it('shows properties, dated connections and who found the node, and follows a connection', async () => {
    const select = vi.fn()
    const events = [
      event(
        'tool_result',
        'graph_query',
        { caller: 'graph_analyst', tool: 'graph_query', call_id: 'a', result: {}, node_ids: ['ADR-1'], edge_ids: [] },
        { turn: 3, refs: ['ADR-1'] },
      ),
    ]
    const panels: RunPanels = {
      view: events.reduce(reduceEvent, emptyRun()),
      flow: deriveFlow(events),
      selection: { kind: 'node', id: 'ADR-1' },
      select,
      highlight: { nodeIds: new Set(), edgeIds: new Set() },
      clearHighlight: vi.fn(),
      cited: { nodeIds: new Set(), edgeIds: new Set() },
      graph: {
        nodes: new Map([address, customer].map((n) => [n.id, n])),
        edges: new Map([[lives.id, lives]]),
        expand: vi.fn(),
      },
      showEvidence: vi.fn(),
      tab: 'graph',
      setTab: vi.fn(),
    }
    render(
      <RunPanelsContext.Provider value={panels}>
        <GraphItemPanel id="ADR-1" />
      </RunPanelsContext.Provider>,
    )
    expect(screen.getByText('100 Amber Street')).toBeInTheDocument()
    expect(screen.getByText(/Found by graph_analyst with graph_query in turn 3/)).toBeInTheDocument()
    expect(screen.getByText('2026-01-01 to now')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Customer Ada Vega' }))
    expect(select).toHaveBeenCalledWith({ kind: 'node', id: 'CUS-1' })
  })
})
