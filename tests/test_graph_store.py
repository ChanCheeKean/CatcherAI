from __future__ import annotations

from pathlib import Path

import pytest
from graph_builder import Graph

import graph_store


@pytest.fixture
def built(tmp_path: Path):
    g = Graph()
    g.node("Customer", "CUS-1", name="Ann")
    g.node("Customer", "CUS-2", name="Bob")
    g.node("Phone", "PHN-1", number="+1 555 0100")
    g.node("Address", "ADR-1", street="1 Elm St", unit="2A")
    g.node("Device", "DEV-1", kind="tablet")
    g.node("Merchant", "MER-1", name="Shop 'n Go; SET x")
    g.edge("HAS_PHONE", "CUS-1", "PHN-1", valid_from="2026-01-01", valid_to="2026-03-01")
    g.edge("HAS_PHONE", "CUS-2", "PHN-1", valid_from="2026-03-02", valid_to="")
    g.edge("LIVES_AT", "CUS-1", "ADR-1", valid_from="2025-01-01", valid_to="")
    g.edge("LOGGED_IN_FROM", "CUS-1", "DEV-1", ts="2026-02-01", ip="10.0.0.1")
    g.write(tmp_path / "jsonl")
    return g, tmp_path


@pytest.fixture
def store(built):
    _, tmp = built
    return graph_store.load(tmp / "jsonl", tmp / "g.lbug")


def test_builder_rejects_bad_input():
    g = Graph()
    g.node("Customer", "CUS-1")
    g.node("Phone", "PHN-1")
    with pytest.raises(ValueError, match="unknown node label"):
        g.node("Alien", "ALN-1")
    with pytest.raises(ValueError, match="must start with"):
        g.node("Customer", "X-1")
    with pytest.raises(ValueError, match="duplicate"):
        g.node("Customer", "CUS-1")
    with pytest.raises(ValueError, match="unknown properties"):
        g.node("Customer", "CUS-9", shoe_size=3)
    with pytest.raises(ValueError, match="unknown edge type"):
        g.edge("KNOWS", "CUS-1", "PHN-1")
    with pytest.raises(ValueError, match="unknown properties"):
        g.edge("HAS_PHONE", "CUS-1", "PHN-1", colour="red")
    with pytest.raises(ValueError, match="dangling"):
        g.edge("HAS_PHONE", "CUS-1", "PHN-404")
    with pytest.raises(ValueError, match="cannot connect"):
        g.edge("HAS_PHONE", "PHN-1", "CUS-1")


def test_load_and_schema_counts(store):
    schema = store.schema()
    assert schema["nodes"]["Customer"]["count"] == 2
    assert schema["nodes"]["Transaction"]["count"] == 0
    assert schema["edges"]["HAS_PHONE"]["count"] == 2
    assert "valid_from" in schema["edges"]["HAS_PHONE"]["props"]


def test_query_returns_ids_and_clean_rows(store):
    out = store.query(
        "MATCH (c:Customer)-[r:HAS_PHONE]->(p:Phone) WHERE c.id = $id RETURN c, r, p.id",
        {"id": "CUS-1"},
    )
    assert out["node_ids"] == ["CUS-1", "PHN-1"]
    assert len(out["edge_ids"]) == 1 and out["edge_ids"][0].startswith("E-")
    customer = out["rows"][0][0]
    assert customer["_label"] == "Customer" and customer["name"] == "Ann"
    assert "_ID" not in customer
    assert not out["truncated"]


def test_query_row_cap_and_path_ids(store):
    out = store.query("MATCH (c:Customer) RETURN c.id", row_cap=1)
    assert len(out["rows"]) == 1 and out["truncated"]
    path = store.query("MATCH p = (c:Customer {id: 'CUS-1'})-[*1..2]->(x) RETURN p")
    assert {"CUS-1", "PHN-1", "ADR-1"} <= set(path["node_ids"])


@pytest.mark.parametrize(
    "kw",
    ["CREATE", "MERGE", "SET", "DELETE", "REMOVE", "DROP", "COPY", "LOAD", "INSTALL", "ATTACH"],
)
def test_query_rejects_write_keywords(store, kw):
    with pytest.raises(ValueError, match="read-only"):
        store.query(f"MATCH (c:Customer) {kw.lower()} c.name = 'x' RETURN c")


def test_query_allows_keywords_inside_literals(store):
    out = store.query("MATCH (m:Merchant) WHERE m.name = 'Shop \\'n Go; SET x' RETURN m.id")
    assert out["rows"] == [["MER-1"]]
    assert (
        store.query('MATCH (m:Merchant) WHERE m.name CONTAINS "DELETE" RETURN m.id')["rows"] == []
    )


def test_neighbors_respect_validity_windows(store):
    def phones(**kw):
        return store.neighbors("PHN-1", ["HAS_PHONE"], "in", **kw)["node_ids"]

    assert phones() == ["CUS-1", "CUS-2", "PHN-1"]
    assert phones(since="2026-02-01", until="2026-02-28") == ["CUS-1", "PHN-1"]
    assert phones(since="2026-03-10") == ["CUS-2", "PHN-1"]
    out = store.neighbors("CUS-1")
    assert {n["type"] for n in out["neighbors"]} == {"HAS_PHONE", "LIVES_AT", "LOGGED_IN_FROM"}
    assert store.neighbors("CUS-1", ["LOGGED_IN_FROM"], since="2026-03-01")["neighbors"] == []
    assert len(store.neighbors("CUS-1", limit=1)["neighbors"]) == 1


def test_write_finding_persists_across_connections(store):
    out = store.write_finding(
        "Ann and Bob shared a phone",
        run_id="r1",
        confidence=0.8,
        evidence_path="CUS-1>PHN-1<CUS-2",
        edges=[
            {"type": "SAME_ACTOR", "src": "CUS-1", "dst": "CUS-2"},
            {"type": "ABOUT", "dst": "CUS-1"},
        ],
    )
    store.close()
    fresh = graph_store.GraphStore(store.db_path)
    rows = fresh.query(
        "MATCH (f:Finding)-[r:ABOUT]->(c:Customer) RETURN f.id, r.run_id, r.confidence"
    )["rows"]
    assert rows == [[out["finding_id"], "r1", 0.8]]
    assert fresh.query("MATCH (:Customer)-[r:SAME_ACTOR]->(:Customer) RETURN r.id")["rows"]


def test_write_finding_rejects_non_inferred_edges(store):
    with pytest.raises(ValueError, match="may not write"):
        store.write_finding("x", "r1", 0.5, edges=[{"type": "HAS_PHONE", "dst": "PHN-1"}])
    with pytest.raises(ValueError, match="cannot connect"):
        store.write_finding("x", "r1", 0.5, edges=[{"type": "SUPPORTS", "dst": "PHN-1"}])


def test_copy_store_isolates_runs(store, tmp_path):
    store.close()
    copy = graph_store.copy_store(store.db_path, tmp_path / "run" / "g.lbug")
    copy.write_finding("only in copy", "r2", 0.5)
    assert copy.schema()["nodes"]["Finding"]["count"] == 1
    assert graph_store.GraphStore(store.db_path).schema()["nodes"]["Finding"]["count"] == 0
