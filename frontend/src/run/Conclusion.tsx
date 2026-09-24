import { categoryLabel, verdictLabel, verdictTone } from './format'
import { useRunPanels } from './RunContext'
import { openPlanItems } from './store'

/** The verdict strip under the canvas; the report itself reads in the inspector, beside the graph. */
export function Conclusion() {
  const { view } = useRunPanels()
  if (!view.report) return <LiveStatus />
  const { verdict, category, headline } = view.report
  const tone = verdictTone[verdict]
  return (
    <section aria-label="Conclusion" className={`border-t border-l-8 bg-vellum px-4 py-2.5 sm:px-6 ${tone.band}`}>
      <p className="flex flex-wrap items-baseline gap-x-3">
        <span className={`font-serif text-xl font-semibold ${tone.text}`}>{verdictLabel[verdict]}</span>
        <span className="text-sm font-medium">{category} · {categoryLabel[category]}</span>
      </p>
      <p className="font-serif leading-snug">{headline}</p>
    </section>
  )
}

function LiveStatus() {
  const { view } = useRunPanels()
  const open = openPlanItems(view)
  let text = 'Starting the investigation…'
  if (view.status === 'failed') text = `The run failed: ${view.error}`
  else if (view.events.length)
    text = `Investigating. Supervisor turn ${view.turn}; ${open.length} of ${view.plan.length} plan items still open.`
  return (
    <section aria-label="Conclusion" className="border-t bg-vellum px-4 py-3 text-sm sm:px-6">
      <p className={view.status === 'failed' ? 'text-rejected' : 'text-graphite'} role="status">
        {text}
      </p>
      {view.status === 'running' && open.length > 0 && (
        <ul className="mt-2 list-disc space-y-0.5 pl-5">
          {open.map((item) => (
            <li key={item.id}>{item.question}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
