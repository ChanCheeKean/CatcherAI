import { Background, Controls, ReactFlow, type Edge, type Node } from '@xyflow/react'
import type { GraphResponse } from '../../api/types'

export function EntityGraph({ graph }: { graph: GraphResponse }) {
  const nodes: Node[] = graph.nodes.map((node, index) => ({ id: node.id, position: { x: (index % 6) * 190, y: Math.floor(index / 6) * 110 }, data: { label: <><span className="block text-[10px] uppercase text-ink-faint">{node.kind}</span><span>{node.label}</span></> }, className: `observatory-node entity-${node.kind.toLowerCase()}` }))
  const edges: Edge[] = graph.edges.map((edge) => ({ id: edge.id, source: edge.source, target: edge.target, label: edge.label, style: { stroke: '#647090' }, labelStyle: { fill: '#97a1bc', fontSize: 9 } }))
  return <div className="h-[560px] rounded-lg border border-border bg-surface-1"><ReactFlow nodes={nodes} edges={edges} fitView minZoom={0.15} maxZoom={1.5} nodesDraggable={false} nodesConnectable={false}><Background color="#232c44" gap={24} /><Controls showInteractive={false} /></ReactFlow></div>
}
