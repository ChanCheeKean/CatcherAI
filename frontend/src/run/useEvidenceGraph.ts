import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { GraphEdge, GraphNode } from '../api/types'
import { fromNeighbor } from './graphModel'

interface GraphData {
  nodes: Map<string, GraphNode>
  edges: Map<string, GraphEdge>
  /** Node and edge ids the reader pulled in by expanding a node, rather than ids the run touched. */
  expanded: Set<string>
}

export interface EvidenceGraph extends GraphData {
  /** Pull a node's one-hop neighbourhood into the map as context. */
  expand: (id: string) => Promise<void>
}

const EMPTY: GraphData = { nodes: new Map(), edges: new Map(), expanded: new Set() }
const BATCH = 120
const SETTLE_MS = 250

/**
 * The evidence graph of a run: properties of every id asked for (what the run touches, plus anything a
 * conclusion cites), fetched in batches, and the edge endpoints that come with them. It only grows;
 * what is drawn at a point of a replay is the caller's choice.
 */
export function useEvidenceGraph(ids: string[]): EvidenceGraph {
  const [data, setData] = useState<GraphData>(EMPTY)
  const asked = useRef(new Set<string>())
  const wanted = ids.join(',')

  const merge = useCallback((nodes: GraphNode[], edges: GraphEdge[], expanded = false) => {
    setData((prev) => ({
      nodes: new Map([...prev.nodes, ...nodes.map((n) => [n.id, n] as const)]),
      edges: new Map([...prev.edges, ...edges.map((e) => [e.id, e] as const)]),
      expanded: expanded ? new Set([...prev.expanded, ...nodes.map((n) => n.id), ...edges.map((e) => e.id)]) : prev.expanded,
    }))
  }, [])

  useEffect(() => {
    const need = [...new Set([...wanted.split(',').filter(Boolean), ...endpointsMissing(data)])].filter(
      (id) => !asked.current.has(id) && !data.nodes.has(id) && !data.edges.has(id),
    )
    if (!need.length) return
    const timer = setTimeout(() => {
      need.forEach((id) => asked.current.add(id))
      for (let i = 0; i < need.length; i += BATCH) {
        api
          .graphElements(need.slice(i, i + BATCH))
          .then((found) => merge(found.nodes, found.edges))
          .catch(() => need.slice(i, i + BATCH).forEach((id) => asked.current.delete(id)))
      }
    }, SETTLE_MS)
    return () => clearTimeout(timer)
  }, [wanted, data, merge])

  const expand = useCallback(
    async (id: string) => {
      const { neighbors } = await api.neighbors(id)
      const hits = neighbors.map((hit) => fromNeighbor(id, hit))
      merge(
        hits.map((h) => h.node),
        hits.map((h) => h.edge),
        true,
      )
    },
    [merge],
  )

  return { ...data, expand }
}

const endpointsMissing = (data: GraphData) =>
  [...data.edges.values()].flatMap((e) => [e.src, e.dst]).filter((id) => !data.nodes.has(id))
