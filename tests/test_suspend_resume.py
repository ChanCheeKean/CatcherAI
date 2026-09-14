from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

import pytest

from harness.evidence import EvidenceSchedulerAccess
from runtime.langgraph_runtime import RunSuspended


async def test_c13_suspends_on_provider_record_and_resumes_in_a_fresh_runtime(make_runtime) -> None:  # type: ignore[no-untyped-def]
    first = make_runtime()
    run_id = await first.start("DSP-2026-90015", auto_resume=False)
    with pytest.raises(RunSuspended) as suspended:
        await first.result(run_id)
    assert suspended.value.wait["awaited_ref"] == "MEP-90015-APP"
    assert suspended.value.wait["latest_safe_decision_date"] == "2026-12-30"
    prefix = first.emitter(run_id).events()
    assert [event.type for event in prefix[-3:]] == [
        "wait_suspended",
        "termination",
        "checkpoint_saved",
    ]
    assert prefix[-2].payload["reason"] == "suspended_external_event"
    assert prefix[-1].payload["status"] == "suspended"
    assert not any(event.type in {"decision_recorded", "evidence_arrived"} for event in prefix)

    second = make_runtime()
    decision = await second.resume(run_id)
    assert decision.network_actions[0].action == "no_dispute"
    assert decision.wait and decision.wait["resolution"] == "arrived"

    emitter = second.emitter(run_id)
    events = emitter.events()
    assert emitter.verify_chain()
    assert [event.seq for event in events] == list(range(1, len(events) + 1))
    counts = Counter(event.type for event in events)
    assert counts["evidence_requested"] == 1, "side effects before the interrupt must not repeat"
    assert counts["node_entered"] == counts["node_exited"]
    assert counts["tool_call"] == counts["tool_result"]
    resumed = next(event for event in events if event.type == "wait_resumed")
    assert resumed.payload["clock_before"].startswith("2026-10-21")
    assert resumed.payload["clock_after"].startswith("2026-10-23T15:00")
    assert resumed.payload["checkpoint_id"] == prefix[-1].payload["checkpoint_id"]
    assert {"checkpoint_restored", "clock_advanced", "evidence_arrived"} <= set(counts)
    terminations = [event.payload["reason"] for event in events if event.type == "termination"]
    assert terminations == ["suspended_external_event", "decision_complete_verifier_passed"]
    assert events[-1].type == "checkpoint_saved"


async def test_missing_provider_record_decides_conservatively_at_latest_safe_time(
    runtime,
    monkeypatch: pytest.MonkeyPatch,  # type: ignore[no-untyped-def]
) -> None:
    original = EvidenceSchedulerAccess.next_evidence

    def late(self: EvidenceSchedulerAccess, case_id: str):  # type: ignore[no-untyped-def]
        row = original(self, case_id)
        return row and {**row, "available_at": "2027-02-01T15:00:00Z"}

    monkeypatch.setattr(EvidenceSchedulerAccess, "next_evidence", late)
    decision = await runtime.run("DSP-2026-90015")

    assert decision.adjudication.review_panel_used is True
    assert decision.adjudication.conservative_default_applied is True
    assert decision.adjudication.confidence < 0.75
    assert decision.cardholder_resolution.outcome == "credited_conservative_default"
    assert str(decision.cardholder_resolution.credit_amount) == "412.60"
    assert [action.action for action in decision.network_actions] == ["no_dispute"]
    events = runtime.emitter(runtime.last_run_id).events()
    resumed = next(event for event in events if event.type == "wait_resumed")
    assert resumed.payload["resolution"] == "latest_safe_time_reached"
    assert events[-1].ts_virtual == datetime(2026, 12, 30, tzinfo=UTC)
    assert not any(event.type == "evidence_arrived" for event in events)
    assert any(event.type == "conservative_default_applied" for event in events)
    termination = [event for event in events if event.type == "termination"][-1]
    assert termination.payload["reason"] == "conservative_default_decided"


async def test_c15_fans_out_independent_tracks_after_the_cardholder_reply(runtime) -> None:  # type: ignore[no-untyped-def]
    decision = await runtime.run("DSP-2026-90017")
    actions = {action.case_id: action for action in decision.network_actions}
    assert actions["DSP-2026-90017"].action == "accept_dispute_response"
    assert actions["DSP-2026-90018"].condition == "13.2"
    assert decision.deadlines["DSP-2026-90017"]["pre_arb_deadline"] == "2026-11-15"
    assert decision.deadlines["DSP-2026-90018"]["reg_z_resolution_deadline"] == "2027-01-05"

    events = runtime.emitter(runtime.last_run_id).events()
    branches = {
        event.payload["branch_id"]
        for event in events
        if event.type == "edge_taken" and event.payload["to"] == "analyze_track"
    }
    assert branches == {"track-DSP-2026-90017", "track-DSP-2026-90018"}
    order = [event.type for event in events]
    assert (
        order.index("persona_reply")
        < order.index("wait_resumed")
        < [index for index, event in enumerate(events) if event.actor.name == "analyze_track"][0]
    )
    message = next(event for event in events if event.type == "persona_message")
    assert message.payload["channel"] == "email"
    assert any(
        event.type == "memory_consolidate" and event.payload["operation"] == "dedupe"
        for event in events
    )


async def test_c09_reroutes_after_evidence_review_and_selects_ce3_version(runtime) -> None:  # type: ignore[no-untyped-def]
    decision = await runtime.run("DSP-2026-90010")
    assert decision.ce3_analysis["qualifies_old"] is False
    assert decision.ce3_analysis["qualifies_new"] is True
    assert decision.ce3_analysis["projected_processing_date"] == "2026-10-26"
    events = runtime.emitter(runtime.last_run_id).events()
    routes = [event.payload["chosen_route"] for event in events if event.type == "route_decision"]
    assert routes == ["cnp_fraud_ce3_digital_l3", "quality_complaint_merchant_first"]
    retrievals = [
        event.payload["filters"]["as_of"] for event in events if event.type == "retrieval"
    ]
    assert retrievals == ["2026-10-20", "2026-10-26"]
    writes = [e for e in events if e.type == "memory_write" and "content" in e.payload]
    assert writes and all("fraudster" not in event.payload["content"] for event in writes)


async def test_c17_value_of_information_stop_still_redirects(runtime) -> None:  # type: ignore[no-untyped-def]
    decision = await runtime.run("DSP-2026-90020")
    assert decision.cardholder_resolution.redirect == {
        "resource": "WEB-04205",
        "deadline": "2026-12-31",
    }
    events = runtime.emitter(runtime.last_run_id).events()
    assert not any(event.type in {"evidence_requested", "persona_message"} for event in events)
    assert [e.payload["reason"] for e in events if e.type == "termination"] == [
        "value_of_information_stop"
    ]
