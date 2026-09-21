import type { CaseReport, TrajectoryEvent } from '../api/types'

let seq = 0
export function event(
  type: string,
  actor: string,
  payload: Record<string, unknown> = {},
  extra: Partial<TrajectoryEvent> = {},
): TrajectoryEvent {
  seq += 1
  return {
    event_id: `e${seq}`,
    run_id: 'run-1',
    case_id: 'DSP-1',
    seq,
    ts_wall: '2026-09-21T10:00:00Z',
    actor: { kind: 'graph_node', name: actor },
    visit: 1,
    turn: 0,
    parent_id: null,
    type,
    summary: `${actor} ${type}`,
    payload,
    refs: [],
    usage: { input_tokens: 0, output_tokens: 0, latency_ms: 0 },
    ...extra,
  }
}

export const evidence = { claim: 'Both cards share one drop address', node_ids: ['ADR-1'], edge_ids: ['E-1'], source_excerpt: null }

export const report: CaseReport = {
  case_id: 'DSP-1',
  verdict: 'rejected',
  claim_family: 'card_not_present_fraud',
  headline: 'The cardholder authorised this purchase through a family tablet.',
  executive_summary: 'The tablet belongs to the household.',
  detailed_reasoning: 'Step one.\nStep two.',
  transactions: [
    {
      txn_id: 'TXN-1',
      verdict: 'rejected',
      disputed_amount: '120.50',
      credit_amount: '0',
      cardholder_liability: '120.50',
      network_action: 'no_dispute',
      reason_code: null,
      rationale: 'Authorised by an household member.',
      evidence: [evidence],
    },
  ],
  hypotheses: [{ hypothesis: 'Card stolen', status: 'rejected', why: 'The device is known.', evidence: [evidence] }],
  decoys_ruled_out: ['Shared IP is a CGNAT block'],
  missing_evidence: [],
  policy_basis: [{ document_id: 'POL-9', why: 'Authorised use' }],
  account_actions: [],
  confidence: 0.9,
  flip_fact: 'The tablet was reported stolen before the purchase',
  cardholder_letter: 'Dear customer, …',
}
