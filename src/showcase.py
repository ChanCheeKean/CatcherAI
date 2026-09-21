"""Committed showcase: the latest completed run of every case, restorable in a fresh clone.

`export` snapshots what the UI needs into `data/showcase/` (a few MB gzipped): the base evidence
graph as JSONL, the case catalog, ground truth and evaluation results, the knowledge store, and per
case the trajectory events plus what the agents added to that run's graph. `install` rebuilds
`data/generated/` and the trajectory store from it, so the UI shows every result without a rerun.
"""

from __future__ import annotations

import gzip
import json
import shutil
import sqlite3
from pathlib import Path

from graph_store import GraphStore, copy_store, load
from observability.emitter import init_event_db
from runtime_entry import RuntimePaths

SHOWCASE = Path("data/showcase")
ROW_CAP = 100_000
EVAL_BATCH = "0-showcase"  # sorts before timestamped batches, so a fresh eval takes over


def _write_gz(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt") as f:
        f.write(text)


def _read_gz(path: Path) -> str:
    with gzip.open(path, "rt") as f:
        return f.read()


def _latest_runs(paths: RuntimePaths) -> dict[str, str]:
    """Per case, the newest run that reached a decision and kept its graph copy."""
    with sqlite3.connect(paths.trajectory_db) as db:
        rows = db.execute(
            "SELECT case_id, run_id FROM run_events WHERE type = 'decision' ORDER BY ts_wall"
        ).fetchall()
    return {case: run for case, run in rows if (paths.run_dir / f"{run}.lbug").exists()}


def _clean(row: dict, drop: str) -> dict:
    return {k: v for k, v in row.items() if k != drop and v is not None}


def _added_to_graph(run_id: str, run_graph: Path, source: GraphStore) -> dict:
    """Nodes and edges the agents wrote in a run, and the memory notes they retired."""
    store = GraphStore(run_graph, read_only=True)
    nodes, edges = [], []
    for label, spec in store.ontology["nodes"].items():
        if "run_id" in spec["props"]:
            rows = store.query(
                f"MATCH (n:{label}) WHERE n.run_id = $r RETURN n", {"r": run_id}, ROW_CAP
            )["rows"]
            nodes += [{"label": label, **_clean(n, "_label")} for (n,) in rows]
    for etype, spec in store.ontology["edges"].items():
        if "run_id" in spec["props"]:
            rows = store.query(
                f"MATCH (a)-[r:{etype}]->(b) WHERE r.run_id = $r RETURN r, a.id, b.id",
                {"r": run_id},
                ROW_CAP,
            )["rows"]
            edges += [{"type": etype, "src": a, "dst": b, **_clean(r, "_type")} for r, a, b in rows]
    status = "MATCH (m:MemoryNote) RETURN m.id, m.status"
    before = dict(source.query(status, row_cap=ROW_CAP)["rows"])
    after = dict(store.query(status, row_cap=ROW_CAP)["rows"])
    store.close()
    return {
        "nodes": nodes,
        "edges": edges,
        "note_status": {i: s for i, s in after.items() if before.get(i, s) != s},
    }


def _apply(store: GraphStore, added: dict) -> None:
    for node in added["nodes"]:
        props = {k: v for k, v in node.items() if k != "label"}
        fields = ", ".join(f"{k}: ${k}" for k in props)
        store.conn.execute(f"CREATE (:{node['label']} {{{fields}}})", props)
    for edge in added["edges"]:
        props = {k: v for k, v in edge.items() if k not in {"type", "src", "dst"}}
        fields = ", ".join(f"{k}: ${k}" for k in props)
        store.conn.execute(
            f"MATCH (a:{store.label_of(edge['src'])} {{id: $src}}), "
            f"(b:{store.label_of(edge['dst'])} {{id: $dst}}) "
            f"CREATE (a)-[:{edge['type']} {{{fields}}}]->(b)",
            {**props, "src": edge["src"], "dst": edge["dst"]},
        )
    for note_id, status in added["note_status"].items():
        store.set_note_status(note_id, status)


def _merged_eval(eval_dir: Path) -> dict:
    """The newest completed evaluation of every case across all batches (crashed attempts skipped)."""
    latest: dict[str, dict] = {}
    for path in sorted(eval_dir.glob("*/summary.json")):
        for case in json.loads(path.read_text())["cases"]:
            if not any("error" in run for run in case["runs"]):
                latest[case["code"]] = case
    cases = list(latest.values())
    return {
        "k": 1,
        "pass_at_1": sum(c["pass_at_1"] for c in cases),
        "pass_at_k": sum(c["pass_at_k"] for c in cases),
        "cases": cases,
    }


def export(paths: RuntimePaths | None = None, out: Path = SHOWCASE) -> dict[str, str]:
    """Snapshot the latest completed run per case into `out`; returns case id to run id."""
    paths = paths or RuntimePaths()
    generated = paths.source_graph.parent
    shutil.rmtree(out, ignore_errors=True)
    (out / "graph").mkdir(parents=True)
    for name in ("nodes.jsonl", "edges.jsonl"):
        _write_gz(out / "graph" / f"{name}.gz", (generated / "graph" / name).read_text())
    shutil.copy2(generated / "graph" / "ontology.json", out / "graph" / "ontology.json")
    for name in ("case_catalog.json", "knowledge.sqlite"):
        shutil.copy2(generated / name, out / name)
    shutil.copytree(generated / "ground_truth", out / "ground_truth")
    (out / "eval.json").write_text(json.dumps(_merged_eval(generated / "eval")))

    runs = _latest_runs(paths)
    source = GraphStore(paths.source_graph, read_only=True)
    with sqlite3.connect(paths.trajectory_db) as db:
        db.row_factory = sqlite3.Row
        for run_id in runs.values():
            rows = db.execute("SELECT * FROM run_events WHERE run_id = ? ORDER BY seq", (run_id,))
            _write_gz(
                out / "runs" / f"{run_id}.events.jsonl.gz",
                "".join(json.dumps(dict(row)) + "\n" for row in rows),
            )
            added = _added_to_graph(run_id, paths.run_dir / f"{run_id}.lbug", source)
            (out / "runs" / f"{run_id}.graph.json").write_text(json.dumps(added))
    source.close()
    return runs


def _insert_events(db: sqlite3.Connection, run_id: str, jsonl: str) -> None:
    """Insert a run's events, unless the database already holds that run."""
    if db.execute("SELECT 1 FROM run_events WHERE run_id = ?", (run_id,)).fetchone():
        return
    rows = [json.loads(line) for line in jsonl.splitlines()]
    columns = ", ".join(rows[0])
    marks = ", ".join("?" for _ in rows[0])
    db.executemany(
        f"INSERT INTO run_events ({columns}) VALUES ({marks})", [list(r.values()) for r in rows]
    )


def install(paths: RuntimePaths | None = None, out: Path = SHOWCASE) -> None:
    """Rebuild whatever is missing under `data/generated/` and the trajectory store from `out`."""
    paths = paths or RuntimePaths()
    if not out.exists():
        return
    generated = paths.source_graph.parent
    if not paths.source_graph.exists():
        graph_dir = generated / "graph"
        graph_dir.mkdir(parents=True, exist_ok=True)
        for name in ("nodes.jsonl", "edges.jsonl"):
            (graph_dir / name).write_text(_read_gz(out / "graph" / f"{name}.gz"))
        shutil.copy2(out / "graph" / "ontology.json", graph_dir / "ontology.json")
        load(graph_dir, paths.source_graph).close()
    for name in ("case_catalog.json", "knowledge.sqlite"):
        if not (generated / name).exists():
            shutil.copy2(out / name, generated / name)
    if not (generated / "ground_truth").exists():
        shutil.copytree(out / "ground_truth", generated / "ground_truth")
    eval_summary = generated / "eval" / EVAL_BATCH / "summary.json"
    if not eval_summary.exists():
        eval_summary.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out / "eval.json", eval_summary)

    init_event_db(paths.trajectory_db)
    with sqlite3.connect(paths.trajectory_db) as db:
        for events in sorted((out / "runs").glob("*.events.jsonl.gz")):
            run_id = events.name.removesuffix(".events.jsonl.gz")
            _insert_events(db, run_id, _read_gz(events))
            run_graph = paths.run_dir / f"{run_id}.lbug"
            if not run_graph.exists():
                store = copy_store(paths.source_graph, run_graph)
                _apply(store, json.loads((out / "runs" / f"{run_id}.graph.json").read_text()))
                store.close()
