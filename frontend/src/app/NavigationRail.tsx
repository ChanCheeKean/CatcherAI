import { useQuery } from '@tanstack/react-query'
import { NavLink } from 'react-router-dom'
import { api } from '../api/client'
import { StatusBadge } from '../components/StatusBadge'

export function NavigationRail() {
  const runsQuery = useQuery({
    queryKey: ['runs', 'recent'],
    queryFn: () => api.listRuns({ limit: 20 }),
    refetchInterval: 5000,
  })

  return (
    <nav aria-label="Cases and runs" className="flex h-full flex-col overflow-hidden">
      <NavLink
        to="/"
        className={({ isActive }) =>
          `mx-3 mt-3 rounded-md px-3 py-2 text-sm font-semibold ${
            isActive ? 'bg-surface-3 text-ink' : 'text-ink-muted hover:bg-surface-3 hover:text-ink'
          }`
        }
        end
      >
        Mission control
      </NavLink>

      <div className="mt-4 flex-1 overflow-y-auto px-3 pb-3">
        <h2 className="px-1 pb-2 text-xs font-medium text-ink-faint">Recent runs</h2>
        {runsQuery.isLoading && <p className="px-1 text-sm text-ink-faint">Loading runs…</p>}
        {runsQuery.isError && (
          <p className="px-1 text-sm text-rose">Couldn't reach the backend API.</p>
        )}
        {runsQuery.data?.items.length === 0 && (
          <p className="px-1 text-sm text-ink-faint">No runs yet. Launch one from Mission control.</p>
        )}
        <ul className="flex flex-col gap-1">
          {runsQuery.data?.items.map((run) => (
            <li key={run.run_id}>
              <NavLink
                to={`/runs/${run.run_id}`}
                className={({ isActive }) =>
                  `block rounded-md px-2 py-2 text-sm ${
                    isActive ? 'bg-surface-3' : 'hover:bg-surface-3'
                  }`
                }
              >
                <span className="block truncate font-medium text-ink">
                  {run.case_id ?? 'Q01 queue'}
                </span>
                <span className="mt-0.5 flex items-center justify-between text-xs text-ink-faint">
                  <StatusBadge status={run.status} pulse />
                  <span>{run.event_count} events</span>
                </span>
              </NavLink>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  )
}
