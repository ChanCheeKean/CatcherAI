from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ActorKind(StrEnum):
    GRAPH_NODE = "graph_node"
    AGENT = "agent"
    SUBAGENT = "subagent"
    TOOL = "tool"
    MEMORY = "memory"
    SANDBOX = "sandbox"
    HARNESS = "harness"
    EVALUATOR = "evaluator"


class Actor(BaseModel):
    kind: ActorKind
    name: str


class RuntimeSnapshot(BaseModel):
    config_hash: str
    agent_runtime: str
    model_gateway: str
    provider: str
    model: str
    adapter_versions: dict[str, str] = Field(default_factory=dict)


class EventUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    latency_ms: int = 0


class Redaction(BaseModel):
    path: str
    category: str
    replacement: str = "[REDACTED]"


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    event_id: str
    run_id: str
    case_id: str | None
    seq: int
    span_id: str
    parent_span_id: str | None
    ts_wall: datetime
    ts_virtual: datetime
    actor: Actor
    type: str
    summary: str
    payload: dict[str, Any]
    refs: list[str] = Field(default_factory=list)
    runtime: RuntimeSnapshot
    usage: EventUsage = Field(default_factory=EventUsage)
    redactions: list[Redaction] = Field(default_factory=list)


class EventDraft(BaseModel):
    actor: Actor
    type: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    refs: list[str] = Field(default_factory=list)
    span_id: str | None = None
    parent_span_id: str | None = None
    usage: EventUsage = Field(default_factory=EventUsage)


def event_json_schema() -> dict[str, Any]:
    return EventEnvelope.model_json_schema()
