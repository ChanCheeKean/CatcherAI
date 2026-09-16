"""Fallback route for cases that don't clearly fit any other category."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import governance
from domain.case import Adjudication, CardholderResolution, DecisionRecord
from runtime.context import RunContext

STEPS: list[str] = []


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """No route-specific investigation for an unclassifiable case."""
    return {}


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    """Conservative, cardholder-favorable default: file nothing uncertain, absorb the loss."""
    case = state["case"]
    amount = Decimal(str(case.get("dispute_amount") or "0"))
    proposal = DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=True,
        claim_family="unknown",
        network_actions=[],
        cardholder_resolution=CardholderResolution(
            outcome="denied",
            credit_amount=Decimal("0"),
            reversal_amount=Decimal("0"),
            liability_amount=Decimal("0"),
        ),
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.0,
            flip_fact="Case did not match any known dispute category.",
        ),
        citations=[],
        confidence=0.0,
        explanation_for_cardholder="Placeholder; will be overwritten by conservative default.",
    )
    return governance.apply_conservative_default(
        proposal,
        disputed_amount=amount,
        reason="case did not match any known dispute category",
    )
