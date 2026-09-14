import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

function value(row: Record<string, unknown>, key: string) { return row[key] == null ? '—' : String(row[key]) }

export function QueueVisualization({ runId, virtualNow, terminal, fallback }: { runId: string; virtualNow: string | null; terminal: boolean; fallback: Array<Record<string, unknown>> }) {
  const queue = useQuery({ queryKey: ['queue-run', runId], queryFn: () => api.getQueueRun(runId), refetchInterval: terminal ? false : 1500 })
  const ranking = queue.data?.ranking ?? fallback
  const now = virtualNow ? new Date(virtualNow) : null
  return <section className="border-b border-border bg-surface-1 p-4"><div className="flex items-baseline justify-between"><div><p className="font-mono text-xs uppercase tracking-widest text-amber">Q01 deadline board</p><h2 className="mt-1 text-lg font-semibold text-ink">Ranked open cases</h2></div><span className="font-mono text-xs text-ink-faint">virtual {virtualNow?.slice(0, 10) ?? '—'}</span></div>
    <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[680px] text-left text-xs"><thead className="text-ink-faint"><tr><th className="pb-2">Rank</th><th>Case</th><th>Clock</th><th>Deadline</th><th>Pressure</th><th>Rights</th></tr></thead><tbody>{ranking.map((row, index) => { const deadline = row.next_deadline ? new Date(String(row.next_deadline)) : null; const days = now && deadline ? Math.ceil((deadline.getTime() - now.getTime()) / 86_400_000) : null; const expired = Array.isArray(row.expired_rights) && row.expired_rights.length > 0; const urgent = expired || (days !== null && days <= 3); return <tr key={value(row, 'case_id') + index} className="border-t border-border"><td className="py-2 font-mono text-ink-faint">{value(row, 'rank')}</td><td className="font-mono text-ink">{value(row, 'case_id')}</td><td className="text-ink-muted">{value(row, 'next_clock').replaceAll('_', ' ')}</td><td className="font-mono text-ink-muted">{value(row, 'next_deadline')}</td><td><span className={urgent ? 'text-rose' : days !== null && days <= 10 ? 'text-amber' : 'text-emerald'}>{expired ? 'expired' : days === null ? 'no hard clock' : days <= 0 ? 'due now' : `${days}d remaining`}</span></td><td className={expired ? 'text-rose' : 'text-ink-faint'}>{expired ? (row.expired_rights as unknown[]).join(', ') : 'intact'}</td></tr> })}</tbody></table></div>
  </section>
}
