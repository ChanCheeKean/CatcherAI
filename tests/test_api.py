from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from runtime.langgraph_runtime import LangGraphRuntime, RunSuspended


@pytest.fixture
def client(project_root: Path, scenario_db: Path) -> TestClient:
    app = create_app(project_root, db_path=scenario_db)
    return TestClient(app)


def test_health_reports_the_configured_store(client: TestClient, scenario_db: Path) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["scenario_db"] is True
    assert body["scenario_db_path"] == str(scenario_db)


def test_meta_never_returns_the_openai_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-never-appear")
    response = client.get("/api/v1/meta")
    assert response.status_code == 200
    body = response.json()
    assert body["adapters"] == {"fake": True, "openai": True}
    assert "sk-should-never-appear" not in response.text


def test_meta_routes_agents_skills_workflow_and_schema(client: TestClient) -> None:
    routes = client.get("/api/v1/meta/routes")
    assert routes.status_code == 200
    assert any(route["id"] for route in routes.json())

    agents = client.get("/api/v1/meta/agents")
    assert agents.status_code == 200
    assert {agent["id"] for agent in agents.json()} >= {"lead_investigator", "panel_adjudicator"}

    skills = client.get("/api/v1/meta/skills")
    assert skills.status_code == 200
    assert any(skill["name"] == "eligibility-check" for skill in skills.json())

    workflow = client.get("/api/v1/meta/workflow")
    assert workflow.status_code == 200
    node_ids = {node["id"] for node in workflow.json()["nodes"]}
    assert {"run_start", "verify", "review_panel", "terminate"} <= node_ids
    edge_pairs = {(edge["source"], edge["target"]) for edge in workflow.json()["edges"]}
    assert ("verify", "replan") in edge_pairs

    schema = client.get("/api/v1/schema/events")
    assert schema.status_code == 200
    assert schema.json()["title"] == "EventEnvelope"


def test_cases_pagination_and_filters(client: TestClient) -> None:
    page_one = client.get("/api/v1/cases", params={"limit": 5})
    assert page_one.status_code == 200
    body = page_one.json()
    assert len(body["items"]) == 5
    assert body["next_cursor"] == "5"

    page_two = client.get("/api/v1/cases", params={"limit": 5, "cursor": body["next_cursor"]})
    assert page_two.status_code == 200
    assert page_two.json()["items"][0]["case_id"] != body["items"][0]["case_id"]

    filtered = client.get("/api/v1/cases", params={"regime": "REG_E", "limit": 50})
    assert filtered.status_code == 200
    assert filtered.json()["items"]
    assert all(row["regime"] == "REG_E" for row in filtered.json()["items"])

    searched = client.get("/api/v1/cases", params={"q": "DSP-2026-90002"})
    assert searched.status_code == 200
    assert [row["case_id"] for row in searched.json()["items"]] == ["DSP-2026-90002"]


def test_case_detail_and_missing_case(client: TestClient) -> None:
    found = client.get("/api/v1/cases/DSP-2026-90002")
    assert found.status_code == 200
    body = found.json()
    assert body["case_id"] == "DSP-2026-90002"
    assert body["transactions"]
    assert "birth_year" not in found.text  # SOP-DSP-004 prohibited signal never crosses the API

    missing = client.get("/api/v1/cases/DSP-2026-NOPE")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "case_not_found"


async def test_run_case_events_and_decision_round_trip(
    client: TestClient, runtime: LangGraphRuntime
) -> None:
    decision = await runtime.run("DSP-2026-90002")
    run_id = runtime.last_run_id
    assert run_id

    run_summary = client.get(f"/api/v1/runs/{run_id}")
    assert run_summary.status_code == 200
    assert run_summary.json()["status"] == "decided"
    assert run_summary.json()["decision_available"] is True

    by_case = client.get("/api/v1/runs", params={"case_id": "DSP-2026-90002"})
    assert by_case.status_code == 200
    assert run_id in {row["run_id"] for row in by_case.json()["items"]}

    first_page = client.get(f"/api/v1/runs/{run_id}/events", params={"limit": 10})
    assert first_page.status_code == 200
    first_body = first_page.json()
    assert len(first_body["items"]) == 10
    assert first_body["items"][0]["seq"] == 1
    assert first_body["next_after_seq"] == 10

    second_page = client.get(
        f"/api/v1/runs/{run_id}/events",
        params={"limit": 10, "after_seq": first_body["next_after_seq"]},
    )
    assert second_page.status_code == 200
    assert second_page.json()["items"][0]["seq"] == 11

    filtered = client.get(
        f"/api/v1/runs/{run_id}/events", params={"type": "route_decision", "limit": 10}
    )
    assert filtered.status_code == 200
    assert [row["type"] for row in filtered.json()["items"]] == ["route_decision"]

    decision_response = client.get(f"/api/v1/runs/{run_id}/decision")
    assert decision_response.status_code == 200
    decision_body = decision_response.json()
    assert decision_body["case_id"] == "DSP-2026-90002"
    assert decision_body["record"]["cardholder_resolution"]["outcome"] == (
        decision.cardholder_resolution.outcome
    )
    assert decision_body["field_provenance"]

    case_detail = client.get("/api/v1/cases/DSP-2026-90002")
    assert run_id in {row["run_id"] for row in case_detail.json()["latest_runs"]}


def test_missing_run_and_decision_404(client: TestClient) -> None:
    run_response = client.get("/api/v1/runs/run-does-not-exist")
    assert run_response.status_code == 404
    assert run_response.json()["error"]["code"] == "run_not_found"

    events_response = client.get("/api/v1/runs/run-does-not-exist/events")
    assert events_response.status_code == 404

    decision_response = client.get("/api/v1/runs/run-does-not-exist/decision")
    assert decision_response.status_code == 404
    assert decision_response.json()["error"]["code"] == "decision_not_found"


async def test_suspended_run_status_and_wait(client: TestClient, make_runtime) -> None:  # type: ignore[no-untyped-def]
    runtime: LangGraphRuntime = make_runtime()
    run_id = await runtime.start("DSP-2026-90015", auto_resume=False)
    with pytest.raises(RunSuspended):
        await runtime.result(run_id)

    summary = client.get(f"/api/v1/runs/{run_id}")
    assert summary.status_code == 200
    body = summary.json()
    assert body["status"] == "suspended"
    assert body["wait"]["awaited_ref"]
    assert body["decision_available"] is False
