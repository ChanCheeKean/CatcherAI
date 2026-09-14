import type { RunStatus } from '../api/types'

const STYLES: Record<RunStatus, { label: string; dot: string; text: string }> = {
  running: { label: 'Running', dot: 'bg-cyan', text: 'text-cyan' },
  suspended: { label: 'Waiting', dot: 'bg-amber', text: 'text-amber' },
  decided: { label: 'Decided', dot: 'bg-emerald', text: 'text-emerald' },
  cancelled: { label: 'Cancelled', dot: 'bg-slate', text: 'text-slate' },
  failed: { label: 'Failed', dot: 'bg-rose', text: 'text-rose' },
  ranked: { label: 'Ranked', dot: 'bg-violet', text: 'text-violet' },
}

export function StatusBadge({ status, pulse = false }: { status: RunStatus; pulse?: boolean }) {
  const style = STYLES[status]
  return (
    <span className={`inline-flex items-center gap-1.5 text-sm font-medium ${style.text}`}>
      <span
        className={`size-1.5 rounded-full ${style.dot} ${pulse && status === 'running' ? 'animate-pulse-edge' : ''}`}
        aria-hidden
      />
      {style.label}
    </span>
  )
}
