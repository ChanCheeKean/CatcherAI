import { useRunPanels } from './RunContext'
import { words } from './format'

export function Notebook() {
  const { view, showEvidence } = useRunPanels()
  if (!view.notebook.length) return <p className="p-4 text-graphite">No Case Notebook entries yet.</p>
  return (
    <section aria-label="Case Notebook" className="h-full overflow-y-auto p-4">
      <ol className="mx-auto max-w-3xl space-y-3">
        {[...view.notebook].sort((a, b) => a.seq - b.seq).map((entry, index, entries) => (
          <li key={entry.entry_id} className="rounded-sm border bg-vellum p-3">
            {(index === 0 || entries[index - 1].author !== entry.author) && (
              <h2 className="mb-2 text-sm font-semibold">{words(entry.author)}</h2>
            )}
            <div className="flex items-start gap-3">
              <span className="id-chip text-xs text-graphite">#{entry.seq}</span>
              <div className="min-w-0 flex-1">
                <span className="rounded-full bg-paper px-2 py-0.5 text-xs font-medium">{words(entry.kind)}</span>
                <p className="mt-2 leading-relaxed">{entry.text}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {[...entry.node_ids, ...entry.edge_ids].map((id) => (
                    <button key={id} type="button" onClick={() => showEvidence({ node_ids: entry.node_ids.includes(id) ? [id] : [], edge_ids: entry.edge_ids.includes(id) ? [id] : [] })}
                      className="ref cursor-pointer hover:underline">{id}</button>
                  ))}
                </div>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
