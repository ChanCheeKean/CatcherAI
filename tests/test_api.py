from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_runtime import (  # noqa: F401  (runtime_paths is a fixture)
    CASE_ID,
    TXN_ID,
    AgentBuilder,
    StructuredModel,
    decide_turn,
    delegate_turn,
    finding,
    report,
    runtime_paths,
    triage,
)

from api.app import create_app
from api.context import ApiContext
from runtime import RuntimePaths
from schemas import SupervisorTurn, Triage


@pytest.fixture
def client(runtime_paths: RuntimePaths, tmp_path: Path) -> TestClient:  # noqa: F811
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            [
                {
                    "case_id": CASE_ID,
                    "title": "Test case",
                    "claim_type": "fraud",
                    "amount": 10.0,
                    "summary": "I do not recognize this charge.",
                }
            ]
        )
    )
    model = StructuredModel(
        {
            Triage: [triage()],
            SupervisorTurn: [delegate_turn(), decide_turn(close_plan=True)],
        }
    )
    builder = AgentBuilder(
        {
            "graph_analyst": finding("Identity path checked.", "CUS-TEST-1"),
            "evidence_analyst": finding("Transaction checked.", TXN_ID),
        },
        report(),
    )
    context = ApiContext(
        paths=runtime_paths,
        catalog=catalog,
        ground_truth_dir=tmp_path / "truth",
        eval_dir=tmp_path / "eval",
        model=model,
        agent_builder=builder,
    )
    return TestClient(create_app(context))


def sse_events(text: str) -> list[dict]:
    events = []
    for block in text.replace("\r\n", "\n").strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "data" in fields:
            events.append(
                {"id": int(fields["id"]), "type": fields["event"], "data": fields["data"]}
            )
    return events


def test_list_cases(client: TestClient) -> None:
    cases = client.get("/cases").json()
    assert [c["case_id"] for c in cases] == [CASE_ID]
    assert cases[0]["claim_type"] == "fraud"


def test_unknown_case_and_run(client: TestClient) -> None:
    assert client.post("/runs", json={"case_id": "DSP-NOPE"}).status_code == 404
    assert client.get("/runs/run-nope").json()["error"]["code"] == "run_not_found"
    assert client.get("/runs/run-nope/events").status_code == 404


def test_run_streams_events_and_returns_report(client: TestClient) -> None:
    started = client.post("/runs", json={"case_id": CASE_ID})
    assert started.status_code == 202
    run_id = started.json()["run_id"]

    stream = client.get(f"/runs/{run_id}/events")
    events = sse_events(stream.text)
    payloads = [json.loads(e["data"]) for e in events]
    types = [e["type"] for e in events]
    assert types[0] == "run_started"
    assert {"decision", "termination"} <= set(types)
    assert [e["id"] for e in events] == list(range(1, len(events) + 1))
    assert all({"actor", "visit", "turn"} <= payload.keys() for payload in payloads)

    resumed = sse_events(client.get(f"/runs/{run_id}/events", headers={"Last-Event-ID": "5"}).text)
    assert [e["id"] for e in resumed] == list(range(6, len(events) + 1))

    run = client.get(f"/runs/{run_id}").json()
    assert run["status"] == "completed"
    assert run["case_id"] == CASE_ID
    assert run["report"]["verdict"] == "accepted"
    assert run["report"]["transactions"][0]["txn_id"] == TXN_ID


def test_cases_point_at_the_latest_completed_run(client: TestClient) -> None:
    assert client.get("/cases").json()[0]["latest_run_id"] is None

    first = client.post("/runs", json={"case_id": CASE_ID}).json()["run_id"]
    sse_events(client.get(f"/runs/{first}/events").text)
    latest = client.get("/cases").json()[0]
    assert (latest["latest_run_id"], latest["latest_verdict"]) == (first, "accepted")

    client.app.state.context.model = StructuredModel({Triage: []})  # the next run fails
    failed = client.post("/runs", json={"case_id": CASE_ID}).json()["run_id"]
    sse_events(client.get(f"/runs/{failed}/events").text)
    assert client.get("/cases").json()[0]["latest_run_id"] == first


def test_failed_run_reports_error(client: TestClient) -> None:
    client.app.state.context.model = StructuredModel({Triage: []})
    run_id = client.post("/runs", json={"case_id": CASE_ID}).json()["run_id"]
    sse_events(client.get(f"/runs/{run_id}/events").text)
    for _ in range(50):
        run = client.get(f"/runs/{run_id}").json()
        if run["status"] != "running":
            break
        time.sleep(0.1)
    assert run["status"] == "failed" and run["error"]


def test_graph_nodes_batch(client: TestClient) -> None:
    edge_id = client.get(f"/graph/neighbors/{CASE_ID}").json()["edge_ids"][0]
    body = client.get("/graph/nodes", params={"ids": f"{TXN_ID},{edge_id},TXN-GONE"}).json()
    assert [n["id"] for n in body["nodes"]] == [TXN_ID]
    assert body["nodes"][0]["label"] == "Transaction"
    assert body["nodes"][0]["properties"]["amount"] == 10.0
    assert [e["id"] for e in body["edges"]] == [edge_id]
    assert {body["edges"][0]["src"], body["edges"][0]["dst"]} <= {CASE_ID, TXN_ID, "CUS-TEST-1"}
    assert body["missing"] == ["TXN-GONE"]


def test_graph_neighbors(client: TestClient) -> None:
    body = client.get(f"/graph/neighbors/{CASE_ID}").json()
    assert {n["node"]["id"] for n in body["neighbors"]} == {TXN_ID, "CUS-TEST-1"}
    assert {n["type"] for n in body["neighbors"]} == {"FILED_BY", "DISPUTES"}
    assert set(body["node_ids"]) == {CASE_ID, TXN_ID, "CUS-TEST-1"}
    assert client.get("/graph/neighbors/ZZZ-1").status_code == 404


def test_run_graph_holds_agent_written_nodes(client: TestClient) -> None:
    run_id = client.post("/runs", json={"case_id": CASE_ID}).json()["run_id"]
    sse_events(client.get(f"/runs/{run_id}/events").text)
    body = client.get(f"/graph/neighbors/{CASE_ID}", params={"run_id": run_id}).json()
    assert TXN_ID in body["node_ids"]
    assert (
        client.get("/graph/nodes", params={"ids": TXN_ID, "run_id": "run-nope"}).status_code == 404
    )


def test_eval_latest_empty_then_overlay(client: TestClient, tmp_path: Path) -> None:
    assert client.get("/eval/latest").json() == {
        "batch": None,
        "k": None,
        "pass_at_1": None,
        "pass_at_k": None,
        "cases": [],
    }
    (tmp_path / "truth").mkdir()
    (tmp_path / "truth" / f"{CASE_ID}.json").write_text(
        json.dumps(
            {
                "case_id": CASE_ID,
                "code": "C01",
                "solution_node_ids": [CASE_ID, TXN_ID],
                "decoy_patterns": [{"cypher": "MATCH (c:Customer) RETURN c"}],
            }
        )
    )
    for batch, passed in (("20260101-000000", 0), ("20260102-000000", 1)):
        out = tmp_path / "eval" / batch
        out.mkdir(parents=True)
        (out / "summary.json").write_text(
            json.dumps(
                {
                    "k": 1,
                    "pass_at_1": passed,
                    "pass_at_k": passed,
                    "cases": [
                        {"code": "C01", "title": "Test case", "pass_at_k": bool(passed)},
                        {"code": "C99", "title": "No truth", "pass_at_k": False},
                    ],
                }
            )
        )
    body = client.get("/eval/latest").json()
    assert body["batch"] == "20260102-000000"
    assert [c["case_id"] for c in body["cases"]] == [CASE_ID]
    assert body["cases"][0]["passed"] is True
    assert body["cases"][0]["solution_node_ids"] == [CASE_ID, TXN_ID]
    assert body["cases"][0]["decoy_node_ids"] == ["CUS-TEST-1"]
