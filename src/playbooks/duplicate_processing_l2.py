"""C04-style route: apparent duplicates that may be split clearings of one authorization."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from runtime.context import RunContext
from sandbox import group_clearings

STEPS = ["gather_evidence", "ask_cardholder"]
EVIDENCE_USE = "test order quantity and split-shipment explanation"


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    auth_id = state["transactions"][0]["auth_id"]
    rows = ctx.call(
        "clearing_group",
        "Compare both postings to their shared authorization and clearing sequence",
        {"auth_id": auth_id, "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.clearing_group(auth_id),
    )
    clearing = ctx.call(
        "compute_group_clearings",
        "Compute whether the postings are split clearings within the authorization",
        {"txn_ids": [row["txn_id"] for row in rows]},
        lambda: group_clearings(rows, ctx.emitter).model_dump(mode="json"),
    )
    intake = date.fromisoformat(state["case"]["opened_at"][:10])
    query = (
        "LFB SOP DSP 001 split shipment VISA 12.6 duplicate processing REGZ 1026.13 no error notice"
    )
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve duplicate-processing and no-error rules effective at intake",
        {"query": query, "as_of": intake.isoformat(), "kinds": ["policy"]},
        lambda: ctx.knowledge.search(query, as_of=intake, kinds=("policy",), limit=8),
    )
    return {"findings": {"clearing": clearing}, "knowledge": knowledge}


def evidence_request(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": "merchant",
        "summary": "Requested the order record needed to test split clearing",
        "evidence_types": ["order", "shipments", "authorization"],
        "target_txn_ids": [row["txn_id"] for row in state["transactions"]],
        "rationale": "Confirm the order quantity and shipment-linked charges",
    }


def cardholder_question(ctx: RunContext, state: dict[str, Any]) -> dict[str, str]:
    return {
        "question": (
            "Did another package from Parcelwick arrive? The order shows quantity 2 lamps "
            "shipped separately."
        ),
        "rationale": "Only the cardholder can confirm the second shipment arrived",
    }


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, transactions = state["case"], state["transactions"]
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=False,
        claim_family="duplicate",
        network_actions=[
            NetworkAction(
                txn_id=transactions[-1]["txn_id"],
                case_id=case["case_id"],
                action="no_dispute",
                reason="not duplicate: multiple clearing sequence of one authorization",
                amount=Decimal(transactions[-1]["billing_amount"]),
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome="no_error_split_shipment",
            credit_amount=Decimal("0"),
            reversal_amount=Decimal(case.get("provisional_credit_amount") or "0"),
            liability_amount=Decimal(transactions[0]["billing_amount"]),
        ),
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.98,
            flip_fact=(
                "The order showed quantity one or total clearings exceeded the authorization."
            ),
        ),
        citations=[
            {"doc_id": "LFB-SOP-DSP-001@v7", "why": "Pre-dispute split-shipment check"},
            {
                "doc_id": "VISA-12.6@2026-04-18",
                "why": "Duplicate processing requires more than one transaction",
            },
            {
                "doc_id": "REGZ-1026.13",
                "why": "No-error notice and provisional-credit reversal requirements",
            },
        ],
        letters=["reg_z_no_error_explanation"],
        confidence=0.98,
        explanation_for_cardholder=(
            "The two postings were separate clearings from one $128.36 authorization "
            "for two lamps shipped separately. Both shipments were delivered; the "
            "merchant's return process remains available."
        ),
    )
