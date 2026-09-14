from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_connection
from api.models import DecisionResponse, EventPage, RunPage, RunSummary
from api.read_models import get_decision, get_run_summary, list_events, list_runs

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=RunPage)
def get_runs(
    connection: Annotated[sqlite3.Connection, Depends(get_connection)],
    case_id: str | None = None,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[int, Query(ge=0)] = 0,
) -> RunPage:
    return list_runs(connection, case_id=case_id, status=status, limit=limit, cursor=cursor)


@router.get("/{run_id}", response_model=RunSummary)
def get_run(
    run_id: str, connection: Annotated[sqlite3.Connection, Depends(get_connection)]
) -> RunSummary:
    return get_run_summary(connection, run_id)


@router.get("/{run_id}/events", response_model=EventPage)
def get_run_events(
    run_id: str,
    connection: Annotated[sqlite3.Connection, Depends(get_connection)],
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


@router.get("/{run_id}/decision", response_model=DecisionResponse)
def get_run_decision(
    run_id: str, connection: Annotated[sqlite3.Connection, Depends(get_connection)]
) -> DecisionResponse:
    return get_decision(connection, run_id)
