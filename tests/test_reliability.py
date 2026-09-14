from __future__ import annotations

from evaluation.reliability import (
    RunObservation,
    aggregate_reliability,
    capability_matrix,
)


def _observation(run_index: int, *, passed: bool = True, outcome: str = "same") -> RunObservation:
    return RunObservation(
        case_id="DSP-TEST",
        run_index=run_index,
        passed=passed,
        trajectory_complete=True,
        hash_chain_valid=True,
        replay_reconciled=True,
        outcome_hash=outcome,
        event_count=10,
        tool_calls=2,
        model_calls=1,
        replans=0,
        waits=0,
        input_tokens=5,
        output_tokens=3,
        cached_tokens=0,
        cost_usd=0.01,
        latency_ms=20,
        capabilities={"Router": passed},
    )


def test_reliability_reports_pass_pow_k_and_outcome_stability() -> None:
    rows = aggregate_reliability(
        [_observation(1), _observation(2), _observation(3, passed=False, outcome="changed")]
    )
    assert len(rows) == 1
    result = rows[0]
    assert result.pass_rate == 2 / 3
    assert result.pass_pow_k == (2 / 3) ** 3
    assert not result.all_k_passed
    assert not result.stable_outcome
    assert result.trajectory_reconciliation_rate == 1
    assert capability_matrix([_observation(1), _observation(2, passed=False)]) == {
        "Router": {"DSP-TEST": False}
    }
