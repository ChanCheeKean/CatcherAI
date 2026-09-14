import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../../api/client'
import { useRunStream } from '../../api/useRunStream'
import { StatusBadge } from '../../components/StatusBadge'
import { projectRunAt, projectionHash } from '../../projections/runProjection'
import { DecisionPanel } from './DecisionPanel'
import { EventTimeline } from './EventTimeline'
import { MetricsStrip } from './MetricsStrip'
import { WorkflowCanvas } from './WorkflowCanvas'
import { ActorSwimlanes } from './ActorSwimlanes'
import { ReasoningArtifacts } from './ReasoningArtifacts'
import { MemoryGraphOverlay } from './MemoryGraphOverlay'
import { ReplayControls, type ReplayFilters } from './ReplayControls'
import { QueueVisualization } from './QueueVisualization'
import { useInspector } from '../../app/InspectorContext'

const TERMINAL = new Set(['decided', 'cancelled', 'failed', 'ranked'])

export function RunObservatoryPage() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const { select } = useInspector()

  const { events, status: streamStatus } = useRunStream(runId ?? null)
  const maxSeq = events.at(-1)?.seq ?? 0
  const requestedSeq = params.get('seq')
  const live = requestedSeq === null
  const cursor = live ? maxSeq : Math.min(Number(requestedSeq) || 0, maxSeq)
  const projection = useMemo(() => projectRunAt(events, cursor), [cursor, events])
  const view = (params.get('view') as 'timeline' | 'swimlanes' | 'artifacts' | 'memory' | null) ?? 'timeline'
  const filters: ReplayFilters = { type: params.get('type') ?? '', actor: params.get('actor') ?? '', text: params.get('q') ?? '' }
  const visibleEvents = useMemo(() => events.filter((event) => event.seq <= cursor && (!filters.type || event.type.includes(filters.type)) && (!filters.actor || `${event.actor.kind} ${event.actor.name}`.toLowerCase().includes(filters.actor.toLowerCase())) && (!filters.text || `${event.summary} ${event.refs.join(' ')}`.toLowerCase().includes(filters.text.toLowerCase()))).slice(-350), [cursor, events, filters.actor, filters.text, filters.type])
  const patchParams = useCallback((values: Record<string, string | null>) => { const next = new URLSearchParams(params); Object.entries(values).forEach(([key, value]) => value === null || value === '' ? next.delete(key) : next.set(key, value)); setParams(next, { replace: true }) }, [params, setParams])

  useEffect(() => { const selectedSeq = Number(params.get('event')); if (selectedSeq) select(events.find((event) => event.seq === selectedSeq) ?? null) }, [events, params, select])

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
  const decisionCommitted = events.some((event) => event.seq <= cursor && event.type === 'decision_recorded')
  const canDecide = decisionCommitted || (live && ((runQuery.data?.decision_available ?? false) || (isTerminal && !projection.failed)))
  const queueCommitted = events.some((event) => event.seq <= cursor && event.type === 'portfolio_ranked')
  const queueFallback = (events.find((event) => event.seq <= cursor && event.type === 'portfolio_ranked')?.payload.top as Array<Record<string, unknown>> | undefined) ?? []
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
        <ReplayControls cursor={cursor} maxSeq={maxSeq} live={live} filters={filters} onCursor={(seq) => patchParams({ seq: String(seq), event: null })} onLive={() => patchParams({ seq: null, event: null })} onFilters={(next) => patchParams({ type: next.type, actor: next.actor, q: next.text })} />
        {runQuery.data?.case_id === null && queueCommitted && <QueueVisualization runId={runId} virtualNow={projection.virtualNow} terminal={isTerminal} fallback={queueFallback} />}
        <WorkflowCanvas projection={projection} />
        <div className="sticky top-0 z-10 flex border-b border-border bg-surface-1 px-3">
          {(['timeline', 'swimlanes', 'artifacts', 'memory'] as const).map((item) => <button key={item} type="button" onClick={() => patchParams({ view: item === 'timeline' ? null : item })} className={`border-b-2 px-3 py-2 text-xs capitalize ${view === item ? 'border-cyan text-cyan' : 'border-transparent text-ink-muted'}`}>{item === 'artifacts' ? 'Reasoning artifacts' : item === 'memory' ? 'Memory & graph' : item}</button>)}
        </div>
        {view === 'timeline' && <><EventTimeline events={visibleEvents} onSelect={(event) => patchParams({ event: String(event.seq) })} />{events.filter((event) => event.seq <= cursor).length > 350 && <p className="p-3 text-center text-xs text-ink-faint">Showing the latest 350 events in this replay prefix. Use filters or seek to inspect earlier events.</p>}</>}
        {view === 'swimlanes' && <div className="overflow-x-auto"><ActorSwimlanes events={visibleEvents} /></div>}
        {view === 'artifacts' && <ReasoningArtifacts projection={projection} />}
        {view === 'memory' && <MemoryGraphOverlay runId={runId} />}
        {canDecide && <DecisionPanel runId={runId} events={events} />}
      </div>

      <MetricsStrip projection={projection} streamStatus={streamStatus} />
      <span className="sr-only" data-testid="projection-hash">{projectionHash(projection)}</span>
    </div>
  )
}
