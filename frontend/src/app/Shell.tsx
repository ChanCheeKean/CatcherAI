import { useQuery } from '@tanstack/react-query'
import { Outlet } from 'react-router-dom'
import { api } from '../api/client'
import { Inspector } from './Inspector'
import { InspectorProvider } from './InspectorContext'
import { NavigationRail } from './NavigationRail'

export function Shell() {
  const metaQuery = useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: 60_000 })

  return (
    <InspectorProvider>
      <div className="flex h-screen flex-col bg-canvas">
        <header className="flex shrink-0 items-center justify-between border-b border-border px-4 py-2.5">
          <div className="flex items-center gap-2.5">
            <span className="size-2 rounded-full bg-cyan" aria-hidden />
            <span className="text-sm font-bold tracking-tight text-ink">Dispute Observatory</span>
          </div>
          <div className="hidden items-center gap-4 font-mono text-xs text-ink-faint sm:flex">
            {metaQuery.data && (
              <>
                <span>model {metaQuery.data.model}</span>
                <span>virtual {metaQuery.data.virtual_clock}</span>
                <span className={metaQuery.data.adapters.openai ? 'text-emerald' : 'text-ink-faint'}>
                  openai {metaQuery.data.adapters.openai ? 'available' : 'unavailable'}
                </span>
              </>
            )}
          </div>
        </header>

        <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[280px_1fr_380px]">
          <aside className="hidden border-r border-border lg:block">
            <NavigationRail />
          </aside>

          <main className="min-h-0 overflow-y-auto">
            <Outlet />
          </main>

          <aside className="hidden border-l border-border lg:block">
            <Inspector />
          </aside>
        </div>
      </div>
    </InspectorProvider>
  )
}
