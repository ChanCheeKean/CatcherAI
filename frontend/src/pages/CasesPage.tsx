import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { CaseSummary } from '../api/types'
import { money, words } from '../run/format'

export function CasesPage() {
  const navigate = useNavigate()
  const cases = useQuery({ queryKey: ['cases'], queryFn: api.listCases })
  const start = useMutation({
    mutationFn: (caseId: string) => api.startRun(caseId),
    onSuccess: (run) => navigate(`/cases/${run.case_id}/runs/${run.run_id}`),
  })

  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-8">
      <header className="mb-8 max-w-2xl">
        <h1 className="font-serif text-4xl leading-tight font-semibold">Disputed card charges</h1>
        <p className="mt-2 text-graphite">
          Pick a case. The agents investigate it in the evidence graph and write up their decision
          while you watch.
        </p>
      </header>

      {cases.isPending && <p className="text-graphite">Loading cases…</p>}
      {cases.isError && (
        <p role="alert" className="text-rejected">
          Could not load cases: {cases.error.message}. Check that the API is running on port 8000.
        </p>
      )}
      {start.isError && (
        <p role="alert" className="mb-4 text-rejected">
          Could not start the run: {start.error.message}
        </p>
      )}

      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cases.data?.map((item) => (
          <li key={item.case_id}>
            <CaseCard item={item} busy={start.isPending} onOpen={() => start.mutate(item.case_id)} />
          </li>
        ))}
      </ul>
    </main>
  )
}

function CaseCard({ item, busy, onOpen }: { item: CaseSummary; busy: boolean; onOpen: () => void }) {
  return (
    <button
      type="button"
      disabled={busy}
      onClick={onOpen}
      className="flex h-full w-full cursor-pointer flex-col rounded-sm border border-rule bg-vellum p-5 text-left transition-colors hover:border-ink disabled:cursor-wait disabled:opacity-60"
    >
      <span className="text-lg leading-snug font-semibold">{item.title}</span>
      <span className="mt-1 text-sm text-graphite">{words(item.claim_type)}</span>
      <span className="mt-3 flex-1 text-[0.95rem] leading-relaxed">{item.summary}</span>
      <span className="mt-5 flex items-baseline justify-between border-t pt-3 text-sm">
        <span className="tabular-nums font-semibold">{money(item.amount)}</span>
        <span className="text-graphite">Investigate</span>
      </span>
    </button>
  )
}
