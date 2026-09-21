import { useMutation, useQuery } from '@tanstack/react-query'
import { useCallback, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { EvidenceLink } from '../api/types'
import { Canvas } from '../run/Canvas'
import { Conclusion } from '../run/Conclusion'
import { citedBy } from '../run/evidence'
import { deriveFlow } from '../run/flow'
import { Inspector } from '../run/Inspector'
import { type CanvasTab, type Highlight, RunPanelsContext, type Selection } from '../run/RunContext'
import { useEvidenceGraph } from '../run/useEvidenceGraph'
import { useRunEvents } from '../run/useRunEvents'

const NO_HIGHLIGHT: Highlight = { nodeIds: new Set(), edgeIds: new Set() }

const statusLabel = { running: 'Running', completed: 'Decided', failed: 'Failed' } as const
const statusDot = { running: 'bg-partial breathing', completed: 'bg-accepted', failed: 'bg-rejected' } as const

/** Keyed by run so that "Run again" starts with a clean selection, highlight and graph. */
export function RunPage() {
  const { runId = '' } = useParams()
  return <RunView key={runId} />
}

function RunView() {
  const { caseId = '', runId = '' } = useParams()
  const navigate = useNavigate()
  const view = useRunEvents(runId)
  const cases = useQuery({ queryKey: ['cases'], queryFn: api.listCases })
  const title = cases.data?.find((item) => item.case_id === caseId)?.title ?? caseId

  const [selection, select] = useState<Selection>(null)
  const [highlight, setHighlight] = useState<Highlight>(NO_HIGHLIGHT)
  const [tab, setTab] = useState<CanvasTab>('flow')

  const showEvidence = useCallback((link: Pick<EvidenceLink, 'node_ids' | 'edge_ids'>) => {
    setHighlight({ nodeIds: new Set(link.node_ids), edgeIds: new Set(link.edge_ids) })
    setTab('graph')
  }, [])
  const clearHighlight = useCallback(() => setHighlight(NO_HIGHLIGHT), [])
  const rerun = useMutation({
    mutationFn: () => api.startRun(caseId),
    onSuccess: (run) => navigate(`/cases/${run.case_id}/runs/${run.run_id}`),
  })
  const flow = useMemo(() => deriveFlow(view.events), [view.events])
  const cited = useMemo(() => citedBy(view.report), [view.report])
  const graph = useEvidenceGraph(runId, [
    ...view.touched.keys(),
    ...cited.nodeIds,
    ...cited.edgeIds,
    ...highlight.nodeIds,
    ...highlight.edgeIds,
  ])
  const panels = useMemo(
    () => ({ view, flow, selection, select, highlight, clearHighlight, cited, graph, showEvidence, tab, setTab }),
    [view, flow, selection, highlight, clearHighlight, cited, graph, showEvidence, tab],
  )

  return (
    <RunPanelsContext.Provider value={panels}>
      <div className="flex min-h-screen flex-col lg:h-screen">
        <header className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b bg-vellum px-4 py-3 sm:px-6">
          <Link to="/" className="text-sm text-graphite underline-offset-4 hover:text-ink hover:underline">
            Back to cases
          </Link>
          <h1 className="text-lg font-semibold">{title}</h1>
          <span role="status" className="flex items-center gap-2 text-sm">
            <span className={`size-2.5 rounded-full ${statusDot[view.status]}`} aria-hidden />
            {statusLabel[view.status]}
          </span>
          <button
            type="button"
            onClick={() => rerun.mutate()}
            disabled={rerun.isPending}
            className="ml-auto cursor-pointer rounded-sm bg-ink px-3 py-1.5 text-sm font-medium text-vellum disabled:opacity-60"
          >
            Run again
          </button>
        </header>

        <div className="grid min-h-[28rem] flex-1 lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_minmax(26rem,32%)]">
          <Canvas />
          <Inspector />
        </div>
        <Conclusion />
      </div>
    </RunPanelsContext.Provider>
  )
}
