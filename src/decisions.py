from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from domain.case import DecisionRecord
from domain.events import Actor, ActorKind, EventDraft
from observability.emitter import EventEmitter


def _leaf_paths(value: Any, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, item in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            paths.extend(_leaf_paths(item, f"{prefix}/{escaped}"))
        return paths
    if isinstance(value, list):
        paths = []
        for index, item in enumerate(value):
            paths.extend(_leaf_paths(item, f"{prefix}/{index}"))
        return paths or [prefix]
    return [prefix or "/"]


class DecisionRepository:
    def __init__(self, db_path: Path, emitter: EventEmitter) -> None:
        self.db_path = db_path
        self.emitter = emitter
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS decision_records (
                    run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
                    record_json TEXT NOT NULL, provenance_json TEXT NOT NULL
                )"""
            )

    def save(
        self, decision: DecisionRecord, source_event_seqs: list[int], source_ids: list[str]
    ) -> None:
        record = decision.model_dump(mode="json")
        provenance = {
            path: {"event_seqs": source_event_seqs, "source_ids": source_ids}
            for path in _leaf_paths(record)
        }
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.GRAPH_NODE, name="record_decision"),
                type="decision_recorded",
                summary="Recorded a complete decision with field-level provenance",
                payload={"record": record, "field_provenance": provenance},
                refs=source_ids,
            )
        )
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO decision_records VALUES (?,?,?,?)",
                (self.emitter.run_id, decision.case_id, json.dumps(record), json.dumps(provenance)),
            )
