from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import httpx
import pytest

from api.app import create_app


@pytest.mark.anyio
async def test_evaluation_reports_are_sanitized_and_link_real_events(
    project_root: Path, scenario_db: Path, tmp_path: Path
) -> None:
    report_dir = tmp_path / "data/generated/eval/demo"
    report_dir.mkdir(parents=True)
    attempt_db = report_dir / "attempt.sqlite"
    with sqlite3.connect(attempt_db) as connection:
        connection.execute(
            """CREATE TABLE run_events (
                run_id TEXT, case_id TEXT, seq INTEGER, type TEXT, summary TEXT, ts_virtual TEXT
            )"""
        )
        connection.execute(
            "INSERT INTO run_events VALUES (?,?,?,?,?,?)",
            (
                "run-proof",
                "CASE-1",
                7,
                "tool_call",
                "Called a recorded tool",
                "2026-10-21T00:00:00Z",
            ),
        )
    report = {
        "attempts": [
            {
                "run_index": 1,
                "run_id": "run-proof",
                "db": str(attempt_db),
                "case_id": "CASE-1",
                "passed": True,
                "trajectory_complete": True,
                "capabilities": [
                    {
                        "name": "tool_calling",
                        "passed": True,
                        "actual": ["tool_call"],
                        "expected": ["tool_call"],
                    }
                ],
                "metrics": {"hash_chain_valid": True, "replay_reconciled": True},
            }
        ],
        "reliability": [{"case_id": "CASE-1", "stable_outcome": True}],
        "capability_matrix": {"tool_calling": {"CASE-1": True}},
    }
    (report_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")

    app = create_app(project_root, db_path=scenario_db, ui_dir=tmp_path / "ui")
    app.state.root = tmp_path
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        listing = await client.get("/api/v1/evaluation/reports")
        detail = await client.get("/api/v1/evaluation/reports/demo")
        traversal = await client.get("/api/v1/evaluation/reports/..")

    assert listing.status_code == detail.status_code == 200
    body = detail.json()
    assert body["summary"]["pass_rate"] == 1
    assert body["proving_events"][0] == {
        "capability": "tool_calling",
        "case_id": "CASE-1",
        "run_id": "run-proof",
        "seq": 7,
        "type": "tool_call",
        "summary": "Called a recorded tool",
        "ts_virtual": "2026-10-21T00:00:00Z",
    }
    assert "attempt.sqlite" not in detail.text
    assert '"db"' not in detail.text
    assert traversal.status_code == 404
