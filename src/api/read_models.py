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
    CaseDetail,
    CasePage,
    CaseSummary,
    CommunicationSummary,
    DecisionResponse,
    RunPage,
    RunRef,
    RunStatus,
    RunSummary,
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
