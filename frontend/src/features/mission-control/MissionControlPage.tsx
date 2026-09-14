import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import { CaseCard } from './CaseCard'
import { CaseFilters, EMPTY_FILTERS, type CaseFilterState } from './CaseFilters'
import { QueueLauncher } from './QueueLauncher'

function isMeaningful(value: string): value is string {
  return value.trim() !== ''
}

export function MissionControlPage() {
  const [filters, setFilters] = useState<CaseFilterState>(EMPTY_FILTERS)

  const casesQuery = useQuery({
    queryKey: ['cases', filters],
    queryFn: () =>
      api.listCases({
        q: isMeaningful(filters.q) ? filters.q : undefined,
        regime: isMeaningful(filters.regime) ? filters.regime : undefined,
        status: isMeaningful(filters.status) ? filters.status : undefined,
        stage: isMeaningful(filters.stage) ? filters.stage : undefined,
        limit: 30,
      }),
  })

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-ink">Mission control</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Select a case and launch an investigation run, or open the Q01 queue.
          </p>
        </div>
        <div className="rounded-lg border border-border bg-surface-2 px-4 py-3">
          <p className="text-xs font-medium text-ink-faint">Q01 portfolio queue</p>
          <div className="mt-2">
            <QueueLauncher />
          </div>
        </div>
      </div>

      <CaseFilters value={filters} onChange={setFilters} />

      {casesQuery.isLoading && <p className="text-sm text-ink-faint">Loading cases…</p>}
      {casesQuery.isError && (
        <p className="text-sm text-rose">
          Couldn't reach the Dispute Observatory API. Is the backend running on port 8000?
        </p>
      )}
      {casesQuery.data && casesQuery.data.items.length === 0 && (
        <p className="text-sm text-ink-faint">No cases match these filters.</p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {casesQuery.data?.items.map((caseItem) => (
          <CaseCard key={caseItem.case_id} caseItem={caseItem} />
        ))}
      </div>
    </div>
  )
}
