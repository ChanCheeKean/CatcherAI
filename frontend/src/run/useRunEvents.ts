import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type { TrajectoryEvent } from '../api/types'
import { emptyRun, isFinal, reduceEvent, type RunView } from './store'

const EVENT_TYPES = [
  'run_started', 'triage', 'plan_updated', 'supervisor_turn', 'delegation_started',
  'delegation_finished', 'skill_loaded', 'tool_call', 'tool_result', 'notebook_write',
  'memory_write', 'decision', 'termination', 'node_entered', 'node_exited', 'edge_taken',
  'model_call', 'error',
] as const

export interface RunStream {
  /** Every event received so far, in sequence order and without repeats. */
  events: TrajectoryEvent[]
  /** Whether the run's last event has arrived: a finished run can be replayed. */
  finished: boolean
  /** Why the run stopped, when the server reports it failed without sending an error event. */
  failure: string | null
}

/**
 * Follow a run's trajectory over SSE (the run page is keyed by run, so each run starts fresh).
 * The browser reconnects with `Last-Event-ID` on its own, so the hook only decides when to stop:
 * after the run's final event, or when the server says the run is no longer active.
 */
export function useRunEvents(runId: string): RunStream {
  const [stream, setStream] = useState<RunStream>({ events: [], finished: false, failure: null })

  useEffect(() => {
    const source = new EventSource(api.eventsUrl(runId))
    const handle = (message: MessageEvent<string>) => {
      const event = JSON.parse(message.data) as TrajectoryEvent
      const final = isFinal(event)
      setStream((prev) =>
        prev.events.some((seen) => seen.seq === event.seq)
          ? prev
          : { ...prev, events: [...prev.events, event], finished: prev.finished || final },
      )
      if (final) source.close()
    }
    for (const type of EVENT_TYPES) source.addEventListener(type, handle as EventListener)
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) return
      void api.getRun(runId).then((run) => {
        if (run.status === 'running') return
        source.close()
        if (run.status === 'failed') setStream((prev) => ({ ...prev, failure: run.error ?? 'The run stopped unexpectedly.' }))
      })
    }
    return () => source.close()
  }, [runId])

  return stream
}

/** The run as it stood after its first `cursor` events; stepping forward folds only the new ones. */
export function useRunView({ events, failure }: RunStream, cursor: number): RunView {
  const [folded, setFolded] = useState({ count: 0, view: emptyRun() })
  const target = Math.min(cursor, events.length)
  let { view } = folded
  // Derived state: fold forward from where the last render stopped, or from the start after a step back.
  if (target !== folded.count) {
    const from = target < folded.count ? 0 : folded.count
    if (from === 0) view = emptyRun()
    for (let i = from; i < target; i++) view = reduceEvent(view, events[i])
    setFolded({ count: target, view })
  }
  return useMemo(() => (failure ? { ...view, status: 'failed', error: failure } : view), [view, failure])
}
