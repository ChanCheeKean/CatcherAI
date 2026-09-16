from __future__ import annotations

from decimal import Decimal

from playbooks import novel_or_ambiguous


def test_decide_credits_the_cardholder_for_the_full_dispute_amount() -> None:
    """A case that matches no known route must still resolve cardholder-favorably:
    `decide()` starts from a `denied` placeholder proposal but always runs it through
    `governance.apply_conservative_default`, which is what actually sets the outcome and
    credit amount. This pins that the override, not the placeholder, wins."""

    state = {
        "case": {
            "case_id": "DSP-NOVEL-1",
            "regime": "reg_e",
            "dispute_amount": "482.17",
        }
    }
    decision = novel_or_ambiguous.decide(ctx=None, state=state)
    assert decision.cardholder_resolution.outcome.startswith("credited")
    assert decision.cardholder_resolution.credit_amount == Decimal("482.17")
