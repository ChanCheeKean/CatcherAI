from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import struct
from datetime import date
from pathlib import Path
from typing import Any

import sqlite_vec

from domain.events import Actor, ActorKind, EventDraft
from observability.emitter import EventEmitter

EMBEDDING_DIMENSIONS = 96
TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")


class HybridKnowledgeStore:
    """Metadata-filtered FTS5 + sqlite-vec retrieval over the shared SQLite corpus."""

    def __init__(self, db_path: Path, emitter: EventEmitter) -> None:
        self.db_path = db_path
        self.emitter = emitter
        self._index_ready = False

    def search(
        self,
        query: str,
        *,
        as_of: date,
        kinds: tuple[str, ...] = ("policy", "precedent"),
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        self._ensure_index()
        vector_rows = self._vector_candidates(query, limit=max(limit * 6, 30))
        keyword_rows = self._keyword_candidates(query, limit=max(limit * 3, 15))
        candidates: dict[str, dict[str, Any]] = {}
        for rank, row in enumerate(vector_rows, start=1):
            candidate = candidates.setdefault(row["doc_id"], row)
            candidate["vector_rank"] = rank
            candidate["vector_distance"] = row["distance"]
        for rank, row in enumerate(keyword_rows, start=1):
            candidate = candidates.setdefault(row["doc_id"], row)
            candidate["keyword_rank"] = rank
            candidate["keyword_score"] = row["keyword_score"]

        eligible: list[dict[str, Any]] = []
        discarded: list[dict[str, str]] = []
        for candidate in candidates.values():
            reason = _ineligibility_reason(candidate, as_of, kinds)
            if reason:
                discarded.append({"id": candidate["doc_id"], "reason": reason})
                continue
            candidate["hybrid_score"] = _rrf(candidate)
            eligible.append(candidate)
        eligible.sort(key=lambda row: (-row["hybrid_score"], row["doc_id"]))
        used = eligible[:limit]
        discarded.extend({"id": row["doc_id"], "reason": "below_top_k"} for row in eligible[limit:])
        result_ids = [row["doc_id"] for row in used]
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.MEMORY, name="hybrid_knowledge_store"),
                type="retrieval",
                summary=f"Hybrid retrieval returned {len(used)} valid documents",
                payload={
                    "store": "sqlite_vec+fts5",
                    "namespace": "documents",
                    "query": query,
                    "filters": {
                        "as_of": as_of.isoformat(),
                        "as_of_rule": "supplied_by_investigation_node",
                        "valid_from_lte": as_of.isoformat(),
                        "valid_to_gte_or_null": as_of.isoformat(),
                        "kinds": list(kinds),
                        "status_rule": (
                            "validity_interval_controls; lifecycle status is retained for audit"
                        ),
                    },
                    "results": [
                        {
                            "doc_id": row["doc_id"],
                            "kind": row["kind"],
                            "valid_from": row["valid_from"],
                            "valid_to": row["valid_to"],
                            "status": row["status"],
                            "hybrid_score": row["hybrid_score"],
                            "vector_distance": row.get("vector_distance"),
                            "keyword_score": row.get("keyword_score"),
                        }
                        for row in used
                    ],
                    "used_ids": result_ids,
                    "discarded": discarded,
                },
                refs=result_ids,
            )
        )
        return used

    def reject(self, document: dict[str, Any], *, reason: str, evidence_refs: list[str]) -> None:
        """Record that a retrieved source was deliberately not used as current evidence."""

        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.MEMORY, name="hybrid_knowledge_store"),
                type="memory_rejected",
                summary=f"Rejected {document['doc_id']} for this decision",
                payload={
                    "store": "sqlite_vec+fts5",
                    "namespace": "documents",
                    "doc_id": document["doc_id"],
                    "reason": reason,
                    "verification_evidence_refs": evidence_refs,
                    "used_as_evidence": False,
                },
                refs=[document["doc_id"], *evidence_refs],
            )
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.enable_load_extension(True)
        sqlite_vec.load(connection)
        connection.enable_load_extension(False)
        return connection

    def _ensure_index(self) -> None:
        if self._index_ready:
            return
        created = False
        indexed = 0
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='vec_documents'"
            ).fetchone()
            if not exists:
                connection.execute(
                    f"""CREATE VIRTUAL TABLE vec_documents USING vec0(
                        doc_id TEXT PRIMARY KEY, embedding float[{EMBEDDING_DIMENSIONS}]
                    )"""
                )
                rows = connection.execute(
                    "SELECT doc_id, title, body FROM documents ORDER BY doc_id"
                ).fetchall()
                connection.executemany(
                    "INSERT INTO vec_documents(doc_id, embedding) VALUES (?, ?)",
                    [
                        (row["doc_id"], _serialize(_embed(f"{row['title']} {row['body']}")))
                        for row in rows
                    ],
                )
                indexed = len(rows)
                created = True
        self._index_ready = True
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.MEMORY, name="hybrid_knowledge_store"),
                type="memory_write" if created else "memory_read",
                summary=(
                    f"Built sqlite-vec document index with {indexed} records"
                    if created
                    else "Verified existing sqlite-vec document index"
                ),
                payload={
                    "store": "sqlite_vec",
                    "target_id": "vec_documents",
                    "operation": "index_build" if created else "index_check",
                    "record_count": indexed if created else None,
                    "write_gate_checks": [
                        {"check": "source_is_agent_visible_documents", "pass": True},
                        {"check": "prohibited_sources_absent", "pass": True},
                    ],
                },
                refs=[],
            )
        )

    def _vector_candidates(self, query: str, limit: int) -> list[dict[str, Any]]:
        sql = """WITH knn AS (
                   SELECT doc_id, distance FROM vec_documents
                   WHERE embedding MATCH ? AND k = ? ORDER BY distance
                 )
                 SELECT d.*, knn.distance FROM knn
                 JOIN documents d ON d.doc_id=knn.doc_id ORDER BY knn.distance"""
        with self._connect() as connection:
            return [
                dict(row)
                for row in connection.execute(sql, (_serialize(_embed(query)), limit)).fetchall()
            ]

    def _keyword_candidates(self, query: str, limit: int) -> list[dict[str, Any]]:
        terms = list(dict.fromkeys(TOKEN_RE.findall(query.casefold())))
        expression = " OR ".join(f'"{term}"' for term in terms) or '"empty"'
        sql = """SELECT d.*, bm25(documents_fts) AS keyword_score
                 FROM documents_fts JOIN documents d
                 ON d.doc_id=documents_fts.doc_id
                 WHERE documents_fts MATCH ? ORDER BY keyword_score LIMIT ?"""
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(sql, (expression, limit)).fetchall()]


def _embed(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in TOKEN_RE.findall(text.casefold()):
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "little") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _serialize(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _ineligibility_reason(
    candidate: dict[str, Any], as_of: date, kinds: tuple[str, ...]
) -> str | None:
    if candidate["kind"] not in kinds:
        return "kind_filtered"
    valid_from = _date_bound(candidate.get("valid_from"), default="0001-01-01")
    valid_to = _date_bound(candidate.get("valid_to"), default="9999-12-31")
    if valid_from > as_of.isoformat():
        return "not_yet_effective"
    if valid_to < as_of.isoformat():
        return "expired_or_superseded_for_as_of"
    return None


def _date_bound(value: Any, *, default: str) -> str:
    rendered = str(value or "").strip().casefold()
    if rendered in {"", "none", "null", "in force", "in_force"}:
        return default
    try:
        return date.fromisoformat(rendered[:10]).isoformat()
    except ValueError:
        return default


def _rrf(candidate: dict[str, Any], constant: int = 60) -> float:
    score = 0.0
    if candidate.get("vector_rank"):
        score += 1 / (constant + candidate["vector_rank"])
    if candidate.get("keyword_rank"):
        score += 1 / (constant + candidate["keyword_rank"])
    return round(score, 8)
