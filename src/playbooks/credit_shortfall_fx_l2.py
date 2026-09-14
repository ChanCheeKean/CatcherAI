"""C07-style route: a refund that looks short in USD because the exchange rate moved.

The sandbox proves the merchant refunded the full transaction-currency amount, so there is no
network dispute and no billing error; the issuer's own fee SOP still gives the cardholder a remedy.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from domain.events import ActorKind
from runtime.context import RunContext, check
from sandbox import fx_refund_breakdown

QUERY = (
    "VISA 11.4 currency conversion credits VISA 13.6 credit not processed LFB SOP DSP 007 foreign "
    "transaction fee reversal LFB CARDHOLDER AGREEMENT foreign transactions"
)
REQUIRED = {
    "VISA-11.4-AMOUNTS-CREDITS-FX@2026-04-18",
    "VISA-13.6@2026-04-18",
    "LFB-SOP-DSP-007@v2",
    "LFB-CARDHOLDER-AGREEMENT@2025-01",
}
FEE_RATE = Decimal("0.03")
REVERSAL_WINDOW_DAYS = 180


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case, refund = state["case"], state["transactions"][0]
    notice = date.fromisoformat(case["opened_at"][:10])
    linked = ctx.call(
        "get_linked_transactions",
        "Find the purchase and fee linked to the disputed credit",
        {"txn_ids": [refund["related_txn_id"] or refund["txn_id"]]},
        lambda: ctx.data.related_transactions([refund["related_txn_id"] or refund["txn_id"]]),
    )
    purchase = next(row for row in linked if row["txn_type"] == "purchase")
    fee = next((row for row in linked if row["txn_type"] == "fee"), None)
    rates = ctx.call(
        "get_fx_rates",
        "Check the network reference rates for purchase and refund dates",
        {"dates": [purchase["txn_local_datetime"][:10], refund["txn_local_datetime"][:10]]},
        lambda: ctx.data.fx_rates(
            [purchase["txn_local_datetime"][:10], refund["txn_local_datetime"][:10]]
        ),
    )
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve FX, credit, fee-reversal and agreement terms as of notice",
        {"query": QUERY, "as_of": notice.isoformat(), "kinds": ["policy"]},
        lambda: ctx.knowledge.search(QUERY, as_of=notice, kinds=("policy",), limit=12),
    )
    breakdown = ctx.call(
        "compute_fx_refund",
        "Recompute both conversions and the fee-reversal rule in the sandbox",
        {
            "purchase_txn_id": purchase["txn_id"],
            "refund_txn_id": refund["txn_id"],
            "fee_rate": float(FEE_RATE),
            "reversal_window_days": REVERSAL_WINDOW_DAYS,
        },
        lambda: fx_refund_breakdown(
            purchase=purchase,
            refund=refund,
            fee=fee,
            fee_rate=FEE_RATE,
            reversal_window_days=REVERSAL_WINDOW_DAYS,
            refs=[purchase["txn_id"], refund["txn_id"], "LFB-SOP-DSP-007@v2"],
            emitter=ctx.emitter,
        ),
    )
    refund_match = "refund {amount} {currency} equals purchase".format(
        amount=refund["txn_amount"], currency=refund["txn_currency"]
    )
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "contradiction_detected",
        "The 'short refund' is exchange-rate movement, not a partial merchant credit",
        {
            "facts": [
                {"statement": "cardholder: merchant refunded less", "source": case["case_id"]},
                {
                    "statement": refund_match,
                    "source": refund["txn_id"],
                },
            ],
            "resolution": "rate moved from purchase to refund date",
            "impact": "no billing error",
        },
        [case["case_id"], refund["txn_id"], purchase["txn_id"]],
    )
    return {
        "knowledge": knowledge,
        "findings": {"purchase": purchase, "fee": fee, "rates": rates, "fx": breakdown},
    }


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings, refund = state["findings"], state["transactions"][0]
    fx, purchase = findings["fx"], findings["purchase"]
    rates = {row["date"]: row["eur_usd"] for row in findings["rates"]}
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    return [
        check(
            "fx_sources_retrieved",
            REQUIRED <= doc_ids,
            {"required": sorted(REQUIRED)},
            sorted(REQUIRED),
        ),
        check(
            "refund_complete_in_transaction_currency",
            fx["transaction_currency_refund_complete"],
            fx,
            [purchase["txn_id"], refund["txn_id"]],
        ),
        check(
            "rates_match_network_reference",
            rates.get(purchase["txn_local_datetime"][:10]) == purchase["fx_rate"]
            and rates.get(refund["txn_local_datetime"][:10]) == refund["fx_rate"],
            rates,
            list(rates),
        ),
        check(
            "credit_posted_before_notice",
            refund["processing_date"] < state["case"]["opened_at"][:10],
            {"credit": refund["processing_date"], "notice": state["case"]["opened_at"][:10]},
            [refund["txn_id"]],
        ),
        check(
            "fee_matches_agreement_rate",
            fx["fee_expected"] == fx["fee_charged"],
            fx,
            [findings["fee"]["txn_id"]] if findings["fee"] else [],
        ),
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, refund, fx = state["case"], state["transactions"][0], state["findings"]["fx"]
    fee = Decimal(fx["fee_reversal_amount"])
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=False,
        claim_family="credit_shortfall_fx",
        network_actions=[
            NetworkAction(
                txn_id=refund["txn_id"],
                case_id=case["case_id"],
                action="no_dispute",
                amount=Decimal(refund["billing_amount"]),
                reason="merchant credit issued in full in transaction currency before any dispute",
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome="no_error_fx_explained_fee_reversed",
            credit_amount=fee,
            reversal_amount=Decimal("0"),
            liability_amount=Decimal("0"),
            credit_type="foreign_transaction_fee_reversal",
        ),
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.98,
            flip_fact="The merchant refunded less than the original transaction-currency amount.",
        ),
        automated_actions=[
            {
                "action": "reverse_foreign_transaction_fee",
                "txn_id": state["findings"]["fee"]["txn_id"],
                "amount": str(fee),
                "policy": "LFB-SOP-DSP-007@v2",
            }
        ],
        letters=["reg_z_no_error_explanation_with_fx_breakdown"],
        conditions_considered=[
            {
                "condition": "13.6",
                "fails_because": "the merchant credit was processed in full before any dispute",
            },
            {
                "condition": "11.4.2 currency difference",
                "fails_because": "applies only when the credit follows a dispute",
            },
        ],
        citations=[
            {
                "doc_id": "VISA-11.4-AMOUNTS-CREDITS-FX@2026-04-18",
                "why": "Conversion difference rules",
            },
            {
                "doc_id": "VISA-13.6@2026-04-18",
                "why": "Credit was processed, so credit-not-processed does not apply",
            },
            {
                "doc_id": "LFB-SOP-DSP-007@v2",
                "why": "Reverse the foreign transaction fee on a full refund",
            },
            {
                "doc_id": "LFB-CARDHOLDER-AGREEMENT@2025-01",
                "why": "Credits convert at the rate on the credit date",
            },
        ],
        confidence=0.98,
        explanation_for_cardholder=(
            f"The merchant refunded the full EUR {refund['txn_amount']}. Your purchase converted "
            "at "
            f"{state['findings']['purchase']['fx_rate']} (${fx['purchase_usd']}) and the refund "
            f"at {refund['fx_rate']} "
            f"(${fx['refund_usd']}), so the ${fx['fx_difference']} difference comes from the "
            "exchange rate, not the "
            f"merchant. Because the refund was complete, we reversed our ${fee} foreign "
            "transaction fee."
        ),
    )
