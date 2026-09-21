import { useQuery } from '@tanstack/react-query'
import {
  Background,
  BaseEdge,
  EdgeLabelRenderer,
  Handle,
  Panel,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useNodesInitialized,
  useReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type { GraphEdge, GraphNode } from '../api/types'
import { bandBounds, columnsFor, layoutGraph, NODE_RADIUS, type Point } from './evidenceLayout'
import { touchedBy } from './evidence'
import { Icon } from './GraphIcon'
import { caption, GRAPH_REGIONS, isAgentWritten, labelStyle } from './graphModel'
import { useRunPanels } from './RunContext'

type Ring = 'solution' | 'decoy' | null
type Scope = 'connected' | 'all' | 'cited'

const SCOPES: { id: Scope; label: string; hint: string }[] = [
  { id: 'connected', label: 'Connected', hint: 'Nodes that have at least one drawn edge, plus cited evidence' },
  { id: 'all', label: 'Everything touched', hint: 'Every node the agents saw, including isolated query hits' },
  { id: 'cited', label: 'Cited only', hint: 'Only the evidence the final report cites' },
]

interface GraphNodeData extends Record<string, unknown> {
  node: GraphNode
  /** Shown only as context (expanded, or an endpoint) rather than touched by an agent. */
  context: boolean
  dim: boolean
  selected: boolean
  cited: boolean
  ring: Ring
  fresh: boolean
}
type EvidenceNode = Node<GraphNodeData, 'entity'>
type BandNode = Node<{ title: string; count: number }, 'band'>

interface GraphEdgeData extends Record<string, unknown> {
  edge: GraphEdge
  /** Offset for parallel edges between the same two nodes, in pixels. */
  bend: number
  dim: boolean
  showLabel: boolean
  emphasised: boolean
}
type EvidenceEdge = Edge<GraphEdgeData, 'link'>

const hidden = { opacity: 0, pointerEvents: 'none', width: 1, height: 1, left: '50%', top: '50%' } as const
const AGENT = 'var(--color-agent)'

/** One ring per node, in priority order: evaluation overlay, then selection, then citation. */
function outlineFor({ ring, selected, cited }: GraphNodeData): string {
  if (ring === 'solution') return 'outline-[3px] outline-accepted'
  if (ring === 'decoy') return 'outline-[3px] outline-dashed outline-rejected'
  if (selected) return 'outline-2 outline-ink'
  if (cited) return 'outline-[3px] outline-highlighter'
  return ''
}

function EntityNode({ data }: NodeProps<EvidenceNode>) {
  const { node, context, dim, fresh } = data
  const { color } = labelStyle(node.label)
  const agent = isAgentWritten(node)
  const outline = outlineFor(data)
  return (
    <div
      className={`flex flex-col items-center transition-opacity ${dim ? 'opacity-25' : context ? 'opacity-60' : ''}`}
      style={{ width: NODE_RADIUS * 2 + 40 }}
      title={`${node.label} ${node.id}`}
    >
      <Handle id="c-in" type="target" position={Position.Top} style={hidden} />
      <Handle id="c-out" type="source" position={Position.Top} style={hidden} />
      <div
        style={{
          width: NODE_RADIUS * 2,
          height: NODE_RADIUS * 2,
          background: color,
          borderColor: agent ? AGENT : 'transparent',
        }}
        className={`flex cursor-pointer items-center justify-center rounded-full border-2 text-white outline-offset-2 ${
          agent ? 'border-dashed' : ''
        } ${outline} ${fresh ? 'arrival' : ''}`}
      >
        <Icon label={node.label} />
      </div>
      <span className="id-chip mt-1 max-w-full truncate rounded-sm bg-vellum/85 px-1 text-ink">{caption(node)}</span>
    </div>
  )
}

function BandView({ data }: NodeProps<BandNode>) {
  return (
    <div className="size-full rounded-sm border bg-vellum/60 px-3 py-2 text-sm font-semibold text-graphite">
      {data.title}
      <span className="ml-2 font-normal tabular-nums">{data.count}</span>
    </div>
  )
}

function LinkView({ sourceX, sourceY, targetX, targetY, data, selected, markerEnd }: EdgeProps<EvidenceEdge>) {
  const { edge, bend, dim, showLabel, emphasised } = data!
  const dx = targetX - sourceX
  const dy = targetY - sourceY
  const length = Math.hypot(dx, dy) || 1
  const cx = (sourceX + targetX) / 2 + (-dy / length) * bend
  const cy = (sourceY + targetY) / 2 + (dx / length) * bend
  const path = `M${sourceX},${sourceY} Q${cx},${cy} ${targetX},${targetY}`
  const labelX = (sourceX + 2 * cx + targetX) / 4
  const labelY = (sourceY + 2 * cy + targetY) / 4
  const agent = isAgentWritten(edge)
  return (
    <>
      <BaseEdge
        path={path}
        markerEnd={markerEnd}
        interactionWidth={14}
        style={{
          stroke: agent ? AGENT : 'var(--color-graphite)',
          strokeWidth: emphasised || selected ? 2.5 : 1.25,
          strokeDasharray: agent ? '6 4' : undefined,
          opacity: dim ? 0.12 : 0.85,
        }}
      />
      {showLabel && !dim && (
        <EdgeLabelRenderer>
          <span
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
            className="id-chip pointer-events-none absolute rounded-sm bg-vellum px-1 text-graphite"
          >
            {edge.type}
          </span>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

const nodeTypes = { entity: EntityNode, band: BandView }
const edgeTypes = { link: LinkView }
const LABEL_LIMIT = 24

/** The nodes and edges currently drawn: recomputed when the graph or the scope changes. */
interface Shape {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

function ringFor(id: string, solution: Set<string>, decoy: Set<string>): Ring {
  if (solution.has(id)) return 'solution'
  if (decoy.has(id)) return 'decoy'
  return null
}

function GraphCanvas() {
  const { view, flow, graph, selection, select, highlight, clearHighlight, cited } = useRunPanels()
  const { fitView } = useReactFlow()
  const measured = useNodesInitialized()
  const running = view.status === 'running'
  const [overlay, setOverlay] = useState(false)
  const [scope, setScope] = useState<Scope>('connected')
  const evalData = useQuery({ queryKey: ['eval'], queryFn: api.evalLatest, staleTime: 60_000 })
  const truth = evalData.data?.cases.find((c) => c.case_id === view.events[0]?.case_id)
  const [settled, setSettled] = useState<{ shape: Shape | null; positions: Map<string, Point> }>({
    shape: null,
    positions: new Map(),
  })

  // Focus: what the reader asked to look at. A cited-evidence chip wins over an agent selection.
  const chipFocus = highlight.nodeIds.size + highlight.edgeIds.size > 0
  const actorName = selection?.kind === 'actor' ? selection.name : null
  const focus = useMemo(() => {
    if (chipFocus) return new Set([...highlight.nodeIds, ...highlight.edgeIds])
    if (actorName) return touchedBy(flow, actorName)
    return null
  }, [chipFocus, highlight, actorName, flow])
  const selectedId = selection?.kind === 'node' ? selection.id : null

  const shape = useMemo<Shape>(() => {
    const drawable = [...graph.edges.values()].filter((e) => graph.nodes.has(e.src) && graph.nodes.has(e.dst))
    const linked = new Set(drawable.flatMap((e) => [e.src, e.dst]))
    const keep = (node: GraphNode) =>
      scope === 'all' ||
      cited.nodeIds.has(node.id) ||
      highlight.nodeIds.has(node.id) ||
      node.id === selectedId ||
      (scope === 'connected' && (linked.has(node.id) || isAgentWritten(node)))
    const nodes = [...graph.nodes.values()].filter(keep)
    const shown = new Set(nodes.map((n) => n.id))
    const edges = drawable.filter((e) => shown.has(e.src) && shown.has(e.dst))
    return { nodes, edges }
  }, [graph.nodes, graph.edges, scope, cited, highlight, selectedId])

  // Derived state: when the graph grows, settle the layout once, starting from where nodes were.
  let placed = settled.positions
  if (settled.shape !== shape) {
    placed = layoutGraph(
      shape.nodes.map((n) => ({ id: n.id, region: labelStyle(n.label).region })),
      shape.edges.map((e) => ({ source: e.src, target: e.dst })),
      settled.positions,
    )
    setSettled({ shape, positions: placed })
  }

  const { nodes, edges } = useMemo(() => {
    const solution = new Set(overlay ? (truth?.solution_node_ids ?? []) : [])
    const decoy = new Set(overlay ? (truth?.decoy_node_ids ?? []) : [])
    const columns = columnsFor(shape.nodes.map((n) => ({ region: labelStyle(n.label).region })))
    const bands: BandNode[] = GRAPH_REGIONS.map(({ id, title }) => {
      const inside = shape.nodes.filter((n) => labelStyle(n.label).region === id)
      const bounds = bandBounds(columns[id], inside.map((n) => placed.get(n.id)!))
      return {
        id: `band-${id}`,
        type: 'band',
        position: { x: bounds.x, y: bounds.y },
        data: { title, count: inside.length },
        style: { width: bounds.width, height: bounds.height },
        draggable: false,
        selectable: false,
        focusable: false,
        zIndex: -1,
      }
    })
    const entities: EvidenceNode[] = shape.nodes.map((node) => {
      const at = placed.get(node.id)!
      return {
        id: node.id,
        type: 'entity',
        position: { x: at.x - NODE_RADIUS - 20, y: at.y - NODE_RADIUS },
        data: {
          node,
          context: !view.touched.has(node.id),
          dim: focus !== null && !focus.has(node.id),
          selected: node.id === selectedId,
          cited: cited.nodeIds.has(node.id),
          ring: ringFor(node.id, solution, decoy),
          fresh: running,
        },
        draggable: false,
      }
    })

    // Parallel edges between the same pair fan out, evenly spread around the straight line.
    const pairs = new Map<string, number>()
    const total = new Map<string, number>()
    const pairKey = (e: GraphEdge) => [e.src, e.dst].sort().join('|')
    for (const edge of shape.edges) {
      const key = pairKey(edge)
      total.set(key, (total.get(key) ?? 0) + 1)
    }
    const roomForLabels = shape.edges.length <= LABEL_LIMIT
    const links: EvidenceEdge[] = shape.edges.map((edge) => {
      const key = pairKey(edge)
      const index = pairs.get(key) ?? 0
      pairs.set(key, index + 1)
      const flipped = edge.src > edge.dst ? -1 : 1
      const related = edge.src === selectedId || edge.dst === selectedId || edge.id === selectedId
      return {
        id: edge.id,
        type: 'link',
        source: edge.src,
        target: edge.dst,
        sourceHandle: 'c-out',
        targetHandle: 'c-in',
        markerEnd: { type: 'arrowclosed', width: 14, height: 14, color: '#4f5c70' },
        data: {
          edge,
          bend: (index - (total.get(key)! - 1) / 2) * 26 * flipped,
          dim: focus !== null && !focus.has(edge.id),
          showLabel: roomForLabels || related || Boolean(focus?.has(edge.id)),
          emphasised: related || cited.edgeIds.has(edge.id) || highlight.edgeIds.has(edge.id),
        },
      }
    })
    return { nodes: [...bands, ...entities], edges: links }
  }, [shape, placed, focus, selectedId, cited, truth, overlay, running, view.touched, highlight])

  // Frame the graph when it grows or the cited set changes; not on every selection.
  // Both keys are strings so the effect compares by value rather than by array identity.
  const citedShown = chipFocus ? [...highlight.nodeIds].filter((id) => graph.nodes.has(id)).join(',') : ''
  const nodeCount = shape.nodes.length
  useEffect(() => {
    if (!measured) return
    const onto = citedShown ? citedShown.split(',').map((id) => ({ id })) : undefined
    const timer = setTimeout(() => void fitView({ duration: 300, padding: 0.12, nodes: onto }), 200)
    return () => clearTimeout(timer)
  }, [nodeCount, citedShown, measured, fitView])

  const found = truth ? truth.solution_node_ids.filter((id) => graph.nodes.has(id)).length : 0

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      fitView
      minZoom={0.15}
      nodesDraggable={false}
      nodesConnectable={false}
      zoomOnDoubleClick={false}
      onNodeClick={(_, node) => node.type === 'entity' && select({ kind: 'node', id: node.id })}
      onNodeDoubleClick={(_, node) => node.type === 'entity' && void graph.expand(node.id)}
      onEdgeClick={(_, edge) => select({ kind: 'node', id: edge.id })}
      onPaneClick={() => select(null)}
    >
      <Background gap={24} />
      <Panel position="top-left" className="flex flex-col items-start gap-1.5 text-xs">
        <div role="group" aria-label="Which nodes to show" className="flex overflow-hidden rounded-sm border bg-vellum">
          {SCOPES.map(({ id, label, hint }) => (
            <button
              key={id}
              type="button"
              title={hint}
              aria-pressed={scope === id}
              disabled={id === 'cited' && !cited.nodeIds.size}
              onClick={() => setScope(id)}
              className="cursor-pointer px-2.5 py-1 not-first:border-l enabled:not-aria-pressed:hover:bg-paper disabled:cursor-not-allowed disabled:opacity-40 aria-pressed:bg-ink aria-pressed:text-vellum"
            >
              {label}
            </button>
          ))}
        </div>
        {actorName && !chipFocus && (
          <span className="rounded-sm border bg-vellum px-2 py-1">Showing what {actorName} touched</span>
        )}
        {chipFocus && (
          <button
            type="button"
            onClick={clearHighlight}
            className="cursor-pointer rounded-sm border bg-highlighter px-2 py-1 font-medium"
          >
            Showing cited evidence. Show everything
          </button>
        )}
        {truth && (
          <label className="flex cursor-pointer items-center gap-1.5 rounded-sm border bg-vellum px-2 py-1">
            <input type="checkbox" checked={overlay} onChange={(e) => setOverlay(e.target.checked)} />
            Evaluation overlay
            {overlay && (
              <span className="text-graphite">
                {found} of {truth.solution_node_ids.length} solution nodes found
              </span>
            )}
          </label>
        )}
      </Panel>
      <Panel position="bottom-left" className="max-w-[26rem] rounded-sm border bg-vellum px-2 py-1.5 text-xs text-graphite">
        <Legend labels={[...new Set(shape.nodes.map((n) => n.label))].sort()} />
        <p className="mt-1">Dashed accent: written by an agent. Faded: context. Double-click a node to expand it.</p>
        {overlay && <p>Green ring: solution. Red dashed ring: decoy.</p>}
      </Panel>
    </ReactFlow>
  )
}

function Legend({ labels }: { labels: string[] }) {
  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-0.5">
      {labels.map((label) => (
        <li key={label} className="flex items-center gap-1">
          <span
            className="flex size-4 items-center justify-center rounded-full text-white"
            style={{ background: labelStyle(label).color }}
          >
            <Icon label={label} size={11} />
          </span>
          {label}
        </li>
      ))}
    </ul>
  )
}

export function EvidenceGraph() {
  const { graph } = useRunPanels()
  if (!graph.nodes.size) return <p className="p-4 text-graphite">Nothing discovered yet. Nodes appear as agents query the graph.</p>
  return (
    <ReactFlowProvider>
      <GraphCanvas />
    </ReactFlowProvider>
  )
}
