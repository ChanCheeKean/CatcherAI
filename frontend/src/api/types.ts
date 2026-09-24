// Mirrors the backend contracts in src/schemas.py and src/api/models.py.

export type Verdict = 'accepted' | 'partially_accepted' | 'rejected' | 'goodwill_credit' | 'not_a_dispute' | 'fraud_referral'
export type DisputeCategory = 'NKN' | 'RET' | 'CNC' | 'CNR' | 'DMG' | 'DSS' | 'DUP' | 'NRC' | 'OVR' | 'PDD'

/** Pydantic serialises Decimal as a string; amounts are read with `Number()`. */
export type Money = string | number

export interface CaseSummary {
  case_id: string
  title: string
  claim: string
  amount: number
  summary: string
  /** Newest finished run of this case, when there is one: opening the case shows it without running. */
  latest_run_id: string | null
  latest_verdict: Verdict | null
}

export interface EvidenceLink {
  claim: string
  node_ids: string[]
  edge_ids: string[]
  source_excerpt: string | null
}

export interface ChargeDecision {
  charge_id: string
  verdict: Verdict
  category: DisputeCategory
  disputed_amount: Money
  credit_amount: Money
  card_member_liability: Money
  rationale: string
  evidence: EvidenceLink[]
}

export interface HypothesisAssessment {
  hypothesis: string
  status: 'accepted' | 'rejected'
  why: string
  evidence: EvidenceLink[]
}

export interface Citation {
  document_id: string
  why: string
}

export interface SystemImprovement {
  target: 'amex_policy' | 'merchant_policy' | 'process' | 'product' | 'data'
  issue: string
  suggestion: string
  evidence: EvidenceLink[]
}

export interface CaseReport {
  case_id: string
  verdict: Verdict
  category: DisputeCategory
  headline: string
  executive_summary: string
  detailed_reasoning: string
  charges: ChargeDecision[]
  hypotheses: HypothesisAssessment[]
  decoys_ruled_out: string[]
  policy_basis: Citation[]
  system_improvements: SystemImprovement[]
  confidence: number
  flip_fact: string
  card_member_letter: string
}

export interface NotebookEntry {
  entry_id: string
  seq: number
  author: string
  kind: 'fact' | 'hypothesis' | 'policy_reading' | 'conflict' | 'ruled_out' | 'improvement_idea'
  text: string
  node_ids: string[]
  edge_ids: string[]
}

export interface GraphOntology {
  groups: Record<string, { title: string; description: string }>
  labels: Record<string, { group: string; description: string }>
  edges: Record<string, { description: string }>
  node_count: number
  edge_count: number
}

export type RunState = 'running' | 'completed' | 'failed'

export interface RunStatus {
  run_id: string
  case_id: string
  status: RunState
  error: string | null
  report: CaseReport | null
}

export type PlanStatus = 'open' | 'done' | 'waived'

export interface PlanItem {
  id: string
  question: string
  status: PlanStatus
  evidence_refs: string[]
  waiver_reason: string | null
}

export interface TrajectoryEvent {
  event_id: string
  run_id: string
  case_id: string | null
  seq: number
  ts_wall: string
  actor: { kind: string; name: string }
  visit: number
  turn: number
  parent_id: string | null
  type: string
  summary: string
  payload: Record<string, unknown>
  refs: string[]
  usage: { input_tokens: number; output_tokens: number; latency_ms: number }
}

export interface ApiErrorBody {
  error: { code: string; message: string }
}

export interface GraphNode {
  id: string
  label: string
  properties: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  type: string
  src: string
  dst: string
  properties: Record<string, unknown>
}

export interface GraphElements {
  nodes: GraphNode[]
  edges: GraphEdge[]
  missing: string[]
}

export interface Neighbors {
  neighbors: {
    type: string
    direction: 'out' | 'in'
    edge: Record<string, unknown>
    node: Record<string, unknown>
  }[]
  truncated: boolean
}

export interface EvalCase {
  case_id: string
  code: string
  title: string
  passed: boolean
  solution_node_ids: string[]
  decoy_node_ids: string[]
}

export interface EvalLatest {
  cases: EvalCase[]
}
