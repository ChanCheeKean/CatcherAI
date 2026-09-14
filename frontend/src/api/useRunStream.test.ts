import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useRunStream } from './useRunStream'
import type { EventEnvelope } from './types'

function envelope(seq: number, type = 'node_entered'): EventEnvelope {
  return {
    schema_version: '1.0',
    event_id: `evt-${seq}`,
    run_id: 'run-1',
    case_id: 'DSP-1',
    seq,
    span_id: 'span-1',
    parent_span_id: null,
    ts_wall: '2026-01-01T00:00:00Z',
    ts_virtual: '2026-01-01T00:00:00Z',
    actor: { kind: 'graph_node', name: 'route' },
    type,
    summary: `event ${seq}`,
    payload: {},
    refs: [],
    runtime: {
      config_hash: 'x',
      agent_runtime: 'x',
      model_gateway: 'x',
      provider: 'fake',
      model: 'fake',
      adapter_versions: {},
    },
    usage: { input_tokens: 0, output_tokens: 0, reasoning_tokens: 0, cached_tokens: 0, cost_usd: '0', latency_ms: 0 },
    redactions: [],
  }
}

function sseFrame(event: EventEnvelope): string {
  return `id: ${event.seq}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`
}

function streamResponse(events: EventEnvelope[]): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      const encoder = new TextEncoder()
      for (const event of events) controller.enqueue(encoder.encode(sseFrame(event)))
      controller.close()
    },
  })
  return new Response(body, { status: 200 })
}

describe('useRunStream', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('merges the REST snapshot with streamed events in seq order, de-duplicated', async () => {
    const fetchMock = vi.fn<typeof fetch>()
    // 1. REST snapshot: events 1 and 2 already committed.
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [envelope(1), envelope(2)], next_after_seq: 2, limit: 500 })),
    )
    // 2. SSE tail: event 2 arrives again (races with the snapshot) then a new event 3.
    fetchMock.mockResolvedValueOnce(streamResponse([envelope(2), envelope(3)]))
    // 3. Status check after the stream closes: the run is done, so the hook should stop.
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ run_id: 'run-1', case_id: 'DSP-1', status: 'decided', event_count: 3, first_seq: 1, last_seq: 3, started_at: null, last_event_at: null, virtual_now: null, wait: null, decision_available: true })),
    )
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderHook(() => useRunStream('run-1'))

    await waitFor(() => expect(result.current.status).toBe('closed'))

    expect(result.current.events.map((event) => event.seq)).toEqual([1, 2, 3])
  })

  it('resets to idle when no run is selected', () => {
    const { result } = renderHook(() => useRunStream(null))
    expect(result.current.status).toBe('idle')
    expect(result.current.events).toEqual([])
  })
})
