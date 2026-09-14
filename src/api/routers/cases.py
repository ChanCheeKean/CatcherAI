from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_connection
from api.models import CaseDetail, CasePage
from api.read_models import get_case_detail, list_cases

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=CasePage)
def get_cases(
    connection: Annotated[sqlite3.Connection, Depends(get_connection)],
    regime: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    claim_family: str | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[int, Query(ge=0)] = 0,
) -> CasePage:
    return list_cases(
        connection,
        regime=regime,
        status=status,
        stage=stage,
        claim_family=claim_family,
        q=q,
        limit=limit,
        cursor=cursor,
    )


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(
    case_id: str, connection: Annotated[sqlite3.Connection, Depends(get_connection)]
) -> CaseDetail:
    return get_case_detail(connection, case_id)
