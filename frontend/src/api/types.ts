// Mirrors the backend contracts in src/schemas.py and src/api/models.py.

export type Verdict = 'accepted' | 'partially_accepted' | 'rejected' | 'not_a_dispute'

/** Pydantic serialises Decimal as a string; amounts are read with `Number()`. */
export type Money = string | number

export interface CaseSummary {
  case_id: string
  title: string
  claim_type: string
  amount: number
  summary: string
}

export interface EvidenceLink {
  claim: string
  node_ids: string[]
  edge_ids: string[]
  source_excerpt: string | null
}

export interface TransactionDecision {
  txn_id: string
  verdict: Verdict
  disputed_amount: Money
  credit_amount: Money
  cardholder_liability: Money
  network_action: 'file_dispute' | 'no_dispute' | 'pre_arbitration' | 'none'
  reason_code: string | null
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

export interface AccountAction {
  action: string
  target_id: string | null
  reason: string
}

export interface CaseReport {
  case_id: string
  verdict: Verdict
  claim_family: string
  headline: string
  executive_summary: string
  detailed_reasoning: string
  transactions: TransactionDecision[]
  hypotheses: HypothesisAssessment[]
  decoys_ruled_out: string[]
  missing_evidence: string[]
  policy_basis: Citation[]
  account_actions: AccountAction[]
  confidence: number
  flip_fact: string
  cardholder_letter: string
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
