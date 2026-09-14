"""C02-style L1 route: an unrecognized descriptor that maps to a familiar merchant."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord
from runtime.context import RunContext

STEPS = ["ask_cardholder"]


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    merchant_id = state["transactions"][0]["merchant_id"]
    variants = ctx.call(
        "graph_descriptor_variants",
        "Traverse the descriptor-to-merchant identity relationship",
        {"merchant_id": merchant_id},
        lambda: ctx.graph.descriptors_for_merchant(merchant_id),
    )
    research = ctx.call(
        "search_research",
        "Verify the payment-facilitator descriptor mapping",
        {"merchant_id": merchant_id, "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.research_for_merchant(merchant_id),
    )
    intake = date.fromisoformat(state["case"]["opened_at"][:10])
    query = "LFB SOP DSP 001 pre-dispute descriptor clarification merchant recognition"
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve the pre-dispute clarification procedure effective at intake",
        {"query": query, "as_of": intake.isoformat(), "kinds": ["policy"]},
        lambda: ctx.knowledge.search(query, as_of=intake, kinds=("policy",), limit=8),
    )
    return {
        "findings": {
            "descriptor_variants": variants,
            "research": research,
            "merchant_name": state["transactions"][0]["merchant_name"],
        },
        "knowledge": knowledge,
    }


def cardholder_question(ctx: RunContext, state: dict[str, Any]) -> dict[str, str]:
    transaction = state["transactions"][0]
    merchant_name = state["findings"]["merchant_name"]
    return {
        "question": (
            f"The statement descriptor {transaction['descriptor']} maps to {merchant_name}, "
            "billed through a payment provider. Do you recognize it?"
        ),
        "rationale": "The answer can resolve the remaining claim-specific question",
    }


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, transaction = state["case"], state["transactions"][0]
    merchant_name = state["findings"]["merchant_name"]
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=False,
        claim_family="descriptor_confusion",
        network_actions=[],
        cardholder_resolution=CardholderResolution(
            outcome="withdrawn_after_clarification",
            credit_amount=Decimal("0"),
            reversal_amount=Decimal("0"),
            liability_amount=Decimal(transaction["billing_amount"]),
        ),
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.99,
            flip_fact="The descriptor mapping or cardholder recognition was incorrect.",
        ),
        citations=[{"doc_id": "LFB-SOP-DSP-001@v7", "why": "Pre-dispute descriptor clarification"}],
        confidence=0.99,
        explanation_for_cardholder=(
            f"The charge is {merchant_name}, shown as {transaction['descriptor']} on the "
            "statement. "
            "You recognized the merchant, so we closed the inquiry without filing a dispute."
        ),
    )
