from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from graph_builder import Graph

import graph_store
from domain.events import RuntimeSnapshot
from memory import retrieval
from observability.emitter import EventEmitter
from tools import Run, make_tools


@pytest.fixture
def run(tmp_path: Path) -> Run:
    g = Graph()
    g.node("Customer", "CUS-1", name="Ann")
    g.node("Customer", "CUS-2", name="Bob")
    g.node("Phone", "PHN-1", number="+1 555 0100")
    g.node("Merchant", "MER-1", name="Shop")
    g.edge("HAS_PHONE", "CUS-1", "PHN-1", valid_from="2026-01-01", valid_to="2026-03-01")
    g.edge("HAS_PHONE", "CUS-2", "PHN-1", valid_from="2026-03-02", valid_to="")
    g.write(tmp_path / "jsonl")
    store = graph_store.load(tmp_path / "jsonl", tmp_path / "g.lbug")
    knowledge = tmp_path / "knowledge.sqlite"
    doc = {"kind": "policy", "valid_from": "", "valid_to": "", "status": "active"}
    retrieval.build(
        knowledge,
        [
            {
                **doc,
                "doc_id": "P1",
                "title": "Reg E error resolution",
                "body": "provisional credit",
            },
            {**doc, "doc_id": "P2", "title": "Visa 10.4", "body": "card absent fraud liability"},
        ],
    )
    emitter = EventEmitter(
        tmp_path / "events.sqlite",
        run_id="run-1",
        case_id="DSP-1",
        runtime=RuntimeSnapshot(config_hash="t", agent_runtime="t", provider="t", model="t"),
    )
    return Run(store, emitter, "run-1", knowledge, date(2026, 4, 1), actor="graph_analyst")


def call(run: Run, name: str, **args) -> dict:
    tool = next(t for t in make_tools(run) if t.name == name)
    return json.loads(tool.invoke(args))


def test_seven_tools_with_typed_args(run):
    tools = make_tools(run)
    assert [t.name for t in tools] == [
        "graph_schema",
        "graph_query",
        "graph_neighbors",
        "graph_write_finding",
        "search_knowledge",
        "memory_write",
        "python",
    ]
    assert all(t.args_schema is not None for t in tools)


def test_graph_tools_happy_path(run):
    assert call(run, "graph_schema")["nodes"]["Customer"]["count"] == 2
    out = call(run, "graph_query", cypher="MATCH (c:Customer) RETURN c.id ORDER BY c.id")
    assert out["rows"] == [["CUS-1"], ["CUS-2"]]
    nb = call(run, "graph_neighbors", id="PHN-1", direction="in", since="2026-03-10")
    assert nb["node_ids"] == ["CUS-2", "PHN-1"]


def test_errors_come_back_as_text(run):
    assert "read-only" in call(run, "graph_query", cypher="MATCH (c) DELETE c")["error"]
    assert "error" in call(run, "graph_query", cypher="MATCH (c:Nope) RETURN c")
    assert (
        "may not write"
        in call(
            run,
            "graph_write_finding",
            text="x",
            confidence=0.5,
            edges=[{"type": "HAS_PHONE", "dst": "PHN-1"}],
        )["error"]
    )


def test_events_carry_graph_ids(run):
    call(
        run,
        "graph_query",
        cypher="MATCH (c:Customer {id: 'CUS-1'})-[r:HAS_PHONE]->(p) RETURN c, r, p",
    )
    events = run.emitter.events()
    assert [e.type for e in events] == ["tool_call", "tool_result"]
    result = events[1].payload
    assert result["caller"] == "graph_analyst" and result["tool"] == "graph_query"
    assert result["node_ids"] == ["CUS-1", "PHN-1"] and len(result["edge_ids"]) == 1
    assert result["call_id"] == events[0].payload["call_id"]


def test_write_finding_emits_graph_write(run):
    out = call(
        run,
        "graph_write_finding",
        text="Ann and Bob share a phone",
        kind="shared_phone",
        confidence=0.7,
        edges=[
            {"type": "SAME_ACTOR", "src": "CUS-1", "dst": "CUS-2"},
            {"type": "ABOUT", "dst": "CUS-1"},
        ],
    )
    assert out["finding_id"].startswith("FND-") and len(out["edge_ids"]) == 2
    types = [e.type for e in run.emitter.events()]
    assert types == ["tool_call", "graph_write", "tool_result"]
    dangling = call(
        run,
        "graph_write_finding",
        text="x",
        confidence=0.5,
        edges=[{"type": "ABOUT", "dst": "CUS-404"}],
    )
    assert "no such node" in dangling["error"]


def test_search_knowledge_policies_and_notes(run):
    call(
        run, "memory_write", op="write", text="Shop is a friendly-fraud hotspot", sources=["MER-1"]
    )
    out = call(run, "search_knowledge", query="provisional credit under Reg E")
    assert out["results"][0]["doc_id"] == "P1"
    notes = call(run, "search_knowledge", query="Shop friendly fraud", kinds=["memory_note"])
    assert notes["results"][0]["kind"] == "memory_note" and notes["node_ids"]


def test_memory_write_lifecycle(run):
    a = call(run, "memory_write", op="write", text="note a", sources=["MER-1"])["note_id"]
    b = call(run, "memory_write", op="supersede", text="note b", sources=["MER-1"], replaces=[a])

    def status(note_id):
        query = "MATCH (m:MemoryNote {id: $i}) RETURN m.status"
        return run.store.query(query, {"i": note_id})["rows"]

    assert status(a) == [["superseded"]] and status(b["note_id"]) == [["active"]]
    merged = call(
        run, "memory_write", op="merge", text="both", sources=["MER-1"], replaces=[a, b["note_id"]]
    )
    assert status(b["note_id"]) == [["merged"]] and merged["note_id"].startswith("MEM-")
    call(run, "memory_write", op="retract", sources=["MER-1"], replaces=[merged["note_id"]])
    assert status(merged["note_id"]) == [["retracted"]]
    assert (
        "at least one source"
        in call(run, "memory_write", op="write", text="x", sources=[])["error"]
    )
    assert "replaces" in call(run, "memory_write", op="retract", sources=["MER-1"])["error"]


def test_python_runs_and_restricts(run):
    out = call(
        run, "python", code="from decimal import Decimal\nprint(Decimal('1.10') + Decimal('2.20'))"
    )
    assert out["stdout"].strip() == "3.30"
    assert "ImportError" in call(run, "python", code="import os")["error"]
    assert "ZeroDivisionError" in call(run, "python", code="1/0")["error"]


def test_python_timeout(run, monkeypatch):
    monkeypatch.setattr("tools.PYTHON_TIMEOUT_SECONDS", 1)
    assert "timed out" in call(run, "python", code="while True: pass")["error"]


def test_long_text_is_clipped(run):
    run.store.conn.execute("MATCH (m:Merchant {id: 'MER-1'}) SET m.name = $n", {"n": "x" * 5000})
    out = call(run, "graph_query", cypher="MATCH (m:Merchant) RETURN m.name")
    assert out["rows"][0][0].endswith("[truncated]") and len(out["rows"][0][0]) < 1300
