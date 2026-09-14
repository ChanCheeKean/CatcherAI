import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import type { Adapter } from '../../api/types'

export function RunLauncher({ caseId }: { caseId: string }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const metaQuery = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: 60_000 })
  const [adapter, setAdapter] = useState<Adapter>('fake')
  const [autoResume, setAutoResume] = useState(true)
  const adapterId = useId()
  const autoResumeId = useId()

  const launch = useMutation({
    mutationFn: () => api.startRun({ case_id: caseId, adapter, auto_resume: autoResume }),
    onSuccess: (response) => {
      void queryClient.invalidateQueries({ queryKey: ['runs'] })
      navigate(`/runs/${response.run_id}`)
    },
  })

  const openaiAvailable = metaQuery.data?.adapters.openai ?? false

  return (
    <div className="flex flex-wrap items-center gap-2">
      <label htmlFor={adapterId} className="sr-only">
        Adapter for {caseId}
      </label>
      <select
        id={adapterId}
        value={adapter}
        onChange={(event) => setAdapter(event.target.value as Adapter)}
        className="rounded-md border border-border bg-surface-1 px-2 py-1 text-xs text-ink focus-visible:outline-2 focus-visible:outline-cyan"
      >
        <option value="fake">fake</option>
        <option value="openai" disabled={!openaiAvailable}>
          openai{openaiAvailable ? '' : ' (unavailable)'}
        </option>
      </select>

      <label htmlFor={autoResumeId} className="flex items-center gap-1.5 text-xs text-ink-muted">
        <input
          id={autoResumeId}
          type="checkbox"
          checked={autoResume}
          onChange={(event) => setAutoResume(event.target.checked)}
          className="accent-cyan"
        />
        auto-resume
      </label>

      <button
        type="button"
        onClick={() => launch.mutate()}
        disabled={launch.isPending}
        className="rounded-md bg-cyan px-3 py-1 text-xs font-semibold text-canvas transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {launch.isPending ? 'Starting…' : 'Run'}
      </button>

      {launch.isError && <span className="text-xs text-rose">Couldn't start the run.</span>}
    </div>
  )
}
