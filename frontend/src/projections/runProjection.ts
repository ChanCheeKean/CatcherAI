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
  }

  for (const event of events) {
    projection.eventCount += 1
    projection.currentSeq = Math.max(projection.currentSeq, event.seq)
    projection.virtualNow = event.ts_virtual

    switch (event.type) {
      case 'tool_call':
        projection.toolCalls += 1
        break
      case 'llm_call_started':
        projection.modelCalls += 1
        break
      case 'subagent_started':
        projection.subagentRuns += 1
        break
      case 'memory_read':
      case 'memory_write':
        projection.memoryOps += 1
        break
      case 'wait_suspended':
        projection.waits += 1
        break
      case 'verifier_check':
        projection.verifierChecks += 1
        break
      case 'termination':
        projection.terminal = true
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
