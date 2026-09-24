import { vi } from 'vitest'
import type { CaseReport, TrajectoryEvent } from '../api/types'
import { deriveFlow } from './flow'
import { graphModel } from './graphModel'
import type { RunPanels } from './RunContext'
import { emptyRun, reduceEvent } from './store'

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

export const evidence = { claim: 'The charge exceeds the agreed amount', node_ids: ['CHG-1'], edge_ids: ['E-1'], source_excerpt: null }

export const report: CaseReport = {
  case_id: 'DSP-1',
  verdict: 'rejected',
  category: 'OVR',
  headline: 'The charged amount matches the agreed price.',
  executive_summary: 'The Merchant charged the agreed price.',
  detailed_reasoning: 'The order confirms the price.',
  charges: [{
    charge_id: 'CHG-1', verdict: 'rejected', category: 'OVR',
    disputed_amount: '120.50', credit_amount: '0', card_member_liability: '120.50',
    rationale: 'The charge matches the order.', evidence: [evidence],
  }],
  hypotheses: [{ hypothesis: 'Wrong amount', status: 'rejected', why: 'The order confirms the amount.', evidence: [evidence] }],
  decoys_ruled_out: ['Another order was refunded'],
  policy_basis: [{ document_id: 'CLS-9', why: 'The accepted price applies.' }],
  system_improvements: [],
  confidence: 0.9,
  flip_fact: 'The order stated a lower price',
  card_member_letter: 'Dear Card Member, …',
}

/** Run-page panels folded from `events`, with inert callbacks; `overrides` replaces any of them. */
export function panels(events: TrajectoryEvent[], overrides: Partial<RunPanels> = {}): RunPanels {
  return {
    view: events.reduce(reduceEvent, emptyRun()),
    flow: deriveFlow(events),
    runLength: 0,
    selection: null,
    select: vi.fn(),
    highlight: { nodeIds: new Set(), edgeIds: new Set() },
    clearHighlight: vi.fn(),
    cited: { nodeIds: new Set(), edgeIds: new Set() },
    graph: { nodes: new Map(), edges: new Map(), expand: vi.fn(), expanded: new Set() },
    graphModel: graphModel({ groups: { case: { title: 'Case', description: '' } }, labels: {}, edges: {}, node_count: 0, edge_count: 0 }),
    showEvidence: vi.fn(),
    tab: 'flow',
    setTab: vi.fn(),
    truth: undefined,
    overlay: false,
    setOverlay: vi.fn(),
    graphScope: null,
    setGraphScope: vi.fn(),
    ...overrides,
  }
}
