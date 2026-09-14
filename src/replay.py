from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from domain.events import EventEnvelope


def load_events(db_path: Path, run_id: str, to_seq: int | None = None) -> list[EventEnvelope]:
    sql = "SELECT * FROM run_events WHERE run_id=?"
    params: list[object] = [run_id]
    if to_seq is not None:
        sql += " AND seq<=?"
        params.append(to_seq)
    sql += " ORDER BY seq"
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(sql, params).fetchall()
    return [_event_from_row(row) for row in rows]


def verify_hash_chain(db_path: Path, run_id: str) -> bool:
    previous: str | None = None
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM run_events WHERE run_id=? ORDER BY seq", (run_id,)
        ).fetchall()
    for expected_seq, row in enumerate(rows, start=1):
        if row["seq"] != expected_seq or row["previous_event_hash"] != previous:
            return False
        event = _event_from_row(row)
        canonical = json.dumps(event.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        computed = hashlib.sha256(f"{previous or ''}{canonical}".encode()).hexdigest()
        if computed != row["event_hash"]:
            return False
        previous = computed
    return bool(rows)


def render_timeline(events: list[EventEnvelope]) -> str:
    lines: list[str] = []
    depth_by_span: dict[str, int] = {}
    for event in events:
        parent_depth = depth_by_span.get(event.parent_span_id or "", -1)
        depth = max(depth_by_span.get(event.span_id, parent_depth + 1), 0)
        depth_by_span[event.span_id] = depth
        indent = "  " * min(depth, 8)
        lines.append(
            f"{event.seq:04d} {event.ts_virtual.isoformat()} "
            f"{indent}{event.actor.kind.value}:{event.actor.name} "
            f"[{event.type}] {event.summary}"
        )
        if event.refs:
            lines.append(f"     {indent}refs: {', '.join(event.refs)}")
    return "\n".join(lines)


def _event_from_row(row: sqlite3.Row) -> EventEnvelope:
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
