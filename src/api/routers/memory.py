from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_connection, get_run_connection
from api.models import MemoryNoteDetail, MemoryNotePage, RunMemoryResponse
from api.read_models import get_memory_note, get_run_memory, list_memory_notes

router = APIRouter(tags=["memory"])


@router.get("/memory/notes", response_model=MemoryNotePage)
async def notes(
    connection: Annotated[sqlite3.Connection, Depends(get_connection)],
    subject: str | None = None,
    scope: str | None = None,
    kind: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    min_confidence: Annotated[float | None, Query(ge=0, le=1)] = None,
    as_of: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[int, Query(ge=0)] = 0,
) -> MemoryNotePage:
    return list_memory_notes(
        connection,
        subject=subject,
        scope=scope,
        kind=kind,
        tag=tag,
        status=status,
        min_confidence=min_confidence,
        as_of=as_of,
        limit=limit,
        cursor=cursor,
    )


@router.get("/memory/notes/{note_id}", response_model=MemoryNoteDetail)
async def note(
    note_id: str, connection: Annotated[sqlite3.Connection, Depends(get_connection)]
) -> MemoryNoteDetail:
    return get_memory_note(connection, note_id)


@router.get("/runs/{run_id}/memory", response_model=RunMemoryResponse)
async def run_memory(
    run_id: str, connection: Annotated[sqlite3.Connection, Depends(get_run_connection)]
) -> RunMemoryResponse:
    return get_run_memory(connection, run_id)
