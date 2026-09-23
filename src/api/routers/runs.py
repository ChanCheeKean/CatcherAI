"""Case list, background runs and the reconnectable trajectory stream."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header
from sse_starlette import EventSourceResponse

from api.context import ApiContext, Ctx
from api.errors import not_found
from api.models import CaseSummary, RunStatus, StartRun
from domain.events import EventEnvelope
from replay import load_events
from schemas import CaseReport

router = APIRouter(tags=["runs"])
POLL_SECONDS = 0.1


def _cases(ctx: ApiContext) -> list[dict]:
    return json.loads(ctx.catalog.read_text())


def _events(ctx: ApiContext, run_id: str, after_seq: int = 0) -> list[EventEnvelope]:
    if not ctx.paths.trajectory_db.exists():
        return []
    try:
        return load_events(ctx.paths.trajectory_db, run_id, after_seq=after_seq)
    except sqlite3.OperationalError:  # the run has not created the event table yet
        return []


def _latest_completed(ctx: ApiContext) -> dict[str, tuple[str, str]]:
    """Per case, the newest finished run that reached a decision."""
    if not ctx.paths.trajectory_db.exists():
        return {}
    try:
        with sqlite3.connect(ctx.paths.trajectory_db) as connection:
            rows = connection.execute(
                "SELECT case_id, run_id, json_extract(payload_json, '$.report.verdict') "
                "FROM run_events WHERE type = 'decision' ORDER BY ts_wall"
            ).fetchall()
    except sqlite3.OperationalError:  # no run has created the event table yet
        return {}
    return {
        case_id: (run_id, verdict) for case_id, run_id, verdict in rows if not ctx.is_active(run_id)
    }


@router.get("/cases", response_model=list[CaseSummary])
def list_cases(ctx: Ctx) -> list[dict]:
    latest = _latest_completed(ctx)
    cases = []
    for case in _cases(ctx):
        run_id, verdict = latest.get(case["case_id"], (None, None))
        cases.append({**case, "latest_run_id": run_id, "latest_verdict": verdict})
    return cases


@router.post("/runs", response_model=RunStatus, status_code=202)
def start_run(body: StartRun, ctx: Ctx) -> RunStatus:
    if body.case_id not in {case["case_id"] for case in _cases(ctx)}:
        raise not_found("case_not_found", f"unknown case {body.case_id}", case_id=body.case_id)
    run_id = f"run-{uuid.uuid4().hex}"
    ctx.start_run(run_id, body.case_id)
    return RunStatus(run_id=run_id, case_id=body.case_id, status="running")


@router.get("/runs/{run_id}", response_model=RunStatus)
def get_run(run_id: str, ctx: Ctx) -> RunStatus:
    events = _events(ctx, run_id)
    run = ctx.runs.get(run_id)
    if run is None and not events:
        raise not_found("run_not_found", f"unknown run {run_id}", run_id=run_id)
    case_id = run.case_id if run else events[0].case_id or ""
    decision = next((e for e in reversed(events) if e.type == "decision"), None)
    if decision:
        report = CaseReport.model_validate(decision.payload["report"])
        return RunStatus(run_id=run_id, case_id=case_id, status="completed", report=report)
    failure = next((e for e in reversed(events) if e.type == "error"), None)
    error = (run.error if run else None) or (failure.payload["error"] if failure else None)
    if error:
        return RunStatus(run_id=run_id, case_id=case_id, status="failed", error=error)
    if ctx.is_active(run_id):
        return RunStatus(run_id=run_id, case_id=case_id, status="running")
    return RunStatus(run_id=run_id, case_id=case_id, status="failed", error="run was interrupted")


@router.get("/runs/{run_id}/events")
async def stream_events(
    ctx: Ctx,
    run_id: str,
    last_event_id: str | None = Header(default=None),
) -> EventSourceResponse:
    """Replay the stored trajectory after `Last-Event-ID`, then follow it until the run ends."""

    if run_id not in ctx.runs and not await asyncio.to_thread(_events, ctx, run_id):
        raise not_found("run_not_found", f"unknown run {run_id}", run_id=run_id)
    after = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

    async def stream() -> AsyncIterator[dict[str, str]]:
        seq = after
        while True:
            finished = not ctx.is_active(run_id)  # sampled first so the final events are drained
            for event in await asyncio.to_thread(_events, ctx, run_id, seq):
                seq = event.seq
                yield {"id": str(seq), "event": event.type, "data": event.model_dump_json()}
            if finished:
                return
            await asyncio.sleep(POLL_SECONDS)

    return EventSourceResponse(stream(), ping=15)
