from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Sequence
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
            "ts_virtual": row["ts_virtual"],
            "actor": {"kind": row["actor_kind"], "name": row["actor_name"]},
            "type": row["type"],
            "summary": row["summary"],
            "payload": json.loads(row["payload_json"]),
            "refs": json.loads(row["refs_json"]),
            "runtime": json.loads(row["runtime_json"]),
            "usage": json.loads(row["usage_json"]),
            "redactions": json.loads(row["redactions_json"]),
        }
    )


def verify_event_chain(rows: Sequence[sqlite3.Row]) -> bool:
    """Replay a `run_events` hash chain (ordered by seq) and confirm every link holds."""

    previous: str | None = None
    for expected_seq, row in enumerate(rows, start=1):
        if row["seq"] != expected_seq or row["previous_event_hash"] != previous:
            return False
        canonical = json.dumps(
            event_from_row(row).model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        computed = hashlib.sha256(f"{previous or ''}{canonical}".encode()).hexdigest()
        if computed != row["event_hash"]:
            return False
        previous = computed
    return bool(rows)
