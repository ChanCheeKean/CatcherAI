"""C18-style route: a debit non-receipt claim where the merchant's refund arrived after intake.

The procedural lesson "check for late merchant credits first" is read as a lead and verified; a
matched credit makes the provisional credit a duplicate, which is reversed with a Reg E notice.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from domain.events import ActorKind
from runtime.context import RunContext, check
from sandbox import business_day_offset

QUERY = (
    "REGE 1005.11 Regulation E error resolution provisional credit VISA 11.2 lifecycle dispute "
    "LFB SOP DSP 006 Reg E investigation"
)
REQUIRED = {"REGE-1005.11", "VISA-11.2-LIFECYCLE@2026-04-18", "LFB-SOP-DSP-006@v4"}
ORDER_NUMBER = re.compile(r"order\s+(\d[\d-]*\d)", re.I)
REFUND_SUFFIX = re.compile(r"REFUND\s+(\d{4})\b", re.I)
HONOR_BUSINESS_DAYS = 5


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case, purchase = state["case"], state["transactions"][0]
    notice = date.fromisoformat(case["opened_at"][:10])
    lessons = ctx.call(
        "read_memory_notes",
        "Read procedural lessons that apply before any network dispute",
        {"subject_ids": [], "as_of": notice.isoformat(), "minimum_confidence": 0.5},
        lambda: ctx.notes.read_current(subject_ids=[], as_of=notice, scope="procedure"),
    )
    activity = ctx.call(
        "get_account_transactions",
        "Look for merchant credits and provisional credits since the purchase",
        {
            "account_id": case["account_id"],
            "since": purchase["processing_date"],
            "until": ctx.clock.now.date().isoformat(),
        },
        lambda: ctx.data.account_transactions(
            case["account_id"],
            since=purchase["processing_date"],
            until=ctx.clock.now.date().isoformat(),
        ),
    )
    communications = ctx.call(
        "get_case_communications",
        "Read intake and any forwarded merchant messages",
        {"case_id": case["case_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.case_communications(case["case_id"]),
    )
    research = ctx.call(
        "search_research",
        "Learn how the marketplace labels refunds on statements",
        {"merchant_id": purchase["merchant_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.research_for_merchant(purchase["merchant_id"]),
    )
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve Reg E reversal and network credit rules",
        {"query": QUERY, "as_of": notice.isoformat(), "kinds": ["policy"]},
        lambda: ctx.knowledge.search(QUERY, as_of=notice, kinds=("policy",), limit=12),
    )
    credits = [
        row
        for row in activity
        if row["txn_type"] == "credit" and row["merchant_id"] == purchase["merchant_id"]
    ]
    provisional = next(
        (
            row
            for row in activity
            if row["txn_type"] == "provisional_credit" and case["case_id"] in row["descriptor"]
        ),
        None,
    )
    orders = [
        match.group(1) for row in communications for match in ORDER_NUMBER.finditer(row["body"])
    ]
    match = next(
        (
            credit
            for credit in credits
            for order in orders
            if (suffix := REFUND_SUFFIX.search(credit["descriptor"]))
            and order.endswith(suffix.group(1))
            and Decimal(credit["billing_amount"]) == Decimal(purchase["billing_amount"])
        ),
        None,
    )
    lesson = next((note for note in lessons if "credit" in note["content"].casefold()), None)
    if lesson and match:
        ctx.notes.verify(
            lesson,
            reason="A merchant credit posted after intake without an original-transaction link",
            evidence_refs=[match["txn_id"]],
        )
    if match:
        ctx.event(
            ActorKind.AGENT,
            "lead_investigator",
            "evidence_added",
            "Matched the late marketplace refund to the disputed order",
            {
                "evidence_ids": [match["txn_id"], *[row["comm_id"] for row in communications]],
                "use": (
                    "refund descriptor suffix equals the order number in the forwarded email; "
                    "same amount"
                ),
                "case_file_path": f"/case/{case['case_id']}/evidence_matrix.json",
            },
            [match["txn_id"], purchase["txn_id"]],
        )
    holidays = [
        date.fromisoformat(row["date"])
        for row in ctx.data.bank_holidays(
            since=ctx.clock.now.date().isoformat(),
            until=(ctx.clock.now.date() + timedelta(days=30)).isoformat(),
        )
    ]
    honored = ctx.call(
        "compute_business_days",
        "Compute how long reversed funds must be honored after today's notice",
        {"start": ctx.clock.now.date().isoformat(), "days": HONOR_BUSINESS_DAYS},
        lambda: business_day_offset(
            start=ctx.clock.now.date(),
            days=HONOR_BUSINESS_DAYS,
            holidays=holidays,
            rule="LFB-SOP-DSP-006 honor period after reversal notice",
            refs=["LFB-SOP-DSP-006@v4"],
            emitter=ctx.emitter,
        ).isoformat(),
    )
    return {
        "knowledge": knowledge,
        "memory_notes": lessons,
        "findings": {
            "matched_credit": match,
            "provisional": provisional,
            "orders": orders,
            "research_ids": [row["doc_id"] for row in research],
            "funds_honored_through": honored,
            "merchant_name": purchase.get("merchant_name")
            or next(
                (row.get("merchant_name") for row in credits if row.get("merchant_name")),
                "merchant",
            ),
        },
        "forced_stop": "value_of_information_stop" if match else None,
    }


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = state["findings"]
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    credit, provisional = findings["matched_credit"], findings["provisional"]
    return [
        check(
            "reg_e_reversal_sources_retrieved",
            REQUIRED <= doc_ids,
            {"required": sorted(REQUIRED)},
            sorted(REQUIRED),
        ),
        check(
            "merchant_credit_matched_without_arn",
            credit is not None,
            {"credit": credit, "orders": findings["orders"]},
            [credit["txn_id"]] if credit else [],
        ),
        check(
            "provisional_credit_would_double_recover",
            bool(credit and provisional)
            and credit["billing_amount"] == provisional["billing_amount"],
            {"provisional": provisional},
            [provisional["txn_id"]] if provisional else [],
        ),
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, purchase, findings = state["case"], state["transactions"][0], state["findings"]
    amount = Decimal(purchase["billing_amount"])
    credit, provisional = findings["matched_credit"], findings["provisional"]
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=False,
        claim_family="not_received",
        network_actions=[
            NetworkAction(
                txn_id=purchase["txn_id"],
                case_id=case["case_id"],
                action="no_dispute",
                reason="merchant credit processed; apply credit",
                amount=amount,
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome="resolved_merchant_credit",
            credit_amount=Decimal("0"),
            reversal_amount=Decimal(provisional["billing_amount"]),
            liability_amount=Decimal("0"),
            reversal_of_txn_id=provisional["txn_id"],
        ),
        deadlines={"funds_honored_through": findings["funds_honored_through"]},
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.97,
            flip_fact="The matched refund belongs to a different order or was reversed.",
        ),
        letters=["reg_e_provisional_credit_reversal_notice"],
        citations=[
            {
                "doc_id": "REGE-1005.11",
                "why": "Error resolved; provisional credit reversal with notice",
            },
            {
                "doc_id": "LFB-SOP-DSP-006@v4",
                "why": "Honor funds for 5 business days after the reversal notice",
            },
            {
                "doc_id": "VISA-11.2-LIFECYCLE@2026-04-18",
                "why": "Apply the merchant credit before any dispute",
            },
        ],
        confidence=0.97,
        explanation_for_cardholder=(
            f"{findings['merchant_name']} refunded ${credit['billing_amount']} for order "
            f"{findings['orders'][0]} on "
            f"{credit['posting_date']}. Because that refund resolves the claim, we are reversing "
            "the "
            f"${provisional['billing_amount']} provisional credit; you can keep using those funds "
            "through "
            f"{findings['funds_honored_through']}."
        ),
    )
