"""Repeated-run reliability and operational metrics for evaluation reports."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from domain.events import EventEnvelope


class RunObservation(BaseModel):
    case_id: str
    run_index: int
    passed: bool
    trajectory_complete: bool
    hash_chain_valid: bool
    replay_reconciled: bool
    outcome_hash: str
    event_count: int
    tool_calls: int
    model_calls: int
    replans: int
    waits: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float
    latency_ms: int
    capabilities: dict[str, bool] = Field(default_factory=dict)


class CaseReliability(BaseModel):
    case_id: str
    attempts: int
    passes: int
    pass_rate: float
    pass_pow_k: float
    all_k_passed: bool
    stable_outcome: bool
    trajectory_reconciliation_rate: float
    mean_events: float
    mean_tool_calls: float
    mean_model_calls: float
    mean_latency_ms: float
    total_cost_usd: float


def observe_run(
    *,
    case_id: str,
    run_index: int,
    passed: bool,
    trajectory_complete: bool,
    hash_chain_valid: bool,
    output: dict[str, Any] | list[dict[str, Any]],
    events: list[EventEnvelope],
    capabilities: dict[str, bool],
) -> RunObservation:
    """Capture one attempt without invoking a model or reading privileged fixtures."""

    canonical = json.dumps(output, sort_keys=True, separators=(",", ":"), default=str)
    counts: dict[str, int] = defaultdict(int)
    for event in events:
        counts[event.type] += 1
    decision_events = [event for event in events if event.type == "decision_recorded"]
    if case_id == "Q01":
        replay_reconciled = counts["portfolio_ranked"] == 1
    else:
        replay_reconciled = (
            len(decision_events) == 1 and decision_events[0].payload.get("record") == output
        )
    return RunObservation(
        case_id=case_id,
        run_index=run_index,
        passed=passed,
        trajectory_complete=trajectory_complete,
        hash_chain_valid=hash_chain_valid,
        replay_reconciled=replay_reconciled,
        outcome_hash=hashlib.sha256(canonical.encode()).hexdigest(),
        event_count=len(events),
        tool_calls=counts["tool_call"],
        model_calls=counts["llm_call"],
        replans=counts["plan_updated"],
        waits=counts["wait_suspended"],
        input_tokens=sum(event.usage.input_tokens for event in events),
        output_tokens=sum(event.usage.output_tokens for event in events),
        cached_tokens=sum(event.usage.cached_tokens for event in events),
        cost_usd=float(sum(event.usage.cost_usd for event in events)),
        latency_ms=sum(event.usage.latency_ms for event in events),
        capabilities=capabilities,
    )


def aggregate_reliability(observations: list[RunObservation]) -> list[CaseReliability]:
    """Report empirical pass rate and pass^k (the chance all k attempts pass)."""

    grouped: dict[str, list[RunObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.case_id].append(observation)
    rows: list[CaseReliability] = []
    for case_id, attempts in sorted(grouped.items()):
        count = len(attempts)
        passes = sum(item.passed for item in attempts)
        pass_rate = passes / count
        reconciled = sum(
            item.trajectory_complete and item.hash_chain_valid and item.replay_reconciled
            for item in attempts
        )
        rows.append(
            CaseReliability(
                case_id=case_id,
                attempts=count,
                passes=passes,
                pass_rate=pass_rate,
                pass_pow_k=pass_rate**count,
                all_k_passed=passes == count,
                stable_outcome=len({item.outcome_hash for item in attempts}) == 1,
                trajectory_reconciliation_rate=reconciled / count,
                mean_events=sum(item.event_count for item in attempts) / count,
                mean_tool_calls=sum(item.tool_calls for item in attempts) / count,
                mean_model_calls=sum(item.model_calls for item in attempts) / count,
                mean_latency_ms=sum(item.latency_ms for item in attempts) / count,
                total_cost_usd=sum(item.cost_usd for item in attempts),
            )
        )
    return rows


def capability_matrix(observations: list[RunObservation]) -> dict[str, dict[str, bool]]:
    """Return capability -> case -> all-attempts-pass."""

    matrix: dict[str, dict[str, bool]] = defaultdict(dict)
    grouped: dict[str, list[RunObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.case_id].append(observation)
    for case_id, attempts in sorted(grouped.items()):
        names = {name for attempt in attempts for name in attempt.capabilities}
        for name in sorted(names):
            matrix[name][case_id] = all(
                attempt.capabilities.get(name, False) for attempt in attempts
            )
    return dict(matrix)
