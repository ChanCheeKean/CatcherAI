import { createContext, useContext } from 'react'
import type { EvidenceLink } from '../api/types'
import type { Flow } from './flow'
import type { EvidenceGraph } from './useEvidenceGraph'
import type { RunView } from './store'

export type Selection = { kind: 'actor'; name: string } | { kind: 'node'; id: string } | null

export interface Highlight {
  nodeIds: Set<string>
  edgeIds: Set<string>
}

export type CanvasTab = 'flow' | 'graph'

/** Everything the run page's panels share: the derived run plus the two cross-panel selections. */
export interface RunPanels {
  view: RunView
  /** The agent map derived from the same events. */
  flow: Flow
  selection: Selection
  select: (selection: Selection) => void
  highlight: Highlight
  clearHighlight: () => void
  /** Everything the final report cites, once there is one. */
  cited: Highlight
  /** Properties of the nodes and edges the agents touched, plus expanded context. */
  graph: EvidenceGraph
  /** Emphasise a piece of cited evidence in the evidence graph and switch to it. */
  showEvidence: (link: Pick<EvidenceLink, 'node_ids' | 'edge_ids'>) => void
  tab: CanvasTab
  setTab: (tab: CanvasTab) => void
}

export const RunPanelsContext = createContext<RunPanels | null>(null)

export function useRunPanels(): RunPanels {
  const panels = useContext(RunPanelsContext)
  if (!panels) throw new Error('useRunPanels must be used inside the run page')
  return panels
}
