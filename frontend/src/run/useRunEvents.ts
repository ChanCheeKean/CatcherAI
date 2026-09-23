import { useEffect, useReducer } from 'react'
import { api } from '../api/client'
import type { TrajectoryEvent } from '../api/types'
import { emptyRun, reduceEvent, type RunView } from './store'

const EVENT_TYPES = [
  'run_started', 'triage', 'plan_updated', 'supervisor_turn', 'delegation_started',
  'delegation_finished', 'skill_loaded', 'tool_call', 'tool_result', 'notebook_write',
  'memory_write', 'decision', 'termination', 'node_entered', 'node_exited', 'edge_taken',
  'model_call', 'error',
] as const

type Action = { event: TrajectoryEvent } | { reset: true } | { failed: string }

const reducer = (view: RunView, action: Action): RunView => {
  if ('reset' in action) return emptyRun()
  if ('failed' in action) return { ...view, status: 'failed', error: action.failed }
  return reduceEvent(view, action.event)
}

/**
 * Follow a run's trajectory over SSE. The browser reconnects with `Last-Event-ID` on its own,
 * so the hook only decides when to stop: after the run's final event, or when the server says
 * the run is no longer active.
 */
export function useRunEvents(runId: string): RunView {
  const [view, dispatch] = useReducer(reducer, undefined, emptyRun)

  useEffect(() => {
    dispatch({ reset: true })
    const source = new EventSource(api.eventsUrl(runId))
    const handle = (message: MessageEvent<string>) => {
      const event = JSON.parse(message.data) as TrajectoryEvent
      dispatch({ event })
      const finished =
        event.type === 'error' || (event.type === 'termination' && event.actor.name === 'consolidate_memory')
      if (finished) source.close()
    }
    for (const type of EVENT_TYPES) source.addEventListener(type, handle as EventListener)
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) return
      void api.getRun(runId).then((run) => {
        if (run.status === 'running') return
        source.close()
        if (run.status === 'failed') dispatch({ failed: run.error ?? 'The run stopped unexpectedly.' })
      })
    }
    return () => source.close()
  }, [runId])

  return view
}
