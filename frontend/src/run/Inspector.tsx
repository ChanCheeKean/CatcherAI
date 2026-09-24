import { ActorPanel } from './ActorPanel'
import { GraphItemPanel } from './GraphItemPanel'
import { Report } from './Report'
import { useRunPanels } from './RunContext'

/**
 * The side panel. A selected agent, tool or graph item shows what happened to it; with nothing
 * selected it holds the report once there is one, so claims and their evidence are on screen together.
 */
export function Inspector() {
  const { flow, selection, select, view } = useRunPanels()
  return (
    <aside aria-label="Inspector" className="min-h-0 overflow-auto bg-vellum p-4">
      {selection && view.report && (
        <button type="button" onClick={() => select(null)} className="mb-3 cursor-pointer text-sm text-graphite underline-offset-4 hover:text-ink hover:underline">
          ← Back to the report
        </button>
      )}
      {selection === null &&
        (view.report ? (
          <Report report={view.report} />
        ) : (
          <>
            <h2 className="mb-2 font-semibold">Inspector</h2>
            <p className="mb-3 text-sm text-graphite">Select an agent or a graph item to see what happened.</p>
          </>
        ))}
      {selection?.kind === 'actor' && <ActorPanel name={selection.name} flow={flow} />}
      {selection?.kind === 'node' && <GraphItemPanel id={selection.id} />}
    </aside>
  )
}
