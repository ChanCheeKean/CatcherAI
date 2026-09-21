"""Real-LLM evaluation: run cases, score each report against evaluator-only ground truth."""

from __future__ import annotations

import json
import re
import signal
import traceback
import uuid
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from domain.events import EventEnvelope
from graph_store import GraphStore
from replay import load_events
from runtime import RuntimePaths, run_case
from schemas import CaseReport

GROUND_TRUTH_DIR = Path("data/generated/ground_truth/cases")
EVAL_DIR = Path("data/generated/eval")
AMOUNT_TOLERANCE = 0.01
ATTEMPT_TIMEOUT_SECONDS = 900
_SIGNAL = re.compile(r"^([a-z]+(?:_[a-z]+)*)(?: \{(?:tool: )?([a-z_]+)?.*\})?$")


def load_truth(case_ids: list[str] | None = None) -> list[dict]:
    truths = [json.loads(p.read_text()) for p in sorted(GROUND_TRUTH_DIR.glob("*.json"))]
    if not case_ids:
        return truths
    wanted = set(case_ids)
    return [t for t in truths if t["case_id"] in wanted or t["code"] in wanted]


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _cited_ids(report: CaseReport) -> set[str]:
    links = [link for t in report.transactions for link in t.evidence]
    links += [link for h in report.hypotheses for link in h.evidence]
    ids = {i for link in links for i in (*link.node_ids, *link.edge_ids)}
    return ids | {t.txn_id for t in report.transactions}


def _trajectory_ids(events: list[EventEnvelope]) -> tuple[set[str], set[str]]:
    """Node ids the agents touched, and all node/edge ids seen (including ones agents wrote)."""
    nodes: set[str] = set()
    every: set[str] = set()
    for event in events:
        if event.type == "tool_result":
            nodes |= set(event.payload.get("node_ids", []))
            every |= nodes | set(event.payload.get("edge_ids", []))
    return nodes, every


def _existing(store: GraphStore, ids: set[str], seen: set[str]) -> set[str]:
    listed = sorted(ids - seen)
    found: set[str] = set()
    for query in (
        "MATCH (n) WHERE n.id IN $ids RETURN n.id",
        "MATCH ()-[r]->() WHERE r.id IN $ids RETURN r.id",
    ):
        found |= {row[0] for row in store.query(query, {"ids": listed}, row_cap=10_000)["rows"]}
    return found | (ids & seen)


def _decoy_ids(store: GraphStore, truth: dict) -> set[str]:
    ids: set[str] = set()
    for decoy in truth["decoy_patterns"]:
        ids |= set(store.query(decoy["cypher"], row_cap=10_000)["node_ids"])
    return ids - set(truth["solution_node_ids"])


def _signals(truth: dict, events: list[EventEnvelope]) -> dict[str, bool]:
    """Each measurable required-capability signal, and whether the trajectory shows it."""
    present = {e.type for e in events}
    tools = {e.payload.get("tool") for e in events if e.type == "tool_call"}
    out: dict[str, bool] = {}
    for capability in truth["required_capabilities"]:
        for sig in capability["trajectory_signals"]:
            match = _SIGNAL.match(sig)
            if not match:
                continue
            name, tool = match.groups()
            out[sig] = (tool in tools) if tool else (name in present or name in tools)
    return out


def score(truth: dict, report: CaseReport, events: list[EventEnvelope], store: GraphStore) -> dict:
    """Pure scoring of one report and its trajectory; nothing here influences the agent."""
    expected = {t["txn_id"]: t for t in truth["expected"]["transactions"]}
    actual = {t.txn_id: t for t in report.transactions}
    txns = {
        txn_id: {
            "verdict": txn_id in actual and actual[txn_id].verdict.value == want["verdict"],
            "credit": txn_id in actual
            and abs(float(actual[txn_id].credit_amount) - want["credit_amount"])
            <= AMOUNT_TOLERANCE,
        }
        for txn_id, want in expected.items()
    }
    solution = set(truth["solution_node_ids"])
    touched, seen = _trajectory_ids(events)
    cited = _cited_ids(report)
    report_text = report.model_dump_json()
    decoys = _decoy_ids(store, truth)
    action_text = [_tokens(f"{a.action} {a.reason}") for a in report.account_actions]
    wanted_actions = truth["expected"]["account_actions"]
    matched_actions = [w for w in wanted_actions if any(_tokens(w) <= t for t in action_text)]
    signals = _signals(truth, events)
    return {
        "verdict_ok": report.verdict.value == truth["expected"]["verdict"],
        "transactions": txns,
        "amounts_ok": all(v["verdict"] and v["credit"] for v in txns.values()),
        "account_actions": {"expected": wanted_actions, "matched": matched_actions},
        "solution_coverage": len(solution & touched) / len(solution),
        "grounding": {
            "cited": len(cited),
            "missing": sorted(cited - _existing(store, cited, seen)),
            "solution_cited": len(solution & cited) / len(solution),
            "decoys_named": sorted(i for i in decoys if i in report_text),
            "decoy_total": len(decoys),
        },
        "missing_evidence_handled": (not truth["missing_evidence"])
        or (report.verdict.value == truth["expected"]["verdict"] and bool(report.missing_evidence)),
        "capability_signals": signals,
        "confidence": report.confidence,
    }


def passed(result: dict) -> bool:
    return result["verdict_ok"] and result["amounts_ok"]


def _raise_timeout(*_: object) -> None:
    raise TimeoutError("attempt timed out")


def _attempt(truth: dict, attempt: int, batch: str, paths: RuntimePaths) -> dict:
    run_id = f"eval-{batch}-{truth['code']}-{attempt}"
    base = {
        "code": truth["code"],
        "case_id": truth["case_id"],
        "attempt": attempt,
        "run_id": run_id,
    }
    # A hung run becomes a scored failure whose traceback shows where it was stuck.
    signal.signal(
        signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("attempt timed out"))
    )
    signal.alarm(ATTEMPT_TIMEOUT_SECONDS)
    try:
        report = run_case(truth["case_id"], paths=paths, run_id=run_id)
    except Exception as error:  # a failed run is a scored failure, not an eval crash
        detail = f"{type(error).__name__}: {error}"
        if isinstance(error, TimeoutError):
            detail += "\n" + traceback.format_exc()
        return {**base, "error": detail, "passed": False}
    finally:
        signal.alarm(0)
    events = load_events(paths.trajectory_db.resolve(), run_id)
    store = GraphStore(paths.source_graph)
    try:
        result = score(truth, report, events, store)
    finally:
        store.close()
    return {**base, **result, "passed": passed(result), "report": report.model_dump(mode="json")}


def evaluate(
    truths: list[dict], k: int = 1, parallel: int = 3, paths: RuntimePaths | None = None
) -> dict[str, Any]:
    paths = paths or RuntimePaths()
    batch = uuid.uuid4().hex[:8]
    jobs = [(t, n) for t in truths for n in range(1, k + 1)]
    # One process per attempt: each LadybugDB database reserves a huge virtual address range.
    with ProcessPoolExecutor(max_workers=parallel) as pool:
        results = list(
            pool.map(_attempt, *zip(*jobs, strict=True), [batch] * len(jobs), [paths] * len(jobs))
        )
    cases = []
    for truth in truths:
        runs = [r for r in results if r["code"] == truth["code"]]
        scored = [r for r in runs if "error" not in r]
        cases.append(
            {
                "code": truth["code"],
                "title": truth["title"],
                "pass_at_1": runs[0]["passed"],
                "pass_at_k": any(r["passed"] for r in runs),
                "runs": runs,
                "mean_coverage": (
                    sum(r["solution_coverage"] for r in scored) / len(scored) if scored else 0.0
                ),
            }
        )
    return {
        "k": k,
        "pass_at_1": sum(c["pass_at_1"] for c in cases),
        "pass_at_k": sum(c["pass_at_k"] for c in cases),
        "cases": cases,
        "mean_coverage": sum(c["mean_coverage"] for c in cases) / len(cases),
    }


def write_summary(summary: dict, out_dir: Path = EVAL_DIR) -> Path:
    out = out_dir / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    lines = [
        f"# Evaluation (k={summary['k']})",
        "",
        f"pass@1 {summary['pass_at_1']}/{len(summary['cases'])} · "
        f"pass@{summary['k']} {summary['pass_at_k']}/{len(summary['cases'])} · "
        f"mean solution coverage {summary['mean_coverage']:.2f}",
        "",
        "| case | pass | verdict | amounts | coverage | cited | decoys named | missing ev. |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for case in summary["cases"]:
        for run in case["runs"]:
            if "error" in run:
                lines.append(f"| {case['code']} | ERROR | {run['error'][:80]} | | | | | |")
                continue
            g = run["grounding"]
            lines.append(
                f"| {case['code']} | {'✓' if run['passed'] else '✗'} | "
                f"{'✓' if run['verdict_ok'] else '✗'} | {'✓' if run['amounts_ok'] else '✗'} | "
                f"{run['solution_coverage']:.2f} | {g['solution_cited']:.2f} | "
                f"{len(g['decoys_named'])}/{g['decoy_total']} | "
                f"{'✓' if run['missing_evidence_handled'] else '✗'} |"
            )
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    return out
