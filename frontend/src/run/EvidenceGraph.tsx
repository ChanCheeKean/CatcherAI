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
  useStore,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useEffect, useMemo, useState } from 'react'
import type { GraphEdge, GraphNode } from '../api/types'
import { bandBounds, columnsFor, layoutGraph, NODE_RADIUS, type Point } from './evidenceLayout'
import { touchedBy } from './evidence'
import { Icon } from './GraphIcon'
import { caption, regionColor } from './graphModel'
import { type GraphScope, useRunPanels } from './RunContext'
import { useMeasuredNodes } from './useMeasuredNodes'

type Ring = 'solution' | 'decoy' | null

const SCOPES: { id: GraphScope; label: string; hint: string }[] = [
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
type BandNode = Node<{ region: string; title: string; count: number }, 'band'>

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
  const { graphModel } = useRunPanels()
  const { color } = graphModel.labelStyle(node.label)
  const outline = outlineFor(data)
  const name = caption(node)
  return (
    <div
      className={`flex flex-col items-center transition-opacity ${dim ? 'opacity-25' : context ? 'opacity-60' : ''}`}
      style={{ width: NODE_RADIUS * 2 + 56 }}
      title={`${node.label} ${node.id}: ${name}`}
    >
      <Handle id="c-in" type="target" position={Position.Top} style={hidden} />
      <Handle id="c-out" type="source" position={Position.Top} style={hidden} />
      <div
        style={{
          width: NODE_RADIUS * 2,
          height: NODE_RADIUS * 2,
          background: color,
        }}
        className={`flex cursor-pointer items-center justify-center rounded-full text-white outline-offset-2 ${outline} ${fresh ? 'arrival' : ''}`}
      >
        <Icon label={node.label} />
      </div>
      <span className="mt-1 line-clamp-2 max-w-full rounded-sm bg-vellum/85 px-1 text-center text-[11px] leading-tight break-words text-ink">
        {name}
      </span>
    </div>
  )
}

/** Band titles sit just above the band and keep a readable size on screen however far the graph is zoomed out. */
function BandView({ data }: NodeProps<BandNode>) {
  const zoom = useStore((state) => state.transform[2])
  return (
    <div className="relative size-full rounded-sm border bg-vellum/60">
      <p style={{ fontSize: 14 / zoom }} className="absolute bottom-full left-0 pb-[0.3em] leading-tight font-semibold whitespace-nowrap">
        <span style={{ color: regionColor(data.region) }}>{data.title}</span>
        <span className="ml-[0.5em] font-normal text-graphite tabular-nums">{data.count}</span>
      </p>
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
  return (
    <>
      <BaseEdge
        path={path}
        markerEnd={markerEnd}
        interactionWidth={14}
        style={{
          stroke: 'var(--color-graphite)',
          strokeWidth: emphasised || selected ? 2.5 : 1.25,
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
  const { view, flow, graph, graphModel, selection, select, highlight, clearHighlight, cited, truth, overlay, setOverlay, graphScope, setGraphScope } =
    useRunPanels()
  const { fitView } = useReactFlow()
  const measured = useNodesInitialized()
  const running = view.status === 'running'
  // Until the reader picks a scope, the graph narrows to the cited evidence once there is a verdict.
  const scope = graphScope ?? (view.report ? 'cited' : 'connected')
  const [settled, setSettled] = useState<{ shape: Shape | null; scope: GraphScope; positions: Map<string, Point> }>({
    shape: null,
    scope,
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
    // The graph holds everything the whole run touches; draw only what exists at this point of the run.
    const present = (id: string) =>
      view.touched.has(id) || cited.nodeIds.has(id) || cited.edgeIds.has(id) || highlight.nodeIds.has(id) || highlight.edgeIds.has(id) || graph.expanded.has(id) || id === selectedId
    const drawable = [...graph.edges.values()].filter((e) => present(e.id) && graph.nodes.has(e.src) && graph.nodes.has(e.dst))
    const linked = new Set(drawable.flatMap((e) => [e.src, e.dst]))
    const keep = (node: GraphNode) =>
      cited.nodeIds.has(node.id) ||
      highlight.nodeIds.has(node.id) ||
      node.id === selectedId ||
      (scope !== 'cited' && linked.has(node.id)) ||
      (scope === 'all' && present(node.id))
    const nodes = [...graph.nodes.values()].filter(keep)
    const shown = new Set(nodes.map((n) => n.id))
    const edges = drawable.filter((e) => shown.has(e.src) && shown.has(e.dst))
    return { nodes, edges }
  }, [graph.nodes, graph.edges, graph.expanded, view.touched, scope, cited, highlight, selectedId])

  // Derived state: when the graph grows, settle the layout once, starting from where nodes were.
  // A new scope is a different picture, so it is laid out afresh to fit its own nodes.
  let placed = settled.positions
  if (settled.shape !== shape) {
    placed = layoutGraph(
      graphModel.regions,
      shape.nodes.map((n) => ({ id: n.id, region: graphModel.labelStyle(n.label).region })),
      shape.edges.map((e) => ({ source: e.src, target: e.dst })),
      settled.scope === scope ? settled.positions : new Map(),
    )
    setSettled({ shape, scope, positions: placed })
  }

  const { nodes: built, edges, shownRegions } = useMemo(() => {
    const solution = new Set(overlay ? (truth?.solution_node_ids ?? []) : [])
    const decoy = new Set(overlay ? (truth?.decoy_node_ids ?? []) : [])
    const columns = columnsFor(graphModel.regions, shape.nodes.map((n) => ({ region: graphModel.labelStyle(n.label).region })))
    const shownRegions = graphModel.regions.filter(({ id }) => columns[id])
    const bands: BandNode[] = shownRegions.map(({ id, title }) => {
      const inside = shape.nodes.filter((n) => graphModel.labelStyle(n.label).region === id)
      const bounds = bandBounds(columns[id]!, inside.map((n) => placed.get(n.id)!))
      return {
        id: `band-${id}`,
        type: 'band',
        position: { x: bounds.x, y: bounds.y },
        data: { region: id, title, count: inside.length },
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
        position: { x: at.x - NODE_RADIUS - 28, y: at.y - NODE_RADIUS },
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
    return { nodes: [...bands, ...entities], edges: links, shownRegions }
  }, [shape, placed, focus, selectedId, cited, truth, overlay, running, view.touched, highlight, graphModel])
  const { nodes, onNodesChange } = useMeasuredNodes(built)

  // Frame the graph when it grows, the cited set changes or the pane is resized; not on every selection.
  // Both keys are strings so the effect compares by value rather than by array identity.
  const citedShown = chipFocus ? [...highlight.nodeIds].filter((id) => graph.nodes.has(id)).join(',') : ''
  const nodeCount = shape.nodes.length
  const paneWidth = useStore((state) => state.width)
  const paneHeight = useStore((state) => state.height)
  useEffect(() => {
    if (!measured) return
    const onto = citedShown ? citedShown.split(',').map((id) => ({ id })) : undefined
    const timer = setTimeout(() => void fitView({ duration: 300, padding: 0.12, nodes: onto }), 200)
    return () => clearTimeout(timer)
  }, [nodeCount, citedShown, measured, paneWidth, paneHeight, fitView])

  const found = truth ? truth.solution_node_ids.filter((id) => view.touched.has(id)).length : 0

  return (
    <ReactFlow
      nodes={nodes}
      onNodesChange={onNodesChange}
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
              onClick={() => setGraphScope(id)}
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
        <Legend regions={shownRegions} />
        <p className="mt-1">Hover a node for its type and id. Faded: context. Double-click to expand.</p>
        {overlay && <p>Green ring: solution. Red dashed ring: decoy.</p>}
      </Panel>
    </ReactFlow>
  )
}

/** One entry per region: each region has its own hue, and the labels inside it are tints of that hue. */
function Legend({ regions }: { regions: { id: string; title: string }[] }) {
  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-0.5">
      {regions.map(({ id, title }) => (
        <li key={id} className="flex items-center gap-1">
          <span className="size-3 rounded-full" style={{ background: regionColor(id) }} />
          {title}
        </li>
      ))}
    </ul>
  )
}

export function EvidenceGraph() {
  const { view, cited } = useRunPanels()
  if (!view.touched.size && !cited.nodeIds.size) return <p className="p-4 text-graphite">Nothing discovered yet. Nodes appear as agents query the graph.</p>
  return (
    <ReactFlowProvider>
      <GraphCanvas />
    </ReactFlowProvider>
  )
}
