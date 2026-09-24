import { ActorPanel } from './ActorPanel'
import { GraphItemPanel } from './GraphItemPanel'
import { Narration } from './Narration'
import { Report } from './Report'
import { useRunPanels } from './RunContext'

/**
 * The side panel. A selected agent, tool or graph item shows what happened to it; with nothing
 * selected it narrates the run, then holds the report, so claims and their evidence are on screen together.
 */
export function Inspector() {
  const { flow, selection, select, view } = useRunPanels()
  return (
    <aside aria-label="Inspector" className="min-h-0 overflow-auto bg-vellum p-4">
      {selection && (
        <button type="button" onClick={() => select(null)} className="mb-3 cursor-pointer text-sm text-graphite underline-offset-4 hover:text-ink hover:underline">
          ← Back to the {view.report ? 'report' : 'run'}
        </button>
      )}
      {selection === null && (view.report ? <Report report={view.report} /> : <Narration />)}
      {selection?.kind === 'actor' && <ActorPanel name={selection.name} flow={flow} />}
      {selection?.kind === 'node' && <GraphItemPanel id={selection.id} />}
    </aside>
  )
}
