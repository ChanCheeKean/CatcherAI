from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.evaluator import GroundTruthEvaluator
from runtime.langgraph_runtime import LangGraphRuntime


@pytest.mark.parametrize(
    "case_id",
    [
        "DSP-2026-90002",
        "DSP-2026-90003",
        "DSP-2026-90005",
        "DSP-2026-90007",
        "DSP-2026-90009",
        "DSP-2026-90012",
        "DSP-2026-90013",
        "DSP-2026-90014",
        "DSP-2026-90011",
        "DSP-2026-90015",
        "DSP-2026-90017",
        "DSP-2026-90022",
        "DSP-2026-90001",
        "DSP-2026-90006",
        "DSP-2026-90008",
        "DSP-2026-90010",
        "DSP-2026-90016",
        "DSP-2026-90019",
        "DSP-2026-90020",
        "DSP-2026-90021",
    ],
)
async def test_vertical_slice_passes_ground_truth_and_capability_eval(
    runtime: LangGraphRuntime, project_root: Path, case_id: str
) -> None:
    decision = await runtime.run(case_id)
    assert runtime.last_run_id
    emitter = runtime.emitter(runtime.last_run_id)
    evaluator = GroundTruthEvaluator(project_root / "data/generated/ground_truth")
    result = evaluator.evaluate(decision, emitter.events(), emitter)
    assert result.passed, result.model_dump_json(indent=2)
    assert result.trajectory_complete
    assert all(check.passed for check in result.deterministic)
    assert all(check.passed and check.actual for check in result.capabilities)


async def test_q01_portfolio_queue_matches_deadline_ranking(
    runtime: LangGraphRuntime, project_root: Path
) -> None:
    from collections import Counter

    from runtime.portfolio import rank_portfolio

    run_id, ranking = await rank_portfolio(runtime)
    emitter = runtime.emitter(run_id)
    events = emitter.events()
    evaluator = GroundTruthEvaluator(project_root / "data/generated/ground_truth")
    result = evaluator.evaluate_queue(ranking, events, emitter)
    assert result.passed, result.model_dump_json(indent=2)
    counts = Counter(event.type for event in events)
    clock_calls = [
        e
        for e in events
        if e.type == "tool_call" and e.payload["tool"] == "compute_portfolio_clocks"
    ]
    assert counts["computation"] == len(ranking) == len(clock_calls)
    fan_out = [e for e in events if e.type == "edge_taken" and e.payload["to"] == "case_clock"]
    assert len(fan_out) == len(ranking)
    assert counts["subagent_started"] == 15
