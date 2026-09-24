import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { GraphEdge, GraphNode } from '../api/types'
import { citedBy, touchedBy } from './evidence'
import { columnsFor, layoutGraph } from './evidenceLayout'
import { evidence, event, report } from './fixtures'
import { deriveFlow } from './flow'
import { GraphItemPanel } from './GraphItemPanel'
import { fromNeighbor, graphModel } from './graphModel'
import { RunPanelsContext, type RunPanels } from './RunContext'
import { emptyRun, reduceEvent } from './store'

const ontology = {
  groups: { parties: { title: 'Parties', description: '' }, commerce: { title: 'Commerce', description: '' }, terms: { title: 'Terms', description: '' }, case: { title: 'Case', description: '' } },
  labels: { CardMember: { group: 'parties', description: '' }, Charge: { group: 'commerce', description: '' }, Clause: { group: 'terms', description: '' }, Dispute: { group: 'case', description: '' } },
  edges: {},
  node_count: 4,
  edge_count: 2,
}
const model = graphModel(ontology)
const ring = [
  { id: 'CMB-1', region: 'parties' },
  { id: 'CMB-2', region: 'parties' },
  { id: 'CHG-1', region: 'commerce' },
  { id: 'DSP-1', region: 'case' },
]
const links = [
  { source: 'CMB-1', target: 'CHG-1' },
  { source: 'DSP-1', target: 'CHG-1' },
]
const regions = model.regions

describe('layoutGraph', () => {
  it('is deterministic and keeps each node inside its region band', () => {
    const first = layoutGraph(regions, ring, links, new Map())
    expect([...layoutGraph(regions, ring, links, new Map())]).toEqual([...first])
    const centre = (id: string) => first.get(id)!.x
    expect(centre('DSP-1')).toBeGreaterThan(centre('CHG-1'))
    expect(centre('CHG-1')).toBeGreaterThan(centre('CMB-1'))
    const columns = columnsFor(regions, ring)
    for (const { id, region } of ring) {
      const { centre, width } = columns[region]!
      expect(Math.abs(first.get(id)!.x - centre)).toBeLessThanOrEqual(width / 2)
    }
  })

  it('keeps earlier nodes near where they were when the graph grows', () => {
    const first = layoutGraph(regions, ring.slice(0, 3), links.slice(0, 1), new Map())
    const grown = layoutGraph(regions, ring, links, first)
    for (const id of ['CMB-1', 'CMB-2', 'CHG-1']) {
      const moved = Math.hypot(grown.get(id)!.x - first.get(id)!.x, grown.get(id)!.y - first.get(id)!.y)
      expect(moved).toBeLessThan(120)
    }
  })
})

describe('graph model', () => {
  it('builds ordered regions and label styles from ontology', () => {
    expect(model.regions.map((r) => r.id)).toEqual(['parties', 'commerce', 'terms', 'case'])
    expect(model.labelStyle('CardMember')).toMatchObject({ region: 'parties', icon: 'person' })
    expect(model.labelStyle('Clause')).toMatchObject({ region: 'terms', icon: 'scroll' })
    expect(model.labelStyle('Unknown').region).toBe('case')
  })

  it('turns a neighbour hit into the node and edge shapes of the lookup endpoint', () => {
    const { node, edge } = fromNeighbor('CMB-1', {
      type: 'FILED_BY',
      direction: 'out',
      edge: { id: 'E-9', _type: 'FILED_BY', amount: 10 },
      node: { id: 'CHG-1', _label: 'Charge', name: 'Test charge' },
    })
    expect(node).toEqual({ id: 'CHG-1', label: 'Charge', properties: { name: 'Test charge' } })
    expect(edge).toMatchObject({ id: 'E-9', type: 'FILED_BY', src: 'CMB-1', dst: 'CHG-1' })
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
    ...call('graph_analyst', 'graph_query', 'a', ['CHG-1'], 'd1'),
    event('node_entered', 'critic', { input: {} }, { parent_id: 'd2' }),
    ...call('critic', 'graph_neighbors', 'b', ['CMB-9'], 'd2'),
  ])

  it('lists what an agent or a tool touched', () => {
    expect([...touchedBy(flow, 'graph_analyst')].sort()).toEqual(['CHG-1', 'E-a'])
    expect([...touchedBy(flow, 'graph_neighbors')].sort()).toEqual(['CMB-9', 'E-b'])
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
  const address: GraphNode = { id: 'CHG-1', label: 'Charge', properties: { name: 'Test charge' } }
  const customer: GraphNode = { id: 'CMB-1', label: 'CardMember', properties: { name: 'Ada Vega' } }
  const lives: GraphEdge = {
    id: 'E-1',
    type: 'CHARGED_TO',
    src: 'CHG-1',
    dst: 'CMB-1',
    properties: {},
  }

  it('shows properties, connections and who found the node, and follows a connection', async () => {
    const select = vi.fn()
    const events = [
      event(
        'tool_result',
        'graph_query',
        { caller: 'graph_analyst', tool: 'graph_query', call_id: 'a', result: {}, node_ids: ['CHG-1'], edge_ids: [] },
        { turn: 3, refs: ['CHG-1'] },
      ),
    ]
    const panels: RunPanels = {
      view: events.reduce(reduceEvent, emptyRun()),
      flow: deriveFlow(events),
      selection: { kind: 'node', id: 'CHG-1' },
      select,
      highlight: { nodeIds: new Set(), edgeIds: new Set() },
      clearHighlight: vi.fn(),
      cited: { nodeIds: new Set(), edgeIds: new Set() },
      graphModel: model,
      graph: {
        nodes: new Map([address, customer].map((n) => [n.id, n])),
        edges: new Map([[lives.id, lives]]),
        expand: vi.fn(),
        expanded: new Set(),
      },
      showEvidence: vi.fn(),
      tab: 'graph',
      setTab: vi.fn(), truth: undefined, overlay: false, setOverlay: vi.fn(), graphScope: null, setGraphScope: vi.fn(),
    }
    render(
      <RunPanelsContext.Provider value={panels}>
        <GraphItemPanel id="CHG-1" />
      </RunPanelsContext.Provider>,
    )
    expect(screen.getByText('Test charge')).toBeInTheDocument()
    expect(screen.getByText(/Found by graph_analyst with graph_query in turn 3/)).toBeInTheDocument()
    expect(screen.getByText('CHARGED_TO')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'CardMember Ada Vega' }))
    expect(select).toHaveBeenCalledWith({ kind: 'node', id: 'CMB-1' })
  })
})
