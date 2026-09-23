import json

import pytest
from graph_builder import Graph

from domain.events import RuntimeSnapshot
from graph_store import GraphStore, load
from memory import retrieval
from observability.emitter import EventEmitter
from tools import READ_ONLY_TOOLS, Run, make_tools


@pytest.fixture
def kit(tmp_path):
    graph = Graph()
    graph.node("CardMember", "CMB-1", name="Ann")
    graph.node("CardAccount", "ACC-1", product="Gold")
    graph.node("Card", "CRD-1", product="Gold")
    graph.node("Merchant", "MER-1", name="Shop")
    graph.node("Order", "ORD-1", summary="Sofa")
    graph.node("Charge", "CHG-1", amount=40.0)
    graph.node("PolicyDocument", "POL-1", title="Return policy")
    graph.node("Clause", "CLS-1", text="Custom sofas are final sale")
    graph.edge("HOLDS", "CMB-1", "ACC-1", role="basic")
    graph.edge("ISSUED_ON", "CRD-1", "ACC-1")
    graph.edge("CHARGED_TO", "CHG-1", "CRD-1")
    graph.edge("AT_MERCHANT", "CHG-1", "MER-1")
    edge_id = graph.edge("HAS_CLAUSE", "POL-1", "CLS-1")
    graph.write(tmp_path / "jsonl")
    path = tmp_path / "evidence.lbug"
    load(tmp_path / "jsonl", path).close()
    knowledge = tmp_path / "knowledge.sqlite"
    retrieval.build(
        knowledge,
        [
            {
                "doc_id": "CLS-1",
                "kind": "policy",
                "title": "Return policy",
                "body": "Custom sofas are final sale",
            }
        ],
    )
    emitter = EventEmitter(
        tmp_path / "events.sqlite",
        run_id="run-1",
        case_id=None,
        runtime=RuntimeSnapshot(
            config_hash="x",
            agent_runtime="test",
            provider="test",
            model="test",
            adapter_versions={},
        ),
    )
    store = GraphStore(path)
    run = Run(store, emitter, "run-1", knowledge, tmp_path / "notebook.sqlite", actor="analyst")
    tools = {tool.name: tool for tool in make_tools(run)}
    yield tools, emitter, edge_id, run
    store.close()


def call(tools, name, **kwargs):
    return json.loads(tools[name].invoke(kwargs))


def test_tool_order_find_and_read_only_set(kit):
    tools, _, _, _ = kit
    assert list(tools) == [
        "graph_schema",
        "graph_query",
        "graph_neighbors",
        "graph_find",
        "search_knowledge",
        "notebook_write",
        "notebook_read",
        "memory_write",
        "python",
    ]
    assert READ_ONLY_TOOLS == set(tools) - {"notebook_write", "memory_write", "python"}
    assert "CLS-1" in call(tools, "graph_find", text="FINAL SALE")["node_ids"]
    assert "CLS-1" in call(tools, "search_knowledge", query="final sale")["node_ids"]


def test_notebook_validates_citations_and_emits(kit):
    tools, emitter, edge_id, _ = kit
    out = call(
        tools,
        "notebook_write",
        kind="fact",
        text="The clause applies",
        node_ids=["CLS-1"],
        edge_ids=[edge_id],
    )
    assert out["node_ids"] == ["CLS-1"]
    assert call(tools, "notebook_read")["entries"][0]["entry_id"] == out["entry_id"]
    assert any(
        e.type == "notebook_write" and e.refs == ["CLS-1", edge_id] for e in emitter.events()
    )
    assert "error" in call(tools, "notebook_write", kind="fact", text="False", node_ids=["CLS-X"])
    assert "error" in call(tools, "notebook_write", kind="fact", text="False", edge_ids=["E-X"])
    assert len(call(tools, "notebook_read")["entries"]) == 1


def test_memory_lifecycle_and_python(kit):
    tools, _, _, _ = kit
    note = call(
        tools, "memory_write", op="write", text="Custom sofas are final sale", sources=["CLS-1"]
    )
    hits = call(tools, "search_knowledge", query="custom sofas", kinds=["memory_note"])["results"]
    assert note["note_id"] in [hit["doc_id"] for hit in hits]
    call(tools, "memory_write", op="retract", sources=["CLS-1"], replaces=[note["note_id"]])
    assert (
        call(tools, "search_knowledge", query="custom sofas", kinds=["memory_note"])["results"]
        == []
    )
    assert call(tools, "python", code="print(2 + 3)")["stdout"] == "5\n"
