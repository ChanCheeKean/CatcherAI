import type { StreamStatus } from '../../api/useRunStream'
import type { RunProjection } from '../../projections/runProjection'

const CONNECTION_LABEL: Record<StreamStatus, string> = {
  idle: 'Idle',
  connecting: 'Connecting…',
  open: 'Live',
  closed: 'Closed',
  error: 'Disconnected',
}

const CONNECTION_COLOR: Record<StreamStatus, string> = {
  idle: 'text-ink-faint',
  connecting: 'text-amber',
  open: 'text-cyan',
  closed: 'text-slate',
  error: 'text-rose',
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="font-mono text-sm text-ink">{value}</span>
      <span className="text-xs text-ink-faint">{label}</span>
    </div>
  )
}

export function MetricsStrip({
  projection,
  streamStatus,
}: {
  projection: RunProjection
  streamStatus: StreamStatus
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-border bg-surface-1 px-4 py-2.5">
      <span className={`flex items-center gap-1.5 text-xs font-medium ${CONNECTION_COLOR[streamStatus]}`}>
        <span
          className={`size-1.5 rounded-full ${CONNECTION_COLOR[streamStatus].replace('text-', 'bg-')} ${
            streamStatus === 'open' ? 'animate-pulse-edge' : ''
          }`}
          aria-hidden
        />
        {CONNECTION_LABEL[streamStatus]}
      </span>
      <Metric label="events" value={String(projection.eventCount)} />
      <Metric label="seq" value={String(projection.currentSeq)} />
      <Metric label="tools" value={String(projection.toolCalls)} />
      <Metric label="model calls" value={String(projection.modelCalls)} />
      <Metric label="subagents" value={String(projection.subagentRuns)} />
      <Metric label="memory ops" value={String(projection.memoryOps)} />
      <Metric label="cost" value={`$${projection.usage.costUsd.toFixed(4)}`} />
      {projection.virtualNow && (
        <Metric label="virtual time" value={projection.virtualNow.slice(0, 19)} />
      )}
    </div>
  )
}
