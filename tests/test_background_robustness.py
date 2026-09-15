from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "case_id",
    [
        "DSP-2026-00047",
        "DSP-2026-00069",
        "DSP-2026-00103",
        "DSP-2026-00166",
        "DSP-2026-00016",
        "DSP-2026-00169",
        "DSP-2026-00231",
    ],
)
async def test_background_case_without_packet_decides_conservatively(runtime, case_id: str) -> None:  # type: ignore[no-untyped-def]
    decision = await runtime.run(case_id)

    assert decision.claim_family == "insufficient_required_evidence"
    assert decision.cardholder_resolution.outcome == "credited_conservative_default"
    assert decision.adjudication.review_panel_used is True
    assert decision.adjudication.conservative_default_applied is True
    assert [action.action for action in decision.network_actions] == ["no_dispute"]

    events = runtime.emitter(runtime.last_run_id).events()
    assert any(event.type == "evidence_unavailable" for event in events)
    assert any(event.type == "conservative_default_applied" for event in events)
    assert not any(event.type == "persona_message" for event in events)
    assert not any(event.type == "error" for event in events)
    assert runtime.emitter(runtime.last_run_id).verify_chain() is True
