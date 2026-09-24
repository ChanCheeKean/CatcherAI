"""Hybrid FTS5 + sqlite-vec search over policy clauses, precedents and Memory Notes."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import struct
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import sqlite_vec

EMBEDDING_DIMENSIONS = 96
TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
FIELDS = ("doc_id", "kind", "title", "body", "status", "sources", "run_id", "confidence")
DEFAULTS = {"status": "active", "sources": "[]", "run_id": "", "confidence": None}


def build(db_path: Path, docs: list[dict[str, Any]]) -> None:
    """Create the knowledge database from scratch: a documents table plus FTS and vector indexes."""
    db_path.unlink(missing_ok=True)
    with _connect(db_path) as db:
        db.execute(f"CREATE TABLE documents ({', '.join(FIELDS)}, PRIMARY KEY (doc_id))")
        db.execute("CREATE VIRTUAL TABLE documents_fts USING fts5(doc_id UNINDEXED, title, body)")
        db.execute(
            f"CREATE VIRTUAL TABLE vec_documents USING vec0("
            f"doc_id TEXT PRIMARY KEY, kind TEXT, status TEXT, "
            f"embedding float[{EMBEDDING_DIMENSIONS}])"
        )
        for doc in docs:
            _insert(db, doc)


def search(
    db_path: Path,
    query: str,
    *,
    kinds: tuple[str, ...] = ("policy", "precedent", "memory_note"),
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Rank active documents of `kinds` by reciprocal-rank fusion of vector and keyword hits."""
    terms = dict.fromkeys(TOKEN_RE.findall(query.casefold()))
    match = " OR ".join(f'"{term}"' for term in terms) or '"empty"'
    in_kinds = f"IN ({','.join('?' * len(kinds))})"
    with _connect(db_path) as db:
        vector_ids = [
            row["doc_id"]
            for row in db.execute(
                "SELECT doc_id FROM vec_documents WHERE embedding MATCH ? AND k = ? "
                f"AND status = 'active' AND kind {in_kinds} ORDER BY distance",
                (_serialize(_embed(query)), max(limit * 6, 30), *kinds),
            )
        ]
        keyword_ids = [
            row["doc_id"]
            for row in db.execute(
                "SELECT f.doc_id FROM documents_fts f JOIN documents d USING (doc_id) "
                f"WHERE documents_fts MATCH ? AND d.status = 'active' AND d.kind {in_kinds} "
                "ORDER BY bm25(documents_fts) LIMIT ?",
                (match, *kinds, max(limit * 3, 15)),
            )
        ]
        scores: dict[str, float] = {}
        for ranking in (vector_ids, keyword_ids):
            for rank, doc_id in enumerate(ranking, start=1):
                scores[doc_id] = scores.get(doc_id, 0.0) + 1 / (60 + rank)
        rows = db.execute(
            f"SELECT * FROM documents WHERE doc_id IN ({','.join('?' * len(scores))})",
            list(scores),
        ).fetchall()
    hits = [{**dict(row), "score": round(scores[row["doc_id"]], 6)} for row in rows]
    hits.sort(key=lambda hit: (-hit["score"], hit["doc_id"]))
    return hits[:limit]


def add_note(db_path: Path, text: str, sources: list[str], run_id: str, confidence: float) -> str:
    """Store an active Memory Note and return its new `MEM-…` id."""
    with _connect(db_path) as db:
        # Take the write lock before counting, so parallel runs cannot pick the same id.
        db.execute("BEGIN IMMEDIATE")
        (count,) = db.execute(
            "SELECT count(*) FROM documents WHERE kind = 'memory_note'"
        ).fetchone()
        doc_id = f"MEM-{count + 1:04d}"
        _insert(
            db,
            {
                "doc_id": doc_id,
                "kind": "memory_note",
                "title": "Memory Note",
                "body": text,
                "sources": json.dumps(sources),
                "run_id": run_id,
                "confidence": confidence,
            },
        )
    return doc_id


def set_status(db_path: Path, doc_id: str, status: str) -> None:
    """Change a document's status; only `active` documents are returned by search."""
    with _connect(db_path) as db:
        if not db.execute(
            "UPDATE documents SET status = ? WHERE doc_id = ?", (status, doc_id)
        ).rowcount:
            raise KeyError(doc_id)
        db.execute("UPDATE vec_documents SET status = ? WHERE doc_id = ?", (status, doc_id))


def _insert(db: sqlite3.Connection, doc: dict[str, Any]) -> None:
    doc = {**DEFAULTS, **doc}
    db.execute(
        f"INSERT INTO documents VALUES ({','.join('?' * len(FIELDS))})", [doc[f] for f in FIELDS]
    )
    db.execute(
        "INSERT INTO documents_fts VALUES (?, ?, ?)", (doc["doc_id"], doc["title"], doc["body"])
    )
    vector = _serialize(_embed(f"{doc['title']} {doc['body']}"))
    db.execute(
        "INSERT INTO vec_documents VALUES (?, ?, ?, ?)",
        (doc["doc_id"], doc["kind"], doc["status"], vector),
    )


@contextmanager
def _connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(db_path)
    try:
        db.row_factory = sqlite3.Row
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        with db:
            yield db
    finally:
        db.close()


def _embed(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in TOKEN_RE.findall(text.casefold()):
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        vector[int.from_bytes(digest[:4], "little") % EMBEDDING_DIMENSIONS] += (
            1.0 if digest[4] & 1 else -1.0
        )
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _serialize(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)
