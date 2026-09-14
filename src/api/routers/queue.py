from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from api.constants import run_urls
from api.dependencies import get_run_connection, get_run_manager
from api.models import QueueRunCreateRequest, QueueRunResponse, RunStartResponse
from api.read_models import get_run_summary
from api.run_manager import RunManager

router = APIRouter(prefix="/queue", tags=["queue"])


@router.post("/runs", response_model=RunStartResponse, status_code=202)
async def start_queue_run(
    body: QueueRunCreateRequest, manager: Annotated[RunManager, Depends(get_run_manager)]
) -> RunStartResponse:
    handle = await manager.start_queue_run(adapter=body.adapter)
    events_url, stream_url = run_urls(handle.run_id)
    return RunStartResponse(
        run_id=handle.run_id,
        case_id=handle.case_id,
        status=handle.status,
        events_url=events_url,
        stream_url=stream_url,
    )


@router.get("/runs/{run_id}", response_model=QueueRunResponse)
async def get_queue_run(
    run_id: str,
    connection: Annotated[sqlite3.Connection, Depends(get_run_connection)],
    manager: Annotated[RunManager, Depends(get_run_manager)],
) -> QueueRunResponse:
    summary = get_run_summary(connection, run_id)
    return QueueRunResponse(
        run_id=run_id, status=summary.status, ranking=manager.queue_ranking(run_id)
    )
