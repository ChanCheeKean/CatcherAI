"""Export and install the static graph, case data, knowledge store and run events."""

from __future__ import annotations

import gzip
import json
import shutil
import sqlite3
from pathlib import Path

from graph_store import load
from observability.emitter import init_event_db
from runtime_entry import RuntimePaths

SHOWCASE = Path("data/showcase")
EVAL_BATCH = "0-showcase"  # sorts before timestamped batches, so a fresh eval takes over


def _write_gz(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt") as f:
        f.write(text)


def _read_gz(path: Path) -> str:
    with gzip.open(path, "rt") as f:
        return f.read()


def _showcase_runs(paths: RuntimePaths, eval_dir: Path, cases: set[str]) -> dict[str, str]:
    """Per catalog case, the newest decided run that passed evaluation, else the newest one."""
    with sqlite3.connect(paths.trajectory_db) as db:
        rows = db.execute(
            "SELECT case_id, run_id FROM run_events WHERE type = 'decision' ORDER BY ts_wall"
        ).fetchall()
    rows = [(case, run) for case, run in rows if case in cases]
    runs = {case: run for case, run in rows}
    decided = {run for _, run in rows}
    for path in sorted(eval_dir.glob("*/summary.json")):
        for case in json.loads(path.read_text())["cases"]:
            for run in case["runs"]:
                if run["passed"] and run["run_id"] in decided:
                    runs[run["case_id"]] = run["run_id"]
    return runs


def _merged_eval(eval_dir: Path, cases: set[str]) -> dict:
    """The newest completed evaluation of every catalog case (crashed attempts skipped)."""
    latest: dict[str, dict] = {}
    for path in sorted(eval_dir.glob("*/summary.json")):
        for case in json.loads(path.read_text())["cases"]:
            runs = case["runs"]
            if runs[0]["case_id"] in cases and not any("error" in run for run in runs):
                latest[case["code"]] = case
    cases = list(latest.values())
    return {
        "k": 1,
        "pass_at_1": sum(c["pass_at_1"] for c in cases),
        "pass_at_k": sum(c["pass_at_k"] for c in cases),
        "cases": cases,
    }


def export(paths: RuntimePaths | None = None, out: Path = SHOWCASE) -> dict[str, str]:
    """Snapshot one completed run per case into `out`; returns case id to run id."""
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
    cases = {case["case_id"] for case in json.loads((generated / "case_catalog.json").read_text())}
    (out / "eval.json").write_text(json.dumps(_merged_eval(generated / "eval", cases)))

    runs = _showcase_runs(paths, generated / "eval", cases)
    with sqlite3.connect(paths.trajectory_db) as db:
        db.row_factory = sqlite3.Row
        for run_id in runs.values():
            rows = db.execute("SELECT * FROM run_events WHERE run_id = ? ORDER BY seq", (run_id,))
            _write_gz(
                out / "runs" / f"{run_id}.events.jsonl.gz",
                "".join(json.dumps(dict(row)) + "\n" for row in rows),
            )
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
