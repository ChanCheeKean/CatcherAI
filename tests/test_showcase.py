import json
import sqlite3

from graph_builder import Graph

from domain.events import Actor, ActorKind, EventDraft, RuntimeSnapshot
from graph_store import GraphStore, load
from observability.emitter import EventEmitter
from runtime_entry import RuntimePaths
from showcase import export, install


def test_showcase_round_trip_restores_static_graph_and_events(tmp_path):
    generated = tmp_path / "source"
    graph = Graph()
    graph.node("CardMember", "CMB-TEST-1", name="Test Member")
    graph.write(generated / "graph")
    source_graph = generated / "evidence.lbug"
    load(generated / "graph", source_graph).close()
    (generated / "case_catalog.json").write_text(json.dumps([{"case_id": "DSP-TEST-1"}]))
    sqlite3.connect(generated / "knowledge.sqlite").close()
    (generated / "ground_truth").mkdir()
    (generated / "ground_truth" / "sample.json").write_text("{}")
    (generated / "eval" / "batch").mkdir(parents=True)
    passed = {"case_id": "DSP-TEST-1", "run_id": "run-test", "passed": True}
    (generated / "eval" / "batch" / "summary.json").write_text(
        json.dumps(
            {"cases": [{"code": "T", "pass_at_1": True, "pass_at_k": True, "runs": [passed]}]}
        )
    )
    source = RuntimePaths(
        source_graph=source_graph, trajectory_db=tmp_path / "source-events.sqlite"
    )
    for run_id, case_id in (
        ("run-test", "DSP-TEST-1"),
        ("run-newer-failed", "DSP-TEST-1"),
        ("run-retired-case", "DSP-OLD-1"),
    ):
        emitter = EventEmitter(
            source.trajectory_db,
            run_id=run_id,
            case_id=case_id,
            runtime=RuntimeSnapshot(
                config_hash="test", agent_runtime="test", provider="test", model="test"
            ),
        )
        emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.AGENT, name="adjudicator"),
                type="notebook_write",
                summary="Finding recorded",
                payload={"entry": {"node_ids": ["CMB-TEST-1"]}},
            )
        )
        emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.AGENT, name="adjudicator"),
                type="decision",
                summary="Decision made",
                payload={"report": {"verdict": "rejected"}},
            )
        )

    bundle = tmp_path / "showcase"
    assert export(source, bundle) == {"DSP-TEST-1": "run-test"}
    assert sorted(path.name for path in (bundle / "runs").iterdir()) == ["run-test.events.jsonl.gz"]
    assert not (bundle / "graph" / "runs").exists()

    restored = RuntimePaths(
        source_graph=tmp_path / "restored" / "evidence.lbug",
        trajectory_db=tmp_path / "restored-events.sqlite",
    )
    install(restored, bundle)
    store = GraphStore(restored.source_graph)
    try:
        assert store.node("CMB-TEST-1")["name"] == "Test Member"
    finally:
        store.close()
    with sqlite3.connect(restored.trajectory_db) as db:
        assert db.execute("SELECT type FROM run_events ORDER BY seq").fetchall() == [
            ("notebook_write",),
            ("decision",),
        ]
    install(restored, bundle)
    with sqlite3.connect(restored.trajectory_db) as db:
        assert db.execute("SELECT count(*) FROM run_events").fetchone()[0] == 2
