import type { EventEnvelope } from '../api/types'

export interface RunProjection {
  eventCount: number
  currentSeq: number
  virtualNow: string | null
  toolCalls: number
  modelCalls: number
  subagentRuns: number
  memoryOps: number
  waits: number
  verifierChecks: number
  usage: {
    inputTokens: number
    outputTokens: number
    costUsd: number
  }
  terminal: boolean
  failed: boolean
  activeNodes: string[]
  completedNodes: string[]
  takenEdges: Array<{ source: string; target: string; seq: number; backEdge: boolean; branchId: string | null }>
  plans: EventEnvelope[]
  hypotheses: EventEnvelope[]
  tools: Array<{ call: EventEnvelope; result?: EventEnvelope }>
  subagents: Array<{ started: EventEnvelope; finished?: EventEnvelope }>
  skills: EventEnvelope[]
  verifier: EventEnvelope[]
  panel: EventEnvelope[]
}

const EMPTY: RunProjection = {
  eventCount: 0,
  currentSeq: 0,
  virtualNow: null,
  toolCalls: 0,
  modelCalls: 0,
  subagentRuns: 0,
  memoryOps: 0,
  waits: 0,
  verifierChecks: 0,
  usage: { inputTokens: 0, outputTokens: 0, costUsd: 0 },
  terminal: false,
  failed: false,
  activeNodes: [], completedNodes: [], takenEdges: [], plans: [], hypotheses: [], tools: [],
  subagents: [], skills: [], verifier: [], panel: [],
}

/**
 * A pure, deterministic reducer over the canonical event log. Replaying the same prefix always
 * yields the same projection, whether the events arrived live or from a historical page — this is
 * the "live and replay are the same view" principle from the design doc, kept intentionally small
 * for Stage 3 (workflow/graph/memory projections land in Stage 4).
 */
export function projectRun(events: EventEnvelope[]): RunProjection {
  const projection: RunProjection = {
    ...EMPTY,
    usage: { ...EMPTY.usage },
    activeNodes: [], completedNodes: [], takenEdges: [], plans: [], hypotheses: [], tools: [],
    subagents: [], skills: [], verifier: [], panel: [],
  }

  const toolById = new Map<string, number>()
  const subagentById = new Map<string, number>()

  for (const event of events) {
    projection.eventCount += 1
    projection.currentSeq = Math.max(projection.currentSeq, event.seq)
    projection.virtualNow = event.ts_virtual

    switch (event.type) {
      case 'tool_call':
        projection.toolCalls += 1
        projection.tools.push({ call: event })
        toolById.set(String(event.payload.call_id), projection.tools.length - 1)
        break
      case 'tool_result': {
        const index = toolById.get(String(event.payload.call_id))
        if (index !== undefined) projection.tools[index].result = event
        break
      }
      case 'llm_call_started':
        projection.modelCalls += 1
        break
      case 'subagent_started':
        projection.subagentRuns += 1
        projection.subagents.push({ started: event })
        subagentById.set(String(event.payload.task_id ?? event.payload.subagent_id ?? event.span_id), projection.subagents.length - 1)
        break
      case 'subagent_finished': {
        const key = String(event.payload.task_id ?? event.payload.subagent_id ?? event.span_id)
        const index = subagentById.get(key)
        if (index !== undefined) projection.subagents[index].finished = event
        break
      }
      case 'node_entered': {
        const node = String(event.payload.node)
        if (!projection.activeNodes.includes(node)) projection.activeNodes.push(node)
        break
      }
      case 'node_exited': {
        const node = String(event.payload.node)
        projection.activeNodes = projection.activeNodes.filter((item) => item !== node)
        if (!projection.completedNodes.includes(node)) projection.completedNodes.push(node)
        break
      }
      case 'edge_taken':
        projection.takenEdges.push({ source: String(event.payload.from), target: String(event.payload.to), seq: event.seq, backEdge: event.payload.back_edge === true, branchId: event.payload.branch_id ? String(event.payload.branch_id) : null })
        break
      case 'plan_created': case 'plan_updated': case 'todo_updated':
        projection.plans.push(event)
        break
      case 'hypothesis_updated': case 'contradiction_detected':
        projection.hypotheses.push(event)
        break
      case 'skill_loaded': projection.skills.push(event); break
      case 'memory_read':
      case 'memory_write':
        projection.memoryOps += 1
        break
      case 'wait_suspended':
        projection.waits += 1
        break
      case 'verifier_check':
        projection.verifierChecks += 1
        projection.verifier.push(event)
        break
      case 'panel_position': case 'adjudication': projection.panel.push(event); break
      case 'termination':
        // A suspend/resume segment also emits `termination(final_status="suspended")`; it is not
        // the end of the run when auto-resume continues the same canonical stream.
        projection.terminal = ['decided', 'cancelled', 'ranked', 'failed'].includes(
          String(event.payload.final_status),
        )
        if (event.payload.final_status === 'failed') projection.failed = true
        break
      case 'error':
        projection.failed = true
        break
      default:
        break
    }

    projection.usage.inputTokens += event.usage.input_tokens
    projection.usage.outputTokens += event.usage.output_tokens
    projection.usage.costUsd += Number(event.usage.cost_usd)
  }

  return projection
}
