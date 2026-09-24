import { categoryLabel, verdictLabel, verdictTone } from './format'
import { useRunPanels } from './RunContext'

/** The verdict strip under the canvas; the report itself reads in the inspector, beside the graph. */
export function Conclusion() {
  const { view } = useRunPanels()
  if (!view.report) return null
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
