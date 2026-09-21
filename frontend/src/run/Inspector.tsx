import { ActorPanel } from './ActorPanel'
import { GraphItemPanel } from './GraphItemPanel'
import { useRunPanels } from './RunContext'

/** Selection-driven side panel: an agent or tool shows what it did; a graph item shows the raw events that touched it. */
export function Inspector() {
  const { flow, selection } = useRunPanels()
  return (
    <aside aria-label="Inspector" className="min-h-0 overflow-auto bg-vellum p-4">
      {selection === null && (
        <>
          <h2 className="mb-2 font-semibold">Inspector</h2>
          <p className="mb-3 text-sm text-graphite">Select an agent or a graph item to see what happened.</p>
        </>
      )}
      {selection?.kind === 'actor' && <ActorPanel name={selection.name} flow={flow} />}
      {selection?.kind === 'node' && <GraphItemPanel id={selection.id} />}
    </aside>
  )
}
