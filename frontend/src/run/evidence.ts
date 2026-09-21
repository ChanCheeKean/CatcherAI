import type { CaseReport } from '../api/types'
import type { Flow } from './flow'
import type { Highlight } from './RunContext'

/** Every node and edge id an agent or tool touched: what "selecting it" means for the evidence graph. */
export function touchedBy(flow: Flow, name: string): Set<string> {
  const calls = flow.visits.get(name)?.flatMap((v) => v.tools) ?? flow.toolCalls.get(name) ?? []
  return new Set(calls.flatMap((call) => [...call.nodeIds, ...call.edgeIds]))
}

/** Everything the final report cites as evidence. */
export function citedBy(report: CaseReport | null): Highlight {
  const links = [...(report?.transactions ?? []), ...(report?.hypotheses ?? [])].flatMap((x) => x.evidence)
  return {
    nodeIds: new Set(links.flatMap((l) => l.node_ids)),
    edgeIds: new Set(links.flatMap((l) => l.edge_ids)),
  }
}
