import { useRunPanels } from './RunContext'

/** Bar length on a log scale, so 31 of 6,509 still shows as a mark rather than nothing. */
const share = (n: number, total: number) => (total > 0 ? Math.log10(n + 1) / Math.log10(total + 1) : 0)

function Stage({ value, label, total, bar }: { value: number; label: string; total: number; bar: string }) {
  return (
    <div className="w-28">
      <p className="text-lg leading-tight font-semibold tabular-nums">{value.toLocaleString()}</p>
      <div aria-hidden className="mt-1 h-1 rounded-full bg-rule/50">
        <div className={`h-full rounded-full transition-[width] duration-300 ${bar}`} style={{ width: `${share(value, total) * 100}%` }} />
      </div>
      <p className="mt-1 text-xs text-graphite">{label}</p>
    </div>
  )
}

/** One square per answer-key item: filled once the run has reached it. */
function Squares({ ids, filled, tone }: { ids: string[]; filled: (id: string) => boolean; tone: string }) {
  return (
    <span aria-hidden className="flex flex-wrap gap-0.5">
      {ids.map((id) => (
        <span key={id} className={`size-2 rounded-[2px] border transition-colors ${filled(id) ? `${tone} border-transparent` : 'border-graphite/40'}`} />
      ))}
    </span>
  )
}

/**
 * How far the investigation narrowed the graph, and, where the evaluation has an answer key for the
 * case, how much of it the run found. Counts follow the replay, so they climb as the agents work.
 */
export function Funnel({ total }: { total: number }) {
  const { view, cited, truth, overlay, setOverlay, setTab } = useRunPanels()
  const examined = [...view.touched.values()].filter((t) => t.kind === 'node').length
  const reportText = view.report ? JSON.stringify(view.report) : ''

  return (
    <div className="flex flex-wrap items-start gap-x-6 gap-y-2">
      <div className="flex gap-3" aria-label="How the investigation narrowed the graph" role="group">
        <Stage value={total} label="nodes in the graph" total={total} bar="bg-graphite/60" />
        <Stage value={examined} label="examined" total={total} bar="bg-ink" />
        <Stage value={cited.nodeIds.size} label="cited in the verdict" total={total} bar="bg-highlighter" />
      </div>
      {truth && (
        <button
          type="button"
          aria-pressed={overlay}
          onClick={() => {
            setOverlay(!overlay)
            setTab('graph')
          }}
          title="The evaluation's answer key for this case. Select to ring these nodes on the evidence graph."
          className="grid cursor-pointer grid-cols-[auto_auto] items-center gap-x-3 gap-y-1 rounded-sm border border-transparent px-2 py-1 text-left text-xs hover:border-rule aria-pressed:border-ink aria-pressed:bg-paper"
        >
          <span className="font-medium">Solution facts</span>
          <span className="flex items-center gap-2">
            <Squares ids={truth.solution_node_ids} filled={(id) => view.touched.has(id)} tone="bg-accepted" />
            <span className="text-graphite tabular-nums">
              {truth.solution_node_ids.filter((id) => view.touched.has(id)).length} of {truth.solution_node_ids.length} found
            </span>
          </span>
          {truth.decoy_node_ids.length > 0 && (
            <>
              <span className="font-medium">Decoys</span>
              <span className="flex items-center gap-2">
                <Squares
                  ids={truth.decoy_node_ids}
                  filled={(id) => (reportText ? reportText.includes(id) : view.touched.has(id))}
                  tone="bg-rejected"
                />
                <span className="text-graphite tabular-nums">
                  {reportText
                    ? `${truth.decoy_node_ids.filter((id) => reportText.includes(id)).length} of ${truth.decoy_node_ids.length} named in the verdict`
                    : `${truth.decoy_node_ids.filter((id) => view.touched.has(id)).length} of ${truth.decoy_node_ids.length} examined`}
                </span>
              </span>
            </>
          )}
        </button>
      )}
    </div>
  )
}
