"""Stable API DTOs. Routers and read models must return these, never raw sqlite rows."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel

from domain.events import EventEnvelope

RunStatus = Literal["running", "suspended", "decided", "cancelled", "failed"]


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
    graph_available: bool


class MetaResponse(BaseModel):
    adapters: dict[str, bool]
    model: str
    virtual_clock: str
    feature_flags: dict[str, bool]


class RouteSummary(BaseModel):
    id: str
    priority: int
    match: dict[str, Any]
    depth: str
    graph_path: str
    agents: list[str]
    skills: list[str]
    budget: dict[str, Any]


class AgentSummary(BaseModel):
    id: str
    version: int
    description: str
    model_role: str
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
