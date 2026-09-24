import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { CaseSummary } from '../api/types'
import { money, verdictLabel, verdictTone } from '../run/format'

export function CasesPage() {
  const navigate = useNavigate()
  const cases = useQuery({ queryKey: ['cases'], queryFn: api.listCases })
  const start = useMutation({
    mutationFn: (caseId: string) => api.startRun(caseId),
    onSuccess: (run) => navigate(`/cases/${run.case_id}/runs/${run.run_id}`),
  })
  /** A case that has already been investigated replays its last run; a fresh one starts an investigation. */
  function openCase(item: CaseSummary) {
    if (item.latest_run_id) navigate(`/cases/${item.case_id}/runs/${item.latest_run_id}?replay`)
    else start.mutate(item.case_id)
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-10 sm:px-8">
      <header className="mb-8 max-w-2xl">
        <h1 className="font-serif text-4xl leading-tight font-semibold">Disputed card charges</h1>
        <p className="mt-2 text-graphite">
          Pick a case to replay its last investigation: the agents search the evidence graph, narrow
          it to the facts that matter, and reach a verdict. Run it again to investigate live.
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
            <CaseCard
              item={item}
              busy={start.isPending}
              onOpen={() => openCase(item)}
              onRerun={() => start.mutate(item.case_id)}
            />
          </li>
        ))}
      </ul>
    </main>
  )
}

interface CaseCardProps {
  item: CaseSummary
  busy: boolean
  onOpen: () => void
  onRerun: () => void
}

function CaseCard({ item, busy, onOpen, onRerun }: CaseCardProps) {
  const verdict = item.latest_verdict
  return (
    <div className="flex h-full flex-col rounded-sm border border-rule bg-vellum transition-colors hover:border-ink">
      <button
        type="button"
        disabled={busy}
        onClick={onOpen}
        className="flex w-full flex-1 cursor-pointer flex-col p-5 pb-3 text-left disabled:cursor-wait disabled:opacity-60"
      >
        <span className="text-lg leading-snug font-semibold">{item.title}</span>
        <span className="mt-1 text-sm text-graphite">{item.claim}</span>
        <span className="mt-3 flex-1 text-[0.95rem] leading-relaxed">{item.summary}</span>
      </button>
      <div className="flex items-baseline justify-between gap-3 border-t px-5 py-3 text-sm">
        <span className="tabular-nums font-semibold">{money(item.amount)}</span>
        {item.latest_run_id ? (
          <span className="flex items-baseline gap-3">
            {verdict && <span className={`font-medium ${verdictTone[verdict].text}`}>{verdictLabel[verdict]}</span>}
            <button
              type="button"
              disabled={busy}
              onClick={onRerun}
              className="cursor-pointer text-graphite underline-offset-4 hover:text-ink hover:underline disabled:opacity-60"
            >
              Run again
            </button>
          </span>
        ) : (
          <span className="text-graphite">Not run yet</span>
        )}
      </div>
    </div>
  )
}
