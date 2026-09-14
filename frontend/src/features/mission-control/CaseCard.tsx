import type { CaseSummary } from '../../api/types'
import { RunLauncher } from './RunLauncher'

const STATUS_TEXT: Record<string, string> = { open: 'text-cyan', closed: 'text-slate' }

function formatAmount(amount: string | null): string {
  if (amount === null) return '—'
  const value = Number(amount)
  return Number.isNaN(value) ? amount : `$${value.toFixed(2)}`
}

export function CaseCard({ caseItem }: { caseItem: CaseSummary }) {
  return (
    <article className="flex flex-col gap-2 rounded-lg border border-border bg-surface-2 p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-mono text-sm font-semibold text-ink">{caseItem.case_id}</p>
          <p className="text-xs text-ink-faint">
            {caseItem.regime.replace('_', ' ')} · claim {caseItem.claim_family_initial}
            {caseItem.network ? ` · ${caseItem.network}` : ''}
          </p>
        </div>
        <span
          className={`text-xs font-medium ${STATUS_TEXT[caseItem.status] ?? 'text-ink-muted'}`}
        >
          {caseItem.status}
        </span>
      </div>

      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <dt className="text-ink-faint">Amount</dt>
        <dd className="font-mono text-ink">{formatAmount(caseItem.dispute_amount)}</dd>
        <dt className="text-ink-faint">Stage</dt>
        <dd className="text-ink-muted">{caseItem.stage}</dd>
        <dt className="text-ink-faint">Opened</dt>
        <dd className="text-ink-muted">{caseItem.opened_at.slice(0, 10)}</dd>
        {caseItem.cardholder_outcome && (
          <>
            <dt className="text-ink-faint">Cardholder</dt>
            <dd className="text-ink-muted">{caseItem.cardholder_outcome}</dd>
          </>
        )}
      </dl>

      <div className="mt-1 border-t border-border pt-3">
        <RunLauncher caseId={caseItem.case_id} />
      </div>
    </article>
  )
}
