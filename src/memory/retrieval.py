"""Hybrid FTS5 + sqlite-vec search over policies and precedents, filtered by validity date."""

from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import struct
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

import sqlite_vec

EMBEDDING_DIMENSIONS = 96
TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
FIELDS = ("doc_id", "kind", "title", "body", "valid_from", "valid_to", "status")


def build(db_path: Path, docs: list[dict[str, Any]]) -> None:
    """Create the knowledge database from scratch: a documents table plus FTS and vector indexes."""
    db_path.unlink(missing_ok=True)
    with _connect(db_path) as db:
        db.execute(f"CREATE TABLE documents ({', '.join(FIELDS)}, PRIMARY KEY (doc_id))")
        db.execute("CREATE VIRTUAL TABLE documents_fts USING fts5(doc_id UNINDEXED, title, body)")
        db.execute(
            f"CREATE VIRTUAL TABLE vec_documents USING vec0("
            f"doc_id TEXT PRIMARY KEY, embedding float[{EMBEDDING_DIMENSIONS}])"
        )
        for doc in docs:
            db.execute(
                f"INSERT INTO documents VALUES ({','.join('?' * len(FIELDS))})",
                [doc[f] for f in FIELDS],
            )
            db.execute(
                "INSERT INTO documents_fts VALUES (?, ?, ?)",
                (doc["doc_id"], doc["title"], doc["body"]),
            )
            vector = _serialize(_embed(f"{doc['title']} {doc['body']}"))
            db.execute("INSERT INTO vec_documents VALUES (?, ?)", (doc["doc_id"], vector))


def search(
    db_path: Path,
    query: str,
    *,
    as_of: date,
    kinds: tuple[str, ...] = ("policy", "precedent"),
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Rank documents by reciprocal-rank fusion of vector and keyword hits, valid on `as_of`."""
    terms = dict.fromkeys(TOKEN_RE.findall(query.casefold()))
    match = " OR ".join(f'"{term}"' for term in terms) or '"empty"'
    with _connect(db_path) as db:
        vector_ids = [
            row["doc_id"]
            for row in db.execute(
                "SELECT doc_id FROM vec_documents "
                "WHERE embedding MATCH ? AND k = ? ORDER BY distance",
                (_serialize(_embed(query)), max(limit * 6, 30)),
            )
        ]
        keyword_ids = [
            row["doc_id"]
            for row in db.execute(
                "SELECT doc_id FROM documents_fts WHERE documents_fts MATCH ? "
                "ORDER BY bm25(documents_fts) LIMIT ?",
                (match, max(limit * 3, 15)),
            )
        ]
        scores: dict[str, float] = {}
        for ranking in (vector_ids, keyword_ids):
            for rank, doc_id in enumerate(ranking, start=1):
                scores[doc_id] = scores.get(doc_id, 0.0) + 1 / (60 + rank)
        rows = {
            row["doc_id"]: dict(row)
            for row in db.execute(
                f"SELECT * FROM documents WHERE doc_id IN ({','.join('?' * len(scores))})",
                list(scores),
            )
        }
    valid = [
        {**row, "score": round(scores[doc_id], 6)}
        for doc_id, row in rows.items()
        if row["kind"] in kinds and _valid_on(row, as_of)
    ]
    valid.sort(key=lambda row: (-row["score"], row["doc_id"]))
    return valid[:limit]


def _valid_on(row: dict[str, Any], as_of: date) -> bool:
    return _bound(row["valid_from"], date.min) <= as_of <= _bound(row["valid_to"], date.max)


def _bound(value: Any, default: date) -> date:
    """Parse a validity bound; anything not an ISO date (empty, "in force") is an open bound."""
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return default


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
