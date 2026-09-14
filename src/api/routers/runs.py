from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sse_starlette import EventSourceResponse

from api.constants import run_urls
from api.dependencies import get_all_connections, get_run_connection, get_run_manager
from api.models import (
    DecisionResponse,
    EventPage,
    RunCreateRequest,
    RunPage,
    RunStartResponse,
    RunSummary,
)
from api.read_models import get_decision, get_run_summary, list_events, list_runs
from api.run_manager import RunManager
from api.sse import stream_run_events

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunStartResponse, status_code=202)
async def start_run(
    body: RunCreateRequest, manager: Annotated[RunManager, Depends(get_run_manager)]
) -> RunStartResponse:
    handle = await manager.start_run(
        case_id=body.case_id, adapter=body.adapter, auto_resume=body.auto_resume
    )
    events_url, stream_url = run_urls(handle.run_id)
    return RunStartResponse(
        run_id=handle.run_id,
        case_id=handle.case_id,
        status=handle.status,
        events_url=events_url,
        stream_url=stream_url,
    )


@router.get("", response_model=RunPage)
async def get_runs(
    connections: Annotated[list[sqlite3.Connection], Depends(get_all_connections)],
    case_id: str | None = None,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[int, Query(ge=0)] = 0,
) -> RunPage:
    return list_runs(connections, case_id=case_id, status=status, limit=limit, cursor=cursor)


@router.get("/{run_id}", response_model=RunSummary)
async def get_run(
    run_id: str, connection: Annotated[sqlite3.Connection, Depends(get_run_connection)]
) -> RunSummary:
    return get_run_summary(connection, run_id)


@router.post("/{run_id}/cancel", response_model=RunSummary)
async def cancel_run(
    run_id: str,
    manager: Annotated[RunManager, Depends(get_run_manager)],
    connection: Annotated[sqlite3.Connection, Depends(get_run_connection)],
) -> RunSummary:
    await manager.cancel(run_id)
    return get_run_summary(connection, run_id)


@router.post("/{run_id}/rerun", response_model=RunStartResponse, status_code=202)
async def rerun_run(
    run_id: str, manager: Annotated[RunManager, Depends(get_run_manager)]
) -> RunStartResponse:
    handle = await manager.rerun(run_id)
    events_url, stream_url = run_urls(handle.run_id)
    return RunStartResponse(
        run_id=handle.run_id,
        case_id=handle.case_id,
        status=handle.status,
        events_url=events_url,
        stream_url=stream_url,
    )


@router.get("/{run_id}/events", response_model=EventPage)
async def get_run_events(
    run_id: str,
    connection: Annotated[sqlite3.Connection, Depends(get_run_connection)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
    type: str | None = None,  # noqa: A002 - matches the documented query parameter name
    actor: str | None = None,
    ref: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> EventPage:
    get_run_summary(connection, run_id)  # 404s cleanly for an unknown run
    events, next_after_seq = list_events(
        connection,
        run_id,
        after_seq=after_seq,
        event_type=type,
        actor=actor,
        ref=ref,
        limit=limit,
    )
    return EventPage(items=events, next_after_seq=next_after_seq, limit=limit)


@router.get("/{run_id}/events/stream")
async def stream_run_events_endpoint(
    run_id: str,
    request: Request,
    manager: Annotated[RunManager, Depends(get_run_manager)],
    connection: Annotated[sqlite3.Connection, Depends(get_run_connection)],
    after_seq: Annotated[int, Query(ge=0)] = 0,
) -> EventSourceResponse:
    get_run_summary(connection, run_id)  # 404s cleanly for an unknown run
    store = manager.resolve_store(run_id)
    last_event_id = request.headers.get("last-event-id")
    start_after = int(last_event_id) if last_event_id else after_seq
    return EventSourceResponse(
        stream_run_events(manager, store, run_id, start_after, request),
        ping=15,
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/{run_id}/decision", response_model=DecisionResponse)
async def get_run_decision(
    run_id: str, connection: Annotated[sqlite3.Connection, Depends(get_run_connection)]
) -> DecisionResponse:
    return get_decision(connection, run_id)
