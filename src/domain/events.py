from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
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


class Actor(BaseModel):
    kind: ActorKind
    name: str


class RuntimeSnapshot(BaseModel):
    config_hash: str
    agent_runtime: str
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
    actor: Actor
    visit: int = 1
    turn: int = 0
    parent_id: str | None = None
    type: str
    summary: str
    payload: dict[str, Any]
    refs: list[str] = Field(default_factory=list)
    runtime: RuntimeSnapshot
    usage: EventUsage = Field(default_factory=EventUsage)


class EventDraft(BaseModel):
    actor: Actor
    visit: int | None = None
    turn: int | None = None
    parent_id: str | None = None
    type: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    refs: list[str] = Field(default_factory=list)
    span_id: str | None = None
    parent_span_id: str | None = None
    usage: EventUsage = Field(default_factory=EventUsage)


class EventContext(BaseModel):
    actor: str | None = None
    visit: int = 1
    turn: int = 0
    parent_id: str | None = None


_EVENT_CONTEXT: ContextVar[EventContext | None] = ContextVar(
    "trajectory_event_context", default=None
)


def current_event_context() -> EventContext:
    return _EVENT_CONTEXT.get() or EventContext()


@contextmanager
def event_context(*, actor: str, visit: int, turn: int, parent_id: str | None = None):
    token = _EVENT_CONTEXT.set(
        EventContext(actor=actor, visit=visit, turn=turn, parent_id=parent_id)
    )
    try:
        yield
    finally:
        _EVENT_CONTEXT.reset(token)


def event_json_schema() -> dict[str, Any]:
    return EventEnvelope.model_json_schema()


def event_from_row(row: sqlite3.Row) -> EventEnvelope:
    """Map one `run_events` sqlite row to the canonical envelope.

    The single source of truth for this mapping: `EventEmitter`, `replay` and the API read
    models all persist/read the same `run_events` schema and must stay in sync with it here.
    """

    return EventEnvelope.model_validate(
        {
            "event_id": row["event_id"],
            "run_id": row["run_id"],
            "case_id": row["case_id"],
            "seq": row["seq"],
            "span_id": row["span_id"],
            "parent_span_id": row["parent_span_id"],
            "ts_wall": row["ts_wall"],
            "actor": {"kind": row["actor_kind"], "name": row["actor_name"]},
            "visit": row["visit"] if "visit" in row.keys() else 1,
            "turn": row["turn"] if "turn" in row.keys() else 0,
            "parent_id": row["parent_id"] if "parent_id" in row.keys() else None,
            "type": row["type"],
            "summary": row["summary"],
            "payload": json.loads(row["payload_json"]),
            "refs": json.loads(row["refs_json"]),
            "runtime": json.loads(row["runtime_json"]),
            "usage": json.loads(row["usage_json"]),
        }
    )
