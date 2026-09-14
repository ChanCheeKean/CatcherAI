import { useEffect, useState } from 'react'
import { api } from './client'
import type { EventEnvelope } from './types'

export type StreamStatus = 'idle' | 'connecting' | 'open' | 'closed' | 'error'

interface UseRunStreamResult {
  events: EventEnvelope[]
  status: StreamStatus
}

const RECONNECT_DELAY_MS = 1000
const TERMINAL_STATUSES = new Set(['decided', 'cancelled', 'failed', 'ranked'])

/**
 * Follows a run's canonical event log. Fetches the current REST snapshot first (so a completed run
 * renders instantly without opening a stream), then tails `/events/stream` for anything still to
 * come. Parses the SSE frames by hand with `fetch`/`ReadableStream` rather than `EventSource`: the
 * backend names each frame's `event:` field after the canonical event type (`tool_call`,
 * `termination`, …), and that vocabulary grows over time, so a fixed set of
 * `addEventListener` calls would silently drop any type this build doesn't know about yet.
 */
export function useRunStream(runId: string | null): UseRunStreamResult {
  const [events, setEvents] = useState<EventEnvelope[]>([])
  const [status, setStatus] = useState<StreamStatus>('idle')

  useEffect(() => {
    setEvents([])
    if (!runId) {
      setStatus('idle')
      return
    }

    let cancelled = false
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined
    const seenSeqs = new Set<number>()
    setStatus('connecting')

    function append(envelope: EventEnvelope) {
      if (seenSeqs.has(envelope.seq)) return
      seenSeqs.add(envelope.seq)
      setEvents((prev) => [...prev, envelope].sort((a, b) => a.seq - b.seq))
    }

    async function isRunFinished(): Promise<boolean> {
      try {
        const summary = await api.getRun(runId!)
        return TERMINAL_STATUSES.has(summary.status)
      } catch {
        return false
      }
    }

    async function tailOnce(afterSeq: number): Promise<number> {
      const response = await fetch(api.runStreamUrl(runId!, afterSeq))
      if (!response.body) throw new Error('stream response had no body')
      setStatus('open')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let lastSeq = afterSeq
      let dataLines: string[] = []

      const flush = () => {
        if (dataLines.length === 0) return
        try {
          const envelope = JSON.parse(dataLines.join('\n')) as EventEnvelope
          append(envelope)
          lastSeq = envelope.seq
        } catch {
          // Ignore malformed frames rather than crashing the stream.
        }
        dataLines = []
      }

      while (!cancelled) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (line === '') {
            flush()
          } else if (line.startsWith('data:')) {
            dataLines.push(line.slice(5).trimStart())
          }
          // `id:`/`event:` lines are informational here — `seq` inside the payload is authoritative.
        }
      }
      flush()
      return lastSeq
    }

    async function run() {
      let afterSeq = 0
      try {
        const page = await api.getRunEvents(runId!, 0, 500)
        if (cancelled) return
        page.items.forEach(append)
        afterSeq = page.items.at(-1)?.seq ?? 0
      } catch {
        if (!cancelled) setStatus('error')
        return
      }

      while (!cancelled) {
        try {
          afterSeq = await tailOnce(afterSeq)
        } catch {
          if (cancelled) return
          setStatus('error')
        }
        if (cancelled) return
        if (await isRunFinished()) {
          setStatus('closed')
          return
        }
        await new Promise<void>((resolve) => {
          reconnectTimer = setTimeout(resolve, RECONNECT_DELAY_MS)
        })
      }
    }

    void run()

    return () => {
      cancelled = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
    }
  }, [runId])

  return { events, status }
}
