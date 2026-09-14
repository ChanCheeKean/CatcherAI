from __future__ import annotations

from collections import Counter
from decimal import Decimal

import pytest

from runtime.langgraph_runtime import LangGraphRuntime


def _assert_transparent(runtime: LangGraphRuntime) -> None:
    assert runtime.last_run_id
    emitter = runtime.emitter(runtime.last_run_id)
    events = emitter.events()
    counts = Counter(event.type for event in events)
    assert emitter.verify_chain()
    assert [event.seq for event in events] == list(range(1, len(events) + 1))
    assert counts["node_entered"] == counts["node_exited"]
    assert counts["tool_call"] == counts["tool_result"]
    assert counts["llm_call_started"] == counts["llm_call"] + counts["llm_call_failed"]
    assert counts["decision_recorded"] == 1
    decision = next(event for event in events if event.type == "decision_recorded")
    assert all(
        value["event_seqs"] and value["source_ids"]
        for value in decision.payload["field_provenance"].values()
    )


@pytest.mark.asyncio
async def test_c03_uses_as_of_policy_splits_transactions_and_supersedes_memory(
    runtime: LangGraphRuntime,
) -> None:
    decision = await runtime.run("DSP-2026-90003")

    assert decision.is_dispute is True
    assert decision.claim_family == "not_received"
    assert decision.split_case_required is True
    actions = {action.txn_id: action for action in decision.network_actions}
    assert actions["TXN-9000301"].action == "write_off_no_chargeback"
    assert actions["TXN-9000302"].action == "file_dispute"
    assert actions["TXN-9000302"].condition == "13.1"
    assert decision.cardholder_resolution.credit_amount == Decimal("32.48")

    events = runtime.emitter(runtime.last_run_id).events()  # type: ignore[arg-type]
    route = next(event for event in events if event.type == "route_decision")
    assert route.payload["chosen_route"] == "bundled_not_received_l2"
    retrieval = next(event for event in events if event.type == "retrieval")
    assert retrieval.payload["filters"]["as_of"] == "2026-10-20"
    assert "LFB-SOP-DSP-002@v4" in retrieval.payload["used_ids"]
    assert "LFB-SOP-DSP-002@v3" not in retrieval.payload["used_ids"]
    assert {
        "VISA-13.1@2026-04-18",
        "VISA-11.2-LIFECYCLE@2026-04-18",
    } <= set(retrieval.payload["used_ids"])
    types = {event.type for event in events}
    assert {
        "memory_read",
        "memory_rejected",
        "memory_supersede",
        "memory_write",
        "computation",
        "evidence_requested",
        "evidence_arrived",
        "termination",
    } <= types
    supersede = next(event for event in events if event.type == "memory_supersede")
    assert supersede.payload["target_id"] == "MEM-0150"
    assert supersede.payload["after"]["valid_to"] == "2026-06-30"
    assert all(check["pass"] for check in supersede.payload["write_gate_checks"])
    request = next(event for event in events if event.type == "evidence_requested")
    assert request.payload["target_txn_ids"] == ["TXN-9000302"]
    _assert_transparent(runtime)


@pytest.mark.asyncio
async def test_c06_verifier_replans_to_13_5_and_computes_unused_portion(
    runtime: LangGraphRuntime,
) -> None:
    decision = await runtime.run("DSP-2026-90007")

    assert decision.is_dispute is True
    assert decision.claim_family == "misrepresentation_trial"
    assert len(decision.network_actions) == 1
    action = decision.network_actions[0]
    assert action.condition == "13.5"
    assert action.amount == Decimal("118.24")
    assert decision.cardholder_resolution.reversal_amount == Decimal("1.64")

    events = runtime.emitter(runtime.last_run_id).events()  # type: ignore[arg-type]
    retrieval = next(event for event in events if event.type == "retrieval")
    assert {
        "VISA-13.2@2026-04-18",
        "VISA-13.5@2026-04-18",
        "VISA-5-RECURRING-MERCHANT-DUTIES@2026-04-18",
        "PRE-0012",
    } <= set(retrieval.payload["used_ids"])
    failed = [
        event
        for event in events
        if event.type == "verifier_check"
        and event.payload.get("check") == "13.2_cancellation_before_transaction"
    ]
    assert len(failed) == 1 and failed[0].payload["pass"] is False
    assert any(event.type == "contradiction_detected" for event in events)
    assert any(event.type == "plan_updated" for event in events)
    assert any(
        event.type == "edge_taken"
        and event.payload["from"] == "replan"
        and event.payload["to"] == "assess_progress"
        and event.payload["back_edge"] is True
        for event in events
    )
    computation = next(
        event
        for event in events
        if event.type == "computation" and event.payload["helper"] == "unused_portion"
    )
    assert computation.payload["output"]["days_used"] == 5
    assert computation.payload["output"]["days_unused"] == 360
    assert computation.payload["output"]["unused_portion"] == "118.24"
    supersede = next(
        event
        for event in events
        if event.type == "memory_supersede" and event.payload["target_id"] == "MEM-0160"
    )
    assert supersede.payload["after"]["valid_to"] == "2026-04-17"
    _assert_transparent(runtime)
