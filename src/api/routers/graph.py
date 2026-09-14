from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_root, get_run_connection
from api.graph_read_models import case_neighborhood
from api.models import GraphResponse, RunGraphResponse
from api.read_models import get_run_graph

router = APIRouter(tags=["graph"])


@router.get("/graph/cases/{case_id}", response_model=GraphResponse)
async def graph_case(
    case_id: str,
    root: Annotated[Path, Depends(get_root)],
    depth: Annotated[int, Query(ge=1, le=3)] = 2,
    limit: Annotated[int, Query(ge=10, le=250)] = 120,
) -> GraphResponse:
    return case_neighborhood(root, case_id, depth=depth, limit=limit)


@router.get("/runs/{run_id}/graph", response_model=RunGraphResponse)
async def run_graph(
    run_id: str, connection: Annotated[sqlite3.Connection, Depends(get_run_connection)]
) -> RunGraphResponse:
    return get_run_graph(connection, run_id)
