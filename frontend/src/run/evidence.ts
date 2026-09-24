import type { CaseReport, EvidenceLink } from '../api/types'
import type { Flow } from './flow'
import type { Highlight } from './RunContext'

/** Every node and edge id an agent or tool touched: what "selecting it" means for the evidence graph. */
export function touchedBy(flow: Flow, name: string): Set<string> {
  const calls = flow.visits.get(name)?.flatMap((v) => v.tools) ?? flow.toolCalls.get(name) ?? []
  return new Set(calls.flatMap((call) => [...call.nodeIds, ...call.edgeIds]))
}

/** Everything the final report cites as evidence. */
export function citedBy(report: CaseReport | null): Highlight {
  const links = [...(report?.charges ?? []), ...(report?.hypotheses ?? []), ...(report?.system_improvements ?? [])].flatMap((x) => x.evidence)
  return {
    nodeIds: new Set(links.flatMap((l) => l.node_ids)),
    edgeIds: new Set(links.flatMap((l) => l.edge_ids)),
  }
}

/** Graph ids inside prose have an uppercase prefix and a digit, so ordinary hyphenated words stay words. */
export const REF_IN_TEXT = /([A-Z]{1,3}-(?=[A-Za-z0-9-]*\d)[A-Za-z0-9][A-Za-z0-9-]*)/

/** The graph ids a sentence names, split into nodes and edges by what the run has loaded. */
export function idsIn(text: string, edges: Map<string, unknown>): Pick<EvidenceLink, 'node_ids' | 'edge_ids'> {
  const ids = [...new Set(text.split(REF_IN_TEXT).filter((_, index) => index % 2))]
  return { node_ids: ids.filter((id) => !edges.has(id)), edge_ids: ids.filter((id) => edges.has(id)) }
}

/** Whether the graph is showing exactly this piece of evidence. */
export const isShown = (highlight: Highlight, link: Pick<EvidenceLink, 'node_ids' | 'edge_ids'>) =>
  highlight.nodeIds.size + highlight.edgeIds.size > 0 &&
  highlight.nodeIds.size === new Set(link.node_ids).size &&
  highlight.edgeIds.size === new Set(link.edge_ids).size &&
  link.node_ids.every((id) => highlight.nodeIds.has(id)) &&
  link.edge_ids.every((id) => highlight.edgeIds.has(id))
