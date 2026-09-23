import json

from fastapi.testclient import TestClient
from graph_builder import Graph

from api.app import create_app
from api.context import ApiContext
from graph_store import load
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

    nodes = client.get("/graph/nodes", params={"ids": "CMB-TEST-1,CMB-MISSING"})
    assert nodes.status_code == 200
    assert [node["id"] for node in nodes.json()["nodes"]] == ["CMB-TEST-1"]
    assert nodes.json()["missing"] == ["CMB-MISSING"]

    cases = client.get("/cases")
    assert cases.status_code == 200
    assert cases.json()[0]["claim"] == "Wrong amount"
    assert "claim_type" not in cases.json()[0]
    assert "category" not in cases.json()[0]
