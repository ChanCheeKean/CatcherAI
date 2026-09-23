"""Per-run Case Notebook entries, separate from the static evidence graph."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

KINDS = ("fact", "hypothesis", "policy_reading", "conflict", "ruled_out", "improvement_idea")


def write_entry(
    db_path: Path,
    run_id: str,
    author: str,
    kind: str,
    text: str,
    node_ids: list[str],
    edge_ids: list[str],
) -> dict:
    if kind not in KINDS:
        raise ValueError(f"unknown notebook kind {kind!r}")
    if not node_ids and not edge_ids:
        raise ValueError("a notebook entry must cite a graph node or edge")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        _init(db)
        db.execute("BEGIN IMMEDIATE")
        seq = db.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM notebook_entries WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
        entry = {
            "entry_id": f"NBK-{uuid.uuid4().hex[:8]}",
            "run_id": run_id,
            "seq": seq,
            "author": author,
            "kind": kind,
            "text": text,
            "node_ids": node_ids,
            "edge_ids": edge_ids,
            "created_at": datetime.now(UTC).isoformat(),
        }
        db.execute(
            "INSERT INTO notebook_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry["entry_id"],
                run_id,
                seq,
                author,
                kind,
                text,
                json.dumps(node_ids),
                json.dumps(edge_ids),
                entry["created_at"],
            ),
        )
    return entry


def read_entries(
    db_path: Path,
    run_id: str,
    kinds: list[str] | None = None,
    author: str | None = None,
) -> list[dict]:
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as db:
        _init(db)
        db.row_factory = sqlite3.Row
        clauses = ["run_id = ?"]
        params: list[str] = [run_id]
        if kinds is not None:
            if not kinds:
                return []
            clauses.append(f"kind IN ({','.join('?' for _ in kinds)})")
            params.extend(kinds)
        if author is not None:
            clauses.append("author = ?")
            params.append(author)
        rows = db.execute(
            f"SELECT * FROM notebook_entries WHERE {' AND '.join(clauses)} ORDER BY seq", params
        ).fetchall()
    return [
        {
            **dict(row),
            "node_ids": json.loads(row["node_ids"]),
            "edge_ids": json.loads(row["edge_ids"]),
        }
        for row in rows
    ]


def _init(db: sqlite3.Connection) -> None:
    db.execute(
        "CREATE TABLE IF NOT EXISTS notebook_entries ("
        "entry_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, seq INTEGER NOT NULL, "
        "author TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL, "
        "node_ids TEXT NOT NULL, edge_ids TEXT NOT NULL, created_at TEXT NOT NULL, "
        "UNIQUE(run_id, seq))"
    )
