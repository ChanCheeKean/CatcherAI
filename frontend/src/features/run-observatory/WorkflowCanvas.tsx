import { Background, Controls, ReactFlow, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { RunProjection } from '../../projections/runProjection'

const COLUMNS: Record<string, number> = { lifecycle: 0, routing: 1, investigation: 2, governance: 3, persistence: 4 }

export function WorkflowCanvas({ projection }: { projection: RunProjection }) {
  const workflow = useQuery({ queryKey: ['workflow'], queryFn: api.workflow, staleTime: Infinity })
  if (!workflow.data) return <div className="h-64 animate-pulse bg-surface-1" />
  const nodes: Node[] = workflow.data.nodes.map((node, index) => {
    const active = projection.activeNodes.includes(node.id)
    const complete = projection.completedNodes.includes(node.id)
    return { id: node.id, position: { x: (COLUMNS[node.kind] ?? index % 5) * 190, y: (index % 6) * 78 }, data: { label: node.label }, className: `observatory-node ${active ? 'is-active' : complete ? 'is-complete' : ''}` }
  })
  const lastTaken = projection.takenEdges.at(-1)
  const edges: Edge[] = workflow.data.edges.map((edge, index) => {
    const taken = projection.takenEdges.some((item) => item.source === edge.source && item.target === edge.target)
    const active = lastTaken?.source === edge.source && lastTaken.target === edge.target
    return { id: `${edge.source}-${edge.target}-${index}`, source: edge.source, target: edge.target, label: edge.label ?? undefined, animated: active, className: `${taken ? 'is-taken' : ''} ${edge.kind === 'resume' ? 'is-back-edge' : ''}`, style: { stroke: taken ? '#34d5ef' : '#303c5c' } }
  })
  return <div className="h-72 border-b border-border bg-surface-1"><ReactFlow nodes={nodes} edges={edges} fitView minZoom={0.3} maxZoom={1.5} nodesDraggable={false} nodesConnectable={false} elementsSelectable><Background color="#232c44" gap={24} /><Controls showInteractive={false} /></ReactFlow></div>
}
