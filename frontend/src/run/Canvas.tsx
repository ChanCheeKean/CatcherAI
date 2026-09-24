import { AgentFlow } from './AgentFlow'
import { EvidenceGraph } from './EvidenceGraph'
import { Notebook } from './Notebook'
import { Swimlanes } from './Swimlanes'
import { useRunPanels, type CanvasTab } from './RunContext'

const TABS: { id: CanvasTab; label: string }[] = [
  { id: 'flow', label: 'Agent flow' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'graph', label: 'Evidence graph' },
  { id: 'notebook', label: 'Notebook' },
]

export function Canvas() {
  const { tab, setTab, flow, view } = useRunPanels()
  return (
    <section aria-label="Run canvas" className="flex min-h-[28rem] flex-col border-b lg:min-h-0 lg:border-r lg:border-b-0">
      <div role="tablist" className="flex gap-1 border-b bg-vellum px-3 pt-2">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            role="tab"
            type="button"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`-mb-px cursor-pointer rounded-t-sm border border-b-0 px-4 py-2 text-sm font-medium ${
              tab === id ? 'border-rule bg-paper' : 'border-transparent text-graphite hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel" className="min-h-0 flex-1">
        {tab === 'flow' && <AgentFlow flow={flow} running={view.status === 'running'} />}
        {tab === 'timeline' && <Swimlanes />}
        {tab === 'graph' && <EvidenceGraph />}
        {tab === 'notebook' && <Notebook />}
      </div>
    </section>
  )
}
