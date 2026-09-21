import {
  BaseEdge,
  Background,
  EdgeLabelRenderer,
  getBezierPath,
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
import { useEffect, useMemo } from 'react'
import { words } from './format'
import { layout, NODE_SIZE, REGIONS, TOOL_SIZE, type Flow, type FlowEdge, type FlowNode } from './flow'
import { useRunPanels } from './RunContext'

interface NodeData extends Record<string, unknown> {
  flow: FlowNode
  subtitle: string
  loops: number
  active: boolean
  selected: boolean
}
type FlowNodeType = Node<NodeData, 'agent' | 'tool'>
type RegionNodeType = Node<{ title: string }, 'region'>

interface EdgeData extends Record<string, unknown> {
  flow: FlowEdge
  routeY: number
  animated: boolean
  /** Whether the selected node is one of this edge's ends; null when nothing is selected. */
  related: boolean | null
  /** Many edges on screen: quieten them until a node is selected. */
  crowded: boolean
}
type FlowEdgeType = Edge<EdgeData, 'flow'>

const invisible = { opacity: 0, pointerEvents: 'none' } as const

/** Every agent node offers the same anchors; each edge picks the ones that keep arrows out of the way. */
function AgentAnchors() {
  return (
    <>
      <Handle id="l" type="target" position={Position.Left} style={{ ...invisible, top: '35%' }} />
      <Handle id="lo" type="source" position={Position.Left} style={{ ...invisible, top: '75%' }} />
      <Handle id="r" type="source" position={Position.Right} style={{ ...invisible, top: '35%' }} />
      <Handle id="ri" type="target" position={Position.Right} style={{ ...invisible, top: '75%' }} />
      <Handle id="ti" type="target" position={Position.Top} style={invisible} />
      <Handle id="bo" type="source" position={Position.Bottom} style={invisible} />
      <Handle id="sl-out" type="source" position={Position.Left} style={{ ...invisible, top: '30%' }} />
      <Handle id="sl-in" type="target" position={Position.Left} style={{ ...invisible, top: '70%' }} />
    </>
  )
}

function AgentNode({ data }: NodeProps<FlowNodeType>) {
  const { flow, subtitle, loops, active, selected } = data
  return (
    <div
      style={{ width: NODE_SIZE.width, height: NODE_SIZE.height }}
      className={`flex cursor-pointer flex-col justify-center rounded-sm border bg-vellum px-3 shadow-[0_1px_0_var(--color-rule)] ${
        flow.adHoc ? 'border-dashed border-graphite' : ''
      } ${selected ? 'outline-2 outline-ink' : ''} ${active ? 'pulse' : ''}`}
    >
      <AgentAnchors />
      <div className="flex items-baseline gap-2">
        <span className="truncate text-sm font-semibold" title={flow.id}>
          {words(flow.id)}
        </span>
        <span className="ml-auto text-xs text-graphite tabular-nums">×{flow.visits}</span>
      </div>
      <div className="flex items-center gap-1.5 text-xs text-graphite">
        {flow.adHoc && <span className="rounded-sm border border-graphite px-1 whitespace-nowrap">ad hoc</span>}
        {loops > 0 && <span title="Decide was rejected while plan items were open">↻ {loops} rejected</span>}
        <span className="truncate" title={subtitle}>
          {subtitle}
        </span>
      </div>
    </div>
  )
}

function ToolNode({ data }: NodeProps<FlowNodeType>) {
  const { flow, active, selected } = data
  return (
    <div
      style={{ width: TOOL_SIZE.width, height: TOOL_SIZE.height }}
      className={`flex cursor-pointer items-center gap-2 rounded-full border bg-paper px-3 ${
        selected ? 'outline-2 outline-ink' : ''
      } ${active ? 'pulse' : ''}`}
    >
      <Handle id="l" type="target" position={Position.Left} style={invisible} />
      <Handle id="rt" type="target" position={Position.Right} style={invisible} />
      <span className="id-chip truncate">{flow.id}</span>
      <span className="ml-auto text-xs text-graphite tabular-nums">×{flow.visits}</span>
    </div>
  )
}

function RegionNode({ data }: NodeProps<RegionNodeType>) {
  return <div className="size-full rounded-sm border bg-vellum/60 px-3 py-2 text-sm font-semibold text-graphite">{data.title}</div>
}

/** A polyline with rounded corners: the underpass that carries the final decision below the columns. */
function rounded(points: [number, number][], radius: number): string {
  let path = `M${points[0][0]},${points[0][1]}`
  for (let i = 1; i < points.length - 1; i++) {
    const [px, py] = points[i - 1]
    const [x, y] = points[i]
    const [nx, ny] = points[i + 1]
    const inLength = Math.hypot(x - px, y - py) || 1
    const outLength = Math.hypot(nx - x, ny - y) || 1
    const before = Math.min(radius, inLength / 2)
    const after = Math.min(radius, outLength / 2)
    path += ` L${x - ((x - px) / inLength) * before},${y - ((y - py) / inLength) * before}`
    path += ` Q${x},${y} ${x + ((nx - x) / outLength) * after},${y + ((ny - y) / outLength) * after}`
  }
  const [lastX, lastY] = points[points.length - 1]
  return `${path} L${lastX},${lastY}`
}

function FlowEdgeView(props: EdgeProps<FlowEdgeType>) {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data } = props
  const { flow, routeY, animated, related, crowded } = data!
  let path: string
  let labelX: number
  let labelY: number
  let text = ''

  if (flow.kind === 'self') {
    const bulge = 46
    path = `M${sourceX},${sourceY} C${sourceX - bulge},${sourceY} ${targetX - bulge},${targetY} ${targetX},${targetY}`
    labelX = sourceX
    labelY = sourceY
  } else if (flow.kind === 'decision') {
    const turnX = targetX - 28
    path = rounded(
      [[sourceX, sourceY], [sourceX, routeY], [turnX, routeY], [turnX, targetY], [targetX, targetY]],
      14,
    )
    labelX = (sourceX + turnX) / 2
    labelY = routeY
    // The supervisor's own reasoning is long; it is in the inspector. The map says how the run ended.
    text = flow.reason.startsWith('forced') ? flow.reason : 'Decide'
  } else {
    ;[path, labelX, labelY] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition })
    if (flow.count > 1) text = `×${flow.count}`
  }

  const dashed = flow.kind === 'return' || flow.kind === 'self'
  return (
    <>
      <BaseEdge
        id={props.id}
        path={path}
        markerEnd="url(#agent-flow-arrow)"
        style={{
          stroke: 'var(--color-graphite)',
          strokeWidth: 1 + Math.min(flow.count, 6) * 0.25,
          strokeDasharray: dashed ? '5 4' : animated ? '6 4' : undefined,
          opacity: related === null ? (crowded ? 0.5 : 1) : related ? 1 : 0.12,
        }}
        className={animated ? 'flow-edge-live' : undefined}
      />
      {text && (related || !crowded) && (
        <EdgeLabelRenderer>
          <span
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
            className="pointer-events-none absolute rounded-sm border bg-vellum px-1.5 text-xs text-ink tabular-nums"
          >
            {text}
          </span>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

const nodeTypes = { agent: AgentNode, tool: ToolNode, region: RegionNode }
const edgeTypes = { flow: FlowEdgeView }

/** Which anchors an edge uses, picked so arrows stay out of the way. */
function anchors(edge: FlowEdge, flow: Flow): { sourceHandle: string; targetHandle: string } {
  const regionIndex = (id: string) => REGIONS.findIndex((r) => r.id === flow.nodes.find((n) => n.id === id)?.region)
  switch (edge.kind) {
    case 'return':
      return { sourceHandle: 'lo', targetHandle: 'ri' }
    case 'self':
      return { sourceHandle: 'sl-out', targetHandle: 'sl-in' }
    case 'decision':
      return { sourceHandle: 'bo', targetHandle: 'l' }
    case 'tool':
      // Decision-stage agents sit right of the tools, so they reach them from the left.
      if (regionIndex(edge.source) > regionIndex(edge.target)) return { sourceHandle: 'lo', targetHandle: 'rt' }
      return { sourceHandle: 'r', targetHandle: 'l' }
    default:
      if (regionIndex(edge.source) === regionIndex(edge.target)) return { sourceHandle: 'bo', targetHandle: 'ti' }
      return { sourceHandle: 'r', targetHandle: 'l' }
  }
}

/** The one line under an agent's name: where it is, or what it was asked to do. */
function subtitleOf(name: string, flow: Flow): string {
  const last = flow.visits.get(name)?.at(-1)
  if (!last) return ''
  if (name === 'supervisor') return `Turn ${last.turn}`
  if (name === 'triage') return words(String((last.output as { case_type?: string } | null)?.case_type ?? ''))
  return String((last.input as { task?: { objective?: string } } | null)?.task?.objective ?? '')
}

function FlowCanvas({ flow, running }: { flow: Flow; running: boolean }) {
  const { selection, select } = useRunPanels()
  const { fitView } = useReactFlow()
  const measured = useNodesInitialized()
  const paneHeight = useStore((state) => state.height)
  const selected = selection?.kind === 'actor' ? selection.name : null

  const { nodes, edges } = useMemo(() => {
    const { position, regions, height } = layout(flow.nodes)
    const loops = flow.edges.find((e) => e.kind === 'self')?.count ?? 0
    const regionNodes: RegionNodeType[] = regions.map((region) => ({
      id: `region-${region.id}`,
      type: 'region',
      position: { x: region.x, y: 0 },
      data: { title: region.title },
      style: { width: region.width, height: region.height },
      draggable: false,
      selectable: false,
      focusable: false,
      zIndex: -1,
    }))
    const flowNodes: FlowNodeType[] = flow.nodes.map((node) => ({
      id: node.id,
      type: node.kind,
      position: position(node),
      data: {
        flow: node,
        subtitle: node.kind === 'agent' ? subtitleOf(node.id, flow) : '',
        loops: node.id === 'supervisor' ? loops : 0,
        active: running && flow.active.has(node.id),
        selected: node.id === selected,
      },
      draggable: false,
    }))
    const crowded = flow.edges.length > 16
    const flowEdges: FlowEdgeType[] = flow.edges.map((edge) => ({
      id: edge.id,
      type: 'flow',
      source: edge.source,
      target: edge.target,
      ...anchors(edge, flow),
      data: {
        flow: edge,
        routeY: height - 16,
        animated: running && edge.id === flow.lastEdge,
        related: selected === null ? null : edge.source === selected || edge.target === selected,
        crowded,
      },
      selectable: false,
    }))
    return { nodes: [...regionNodes, ...flowNodes], edges: flowEdges }
  }, [flow, running, selected])

  // A new node or a resized pane changes what fits; a repeat visit does not, so the view stays where the reader left it.
  const nodeCount = flow.nodes.length
  useEffect(() => {
    if (!nodeCount || !measured) return
    // Wait a beat so nodes added in this render have been measured before framing them.
    const timer = setTimeout(() => void fitView({ duration: 250, padding: 0.08 }), 150)
    return () => clearTimeout(timer)
  }, [nodeCount, measured, paneHeight, fitView])

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      fitView
      minZoom={0.2}
      nodesDraggable={false}
      nodesConnectable={false}
      onNodeClick={(_, node) => node.type !== 'region' && select({ kind: 'actor', name: node.id })}
      onPaneClick={() => select(null)}
    >
      <Background gap={24} />
      <svg width="0" height="0" aria-hidden>
        <defs>
          <marker id="agent-flow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,1 L10,5 L0,9 z" fill="var(--color-graphite)" />
          </marker>
        </defs>
      </svg>
      <Panel position="bottom-left" className="rounded-sm border bg-vellum px-2 py-1 text-xs text-graphite">
        The supervisor decides each delegation. Dashed arcs return findings to the supervisor.
      </Panel>
    </ReactFlow>
  )
}

export function AgentFlow({ flow, running }: { flow: Flow; running: boolean }) {
  if (!flow.nodes.length) return <p className="p-4 text-graphite">Waiting for the first agent to start…</p>
  return (
    <ReactFlowProvider>
      <FlowCanvas flow={flow} running={running} />
    </ReactFlowProvider>
  )
}
