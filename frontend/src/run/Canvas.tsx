import { AgentFlow } from './AgentFlow'
import { useRunPanels, type CanvasTab } from './RunContext'

const TABS: { id: CanvasTab; label: string }[] = [
  { id: 'flow', label: 'Agent flow' },
  { id: 'graph', label: 'Evidence graph' },
]

export function Canvas() {
  const { tab, setTab, flow, view } = useRunPanels()
  return (
    <section aria-label="Run canvas" className="flex min-h-0 flex-col border-b lg:border-r lg:border-b-0">
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
      <div role="tabpanel" className={`min-h-0 flex-1 ${tab === 'flow' ? '' : 'overflow-auto p-4'}`}>
        {tab === 'flow' ? <AgentFlow flow={flow} running={view.status === 'running'} /> : <EvidenceGraphStub />}
      </div>
    </section>
  )
}

/** Stand-in until the graph view arrives: the ids the agents have touched. */
function EvidenceGraphStub() {
  const { view, highlight, selection, select } = useRunPanels()
  if (!view.touched.size) return <p className="text-graphite">Nothing discovered yet.</p>
  return (
    <>
      <p className="mb-3 text-sm text-graphite">
        {view.touched.size} graph items discovered so far.
      </p>
      <ul className="flex flex-wrap gap-1.5">
        {[...view.touched.keys()].map((id) => {
          const cited = highlight.nodeIds.has(id) || highlight.edgeIds.has(id)
          return (
            <li key={id}>
              <button
                type="button"
                onClick={() => select({ kind: 'node', id })}
                aria-pressed={selection?.kind === 'node' && selection.id === id}
                className={`id-chip cursor-pointer rounded-sm border px-1.5 py-0.5 aria-pressed:border-ink ${
                  cited ? 'bg-highlighter' : 'bg-vellum'
                }`}
              >
                {id}
              </button>
            </li>
          )
        })}
      </ul>
    </>
  )
}
