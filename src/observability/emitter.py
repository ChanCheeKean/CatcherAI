from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import uuid
from collections.abc import AsyncIterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

from domain.events import (
    EventDraft,
    EventEnvelope,
    RuntimeSnapshot,
    current_event_context,
    event_from_row,
)


class EventEmitter:
    """Persist and stream the append-only trajectory for one run."""

    def __init__(
        self,
        db_path: Path,
        *,
        run_id: str,
        case_id: str | None,
        runtime: RuntimeSnapshot,
    ) -> None:
        self.db_path = db_path
        self.run_id = run_id
        self.case_id = case_id
        self.runtime = runtime
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
                    actor_kind TEXT NOT NULL,
                    actor_name TEXT NOT NULL,
                    visit INTEGER NOT NULL DEFAULT 1,
                    turn INTEGER NOT NULL DEFAULT 0,
                    parent_id TEXT,
                    type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    refs_json TEXT NOT NULL,
                    runtime_json TEXT NOT NULL,
                    usage_json TEXT NOT NULL,
                    UNIQUE(run_id, seq)
                );
                """
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(run_events)").fetchall()
            }
            for name, ddl in (
                ("visit", "INTEGER NOT NULL DEFAULT 1"),
                ("turn", "INTEGER NOT NULL DEFAULT 0"),
                ("parent_id", "TEXT"),
            ):
                if name not in columns:
                    connection.execute(f"ALTER TABLE run_events ADD COLUMN {name} {ddl}")

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

    def emit(self, draft: EventDraft) -> EventEnvelope:
        with self._lock, self._connect() as connection:
            last = connection.execute(
                "SELECT seq FROM run_events WHERE run_id=? ORDER BY seq DESC LIMIT 1",
                (self.run_id,),
            ).fetchone()
            seq = 1 if last is None else int(last["seq"]) + 1
            span_id = draft.span_id or self.current_span
            parent_span_id = draft.parent_span_id
            if (
                parent_span_id is None
                and span_id == self.current_span
                and len(self._span_stack.get()) > 1
            ):
                parent_span_id = self._span_stack.get()[-2]
            context = current_event_context()
            envelope = EventEnvelope(
                event_id=f"evt-{uuid.uuid4().hex}",
                run_id=self.run_id,
                case_id=self.case_id,
                seq=seq,
                span_id=span_id,
                parent_span_id=parent_span_id,
                ts_wall=datetime.now(UTC),
                actor=draft.actor,
                visit=draft.visit if draft.visit is not None else context.visit,
                turn=draft.turn if draft.turn is not None else context.turn,
                parent_id=draft.parent_id if draft.parent_id is not None else context.parent_id,
                type=draft.type,
                summary=draft.summary,
                payload=draft.payload,
                refs=draft.refs,
                runtime=self.runtime,
                usage=draft.usage,
            )
            connection.execute(
                """INSERT INTO run_events (
                    event_id, run_id, case_id, seq, span_id, parent_span_id, ts_wall,
                    actor_kind, actor_name, visit, turn, parent_id, type, summary,
                    payload_json, refs_json, runtime_json, usage_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    envelope.event_id,
                    envelope.run_id,
                    envelope.case_id,
                    envelope.seq,
                    envelope.span_id,
                    envelope.parent_span_id,
                    envelope.ts_wall.isoformat(),
                    envelope.actor.kind.value,
                    envelope.actor.name,
                    envelope.visit,
                    envelope.turn,
                    envelope.parent_id,
                    envelope.type,
                    envelope.summary,
                    json.dumps(envelope.payload, default=str),
                    json.dumps(envelope.refs),
                    json.dumps(envelope.runtime.model_dump(mode="json")),
                    json.dumps(envelope.usage.model_dump(mode="json")),
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
        return [event_from_row(row) for row in rows]
