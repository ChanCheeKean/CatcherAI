import type { Node, NodeChange } from '@xyflow/react'
import { useCallback, useMemo, useState } from 'react'

type Size = { width: number; height: number }

/**
 * Nodes rebuilt on every render lose the size React Flow measured, and an unmeasured node stays
 * hidden. Keep the measured sizes here and hand them back on each rebuilt node, as a replay
 * rebuilds the nodes many times a second.
 */
export function useMeasuredNodes<N extends Node>(nodes: N[]): { nodes: N[]; onNodesChange: (changes: NodeChange<N>[]) => void } {
  const [sizes, setSizes] = useState<Map<string, Size>>(new Map())
  const onNodesChange = useCallback((changes: NodeChange<N>[]) => {
    const measured = changes.flatMap((change) => (change.type === 'dimensions' && change.dimensions ? [[change.id, change.dimensions] as const] : []))
    if (measured.length) setSizes((prev) => new Map([...prev, ...measured]))
  }, [])
  const withSizes = useMemo(() => nodes.map((node) => (sizes.has(node.id) ? { ...node, measured: sizes.get(node.id) } : node)), [nodes, sizes])
  return { nodes: withSizes, onNodesChange }
}
