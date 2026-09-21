from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

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

from graph_store import GraphStore
from replay import load_events
from runtime import RuntimePaths, run_case
from schemas import SupervisorTurn, Triage
from showcase import export, install


def test_export_then_install_restores_run_and_agent_written_graph(
    runtime_paths: RuntimePaths,  # noqa: F811
    tmp_path: Path,
) -> None:
    generated = runtime_paths.source_graph.parent
    shutil.copytree(tmp_path / "jsonl", generated / "graph")
    (generated / "case_catalog.json").write_text(json.dumps([{"case_id": CASE_ID}]))
    (generated / "ground_truth").mkdir()
    (generated / "eval" / "batch").mkdir(parents=True)
    (generated / "eval" / "batch" / "summary.json").write_text(
        json.dumps(
            {"k": 1, "cases": [{"code": "C00", "pass_at_1": True, "pass_at_k": True, "runs": [{}]}]}
        )
    )

    run_id = "run-showcase"
    run_case(
        CASE_ID,
        paths=runtime_paths,
        run_id=run_id,
        model=StructuredModel(
            {Triage: [triage()], SupervisorTurn: [delegate_turn(), decide_turn(close_plan=True)]}
        ),
        agent_builder=AgentBuilder(
            {
                "graph_analyst": finding("Identity path checked.", "CUS-TEST-1"),
                "evidence_analyst": finding("Transaction checked.", TXN_ID),
            },
            report(),
        ),
    )
    store = GraphStore(runtime_paths.run_dir / f"{run_id}.lbug")
    written = store.write_finding(
        "Agent finding", run_id, 0.9, edges=[{"type": "SUPPORTS", "dst": TXN_ID}]
    )
    store.close()

    showcase = tmp_path / "showcase"
    assert export(runtime_paths, showcase) == {CASE_ID: run_id}

    fresh = replace(
        runtime_paths,
        source_graph=tmp_path / "fresh" / "evidence.lbug",
        run_dir=tmp_path / "fresh" / "runs",
        trajectory_db=tmp_path / "fresh" / "trajectory.sqlite",
    )
    fresh.source_graph.parent.mkdir()
    install(fresh, showcase)
    install(fresh, showcase)  # idempotent

    original = load_events(runtime_paths.trajectory_db, run_id)
    assert [e.seq for e in load_events(fresh.trajectory_db, run_id)] == [e.seq for e in original]
    restored = GraphStore(fresh.run_dir / f"{run_id}.lbug", read_only=True)
    found = restored.query(
        "MATCH (f:Finding {id: $id})-[r]->(t:Transaction) RETURN r.id, t.id",
        {"id": written["finding_id"]},
    )["rows"]
    restored.close()
    assert found == [[written["edge_ids"][0], TXN_ID]]
    assert (fresh.source_graph.parent / "eval" / "0-showcase" / "summary.json").exists()
