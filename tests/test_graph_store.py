from __future__ import annotations

from pathlib import Path

import pytest
from graph_builder import Graph

import graph_store


@pytest.fixture
def store_path(tmp_path: Path):
    g = Graph()
    g.node("CardMember", "CMB-1", name="Ann")
    g.node("CardMember", "CMB-2", name="Bob")
    g.node("CardAccount", "ACC-1", product="Platinum")
    g.node("Card", "CRD-1", product="Platinum")
    g.node("Card", "CRD-2", product="Gold")
    g.node("Merchant", "MER-1", name="Shop 'n Go; SET x")
    g.node("Charge", "CHG-1", amount=24.0)
    g.node("PolicyDocument", "POL-1", title="Return policy")
    g.node("Clause", "CLS-1", text="Custom goods are final sale")
    g.node("Clause", "CLS-2", text="Standard goods may be returned")
    g.edge("HOLDS", "CMB-1", "ACC-1", role="basic")
    g.edge("HOLDS", "CMB-2", "ACC-1", role="additional")
    g.edge("ISSUED_ON", "CRD-1", "ACC-1")
    g.edge("ISSUED_ON", "CRD-2", "ACC-1")
    g.edge("CHARGED_TO", "CHG-1", "CRD-1")
    g.edge("AT_MERCHANT", "CHG-1", "MER-1")
    g.edge("HAS_CLAUSE", "POL-1", "CLS-1")
    g.edge("HAS_CLAUSE", "POL-1", "CLS-2")
    g.write(tmp_path / "jsonl")
    path = tmp_path / "g.lbug"
    graph_store.load(tmp_path / "jsonl", path).close()
    return path


@pytest.fixture
def store(store_path):
    db = graph_store.GraphStore(store_path)
    yield db
    db.close()


def test_builder_rejects_bad_input():
    g = Graph()
    g.node("CardMember", "CMB-1")
    g.node("CardAccount", "ACC-1")
    with pytest.raises(ValueError, match="unknown node label"):
        g.node("Alien", "ALN-1")
    with pytest.raises(ValueError, match="must start with"):
        g.node("Card", "CMB-3")
    with pytest.raises(ValueError, match="duplicate"):
        g.node("CardMember", "CMB-1")
    with pytest.raises(ValueError, match="unknown properties"):
        g.node("CardMember", "CMB-9", shoe_size=3)
    with pytest.raises(ValueError, match="unknown edge type"):
        g.edge("KNOWS", "CMB-1", "ACC-1")
    with pytest.raises(ValueError, match="unknown properties"):
        g.edge("HOLDS", "CMB-1", "ACC-1", colour="red")
    with pytest.raises(ValueError, match="dangling"):
        g.edge("HOLDS", "CMB-1", "ACC-404")
    with pytest.raises(ValueError, match="cannot connect"):
        g.edge("HOLDS", "ACC-1", "CMB-1")


def test_load_and_schema_counts(store):
    schema = store.schema()
    assert schema["nodes"]["CardMember"]["count"] == 2
    assert schema["nodes"]["Charge"]["count"] == 1
    assert schema["nodes"]["Clause"]["group"] == "terms"
    assert schema["nodes"]["Clause"]["description"]
    assert schema["nodes"]["Clause"]["props"]["text"]["description"]
    assert schema["edges"]["HAS_CLAUSE"]["count"] == 2
    assert schema["groups"]["terms"]["title"] == "Terms"


def test_query_returns_ids_and_clean_rows(store):
    out = store.query(
        "MATCH (c:CardMember)-[r:HOLDS]->(a:CardAccount) WHERE c.id = $id RETURN c, r, a.id",
        {"id": "CMB-1"},
    )
    assert out["node_ids"] == ["ACC-1", "CMB-1"]
    assert len(out["edge_ids"]) == 1 and out["edge_ids"][0].startswith("E-")
    member = out["rows"][0][0]
    assert member["_label"] == "CardMember" and member["name"] == "Ann"
    assert "_ID" not in member
    assert not out["truncated"]


def test_query_row_cap_and_path_ids(store):
    out = store.query("MATCH (c:CardMember) RETURN c.id", row_cap=1)
    assert len(out["rows"]) == 1 and out["truncated"]
    path = store.query("MATCH p = (c:CardMember {id: 'CMB-1'})-[*1..2]->(x) RETURN p")
    assert {"CMB-1", "ACC-1"} <= set(path["node_ids"])


@pytest.mark.parametrize(
    "kw",
    ["CREATE", "MERGE", "SET", "DELETE", "REMOVE", "DROP", "COPY", "LOAD", "INSTALL", "ATTACH"],
)
def test_query_rejects_write_keywords(store, kw):
    with pytest.raises(ValueError, match="read-only"):
        store.query(f"MATCH (c:CardMember) {kw.lower()} c.name = 'x' RETURN c")


def test_query_allows_keywords_inside_literals(store):
    out = store.query("MATCH (m:Merchant) WHERE m.name = 'Shop \\'n Go; SET x' RETURN m.id")
    assert out["rows"] == [["MER-1"]]
    assert (
        store.query('MATCH (m:Merchant) WHERE m.name CONTAINS "DELETE" RETURN m.id')["rows"] == []
    )


def test_neighbors(store):
    out = store.neighbors("ACC-1", ["HOLDS"], "in")
    assert out["node_ids"] == ["ACC-1", "CMB-1", "CMB-2"]
    assert len(out["neighbors"]) == 2
    assert len(store.neighbors("ACC-1", limit=1)["neighbors"]) == 1


def test_node_and_find(store):
    assert store.node("CMB-1")["name"] == "Ann"
    with pytest.raises(ValueError, match="no such node"):
        store.node("CMB-404")
    hits = store.find("FINAL SALE")
    assert [m["_label"] for m in hits["matches"]] == ["Clause"]
    assert hits["node_ids"] == [hits["matches"][0]["id"]]
    assert store.find("final sale", labels=["Merchant"])["matches"] == []


def test_store_opened_by_runs_is_read_only(store):
    with pytest.raises(RuntimeError):
        store.conn.execute("CREATE (:Merchant {id: 'MER-X', name: 'x'})")
