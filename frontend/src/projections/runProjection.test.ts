import { describe, expect, it } from 'vitest'
import type { EventEnvelope } from '../api/types'
import { projectRun, projectRunAt, projectionHash } from './runProjection'

function event(seq: number, type: string, payload: Record<string, unknown>): EventEnvelope {
  return {
    schema_version: '1.0', event_id: `e${seq}`, run_id: 'r', case_id: 'c', seq,
    span_id: 's', parent_span_id: null, ts_wall: '2026-01-01T00:00:00Z',
    ts_virtual: '2026-01-01T00:00:00Z', actor: { kind: 'graph_node', name: 'node' },
    type, summary: type, payload, refs: [],
    runtime: { config_hash: 'x', agent_runtime: 'x', model_gateway: 'x', provider: 'fake', model: 'fake', adapter_versions: {} },
    usage: { input_tokens: 0, output_tokens: 0, reasoning_tokens: 0, cached_tokens: 0, cost_usd: '0', latency_ms: 0 }, redactions: [],
  }
}

describe('projectRun advanced observability', () => {
  it('reconstructs nodes, back-edges, exchanges and safe artifacts deterministically', () => {
    const projection = projectRun([
      event(1, 'node_entered', { node: 'verify' }),
      event(2, 'verifier_check', { passed: false }),
      event(3, 'node_exited', { node: 'verify' }),
      event(4, 'edge_taken', { from: 'verify', to: 'replan', back_edge: true }),
      event(5, 'plan_updated', { plan_id: 'p', diff: { before: 1, after: 2 } }),
      event(6, 'tool_call', { call_id: 't1' }),
      event(7, 'tool_result', { call_id: 't1', status: 'success' }),
    ])
    expect(projection.completedNodes).toEqual(['verify'])
    expect(projection.takenEdges[0]).toMatchObject({ source: 'verify', target: 'replan', backEdge: true })
    expect(projection.verifier[0].payload.passed).toBe(false)
    expect(projection.plans).toHaveLength(1)
    expect(projection.tools[0].result?.seq).toBe(7)
  })

  it('does not treat a suspended auto-resume segment as the end of the run', () => {
    const projection = projectRun([
      event(1, 'wait_suspended', { wait_id: 'w1' }),
      event(2, 'termination', { final_status: 'suspended' }),
      event(3, 'wait_resumed', { wait_id: 'w1' }),
    ])
    expect(projection.terminal).toBe(false)
    expect(projection.waits).toBe(1)
  })
})

it('replaying a large trace reaches the same final projection hash as live follow', () => {
  const events = Array.from({ length: 1000 }, (_, index) => event(index + 1, index % 5 === 0 ? 'tool_call' : 'checkpoint_saved', index % 5 === 0 ? { call_id: `call-${index}` } : {}))
  const live = projectRun(events)
  const replayed = projectRunAt(events, 1000)
  expect(projectionHash(replayed)).toBe(projectionHash(live))
  expect(replayed.eventCount).toBe(1000)
})
