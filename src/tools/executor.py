from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any, TypeVar

from domain.events import Actor, ActorKind, EventDraft, EventUsage
from observability.emitter import EventEmitter
from tools.schemas import validate_tool_input

T = TypeVar("T")


class ToolExecutor:
    def __init__(self, emitter: EventEmitter) -> None:
        self.emitter = emitter
        self.calls = 0
        self.limit: int | None = None

    def call(
        self,
        name: str,
        *,
        rationale: str,
        arguments: dict[str, Any],
        function: Callable[[], T],
        actor: str = "lead_investigator",
        version: int = 1,
    ) -> T:
        if not rationale.strip():
            raise ValueError("tool rationale is required")
        validated_arguments = validate_tool_input(name, arguments)
        if self.limit is not None and self.calls >= self.limit:
            self.emitter.emit(
                EventDraft(
                    actor=Actor(kind=ActorKind.HARNESS, name="budget_manager"),
                    type="access_denied",
                    summary=f"Denied {name}; tool-call budget is exhausted",
                    payload={
                        "tool": name,
                        "dimension": "tool_calls",
                        "used": self.calls,
                        "limit": self.limit,
                    },
                )
            )
            raise RuntimeError("tool-call budget exhausted")
        call_id = f"tool-{uuid.uuid4().hex}"
        self.calls += 1
        parent_span = self.emitter.current_span
        with self.emitter.span(call_id):
            self.emitter.emit(
                EventDraft(
                    actor=Actor(kind=ActorKind.TOOL, name=name),
                    type="tool_call",
                    summary=f"Called {name}: {rationale}",
                    payload={
                        "call_id": call_id,
                        "tool": name,
                        "version": version,
                        "rationale": rationale,
                        "arguments": validated_arguments,
                        "calling_actor": actor,
                    },
                    span_id=call_id,
                    parent_span_id=parent_span,
                )
            )
            started = time.perf_counter()
            try:
                result = function()
            except Exception as exc:
                self.emitter.emit(
                    EventDraft(
                        actor=Actor(kind=ActorKind.TOOL, name=name),
                        type="tool_result",
                        summary=f"{name} failed",
                        payload={
                            "call_id": call_id,
                            "status": "error",
                            "error": str(exc),
                            "duration_ms": int((time.perf_counter() - started) * 1000),
                        },
                        span_id=call_id,
                        parent_span_id=parent_span,
                    )
                )
                raise
            refs = _source_ids(result)
            blob = self.emitter.put_blob(result)
            duration_ms = int((time.perf_counter() - started) * 1000)
            self.emitter.emit(
                EventDraft(
                    actor=Actor(kind=ActorKind.TOOL, name=name),
                    type="tool_result",
                    summary=f"{name} returned {len(refs)} source records",
                    payload={
                        "call_id": call_id,
                        "status": "success",
                        "result_blob": blob,
                        "source_ids": refs,
                        "duration_ms": duration_ms,
                        "retry_count": 0,
                    },
                    refs=refs,
                    usage=EventUsage(latency_ms=duration_ms),
                    span_id=call_id,
                    parent_span_id=parent_span,
                )
            )
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.HARNESS, name="budget_manager"),
                type="budget_update",
                summary="Updated tool-call budget",
                payload={
                    "dimension": "tool_calls",
                    "used": self.calls,
                    "limit": self.limit,
                    "delta": 1,
                    "remaining": None if self.limit is None else self.limit - self.calls,
                },
            )
        )
        return result

    def account_external_call(self, name: str) -> None:
        """Count a centrally instrumented framework tool such as Deep Agents `task`."""

        if self.limit is not None and self.calls >= self.limit:
            raise RuntimeError(f"tool-call budget exhausted before {name}")
        self.calls += 1
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.HARNESS, name="budget_manager"),
                type="budget_update",
                summary=f"Updated tool-call budget for {name}",
                payload={
                    "dimension": "tool_calls",
                    "used": self.calls,
                    "limit": self.limit,
                    "delta": 1,
                    "remaining": None if self.limit is None else self.limit - self.calls,
                },
            )
        )


def _source_ids(value: Any) -> list[str]:
    keys = (
        "case_id",
        "txn_id",
        "packet_id",
        "doc_id",
        "comm_id",
        "event_id",
        "node_id",
        "merchant_node_id",
        "account_id",
    )
    rows = value if isinstance(value, list) else [value]
    found: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            found.extend(str(row[key]) for key in keys if row.get(key))
    return list(dict.fromkeys(found))
