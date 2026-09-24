import { useMutation, useQuery } from '@tanstack/react-query'
import { useCallback, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import type { EvidenceLink } from '../api/types'
import { Canvas } from '../run/Canvas'
import { Conclusion } from '../run/Conclusion'
import { citedBy } from '../run/evidence'
import { deriveFlow } from '../run/flow'
import { Funnel } from '../run/Funnel'
import { graphModel } from '../run/graphModel'
import { Inspector } from '../run/Inspector'
import { type CanvasTab, type GraphScope, type Highlight, RunPanelsContext, type Selection } from '../run/RunContext'
import { graphIds } from '../run/store'
import { Timeline } from '../run/Timeline'
import { useEvidenceGraph } from '../run/useEvidenceGraph'
import { useRunEvents, useRunView } from '../run/useRunEvents'

const NO_HIGHLIGHT: Highlight = { nodeIds: new Set(), edgeIds: new Set() }

const statusLabel = { running: 'Running', completed: 'Decided', failed: 'Failed' } as const
/** Opening a case with `?replay` plays its recorded run from the start. */
const REPLAY_PARAM = 'replay'
const statusDot = { running: 'bg-partial breathing', completed: 'bg-accepted', failed: 'bg-rejected' } as const

/** Keyed by run so that "Run again" starts with a clean selection, highlight and graph. */
export function RunPage() {
  const { runId = '' } = useParams()
  return <RunView key={runId} />
}

function RunView() {
  const { caseId = '', runId = '' } = useParams()
  const navigate = useNavigate()
  const [search] = useSearchParams()
  const autoplay = search.has(REPLAY_PARAM)
  const stream = useRunEvents(runId)
  // How many events are shown: all of them (following a live run) until the replay controls take over.
  const [cursor, setCursor] = useState<number | null>(autoplay ? 0 : null)
  const view = useRunView(stream, cursor ?? stream.events.length)
  const replaying = cursor !== null && cursor < stream.events.length
  const cases = useQuery({ queryKey: ['cases'], queryFn: api.listCases })
  const ontology = useQuery({ queryKey: ['ontology'], queryFn: api.getOntology, staleTime: Infinity })
  const evalData = useQuery({ queryKey: ['eval'], queryFn: api.evalLatest, staleTime: 60_000 })
  const truth = evalData.data?.cases.find((item) => item.case_id === caseId)
  const [overlay, setOverlay] = useState(false)
  const [graphScope, setGraphScope] = useState<GraphScope | null>(null)
  const model = useMemo(() => ontology.data && graphModel(ontology.data), [ontology.data])
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
  // Fetch what the whole run touches up front, so a replay never waits on the graph.
  const runIds = useMemo(() => graphIds(stream.events), [stream.events])
  const graph = useEvidenceGraph([
    ...runIds,
    ...cited.nodeIds,
    ...cited.edgeIds,
    ...highlight.nodeIds,
    ...highlight.edgeIds,
  ])
  const panels = useMemo(
    () =>
      model && {
        view, flow, selection, select, highlight, clearHighlight, cited, graph, graphModel: model, showEvidence, tab, setTab, truth, overlay, setOverlay, graphScope, setGraphScope,
      },
    [view, flow, selection, highlight, clearHighlight, cited, graph, model, showEvidence, tab, truth, overlay, graphScope],
  )

  return (
    <RunPanelsContext.Provider value={panels ?? null}>
      {!model ? (
        <p className="p-4">{ontology.error ? `Could not load graph ontology: ${ontology.error.message}` : 'Loading graph ontology…'}</p>
      ) : (
      <div className="flex min-h-screen flex-col lg:h-screen">
        <header className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b bg-vellum px-4 py-3 sm:px-6">
          <Link to="/" className="text-sm text-graphite underline-offset-4 hover:text-ink hover:underline">
            Back to cases
          </Link>
          <h1 className="text-lg font-semibold">{title}</h1>
          <span role="status" className="flex items-center gap-2 text-sm">
            <span className={`size-2.5 rounded-full ${statusDot[view.status]}`} aria-hidden />
            {replaying && view.status === 'running' ? 'Replaying' : statusLabel[view.status]}
          </span>
          {ontology.data && (
            <div className="order-last basis-full lg:order-none lg:ml-6 lg:basis-auto">
              <Funnel total={ontology.data.node_count} />
            </div>
          )}
          <button
            type="button"
            onClick={() => rerun.mutate()}
            disabled={rerun.isPending}
            className="ml-auto cursor-pointer rounded-sm bg-ink px-3 py-1.5 text-sm font-medium text-vellum disabled:opacity-60"
          >
            Run again
          </button>
        </header>
        {stream.finished && <Timeline events={stream.events} onCursor={setCursor} autoplay={autoplay} />}

        <div className="grid min-h-[28rem] flex-1 lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_minmax(26rem,32%)]">
          <Canvas />
          <Inspector />
        </div>
        <Conclusion />
      </div>
      )}
    </RunPanelsContext.Provider>
  )
}
