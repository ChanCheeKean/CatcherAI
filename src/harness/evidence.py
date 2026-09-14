from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from domain.events import Actor, ActorKind, EventDraft
from observability.emitter import EventEmitter


class EvidenceSchedulerAccess:
    """Harness-only view of future evidence availability."""

    def __init__(self, db_path: Path, emitter: EventEmitter) -> None:
        self.db_path = db_path
        self.emitter = emitter

    def next_evidence(self, case_id: str) -> dict[str, Any] | None:
        sql = """SELECT packet_id, case_id, txn_id, available_at
                 FROM evidence_packet_documents WHERE case_id=? AND available_at>?
                 ORDER BY available_at LIMIT 1"""
        params = (case_id, self.emitter.virtual_now.isoformat().replace("+00:00", "Z"))
        with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(sql, params).fetchone()
        result = dict(row) if row else None
        refs = [result["packet_id"]] if result else []
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.HARNESS, name="evidence_scheduler"),
                type="sql_query",
                summary="Harness checked the next scheduled evidence event",
                payload={
                    "store": "sqlite",
                    "query_id": "harness_next_evidence",
                    "sql": sql,
                    "parameters": list(params),
                    "filters": {"future_events": True},
                    "result_ids": refs,
                    "used_ids": refs,
                    "discarded": [],
                },
                refs=refs,
            )
        )
        return result
