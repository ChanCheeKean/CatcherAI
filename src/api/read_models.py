"""Projections from the read-only scenario SQLite store to stable API DTOs.

Every query here is read-only (`mode=ro`) and never touches ground-truth/simulation tables.
Unlike `data.access.CaseDataAccess`, these reads are not part of an instrumented agent run and
do not emit `sql_query` events: the API is a separate presentation adapter over already-committed
data, not a tool an agent calls.
"""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from typing import Any

from api.errors import not_found
from api.models import (
    BlobResponse,
    CaseDetail,
    CasePage,
    CaseSummary,
    CommunicationSummary,
    DecisionResponse,
    GraphEdge,
    GraphNode,
    MemoryNoteDetail,
    MemoryNotePage,
    MemoryNoteSummary,
    RunGraphResponse,
    RunMemoryResponse,
    RunPage,
    RunRef,
    RunStatus,
    RunSummary,
    SourceResponse,
    TransactionSummary,
)
from domain.events import EventEnvelope, event_from_row

CASE_FIELDS = (
    "case_id",
    "regime",
    "status",
    "stage",
    "customer_id",
    "account_id",
    "claim_family_initial",
    "network",
    "network_condition",
    "dispute_amount",
    "opened_at",
    "cardholder_outcome",
    "network_outcome",
)


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _decimal(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _case_summary(row: sqlite3.Row) -> CaseSummary:
    data = dict(row)
    data["dispute_amount"] = _decimal(data.get("dispute_amount"))
    return CaseSummary.model_validate(data)


def list_cases(
    connection: sqlite3.Connection,
    *,
    regime: str | None,
    status: str | None,
    stage: str | None,
    claim_family: str | None,
    q: str | None,
    limit: int,
    cursor: int,
) -> CasePage:
    clauses: list[str] = []
    params: list[Any] = []
    if regime:
        clauses.append("regime = ?")
        params.append(regime)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if stage:
        clauses.append("stage = ?")
        params.append(stage)
    if claim_family:
        clauses.append("claim_family_initial = ?")
        params.append(claim_family)
    if q:
        clauses.append("(case_id LIKE ? OR customer_id LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""SELECT {", ".join(CASE_FIELDS)} FROM disputes {where}
              ORDER BY opened_at DESC, case_id LIMIT ? OFFSET ?"""
    rows = connection.execute(sql, [*params, limit + 1, cursor]).fetchall()
    has_more = len(rows) > limit
    items = [_case_summary(row) for row in rows[:limit]]
    return CasePage(items=items, next_cursor=str(cursor + limit) if has_more else None, limit=limit)


def get_case_detail(connection: sqlite3.Connection, case_id: str) -> CaseDetail:
    row = connection.execute(
        f"SELECT {', '.join(CASE_FIELDS)} FROM disputes WHERE case_id = ?", (case_id,)
    ).fetchone()
    if row is None:
        raise not_found("case_not_found", f"unknown case {case_id}", case_id=case_id)
    summary = _case_summary(row)
    txn_rows = connection.execute(
        """SELECT t.txn_id, t.merchant_id, m.dba_name AS merchant_name, t.descriptor,
                  t.channel, t.billing_amount, t.processing_date
           FROM dispute_transactions dt
           JOIN transactions t ON t.txn_id = dt.txn_id
           LEFT JOIN merchants m ON m.merchant_id = t.merchant_id
           WHERE dt.case_id = ? ORDER BY t.processing_date, t.txn_id""",
        (case_id,),
    ).fetchall()
    transactions = [
        TransactionSummary.model_validate(
            {**dict(row), "billing_amount": _decimal(row["billing_amount"])}
        )
        for row in txn_rows
    ]
    comm_rows = connection.execute(
        """SELECT comm_id, channel, party, timestamp_utc, subject FROM communications
           WHERE case_id = ? ORDER BY timestamp_utc""",
        (case_id,),
    ).fetchall()
    communications = [CommunicationSummary.model_validate(dict(row)) for row in comm_rows]
    latest_runs = [
        RunRef(
            run_id=run.run_id,
            status=run.status,
            started_at=run.started_at,
            last_event_at=run.last_event_at,
            event_count=run.event_count,
        )
        for run in _runs_for_cases(connection, [case_id])
    ]
    return CaseDetail(
        **summary.model_dump(),
        transactions=transactions,
        communications=communications,
        latest_runs=latest_runs,
    )


_TERMINAL_STATUS_BY_FINAL_STATUS: dict[str, RunStatus] = {
    "suspended": "suspended",
    "cancelled": "cancelled",
    "decided": "decided",
    "ranked": "ranked",
}


def derive_status(connection: sqlite3.Connection, run_id: str) -> RunStatus:
    """A run's terminal state is marked by its latest `error` or `termination` event, which may
    not be the very last committed row: `terminate` also emits a trailing `run_completed` event,
    and the checkpointer wrapper commits `checkpoint_saved` after that. A run that suspends and
    auto-resumes internally (§4.4) emits one `termination` per segment, so only the *latest* one
    reflects where the run currently stands; SSE streaming (`api/sse.py`) additionally consults
    whether the driving task itself is still alive before treating a mid-run "suspended" reading
    as the end of the stream."""

    row = connection.execute(
        """SELECT type, payload_json FROM run_events
           WHERE run_id = ? AND type IN ('error', 'termination')
           ORDER BY seq DESC LIMIT 1""",
        (run_id,),
    ).fetchone()
    if row is None:
        return "running"
    if row["type"] == "error":
        return "failed"
    payload = json.loads(row["payload_json"])
    return _TERMINAL_STATUS_BY_FINAL_STATUS.get(payload.get("final_status"), "running")


def _runs_for_cases(connection: sqlite3.Connection, case_ids: list[str] | None) -> list[RunSummary]:
    """One pass over `run_events`/`decision_records` per run-set instead of the ~5 follow-up
    queries per run this used to issue (first/last event, status, wait payload, decision
    existence) — this is called once per case (`get_case_detail`) and once for the whole `/runs`
    listing across every known store, so the per-run round trips added up quickly."""

    if not _table_exists(connection, "run_events"):
        return []
    where = ""
    params: list[Any] = []
    if case_ids:
        placeholders = ",".join("?" for _ in case_ids)
        where = f"WHERE run_id IN (SELECT run_id FROM run_events WHERE case_id IN ({placeholders}))"
        params = list(case_ids)
    aggregate_rows = connection.execute(
        f"""SELECT run_id, case_id, COUNT(*) AS event_count,
                   MIN(seq) AS first_seq, MAX(seq) AS last_seq
            FROM run_events {where} GROUP BY run_id ORDER BY last_seq DESC""",
        params,
    ).fetchall()
    if not aggregate_rows:
        return []

    run_ids = [row["run_id"] for row in aggregate_rows]
    run_placeholders = ",".join("?" for _ in run_ids)

    endpoint_pairs = [(row["run_id"], row["first_seq"]) for row in aggregate_rows]
    endpoint_pairs.extend((row["run_id"], row["last_seq"]) for row in aggregate_rows)
    pair_placeholders = ",".join("(?,?)" for _ in endpoint_pairs)
    endpoints = {
        (row["run_id"], row["seq"]): row
        for row in connection.execute(
            f"""SELECT run_id, seq, ts_wall, ts_virtual FROM run_events
                WHERE (run_id, seq) IN ({pair_placeholders})""",
            [value for pair in endpoint_pairs for value in pair],
        ).fetchall()
    }

    statuses: dict[str, RunStatus] = {}
    for row in connection.execute(
        f"""SELECT run_id, type, payload_json FROM (
                SELECT run_id, type, payload_json,
                       ROW_NUMBER() OVER (PARTITION BY run_id ORDER BY seq DESC) AS rn
                FROM run_events
                WHERE run_id IN ({run_placeholders}) AND type IN ('error', 'termination')
            ) WHERE rn = 1""",
        run_ids,
    ).fetchall():
        if row["type"] == "error":
            statuses[row["run_id"]] = "failed"
        else:
            payload = json.loads(row["payload_json"])
            statuses[row["run_id"]] = _TERMINAL_STATUS_BY_FINAL_STATUS.get(
                payload.get("final_status"), "running"
            )

    suspended_ids = [run_id for run_id in run_ids if statuses.get(run_id) == "suspended"]
    waits: dict[str, dict[str, Any]] = {}
    if suspended_ids:
        suspended_placeholders = ",".join("?" for _ in suspended_ids)
        waits = {
            row["run_id"]: json.loads(row["payload_json"])
            for row in connection.execute(
                f"""SELECT run_id, payload_json FROM (
                        SELECT run_id, payload_json,
                               ROW_NUMBER() OVER (PARTITION BY run_id ORDER BY seq DESC) AS rn
                        FROM run_events
                        WHERE run_id IN ({suspended_placeholders}) AND type = 'wait_suspended'
                    ) WHERE rn = 1""",
                suspended_ids,
            ).fetchall()
        }

    decided_run_ids: set[str] = set()
    if _table_exists(connection, "decision_records"):
        decided_run_ids = {
            row["run_id"]
            for row in connection.execute(
                "SELECT DISTINCT run_id FROM decision_records "
                f"WHERE run_id IN ({run_placeholders})",
                run_ids,
            ).fetchall()
        }

    summaries: list[RunSummary] = []
    for row in aggregate_rows:
        run_id = row["run_id"]
        first_event = endpoints.get((run_id, row["first_seq"]))
        last_event = endpoints[(run_id, row["last_seq"])]
        summaries.append(
            RunSummary(
                run_id=run_id,
                case_id=row["case_id"],
                status=statuses.get(run_id, "running"),
                event_count=row["event_count"],
                first_seq=row["first_seq"],
                last_seq=row["last_seq"],
                started_at=first_event["ts_wall"] if first_event else None,
                last_event_at=last_event["ts_wall"],
                virtual_now=last_event["ts_virtual"],
                wait=waits.get(run_id),
                decision_available=run_id in decided_run_ids,
            )
        )
    return summaries


def list_runs(
    connections: list[sqlite3.Connection],
    *,
    case_id: str | None,
    status: str | None,
    limit: int,
    cursor: int,
) -> RunPage:
    """Merge runs across every store the API currently knows about (§4.1, Stage 2 decision): the
    configured default store plus every isolated UI-run workspace in the durable run registry."""

    by_run_id: dict[str, RunSummary] = {}
    for connection in connections:
        for run in _runs_for_cases(connection, [case_id] if case_id else None):
            by_run_id.setdefault(run.run_id, run)
    runs = sorted(
        by_run_id.values(), key=lambda run: (run.last_event_at or "", run.last_seq), reverse=True
    )
    if status:
        runs = [run for run in runs if run.status == status]
    window = runs[cursor : cursor + limit + 1]
    has_more = len(window) > limit
    items = window[:limit]
    return RunPage(items=items, next_cursor=str(cursor + limit) if has_more else None, limit=limit)


def get_run_summary(connection: sqlite3.Connection, run_id: str) -> RunSummary:
    runs = _runs_for_cases(connection, None)
    for run in runs:
        if run.run_id == run_id:
            return run
    raise not_found("run_not_found", f"unknown run {run_id}", run_id=run_id)


def list_events(
    connection: sqlite3.Connection,
    run_id: str,
    *,
    after_seq: int,
    event_type: str | None,
    actor: str | None,
    ref: str | None,
    limit: int,
) -> tuple[list[EventEnvelope], int | None]:
    if not _table_exists(connection, "run_events"):
        return [], None
    clauses = ["run_id = ?", "seq > ?"]
    params: list[Any] = [run_id, after_seq]
    if event_type:
        clauses.append("type = ?")
        params.append(event_type)
    if actor:
        clauses.append("actor_name = ?")
        params.append(actor)
    if ref:
        clauses.append("refs_json LIKE ?")
        params.append(f'%"{ref}"%')
    sql = f"SELECT * FROM run_events WHERE {' AND '.join(clauses)} ORDER BY seq LIMIT ?"
    rows = connection.execute(sql, [*params, limit + 1]).fetchall()
    has_more = len(rows) > limit
    events = [event_from_row(row) for row in rows[:limit]]
    next_after_seq = events[-1].seq if has_more and events else None
    return events, next_after_seq


def get_decision(connection: sqlite3.Connection, run_id: str) -> DecisionResponse:
    message = f"no decision recorded for run {run_id}"
    if not _table_exists(connection, "decision_records"):
        raise not_found("decision_not_found", message, run_id=run_id)
    row = connection.execute(
        "SELECT case_id, record_json, provenance_json FROM decision_records WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if row is None:
        raise not_found("decision_not_found", message, run_id=run_id)
    return DecisionResponse(
        run_id=run_id,
        case_id=row["case_id"],
        record=json.loads(row["record_json"]),
        field_provenance=json.loads(row["provenance_json"]),
    )


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    parsed = json.loads(value)
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _memory_note(row: sqlite3.Row) -> MemoryNoteSummary:
    return MemoryNoteSummary(
        note_id=row["note_id"],
        kind=row["kind"],
        scope=row["scope"],
        subject_ids=_json_list(row["subject_ids"]),
        content=row["content"],
        created_at=row["created_at"],
        created_by=row["created_by"],
        source_refs=_json_list(row["source_refs"]),
        confidence=float(row["confidence"]),
        status=row["status"],
        valid_from=row["valid_from"] or None,
        valid_to=row["valid_to"] or None,
        superseded_by=row["superseded_by"] or None,
        tags=_json_list(row["tags"]),
        sensitivity=row["sensitivity"],
        last_accessed_at=row["last_accessed_at"] or None,
        access_count=int(row["access_count"] or 0),
    )


def list_memory_notes(
    connection: sqlite3.Connection,
    *,
    subject: str | None,
    scope: str | None,
    kind: str | None,
    tag: str | None,
    status: str | None,
    min_confidence: float | None,
    as_of: str | None,
    limit: int,
    cursor: int,
) -> MemoryNotePage:
    clauses: list[str] = []
    params: list[Any] = []
    for field, value in (("scope", scope), ("kind", kind), ("status", status)):
        if value:
            clauses.append(f"{field} = ?")
            params.append(value)
    if subject:
        clauses.append("subject_ids LIKE ?")
        params.append(f'%"{subject}"%')
    if tag:
        clauses.append("tags LIKE ?")
        params.append(f'%"{tag}"%')
    if min_confidence is not None:
        clauses.append("CAST(confidence AS REAL) >= ?")
        params.append(min_confidence)
    if as_of:
        clauses.extend(["valid_from <= ?", "(valid_to IS NULL OR valid_to = '' OR ? < valid_to)"])
        params.extend([as_of, as_of])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = connection.execute(
        f"""SELECT * FROM agent_memory_notes {where}
            ORDER BY created_at DESC, note_id LIMIT ? OFFSET ?""",
        [*params, limit + 1, cursor],
    ).fetchall()
    return MemoryNotePage(
        items=[_memory_note(row) for row in rows[:limit]],
        next_cursor=str(cursor + limit) if len(rows) > limit else None,
        limit=limit,
    )


def get_memory_note(connection: sqlite3.Connection, note_id: str) -> MemoryNoteDetail:
    row = connection.execute(
        "SELECT * FROM agent_memory_notes WHERE note_id=?", (note_id,)
    ).fetchone()
    if row is None:
        raise not_found("memory_note_not_found", f"unknown memory note {note_id}", note_id=note_id)
    events: list[EventEnvelope] = []
    if _table_exists(connection, "run_events"):
        event_rows = connection.execute(
            """SELECT * FROM run_events WHERE refs_json LIKE ? OR payload_json LIKE ?
               ORDER BY ts_wall, seq""",
            (f'%"{note_id}"%', f'%"{note_id}"%'),
        ).fetchall()
        events = [event_from_row(event_row) for event_row in event_rows]
    return MemoryNoteDetail(**_memory_note(row).model_dump(), lifecycle_events=events)


_MEMORY_EVENT_TYPES = (
    "memory_read",
    "memory_verified",
    "memory_rejected",
    "memory_write",
    "memory_write_skipped",
    "memory_supersede",
    "memory_retract",
    "memory_consolidate",
    "memory_expire",
    "memory_purge",
    "write_rejected",
)


def get_run_memory(connection: sqlite3.Connection, run_id: str) -> RunMemoryResponse:
    get_run_summary(connection, run_id)
    placeholders = ",".join("?" for _ in _MEMORY_EVENT_TYPES)
    rows = connection.execute(
        f"SELECT * FROM run_events WHERE run_id=? AND type IN ({placeholders}) ORDER BY seq",
        (run_id, *_MEMORY_EVENT_TYPES),
    ).fetchall()
    operations = [event_from_row(row) for row in rows]
    groups: dict[str, int] = {}
    for event in operations:
        store = str(event.payload.get("store", "unspecified"))
        groups[store] = groups.get(store, 0) + 1
    return RunMemoryResponse(run_id=run_id, operations=operations, groups=groups)


def get_run_graph(connection: sqlite3.Connection, run_id: str) -> RunGraphResponse:
    get_run_summary(connection, run_id)
    rows = connection.execute(
        """SELECT * FROM run_events WHERE run_id=?
           AND type IN ('graph_query','graph_write') ORDER BY seq""",
        (run_id,),
    ).fetchall()
    operations = [event_from_row(row) for row in rows]
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    for event in operations:
        ids = event.payload.get("node_ids", [])
        if isinstance(ids, list):
            for node_id in ids:
                value = str(node_id)
                nodes[value] = GraphNode(
                    id=value,
                    label=value.split(":", 1)[-1],
                    kind=value.split(":", 1)[0],
                    properties={},
                    source_refs=[value],
                    event_seqs=[event.seq],
                )
        after = event.payload.get("after")
        if event.type == "graph_write" and isinstance(after, dict):
            target = str(after.get("node_id", event.payload.get("target_id", "hypothesis")))
            nodes[target] = GraphNode(
                id=target,
                label=str(after.get("kind", target)),
                kind="Hypothesis",
                properties=after,
                source_refs=[str(x) for x in after.get("evidence_refs", [])],
                event_seqs=[event.seq],
            )
            for index, subject in enumerate(after.get("subject_ids", [])):
                subject_id = str(subject)
                nodes.setdefault(
                    subject_id,
                    GraphNode(
                        id=subject_id,
                        label=subject_id.split(":", 1)[-1],
                        kind=subject_id.split(":", 1)[0],
                        properties={},
                        source_refs=[subject_id],
                        event_seqs=[event.seq],
                    ),
                )
                edges.append(
                    GraphEdge(
                        id=f"{target}:{index}",
                        source=target,
                        target=subject_id,
                        label=str(after.get("relationship", "RELATED_TO")),
                        properties={},
                        source_refs=[str(x) for x in after.get("evidence_refs", [])],
                        event_seqs=[event.seq],
                    )
                )
    return RunGraphResponse(
        run_id=run_id, operations=operations, nodes=list(nodes.values()), edges=edges
    )


def get_blob(connection: sqlite3.Connection, run_id: str, sha256: str) -> BlobResponse:
    get_run_summary(connection, run_id)
    digest = sha256.removeprefix("sha256:")
    row = connection.execute("SELECT * FROM run_blobs WHERE sha256=?", (digest,)).fetchone()
    if row is None:
        raise not_found("blob_not_found", f"unknown blob {digest}", sha256=digest)
    raw = bytes(row["content"])
    content: Any = (
        json.loads(raw)
        if row["media_type"] == "application/json"
        else raw.decode("utf-8", errors="replace")
    )
    return BlobResponse(
        sha256=digest, media_type=row["media_type"], size_bytes=row["size_bytes"], content=content
    )


def resolve_source(connection: sqlite3.Connection, source_id: str) -> SourceResponse:
    resolvers: list[tuple[str, str, str, tuple[Any, ...]]] = [
        ("case", "SELECT * FROM disputes WHERE case_id=?", "case_id", (source_id,)),
        ("transaction", "SELECT * FROM transactions WHERE txn_id=?", "txn_id", (source_id,)),
        ("communication", "SELECT * FROM communications WHERE comm_id=?", "comm_id", (source_id,)),
        (
            "memory_note",
            "SELECT * FROM agent_memory_notes WHERE note_id=?",
            "note_id",
            (source_id,),
        ),
        (
            "document",
            "SELECT * FROM documents WHERE doc_id=?",
            "doc_id",
            (source_id.split("@", 1)[0],),
        ),
        (
            "evidence_packet",
            """SELECT packet_id,case_id,txn_id,available_at,json
               FROM evidence_packet_documents WHERE packet_id=?""",
            "packet_id",
            (source_id,),
        ),
    ]
    for kind, sql, title_field, params in resolvers:
        row = connection.execute(sql, params).fetchone()
        if row is None:
            continue
        data = dict(row)
        if kind == "evidence_packet":
            data["document"] = json.loads(data.pop("json"))
        for key in ("subject_ids", "source_refs", "tags", "meta_json"):
            if key in data and data[key]:
                data[key] = json.loads(data[key])
        related = [source_id]
        return SourceResponse(
            source_id=source_id,
            kind=kind,
            title=str(data.get(title_field, source_id)),
            data=data,
            related_source_ids=related,
        )
    raise not_found("source_not_found", f"unknown source {source_id}", source_id=source_id)
