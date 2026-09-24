import type { ReactNode } from 'react'
import { Ref } from './Fields'
import { PlanChecklist } from './ModelOutput'
import { words } from './format'
import { useRunPanels } from './RunContext'
import { openPlanItems } from './store'

/**
 * What the inspector says while a run is under way and nothing is selected: who is working, the
 * supervisor's latest reasoning, the newest Case Notebook finding and the plan items still open.
 * It follows the replay cursor, so a replay narrates itself.
 */
export function Narration() {
  const { view, flow, showEvidence } = useRunPanels()
  const open = openPlanItems(view)
  const reasoning = view.events.findLast((event) => event.type === 'supervisor_turn')
  const finding = view.notebook.at(-1)
  const working = [...flow.active]

  let status = 'Starting the investigation…'
  if (view.status === 'failed') status = `The run failed: ${view.error}`
  else if (view.events.length) status = `Investigating. Supervisor turn ${view.turn}; ${open.length} of ${view.plan.length} plan items still open.`

  return (
    <div aria-label="Run narration" className="space-y-5">
      <p role="status" className={view.status === 'failed' ? 'font-medium text-rejected' : 'font-medium'}>
        {status}
      </p>
      {working.length > 0 && (
        <Part title="Working now">
          <p className="text-sm">{working.map(words).join(', ')}</p>
        </Part>
      )}
      {reasoning && (
        <Part title={`Supervisor, turn ${reasoning.turn}`}>
          <p className="text-sm leading-relaxed">{String(reasoning.payload.reasoning ?? '')}</p>
        </Part>
      )}
      {finding && (
        <Part title={`Newest Case Notebook finding (${view.notebook.length} so far)`}>
          <p className="text-xs text-graphite">
            {words(finding.author)} · {words(finding.kind)}
          </p>
          <p className="mt-1 text-sm leading-relaxed">{finding.text}</p>
          <p className="mt-2 flex flex-wrap gap-1">
            {finding.node_ids.map((id) => (
              <Ref key={id} id={id} onClick={() => showEvidence(finding)} />
            ))}
          </p>
        </Part>
      )}
      {open.length > 0 && (
        <Part title={`Open plan items (${view.plan.length - open.length} of ${view.plan.length} closed)`}>
          <div className="text-sm">
            <PlanChecklist plan={open} />
          </div>
        </Part>
      )}
      <p className="text-xs text-graphite">Select an agent, a lane or a graph item to see exactly what happened.</p>
    </div>
  )
}

function Part({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-1 text-xs font-semibold tracking-wide text-graphite uppercase">{title}</h3>
      {children}
    </section>
  )
}
