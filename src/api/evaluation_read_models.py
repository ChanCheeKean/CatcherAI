from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from api.errors import not_found
from api.models import (
    EvaluationAttemptSummary,
    EvaluationProvingEvent,
    EvaluationReportDetail,
    EvaluationReportSummary,
)


def _reports_root(root: Path) -> Path:
    return (root / "data/generated/eval").resolve()


def _report_path(root: Path, report_id: str) -> Path:
    reports_root = _reports_root(root)
    candidate = (reports_root / report_id / "report.json").resolve()
    if candidate.parent.parent != reports_root or not candidate.is_file():
        raise not_found(
            "evaluation_report_not_found",
            "Evaluation report was not found",
            report_id=report_id,
        )
    return candidate


def _load_report(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise not_found("evaluation_report_not_found", "Evaluation report is unavailable") from exc
    if not isinstance(value, dict):
        raise not_found("evaluation_report_not_found", "Evaluation report is unavailable")
    return value


def _summary(report_id: str, path: Path, report: dict[str, Any]) -> EvaluationReportSummary:
    attempts = report.get("attempts", [])
    reliability = report.get("reliability", [])
    valid_attempts = [item for item in attempts if isinstance(item, dict)]
    passed = sum(item.get("passed") is True for item in valid_attempts)
    reconciled = sum(
        item.get("metrics", {}).get("replay_reconciled") is True
        and item.get("metrics", {}).get("hash_chain_valid") is True
        for item in valid_attempts
    )
    return EvaluationReportSummary(
        report_id=report_id,
        modified_at=datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
        attempts=len(valid_attempts),
        passed=passed,
        cases=len(reliability),
        pass_rate=passed / len(valid_attempts) if valid_attempts else 0,
        stable_cases=sum(item.get("stable_outcome") is True for item in reliability),
        reconciled_attempts=reconciled,
    )


def list_evaluation_reports(root: Path) -> list[EvaluationReportSummary]:
    reports_root = _reports_root(root)
    if not reports_root.is_dir():
        return []
    reports: list[EvaluationReportSummary] = []
    for path in reports_root.glob("*/report.json"):
        report = _load_report(path)
        reports.append(_summary(path.parent.name, path, report))
    return sorted(reports, key=lambda item: item.modified_at, reverse=True)


def _attempt_db(root: Path, report_path: Path, value: object) -> Path | None:
    if not isinstance(value, str):
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    # A report may refer only to a sibling attempt store in its own fixed report directory.
    if candidate.parent != report_path.parent or not candidate.is_file():
        return None
    return candidate


def _proving_events(
    root: Path, report_path: Path, attempts: list[dict[str, Any]]
) -> list[EvaluationProvingEvent]:
    result: list[EvaluationProvingEvent] = []
    for attempt in attempts:
        db_path = _attempt_db(root, report_path, attempt.get("db"))
        if db_path is None:
            continue
        capabilities = attempt.get("capabilities", [])
        event_types = {
            str(event_type)
            for capability in capabilities
            if isinstance(capability, dict)
            for event_type in capability.get("actual", [])
            if isinstance(event_type, str)
        }
        if not event_types:
            continue
        placeholders = ",".join("?" for _ in event_types)
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""SELECT run_id, case_id, seq, type, summary, ts_virtual
                    FROM run_events WHERE run_id=? AND type IN ({placeholders}) ORDER BY seq""",
                [attempt.get("run_id"), *sorted(event_types)],
            ).fetchall()
        first_by_type: dict[str, sqlite3.Row] = {}
        for row in rows:
            first_by_type.setdefault(str(row["type"]), row)
        for capability in capabilities:
            if not isinstance(capability, dict):
                continue
            for event_type in capability.get("actual", []):
                row = first_by_type.get(event_type)
                if row is None:
                    continue
                result.append(
                    EvaluationProvingEvent(
                        capability=str(capability.get("name", "unknown")),
                        case_id=str(attempt.get("case_id", row["case_id"] or "")),
                        run_id=str(row["run_id"]),
                        seq=int(row["seq"]),
                        type=str(row["type"]),
                        summary=str(row["summary"]),
                        ts_virtual=str(row["ts_virtual"]),
                    )
                )
    return result


def get_evaluation_report(root: Path, report_id: str) -> EvaluationReportDetail:
    path = _report_path(root, report_id)
    report = _load_report(path)
    raw_attempts = [item for item in report.get("attempts", []) if isinstance(item, dict)]
    attempts = [
        EvaluationAttemptSummary(
            run_index=int(item.get("run_index", 0)),
            run_id=str(item.get("run_id", "")),
            case_id=str(item.get("case_id", "")),
            passed=item.get("passed") is True,
            trajectory_complete=item.get("trajectory_complete") is True,
            metrics=dict(item.get("metrics", {})),
            capabilities=[
                dict(value) for value in item.get("capabilities", []) if isinstance(value, dict)
            ],
        )
        for item in raw_attempts
    ]
    return EvaluationReportDetail(
        report_id=report_id,
        summary=_summary(report_id, path, report),
        reliability=[
            dict(item) for item in report.get("reliability", []) if isinstance(item, dict)
        ],
        capability_matrix={
            str(capability): {str(case_id): bool(passed) for case_id, passed in cases.items()}
            for capability, cases in report.get("capability_matrix", {}).items()
            if isinstance(cases, dict)
        },
        attempts=attempts,
        proving_events=_proving_events(root, path, raw_attempts),
    )
