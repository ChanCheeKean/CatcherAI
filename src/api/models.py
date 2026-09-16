"""Stable API DTOs. Routers and read models must return these, never raw sqlite rows."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from domain.events import EventEnvelope

RunStatus = Literal["running", "suspended", "decided", "cancelled", "failed", "ranked"]
Adapter = Literal["fake", "openai"]


class CaseSummary(BaseModel):
    case_id: str
    regime: str
    status: str
    stage: str
    customer_id: str
    account_id: str
    claim_family_initial: str
    network: str | None
    network_condition: str | None
    dispute_amount: Decimal | None
    opened_at: str
    cardholder_outcome: str | None
    network_outcome: str | None


class CasePage(BaseModel):
    items: list[CaseSummary]
    next_cursor: str | None
    limit: int


class TransactionSummary(BaseModel):
    txn_id: str
    merchant_id: str
    merchant_name: str | None
    descriptor: str | None
    channel: str | None
    billing_amount: Decimal | None
    processing_date: str | None


class CommunicationSummary(BaseModel):
    comm_id: str
    channel: str | None
    party: str | None
    timestamp_utc: str | None
    subject: str | None


class RunRef(BaseModel):
    run_id: str
    status: RunStatus
    started_at: str | None
    last_event_at: str | None
    event_count: int


class CaseDetail(CaseSummary):
    transactions: list[TransactionSummary]
    communications: list[CommunicationSummary]
    latest_runs: list[RunRef]


class RunSummary(BaseModel):
    run_id: str
    case_id: str | None
    status: RunStatus
    event_count: int
    first_seq: int
    last_seq: int
    started_at: str | None
    last_event_at: str | None
    virtual_now: str | None
    wait: dict[str, Any] | None
    decision_available: bool


class RunPage(BaseModel):
    items: list[RunSummary]
    next_cursor: str | None
    limit: int


class EventPage(BaseModel):
    items: list[EventEnvelope]
    next_after_seq: int | None
    limit: int


class DecisionResponse(BaseModel):
    run_id: str
    case_id: str
    record: dict[str, Any]
    field_provenance: dict[str, Any]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    scenario_db: bool
    scenario_db_path: str


class MetaResponse(BaseModel):
    adapters: dict[str, bool]
    model: str
    virtual_clock: str
    feature_flags: dict[str, bool]


class RouteSummary(BaseModel):
    id: str
    depth: str
    description: str
    required_skills: list[str]


class AgentSummary(BaseModel):
    id: str
    version: int
    description: str
    tools: list[str]
    skills: list[str]


class SkillSummary(BaseModel):
    name: str
    description: str
    version: int
    path: str


class WorkflowNode(BaseModel):
    id: str
    label: str
    kind: str


class WorkflowEdge(BaseModel):
    source: str
    target: str
    kind: Literal["fixed", "conditional", "fan_out", "resume"]
    label: str | None = None


class WorkflowGraph(BaseModel):
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]


class RunCreateRequest(BaseModel):
    case_id: str
    adapter: Adapter = "fake"
    auto_resume: bool = True


class QueueRunCreateRequest(BaseModel):
    adapter: Adapter = "fake"


class RunStartResponse(BaseModel):
    run_id: str
    case_id: str | None
    status: RunStatus
    events_url: str
    stream_url: str


class QueueRunResponse(BaseModel):
    run_id: str
    status: RunStatus
    ranking: list[dict[str, Any]] | None


class MemoryNoteSummary(BaseModel):
    note_id: str
    kind: str
    scope: str
    subject_ids: list[str]
    content: str
    created_at: str
    created_by: str
    source_refs: list[str]
    confidence: float
    status: str
    valid_from: str | None
    valid_to: str | None
    superseded_by: str | None
    tags: list[str]
    sensitivity: str
    last_accessed_at: str | None
    access_count: int


class MemoryNotePage(BaseModel):
    items: list[MemoryNoteSummary]
    next_cursor: str | None
    limit: int


class MemoryNoteDetail(MemoryNoteSummary):
    lifecycle_events: list[EventEnvelope]


class RunMemoryResponse(BaseModel):
    run_id: str
    operations: list[EventEnvelope]
    groups: dict[str, int]


class GraphNode(BaseModel):
    id: str
    label: str
    kind: str
    properties: dict[str, Any]
    source_refs: list[str]
    event_seqs: list[int] = Field(default_factory=list)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    properties: dict[str, Any]
    source_refs: list[str]
    event_seqs: list[int] = Field(default_factory=list)


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    legend: dict[str, str]


class RunGraphResponse(BaseModel):
    run_id: str
    operations: list[EventEnvelope]
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class SourceResponse(BaseModel):
    source_id: str
    kind: str
    title: str
    data: dict[str, Any]
    related_source_ids: list[str]


class BlobResponse(BaseModel):
    sha256: str
    media_type: str
    size_bytes: int
    content: Any


class EvaluationReportSummary(BaseModel):
    report_id: str
    modified_at: str
    attempts: int
    passed: int
    cases: int
    pass_rate: float
    stable_cases: int
    reconciled_attempts: int


class EvaluationProvingEvent(BaseModel):
    capability: str
    case_id: str
    run_id: str
    seq: int
    type: str
    summary: str
    ts_virtual: str


class EvaluationAttemptSummary(BaseModel):
    run_index: int
    run_id: str
    case_id: str
    passed: bool
    trajectory_complete: bool
    metrics: dict[str, Any]
    capabilities: list[dict[str, Any]]


class EvaluationReportDetail(BaseModel):
    report_id: str
    summary: EvaluationReportSummary
    reliability: list[dict[str, Any]]
    capability_matrix: dict[str, dict[str, bool]]
    attempts: list[EvaluationAttemptSummary]
    proving_events: list[EvaluationProvingEvent]
