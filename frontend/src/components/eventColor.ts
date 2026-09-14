import type { EventEnvelope } from '../api/types'

/** Fixed accent meanings from the design doc: cyan=active, violet=model/subagent, amber=wait,
 *  emerald=verified, rose=contradiction/failure, slate=historical/inactive. */
export function eventAccent(event: EventEnvelope): 'cyan' | 'violet' | 'amber' | 'emerald' | 'rose' | 'slate' {
  if (event.type === 'error' || event.type === 'contradiction_detected') return 'rose'
  if (event.type === 'termination' && event.payload.final_status === 'failed') return 'rose'
  if (event.type.startsWith('wait_')) return 'amber'
  if (event.type === 'verifier_check') return event.payload.passed === false ? 'rose' : 'emerald'
  if (event.type === 'panel_position' || event.type === 'adjudication') return 'emerald'
  if (event.actor.kind === 'agent' || event.actor.kind === 'subagent' || event.type.startsWith('llm_call'))
    return 'violet'
  if (
    event.type.startsWith('tool_') ||
    event.type.startsWith('node_') ||
    event.type === 'edge_taken' ||
    event.type.startsWith('graph_')
  )
    return 'cyan'
  return 'slate'
}
