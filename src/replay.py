from __future__ import annotations

import sqlite3
from pathlib import Path

from domain.events import EventEnvelope, event_from_row


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
    return [event_from_row(row) for row in rows]


def render_timeline(events: list[EventEnvelope]) -> str:
    lines: list[str] = []
    depth_by_span: dict[str, int] = {}
    for event in events:
        parent_depth = depth_by_span.get(event.parent_span_id or "", -1)
        depth = max(depth_by_span.get(event.span_id, parent_depth + 1), 0)
        depth_by_span[event.span_id] = depth
        indent = "  " * min(depth, 8)
        lines.append(
            f"{event.seq:04d} {event.ts_wall.isoformat()} "
            f"{indent}{event.actor.kind.value}:{event.actor.name} "
            f"[{event.type}] {event.summary}"
        )
        if event.refs:
            lines.append(f"     {indent}refs: {', '.join(event.refs)}")
    return "\n".join(lines)
