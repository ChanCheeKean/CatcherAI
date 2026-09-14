import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import type { Adapter } from '../../api/types'

export function QueueLauncher() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [adapter, setAdapter] = useState<Adapter>('fake')

  const launch = useMutation({
    mutationFn: () => api.startQueueRun(adapter),
    onSuccess: (response) => {
      void queryClient.invalidateQueries({ queryKey: ['runs'] })
      navigate(`/runs/${response.run_id}`)
    },
  })

  return (
    <div className="flex items-center gap-2">
      <select
        value={adapter}
        onChange={(event) => setAdapter(event.target.value as Adapter)}
        className="rounded-md border border-border bg-surface-1 px-2 py-1 text-xs text-ink focus-visible:outline-2 focus-visible:outline-cyan"
      >
        <option value="fake">fake</option>
        <option value="openai">openai</option>
      </select>
      <button
        type="button"
        onClick={() => launch.mutate()}
        disabled={launch.isPending}
        className="rounded-md bg-violet px-3 py-1 text-xs font-semibold text-canvas transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {launch.isPending ? 'Ranking…' : 'Rank queue'}
      </button>
      {launch.isError && <span className="text-xs text-rose">Couldn't start the queue run.</span>}
    </div>
  )
}
