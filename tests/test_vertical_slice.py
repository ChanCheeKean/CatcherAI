from __future__ import annotations

from collections import Counter
from typing import Any

import pytest

from runtime.langgraph_runtime import LangGraphRuntime


def _leaf_paths(value: Any, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        return [
            path for key, item in value.items() for path in _leaf_paths(item, f"{prefix}/{key}")
        ]
    if isinstance(value, list):
        return [
            path
            for index, item in enumerate(value)
            for path in _leaf_paths(item, f"{prefix}/{index}")
        ] or [prefix]
    return [prefix or "/"]


def _assert_complete_trajectory(runtime: LangGraphRuntime) -> None:
    assert runtime.last_run_id
    emitter = runtime.emitter(runtime.last_run_id)
    events = emitter.events()
    assert emitter.verify_chain()
    assert [event.seq for event in events] == list(range(1, len(events) + 1))

    spans = {event.span_id for event in events}
    assert all(event.parent_span_id in spans for event in events if event.parent_span_id)

    counts = Counter(event.type for event in events)
    assert counts["node_entered"] == counts["node_exited"]
    assert counts["tool_call"] == counts["tool_result"]
    assert counts["llm_call_started"] == counts["llm_call"] + counts["llm_call_failed"]
    assert counts["edge_taken"] == counts["node_exited"] + 1

    calls = {event.payload["call_id"] for event in events if event.type == "tool_call"}
    results = {event.payload["call_id"] for event in events if event.type == "tool_result"}
    assert calls == results

    decision_event = next(event for event in events if event.type == "decision_recorded")
    record = decision_event.payload["record"]
    provenance = decision_event.payload["field_provenance"]
    assert set(_leaf_paths(record)) == set(provenance)
    assert all(item["event_seqs"] and item["source_ids"] for item in provenance.values())
    assert [event.type for event in events[-5:]] == [
        "termination",
        "run_completed",
        "node_exited",
        "edge_taken",
        "checkpoint_saved",
    ]
    assert events[-2].payload["to"] == "__end__"
    assert events[-1].refs == [events[-1].payload["checkpoint_id"]]


@pytest.mark.asyncio
async def test_c02_l1_descriptor_inquiry_stops_early(runtime: LangGraphRuntime) -> None:
    decision = await runtime.run("DSP-2026-90002")
    assert decision.is_dispute is False
    assert decision.claim_family == "descriptor_confusion"
    assert decision.network_actions == []
    assert decision.cardholder_resolution.outcome == "withdrawn_after_clarification"

    events = runtime.emitter(runtime.last_run_id).events()  # type: ignore[arg-type]
    types = {event.type for event in events}
    assert {
        "route_decision",
        "skill_loaded",
        "llm_call",
        "tool_call",
        "persona_reply",
        "guardrail_check",
        "automated_action",
        "memory_write_skipped",
        "termination",
    } <= types
    route = next(event for event in events if event.type == "route_decision")
    assert route.payload["chosen_route"] == "descriptor_confusion_l1"
    assert route.payload["depth"] == "L1"
    terminations = [event.payload["reason"] for event in events if event.type == "termination"]
    assert terminations == ["suspended_external_event", "l1_early_stop"]
    tool_budget = [
        event.payload
        for event in events
        if event.type == "budget_update" and event.payload["dimension"] == "tool_calls"
    ]
    assert tool_budget[-1]["used"] <= tool_budget[-1]["limit"] == 7
    _assert_complete_trajectory(runtime)


@pytest.mark.asyncio
async def test_c04_split_clearing_uses_clock_evidence_and_sandbox(
    runtime: LangGraphRuntime,
) -> None:
    decision = await runtime.run("DSP-2026-90005")
    assert decision.is_dispute is False
    assert decision.claim_family == "duplicate"
    assert decision.cardholder_resolution.outcome == "no_error_split_shipment"
    assert str(decision.cardholder_resolution.reversal_amount) == "64.18"

    events = runtime.emitter(runtime.last_run_id).events()  # type: ignore[arg-type]
    types = {event.type for event in events}
    assert {
        "computation",
        "evidence_requested",
        "evidence_arrived",
        "evidence_added",
        "clock_advanced",
        "untrusted_content_flagged",
        "persona_reply",
        "automated_action",
    } <= types
    computation = next(
        event
        for event in events
        if event.type == "computation" and event.payload["helper"] == "group_clearings"
    )
    assert computation.payload["output"]["is_split_clearing"] is True
    assert computation.payload["output"]["exceeds_authorization"] is False
    actions = [event.payload["action"] for event in events if event.type == "automated_action"]
    assert "reverse_provisional_credit" in actions
    _assert_complete_trajectory(runtime)
