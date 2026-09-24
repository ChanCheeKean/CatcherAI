import json

from fastapi.testclient import TestClient
from graph_builder import Graph

from api.app import create_app
from api.context import ApiContext
from domain.events import Actor, ActorKind, EventDraft, RuntimeSnapshot
from graph_store import load
from observability.emitter import EventEmitter
from runtime_entry import RuntimePaths


def test_ontology_nodes_and_case_catalog(tmp_path):
    graph = Graph()
    graph.node("CardMember", "CMB-TEST-1", name="Test Member")
    graph.write(tmp_path / "graph")
    source = tmp_path / "evidence.lbug"
    load(tmp_path / "graph", source).close()
    catalog = tmp_path / "case_catalog.json"
    catalog.write_text(
        json.dumps(
            [
                {
                    "case_id": "DSP-TEST-1",
                    "title": "Test dispute",
                    "claim": "Wrong amount",
                    "amount": 10.0,
                    "summary": "A test dispute",
                }
            ]
        )
    )
    client = TestClient(
        create_app(ApiContext(paths=RuntimePaths(source_graph=source), catalog=catalog))
    )

    ontology = client.get("/graph/ontology")
    assert ontology.status_code == 200
    body = ontology.json()
    assert body["groups"]
    assert all(value["group"] in body["groups"] for value in body["labels"].values())
    assert all(value["description"] for value in body["labels"].values())
    assert all(value["description"] for value in body["edges"].values())
    assert (body["node_count"], body["edge_count"]) == (1, 0)

    nodes = client.get("/graph/nodes", params={"ids": "CMB-TEST-1,CMB-MISSING"})
    assert nodes.status_code == 200
    assert [node["id"] for node in nodes.json()["nodes"]] == ["CMB-TEST-1"]
    assert nodes.json()["missing"] == ["CMB-MISSING"]

    cases = client.get("/cases")
    assert cases.status_code == 200
    assert cases.json()[0]["claim"] == "Wrong amount"
    assert cases.json()[0]["latest"] is None
    assert "claim_type" not in cases.json()[0]
    assert "category" not in cases.json()[0]


def test_case_catalog_summarises_the_latest_decided_run(tmp_path):
    catalog = tmp_path / "case_catalog.json"
    catalog.write_text(
        json.dumps(
            [{"case_id": "DSP-TEST-1", "title": "T", "claim": "C", "amount": 1.0, "summary": "S"}]
        )
    )
    paths = RuntimePaths(trajectory_db=tmp_path / "trajectory.sqlite")
    emitter = EventEmitter(
        paths.trajectory_db,
        run_id="run-test",
        case_id="DSP-TEST-1",
        runtime=RuntimeSnapshot(config_hash="t", agent_runtime="t", provider="t", model="t"),
    )
    for name, kind, payload in (
        ("graph_analyst", "tool_result", {"node_ids": ["CMB-1", "CHG-1"], "edge_ids": ["E-1"]}),
        ("policy_analyst", "notebook_write", {"node_ids": ["CHG-1", "CLS-1"]}),
        ("adjudicator", "decision", {"report": {"verdict": "rejected"}}),
    ):
        emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.AGENT, name=name),
                type=kind,
                summary=kind,
                payload=payload,
            )
        )
    (tmp_path / "eval" / "batch").mkdir(parents=True)
    run = {"case_id": "DSP-TEST-1", "run_id": "run-test", "passed": True}
    (tmp_path / "eval" / "batch" / "summary.json").write_text(
        json.dumps({"cases": [{"runs": [run]}]})
    )
    client = TestClient(
        create_app(ApiContext(paths=paths, catalog=catalog, eval_dir=tmp_path / "eval"))
    )

    latest = client.get("/cases").json()[0]["latest"]

    assert latest["seconds"] >= 0
    assert {
        key: latest[key] for key in ("run_id", "verdict", "agents", "nodes_examined", "passed")
    } == {
        "run_id": "run-test",
        "verdict": "rejected",
        "agents": 3,
        "nodes_examined": 3,
        "passed": True,
    }
