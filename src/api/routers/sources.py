from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_connection, get_run_connection
from api.models import BlobResponse, SourceResponse
from api.read_models import get_blob, resolve_source

router = APIRouter(tags=["sources"])


@router.get("/sources/{source_id}", response_model=SourceResponse)
async def source(
    source_id: str, connection: Annotated[sqlite3.Connection, Depends(get_connection)]
) -> SourceResponse:
    return resolve_source(connection, source_id)


@router.get("/runs/{run_id}/blobs/{sha256}", response_model=BlobResponse)
async def blob(
    run_id: str, sha256: str, connection: Annotated[sqlite3.Connection, Depends(get_run_connection)]
) -> BlobResponse:
    return get_blob(connection, run_id, sha256)
