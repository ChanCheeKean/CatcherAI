// Mirrors src/api/models.py and src/domain/events.py. Keep in sync by hand — the backend has no
// generated TS client yet; schemas/openapi.json is the source of truth if these drift.

export type RunStatus = 'running' | 'suspended' | 'decided' | 'cancelled' | 'failed' | 'ranked'
export type Adapter = 'fake' | 'openai'

export type ActorKind =
  | 'graph_node'
  | 'agent'
  | 'subagent'
  | 'tool'
  | 'memory'
  | 'sandbox'
  | 'harness'
  | 'evaluator'

export interface Actor {
  kind: ActorKind
  name: string
}

export interface RuntimeSnapshot {
  config_hash: string
  agent_runtime: string
  model_gateway: string
  provider: string
  model: string
  adapter_versions: Record<string, string>
}

export interface EventUsage {
  input_tokens: number
  output_tokens: number
  reasoning_tokens: number
  cached_tokens: number
  cost_usd: string
  latency_ms: number
}

export interface Redaction {
  path: string
  category: string
  replacement: string
}

export interface EventEnvelope {
  schema_version: '1.0'
  event_id: string
  run_id: string
  case_id: string | null
  seq: number
  span_id: string
  parent_span_id: string | null
  ts_wall: string
  ts_virtual: string
  actor: Actor
  type: string
  summary: string
  payload: Record<string, unknown>
  refs: string[]
  runtime: RuntimeSnapshot
  usage: EventUsage
  redactions: Redaction[]
}

export interface CaseSummary {
  case_id: string
  regime: string
  status: string
  stage: string
  customer_id: string
  account_id: string
  claim_family_initial: string
  network: string | null
  network_condition: string | null
  dispute_amount: string | null
  opened_at: string
  cardholder_outcome: string | null
  network_outcome: string | null
}

export interface CasePage {
  items: CaseSummary[]
  next_cursor: string | null
  limit: number
}

export interface TransactionSummary {
  txn_id: string
  merchant_id: string
  merchant_name: string | null
  descriptor: string | null
  channel: string | null
  billing_amount: string | null
  processing_date: string | null
}

export interface CommunicationSummary {
  comm_id: string
  channel: string | null
  party: string | null
  timestamp_utc: string | null
  subject: string | null
}

export interface RunRef {
  run_id: string
  status: RunStatus
  started_at: string | null
  last_event_at: string | null
  event_count: number
}

export interface CaseDetail extends CaseSummary {
  transactions: TransactionSummary[]
  communications: CommunicationSummary[]
  latest_runs: RunRef[]
}

export interface RunSummary {
  run_id: string
  case_id: string | null
  status: RunStatus
  event_count: number
  first_seq: number
  last_seq: number
  started_at: string | null
  last_event_at: string | null
  virtual_now: string | null
  wait: Record<string, unknown> | null
  decision_available: boolean
}

export interface RunPage {
  items: RunSummary[]
  next_cursor: string | null
  limit: number
}

export interface EventPage {
  items: EventEnvelope[]
  next_after_seq: number | null
  limit: number
}

export interface DecisionResponse {
  run_id: string
  case_id: string
  record: Record<string, unknown>
  field_provenance: Record<string, unknown>
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  scenario_db: boolean
  scenario_db_path: string
}

export interface MetaResponse {
  adapters: Record<Adapter, boolean>
  model: string
  virtual_clock: string
  feature_flags: Record<string, boolean>
}

export interface WorkflowNode {
  id: string
  label: string
  kind: string
}

export interface WorkflowEdge {
  source: string
  target: string
  kind: 'fixed' | 'conditional' | 'fan_out' | 'resume'
  label: string | null
}

export interface WorkflowGraph {
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
}

export interface RunCreateRequest {
  case_id: string
  adapter: Adapter
  auto_resume: boolean
}

export interface RunStartResponse {
  run_id: string
  case_id: string | null
  status: RunStatus
  events_url: string
  stream_url: string
}

export interface QueueRunResponse {
  run_id: string
  status: RunStatus
  ranking: Array<Record<string, unknown>> | null
}

export interface MemoryNote {
  note_id: string
  kind: string
  scope: string
  subject_ids: string[]
  content: string
  created_at: string
  created_by: string
  source_refs: string[]
  confidence: number
  status: string
  valid_from: string | null
  valid_to: string | null
  superseded_by: string | null
  tags: string[]
  sensitivity: string
  last_accessed_at: string | null
  access_count: number
}

export interface MemoryNotePage { items: MemoryNote[]; next_cursor: string | null; limit: number }
export interface RunMemoryResponse { run_id: string; operations: EventEnvelope[]; groups: Record<string, number> }
export interface GraphNode { id: string; label: string; kind: string; properties: Record<string, unknown>; source_refs: string[]; event_seqs: number[] }
export interface GraphEdge { id: string; source: string; target: string; label: string; properties: Record<string, unknown>; source_refs: string[]; event_seqs: number[] }
export interface GraphResponse { nodes: GraphNode[]; edges: GraphEdge[]; legend: Record<string, string> }
export interface RunGraphResponse { run_id: string; operations: EventEnvelope[]; nodes: GraphNode[]; edges: GraphEdge[] }
export interface SourceResponse { source_id: string; kind: string; title: string; data: Record<string, unknown>; related_source_ids: string[] }
export interface BlobResponse { sha256: string; media_type: string; size_bytes: number; content: unknown }

export interface EvaluationReportSummary { report_id: string; modified_at: string; attempts: number; passed: number; cases: number; pass_rate: number; stable_cases: number; reconciled_attempts: number }
export interface EvaluationProvingEvent { capability: string; case_id: string; run_id: string; seq: number; type: string; summary: string; ts_virtual: string }
export interface EvaluationAttempt { run_index: number; run_id: string; case_id: string; passed: boolean; trajectory_complete: boolean; metrics: Record<string, unknown>; capabilities: Array<Record<string, unknown>> }
export interface EvaluationReportDetail { report_id: string; summary: EvaluationReportSummary; reliability: Array<Record<string, unknown>>; capability_matrix: Record<string, Record<string, boolean>>; attempts: EvaluationAttempt[]; proving_events: EvaluationProvingEvent[] }

export interface ApiErrorBody {
  error: { code: string; message: string; details: Record<string, unknown> }
}
