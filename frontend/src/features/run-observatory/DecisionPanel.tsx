import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

function formatMoney(amount: unknown): string {
  const value = Number(amount)
  return Number.isNaN(value) ? String(amount) : `$${value.toFixed(2)}`
}

/**
 * Stage 3's minimal decision view: the cardholder/network outcomes and confidence a demo needs to
 * show "reached a decision live." The full field-provenance explorer (event_seqs/source_ids per
 * field, clickable evidence trail) is Stage 4 scope per the design doc §3.3.
 */
export function DecisionPanel({ runId }: { runId: string }) {
  const decisionQuery = useQuery({
    queryKey: ['decision', runId],
    queryFn: () => api.getRunDecision(runId),
  })

  if (decisionQuery.isLoading) {
    return <p className="p-4 text-sm text-ink-faint">Loading decision…</p>
  }
  if (decisionQuery.isError || !decisionQuery.data) {
    return null
  }

  const record = decisionQuery.data.record as Record<string, unknown>
  const cardholder = record.cardholder_resolution as Record<string, unknown> | undefined
  const networkActions = (record.network_actions as Array<Record<string, unknown>>) ?? []
  const confidence = Number(record.confidence ?? 0)

  return (
    <div className="grid grid-cols-1 gap-4 border-t border-border bg-surface-1 p-4 sm:grid-cols-2">
      <div className="rounded-lg border border-border bg-surface-2 p-3">
        <h3 className="text-xs font-medium text-ink-faint">Cardholder outcome</h3>
        {cardholder ? (
          <dl className="mt-2 grid grid-cols-2 gap-x-2 gap-y-1 text-xs">
            <dt className="text-ink-faint">Outcome</dt>
            <dd className="text-ink">{String(cardholder.outcome)}</dd>
            <dt className="text-ink-faint">Credit</dt>
            <dd className="font-mono text-emerald">{formatMoney(cardholder.credit_amount)}</dd>
            <dt className="text-ink-faint">Liability</dt>
            <dd className="font-mono text-ink">{formatMoney(cardholder.liability_amount)}</dd>
          </dl>
        ) : (
          <p className="mt-2 text-xs text-ink-faint">Not recorded.</p>
        )}
      </div>

      <div className="rounded-lg border border-border bg-surface-2 p-3">
        <h3 className="text-xs font-medium text-ink-faint">Network actions</h3>
        {networkActions.length > 0 ? (
          <ul className="mt-2 flex flex-col gap-1 text-xs">
            {networkActions.map((action) => (
              <li key={String(action.txn_id)} className="flex justify-between gap-2">
                <span className="font-mono text-ink-muted">{String(action.txn_id)}</span>
                <span className="text-ink">{String(action.action)}</span>
                <span className="font-mono text-ink">{formatMoney(action.amount)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-xs text-ink-faint">No network action recorded.</p>
        )}
      </div>

      <div className="sm:col-span-2">
        <p className="text-sm text-ink-muted">{String(record.explanation_for_cardholder ?? '')}</p>
        <p className="mt-1 text-xs text-ink-faint">
          confidence {confidence.toFixed(2)} · claim family {String(record.claim_family ?? '—')}
        </p>
      </div>
    </div>
  )
}
