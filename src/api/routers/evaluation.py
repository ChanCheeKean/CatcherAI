from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_root
from api.evaluation_read_models import get_evaluation_report, list_evaluation_reports
from api.models import EvaluationReportDetail, EvaluationReportSummary

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/reports", response_model=list[EvaluationReportSummary])
async def reports(root: Annotated[Path, Depends(get_root)]) -> list[EvaluationReportSummary]:
    return list_evaluation_reports(root)


@router.get("/reports/{report_id}", response_model=EvaluationReportDetail)
async def report(
    report_id: str, root: Annotated[Path, Depends(get_root)]
) -> EvaluationReportDetail:
    return get_evaluation_report(root, report_id)
