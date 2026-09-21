import type { PlanItem, TrajectoryEvent } from '../api/types'

export type Region = 'planning' | 'investigation' | 'tools' | 'decision'
export const REGIONS: { id: Region; title: string }[] = [
  { id: 'planning', title: 'Planning' },
  { id: 'investigation', title: 'Investigation' },
  { id: 'tools', title: 'Tools and memory' },
  { id: 'decision', title: 'Decision' },
]

export interface ToolCall {
  seq: number
  tool: string
  callId: string
  args: unknown
  result: unknown
  nodeIds: string[]
  edgeIds: string[]
}

/** One entry of an agent node, from node_entered to node_exited. */
export interface Visit {
  actor: string
  visit: number
  turn: number
  parentId: string | null
  input: unknown
  output: unknown
  startedAt: string
  durationMs: number | null
  tokens: number
  skills: string[]
  tools: ToolCall[]
  /** Plan as it stood when the supervisor finished this turn. */
  plan: PlanItem[] | null
  /** Why the run left this node, from edge_taken (e.g. "decided by supervisor"). */
  exits: string[]
}

export interface FlowNode {
  id: string
  kind: 'agent' | 'tool'
  region: Region
  visits: number
  adHoc: boolean
  /** Position within its region; nodes are appended in order of first appearance. */
  order: number
}

export interface FlowEdge {
  id: string
  source: string
  target: string
  kind: 'forward' | 'return' | 'self' | 'tool' | 'decision'
  count: number
  /** The agent whose LLM decision took this edge, when there is one. */
  decidedBy: string | null
  /** Most recent reason given by the runtime for taking the edge. */
  reason: string
}

export interface Flow {
  nodes: FlowNode[]
  edges: FlowEdge[]
  visits: Map<string, Visit[]>
  toolCalls: Map<string, (ToolCall & { caller: string; visit: number })[]>
  /** Nodes with a visit that has started but not yet finished. */
  active: Set<string>
  lastEdge: string | null
}

const FIXED_REGION: Record<string, Region> = {
  triage: 'planning',
  supervisor: 'planning',
  adjudicator: 'decision',
  consolidate_memory: 'decision',
}

const visitKey = (actor: string, visit: number) => `${actor}#${visit}`

/** Tool calls made by the memory step report the memory_keeper role, but belong to consolidate_memory. */
const nodeOfCaller = (caller: string, parentId: string | null) =>
  !parentId && caller === 'memory_keeper' ? 'consolidate_memory' : caller

function edgeKind(source: string, target: string): FlowEdge['kind'] {
  if (source === target) return 'self'
  if (target === 'supervisor' && source !== 'triage') return 'return'
  if (target === 'adjudicator') return 'decision'
  return 'forward'
}

function append<T>(map: Map<string, T[]>, key: string, value: T): void {
  const list = map.get(key)
  if (list) list.push(value)
  else map.set(key, [value])
}

/** Build the agent map from trajectory events alone; the same events always give the same map. */
export function deriveFlow(events: TrajectoryEvent[]): Flow {
  const visitsByKey = new Map<string, Visit>()
  const visits = new Map<string, Visit[]>()
  const toolCalls: Flow['toolCalls'] = new Map()
  const nodes = new Map<string, FlowNode>()
  const edges = new Map<string, FlowEdge>()
  const activeKeys = new Set<string>()
  const counters: Record<Region, number> = { planning: 0, investigation: 0, tools: 0, decision: 0 }
  let plan: PlanItem[] = []
  let lastEdge: string | null = null

  const touchNode = (id: string, kind: FlowNode['kind'], region: Region): FlowNode => {
    let node = nodes.get(id)
    if (!node) {
      node = { id, kind, region, visits: 0, adHoc: false, order: counters[region]++ }
      nodes.set(id, node)
    }
    return node
  }
  const touchEdge = (source: string, target: string, kind: FlowEdge['kind']): FlowEdge => {
    const id = `${source}>${target}`
    let edge = edges.get(id)
    if (!edge) {
      edge = { id, source, target, kind, count: 0, decidedBy: null, reason: '' }
      edges.set(id, edge)
    }
    return edge
  }
  const startVisit = (event: TrajectoryEvent): Visit => {
    const { name } = event.actor
    const key = visitKey(name, event.visit)
    let visit = visitsByKey.get(key)
    if (!visit) {
      visit = {
        actor: name,
        visit: event.visit,
        turn: event.turn,
        parentId: event.parent_id,
        input: null,
        output: null,
        startedAt: event.ts_wall,
        durationMs: null,
        tokens: 0,
        skills: [],
        tools: [],
        plan: null,
        exits: [],
      }
      visitsByKey.set(key, visit)
      append(visits, name, visit)
      touchNode(name, 'agent', FIXED_REGION[name] ?? 'investigation').visits += 1
    }
    return visit
  }

  for (const event of events) {
    const { payload } = event
    const name = event.actor.name

    if (event.type === 'node_entered') {
      const visit = startVisit(event)
      visit.input = payload.input
      visit.startedAt = event.ts_wall
      activeKeys.add(visitKey(name, event.visit))
    } else if (event.type === 'node_exited') {
      const visit = startVisit(event)
      visit.output = payload.output
      visit.durationMs = Date.parse(event.ts_wall) - Date.parse(visit.startedAt)
      if (name === 'triage' || name === 'supervisor') visit.plan = plan
      activeKeys.delete(visitKey(name, event.visit))
    } else if (event.type === 'delegation_started') {
      const task = payload.task as { instructions?: string | null }
      const node = touchNode(name, 'agent', 'investigation')
      if (task.instructions) node.adHoc = true
    } else if (event.type === 'triage' || event.type === 'plan_updated') {
      plan = payload.plan as PlanItem[]
    } else if (event.type === 'skill_loaded') {
      visitsByKey.get(visitKey(nodeOfCaller(name, event.parent_id), event.visit))?.skills.push(String(payload.skill))
    } else if (event.type === 'model_call') {
      const { input_tokens, output_tokens } = payload as { input_tokens?: number; output_tokens?: number }
      const visit = visitsByKey.get(visitKey(name, event.visit))
      if (visit) visit.tokens += (input_tokens ?? 0) + (output_tokens ?? 0)
    } else if (event.type === 'tool_call') {
      const caller = nodeOfCaller(String(payload.caller), event.parent_id)
      const tool = String(payload.tool)
      const call: ToolCall = {
        seq: event.seq,
        tool,
        callId: String(payload.call_id),
        args: payload.args,
        result: null,
        nodeIds: [],
        edgeIds: [],
      }
      visitsByKey.get(visitKey(caller, event.visit))?.tools.push(call)
      append(toolCalls, tool, { ...call, caller, visit: event.visit })
      touchNode(tool, 'tool', 'tools').visits += 1
      touchEdge(caller, tool, 'tool').count += 1
    } else if (event.type === 'tool_result') {
      const caller = nodeOfCaller(String(payload.caller), event.parent_id)
      const call = visitsByKey
        .get(visitKey(caller, event.visit))
        ?.tools.find((c) => c.callId === payload.call_id)
      const shared = toolCalls.get(String(payload.tool))?.find((c) => c.callId === payload.call_id)
      for (const target of [call, shared]) {
        if (!target) continue
        target.result = payload.result
        target.nodeIds = payload.node_ids as string[]
        target.edgeIds = payload.edge_ids as string[]
      }
    } else if (event.type === 'edge_taken') {
      const { source, target, reason } = payload as { source: string; target: string; reason: string }
      if (target === 'end') continue
      const edge = touchEdge(source, target, edgeKind(source, target))
      edge.count += 1
      edge.reason = reason
      if (source === 'supervisor' && edge.kind === 'forward') edge.decidedBy = 'supervisor'
      lastEdge = edge.id
      visitsByKey.get(visitKey(source, event.visit))?.exits.push(reason)
    }
  }

  return {
    nodes: [...nodes.values()],
    edges: [...edges.values()],
    visits,
    toolCalls,
    active: new Set([...activeKeys].map((key) => key.slice(0, key.lastIndexOf('#')))),
    lastEdge,
  }
}

export const NODE_SIZE = { width: 184, height: 60 }
export const TOOL_SIZE = { width: 176, height: 40 }
/** Width of one slot: a node plus the corridor that arrows pass through. */
const SLOT = 240
const ROW = NODE_SIZE.height + 22
const HEADER = 44
/** Investigation wraps into another slot after this many roles; the other regions stay one slot wide. */
export const ROLES_PER_SLOT = 6

/**
 * Regions sit left to right, nodes stack by first appearance, and nothing moves once placed. The only
 * shift is the regions right of Investigation moving over by one slot when it wraps.
 */
export function layout(nodes: FlowNode[]) {
  const count = (region: Region) => nodes.filter((n) => n.region === region).length
  const slots = (region: Region) =>
    region === 'investigation' ? Math.max(1, Math.ceil(count(region) / ROLES_PER_SLOT)) : 1
  const rows = (region: Region) => (region === 'investigation' ? Math.min(count(region), ROLES_PER_SLOT) : count(region))

  const height = HEADER + Math.max(1, ...REGIONS.map((r) => rows(r.id))) * ROW + 12
  const left = new Map<Region, number>()
  let x = 0
  for (const { id } of REGIONS) {
    left.set(id, x)
    x += slots(id) * SLOT
  }

  const position = (node: FlowNode) => {
    const size = node.kind === 'tool' ? TOOL_SIZE : NODE_SIZE
    const perSlot = node.region === 'investigation' ? ROLES_PER_SLOT : Infinity
    return {
      x: left.get(node.region)! + Math.floor(node.order / perSlot) * SLOT + (SLOT - size.width) / 2,
      y: HEADER + (node.order % perSlot) * ROW + (NODE_SIZE.height - size.height) / 2,
    }
  }
  const regions = REGIONS.map((region) => ({
    ...region,
    x: left.get(region.id)! + 6,
    width: slots(region.id) * SLOT - 12,
    height,
  }))
  return { position, regions, height }
}
