import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { useRunStream } from '../../api/useRunStream'
import { StatusBadge } from '../../components/StatusBadge'
import { projectRun } from '../../projections/runProjection'
import { DecisionPanel } from './DecisionPanel'
import { EventTimeline } from './EventTimeline'
import { MetricsStrip } from './MetricsStrip'
import { WorkflowCanvas } from './WorkflowCanvas'
import { ActorSwimlanes } from './ActorSwimlanes'
import { ReasoningArtifacts } from './ReasoningArtifacts'
import { MemoryGraphOverlay } from './MemoryGraphOverlay'

const TERMINAL = new Set(['decided', 'cancelled', 'failed', 'ranked'])

export function RunObservatoryPage() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { events, status: streamStatus } = useRunStream(runId ?? null)
  const projection = useMemo(() => projectRun(events), [events])
  const [view, setView] = useState<'timeline' | 'swimlanes' | 'artifacts' | 'memory'>('timeline')

  const runQuery = useQuery({
    queryKey: ['run', runId],
    queryFn: () => api.getRun(runId!),
    enabled: Boolean(runId),
    // The live event stream is the authoritative signal for "is this run over"; REST status only
    // needs to stay fresh enough for the header badge and the cancel/rerun controls.
    refetchInterval: projection.terminal ? false : 3000,
  })

  const cancel = useMutation({
    mutationFn: () => api.cancelRun(runId!),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['run', runId] }),
  })
  const rerun = useMutation({
    mutationFn: () => api.rerunRun(runId!),
    onSuccess: (response) => navigate(`/runs/${response.run_id}`),
  })

  if (!runId) return null

  const restStatus = runQuery.data?.status
  const isTerminal = projection.terminal || Boolean(restStatus && TERMINAL.has(restStatus))
  const canDecide = (runQuery.data?.decision_available ?? false) || (isTerminal && !projection.failed)
  // Prefer the live event stream over the polled REST status: a run can decide between two polls,
  // and the stream already told us so.
  const displayStatus = projection.failed
    ? 'failed'
    : projection.terminal
      ? restStatus && TERMINAL.has(restStatus)
        ? restStatus
        : 'decided'
      : (restStatus ?? 'running')

  return (
    <div className="flex h-full flex-col">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div>
          <p className="font-mono text-xs text-ink-faint">run {runId}</p>
          <div className="mt-0.5 flex items-center gap-3">
            <h1 className="text-lg font-bold text-ink">
              {runQuery.data?.case_id ?? 'Q01 queue'}
            </h1>
            <StatusBadge status={displayStatus} pulse />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => cancel.mutate()}
            disabled={cancel.isPending || isTerminal}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:border-rose hover:text-rose disabled:opacity-40"
          >
            Cancel run
          </button>
          <button
            type="button"
            onClick={() => rerun.mutate()}
            disabled={rerun.isPending}
            className="rounded-md bg-surface-3 px-3 py-1.5 text-xs font-medium text-ink transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            Rerun
          </button>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <WorkflowCanvas projection={projection} />
        <div className="sticky top-0 z-10 flex border-b border-border bg-surface-1 px-3">
          {(['timeline', 'swimlanes', 'artifacts', 'memory'] as const).map((item) => <button key={item} type="button" onClick={() => setView(item)} className={`border-b-2 px-3 py-2 text-xs capitalize ${view === item ? 'border-cyan text-cyan' : 'border-transparent text-ink-muted'}`}>{item === 'artifacts' ? 'Reasoning artifacts' : item === 'memory' ? 'Memory & graph' : item}</button>)}
        </div>
        {view === 'timeline' && <EventTimeline events={events} />}
        {view === 'swimlanes' && <div className="overflow-x-auto"><ActorSwimlanes events={events} /></div>}
        {view === 'artifacts' && <ReasoningArtifacts projection={projection} />}
        {view === 'memory' && <MemoryGraphOverlay runId={runId} />}
        {canDecide && <DecisionPanel runId={runId} events={events} />}
      </div>

      <MetricsStrip projection={projection} streamStatus={streamStatus} />
    </div>
  )
}
