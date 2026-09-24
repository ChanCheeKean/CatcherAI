import { createContext, useContext } from 'react'
import type { EvalCase, EvidenceLink } from '../api/types'
import type { Flow } from './flow'
import type { EvidenceGraph } from './useEvidenceGraph'
import type { RunView } from './store'
import type { graphModel } from './graphModel'

export type Selection = { kind: 'actor'; name: string } | { kind: 'node'; id: string } | null

export interface Highlight {
  nodeIds: Set<string>
  edgeIds: Set<string>
}

export type CanvasTab = 'flow' | 'timeline' | 'graph' | 'notebook'
/** Which nodes the evidence graph draws. */
export type GraphScope = 'connected' | 'all' | 'cited'

/** Everything the run page's panels share: the derived run plus the two cross-panel selections. */
export interface RunPanels {
  view: RunView
  /** The agent map derived from the same events. */
  flow: Flow
  /** Run time of the whole recorded run in ms, so a replay's time axis does not rescale as it plays. */
  runLength: number
  selection: Selection
  select: (selection: Selection) => void
  highlight: Highlight
  clearHighlight: () => void
  /** Everything the final report cites, once there is one. */
  cited: Highlight
  /** Properties of the nodes and edges the agents touched, plus expanded context. */
  graph: EvidenceGraph
  graphModel: ReturnType<typeof graphModel>
  /** Emphasise a piece of cited evidence in the evidence graph and switch to it. */
  showEvidence: (link: Pick<EvidenceLink, 'node_ids' | 'edge_ids'>) => void
  tab: CanvasTab
  setTab: (tab: CanvasTab) => void
  /** The evaluation's answer key for this case, when there is one. */
  truth: EvalCase | undefined
  /** Whether the evidence graph rings the answer key's solution and decoy nodes. */
  overlay: boolean
  setOverlay: (on: boolean) => void
  /** The scope the reader picked for the evidence graph; null until they pick one. Kept across tabs. */
  graphScope: GraphScope | null
  setGraphScope: (scope: GraphScope) => void
}

export const RunPanelsContext = createContext<RunPanels | null>(null)

export function useRunPanels(): RunPanels {
  const panels = useContext(RunPanelsContext)
  if (!panels) throw new Error('useRunPanels must be used inside the run page')
  return panels
}
