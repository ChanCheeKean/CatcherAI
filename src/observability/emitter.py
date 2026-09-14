from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import threading
import uuid
from collections.abc import AsyncIterator, Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from domain.events import EventDraft, EventEnvelope, RuntimeSnapshot
from observability.redaction import redact


class EventEmitter:
    """Validate, redact, persist, and retrieve the canonical append-only trajectory."""

    def __init__(
        self,
        db_path: Path,
        *,
        run_id: str,
        case_id: str | None,
        runtime: RuntimeSnapshot,
        virtual_now: datetime,
    ) -> None:
        self.db_path = db_path
        self.run_id = run_id
        self.case_id = case_id
        self.runtime = runtime
        self.virtual_now = virtual_now
        self._lock = threading.RLock()
        self._root_span = f"span-run-{run_id}"
        self._span_stack: ContextVar[tuple[str, ...]] = ContextVar(
            f"span_stack_{run_id}", default=(self._root_span,)
        )
        self._subscribers: list[asyncio.Queue[EventEnvelope | None]] = []
        self._stream_closed = False
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS run_events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    case_id TEXT,
                    seq INTEGER NOT NULL,
                    span_id TEXT NOT NULL,
                    parent_span_id TEXT,
                    ts_wall TEXT NOT NULL,
                    ts_virtual TEXT NOT NULL,
                    actor_kind TEXT NOT NULL,
                    actor_name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    refs_json TEXT NOT NULL,
                    runtime_json TEXT NOT NULL,
                    usage_json TEXT NOT NULL,
                    redactions_json TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    previous_event_hash TEXT,
                    UNIQUE(run_id, seq)
                );
                CREATE TABLE IF NOT EXISTS run_blobs (
                    sha256 TEXT PRIMARY KEY,
                    media_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    content BLOB NOT NULL
                );
                """
            )

    @property
    def current_span(self) -> str:
        return self._span_stack.get()[-1]

    @contextmanager
    def span(self, span_id: str):
        stack = self._span_stack.get()
        token = self._span_stack.set((*stack, span_id))
        try:
            yield
        finally:
            self._span_stack.reset(token)

    def set_virtual_now(self, value: datetime) -> None:
        self.virtual_now = value

    def put_blob(self, value: Any, media_type: str = "application/json") -> str:
        redacted, _ = redact(value)
        content = (
            json.dumps(redacted, sort_keys=True, default=str, separators=(",", ":")).encode()
            if media_type == "application/json"
            else str(redacted).encode()
        )
        digest = hashlib.sha256(content).hexdigest()
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO run_blobs VALUES (?,?,?,?)",
                (digest, media_type, len(content), content),
            )
        return f"sha256:{digest}"

    def emit(self, draft: EventDraft) -> EventEnvelope:
        with self._lock, self._connect() as connection:
            payload, redactions = redact(draft.payload)
            refs, ref_redactions = redact(draft.refs)
            redactions.extend(ref_redactions)
            last = connection.execute(
                "SELECT seq, event_hash FROM run_events WHERE run_id=? ORDER BY seq DESC LIMIT 1",
                (self.run_id,),
            ).fetchone()
            seq = 1 if last is None else int(last["seq"]) + 1
            previous_hash = None if last is None else str(last["event_hash"])
            span_id = draft.span_id or self.current_span
            parent_span_id = draft.parent_span_id
            if (
                parent_span_id is None
                and span_id == self.current_span
                and len(self._span_stack.get()) > 1
            ):
                parent_span_id = self._span_stack.get()[-2]
            envelope = EventEnvelope(
                event_id=f"evt-{uuid.uuid4().hex}",
                run_id=self.run_id,
                case_id=self.case_id,
                seq=seq,
                span_id=span_id,
                parent_span_id=parent_span_id,
                ts_wall=datetime.now(UTC),
                ts_virtual=self.virtual_now,
                actor=draft.actor,
                type=draft.type,
                summary=draft.summary,
                payload=payload,
                refs=refs,
                runtime=self.runtime,
                usage=draft.usage,
                redactions=redactions,
            )
            serialized = envelope.model_dump(mode="json")
            canonical = json.dumps(serialized, sort_keys=True, separators=(",", ":"))
            event_hash = hashlib.sha256(f"{previous_hash or ''}{canonical}".encode()).hexdigest()
            connection.execute(
                """INSERT INTO run_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    envelope.event_id,
                    envelope.run_id,
                    envelope.case_id,
                    envelope.seq,
                    envelope.span_id,
                    envelope.parent_span_id,
                    envelope.ts_wall.isoformat(),
                    envelope.ts_virtual.isoformat(),
                    envelope.actor.kind.value,
                    envelope.actor.name,
                    envelope.type,
                    envelope.summary,
                    json.dumps(envelope.payload, default=str),
                    json.dumps(envelope.refs),
                    json.dumps(envelope.runtime.model_dump(mode="json")),
                    json.dumps(envelope.usage.model_dump(mode="json")),
                    json.dumps([item.model_dump(mode="json") for item in envelope.redactions]),
                    event_hash,
                    previous_hash,
                ),
            )
            for subscriber in self._subscribers:
                subscriber.put_nowait(envelope)
            return envelope

    async def subscribe(self) -> AsyncIterator[EventEnvelope]:
        """Yield the persisted prefix followed by events as they are committed."""

        queue: asyncio.Queue[EventEnvelope | None] = asyncio.Queue()
        with self._lock:
            existing = self.events()
            closed = self._stream_closed
            if not closed:
                self._subscribers.append(queue)
        try:
            for event in existing:
                yield event
            if closed:
                return
            while True:
                event = await queue.get()
                if event is None:
                    return
                yield event
        finally:
            with self._lock:
                if queue in self._subscribers:
                    self._subscribers.remove(queue)

    def close_stream(self) -> None:
        with self._lock:
            self._stream_closed = True
            for subscriber in self._subscribers:
                subscriber.put_nowait(None)

    def events(self) -> list[EventEnvelope]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM run_events WHERE run_id=? ORDER BY seq", (self.run_id,)
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> EventEnvelope:
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

    def verify_chain(self) -> bool:
        previous: str | None = None
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM run_events WHERE run_id=? ORDER BY seq", (self.run_id,)
            ).fetchall()
        for expected_seq, row in enumerate(rows, start=1):
            if row["seq"] != expected_seq or row["previous_event_hash"] != previous:
                return False
            event = self._row_to_event(row)
            canonical = json.dumps(
                event.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            )
            computed = hashlib.sha256(f"{previous or ''}{canonical}".encode()).hexdigest()
            if computed != row["event_hash"]:
                return False
            previous = computed
        return bool(rows)

    def last_event(self) -> EventEnvelope | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM run_events WHERE run_id=? ORDER BY seq DESC LIMIT 1", (self.run_id,)
            ).fetchone()
        return self._row_to_event(row) if row else None

    def restore_virtual_now(self) -> None:
        """Continue a persisted run at the virtual time of its last event."""

        last = self.last_event()
        if last is not None:
            self.virtual_now = last.ts_virtual

    def last_budget_used(self, dimension: str) -> int:
        used = [
            int(event.payload["used"])
            for event in self.events()
            if event.type == "budget_update" and event.payload.get("dimension") == dimension
        ]
        return used[-1] if used else 0

    def event_types(self) -> Iterable[str]:
        return (event.type for event in self.events())
