import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY } from 'd3-force'
import { GRAPH_REGIONS, type GraphRegion } from './graphModel'

const MIN_BAND_WIDTH = 420
const BAND_GAP = 24
export const NODE_RADIUS = 22

interface Column {
  centre: number
  width: number
}
type Columns = Record<GraphRegion, Column>

/** Side-by-side region columns, each wide enough for the nodes it holds (in steps, so growth rarely moves them). */
export function columnsFor(nodes: { region: GraphRegion }[]): Columns {
  const widths = GRAPH_REGIONS.map(({ id }) => {
    const count = nodes.filter((n) => n.region === id).length
    return Math.max(MIN_BAND_WIDTH, Math.ceil((Math.sqrt(count) * 80) / 120) * 120)
  })
  const total = widths.reduce((sum, w) => sum + w, 0) + BAND_GAP * (widths.length - 1)
  let left = -total / 2
  const columns = {} as Columns
  GRAPH_REGIONS.forEach(({ id }, i) => {
    columns[id] = { centre: left + widths[i] / 2, width: widths[i] }
    left += widths[i] + BAND_GAP
  })
  return columns
}

export interface Point {
  x: number
  y: number
}
interface SimNode extends Point {
  id: string
  region: GraphRegion
  vx?: number
  vy?: number
}

/**
 * Settle a force layout: links pull neighbours together, and each node is drawn toward the
 * centre of its region so clusters stay legible while regions stay separate. Nodes that were
 * placed before keep their position as the starting point, so growth never reshuffles the map.
 * Deterministic: new nodes start beside a placed neighbour (or at their region centre) at a
 * spot derived from their index, and d3-force's own random source is a fixed LCG.
 */
export function layoutGraph(
  nodes: { id: string; region: GraphRegion }[],
  edges: { source: string; target: string }[],
  previous: Map<string, Point>,
): Map<string, Point> {
  const columns = columnsFor(nodes)
  const start = new Map(previous)
  const simNodes: SimNode[] = nodes.map((node, index) => {
    const known = start.get(node.id)
    if (known) return { ...node, ...known }
    const anchor = edges
      .filter((e) => e.source === node.id || e.target === node.id)
      .map((e) => start.get(e.source === node.id ? e.target : e.source))
      .find(Boolean)
    const angle = index * 2.4
    const spread = 36 + (index % 5) * 6
    const place = {
      x: (anchor?.x ?? columns[node.region].centre) + Math.cos(angle) * spread,
      y: (anchor?.y ?? 0) + Math.sin(angle) * spread,
    }
    start.set(node.id, place)
    return { ...node, ...place }
  })

  const links = edges.map((e) => ({ source: e.source, target: e.target }))
  const simulation = forceSimulation(simNodes)
    .alpha(previous.size ? 0.4 : 1)
    .force('link', forceLink<SimNode, (typeof links)[number]>(links).id((n) => n.id).distance(78).strength(0.6))
    .force('charge', forceManyBody().strength(-170))
    .force('collide', forceCollide(NODE_RADIUS + 16))
    .force('x', forceX<SimNode>((n) => columns[n.region].centre).strength(0.06))
    .force('y', forceY(0).strength(0.05))
    .stop()
  // Clamp inside the loop, so nodes pushed against a band edge still get separated by the collision force.
  for (let i = 0; i < 280; i++) {
    simulation.tick()
    for (const n of simNodes) {
      const { centre, width } = columns[n.region]
      const limit = width / 2 - NODE_RADIUS - 8
      n.x = Math.max(centre - limit, Math.min(centre + limit, n.x))
    }
  }
  return new Map(simNodes.map((n) => [n.id, { x: n.x, y: n.y }]))
}

/** The band behind a region: a fixed column as tall as the nodes it holds. */
export function bandBounds(column: Column, positions: Point[]) {
  const ys = positions.map((p) => p.y)
  const top = Math.min(-160, ...ys) - NODE_RADIUS - 48
  const bottom = Math.max(160, ...ys) + NODE_RADIUS + 48
  return { x: column.centre - column.width / 2, y: top, width: column.width, height: bottom - top }
}
