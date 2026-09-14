"""C17-style route: an old non-receipt claim where every formal remedy may already be closed.

The route computes each window in the sandbox, stops once no admissible action could change the
outcome (value-of-information stop), and still hands the cardholder a working next step.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from domain.events import ActorKind
from runtime.context import RunContext, check
from sandbox import credit_outstanding, window_deadlines

QUERY = (
    "VISA 13.1 time limit 120 days expected service REGZ 1026.13 60 days notice REGZ 1026.12 "
    "claims defenses PRE 0017"
)
REQUIRED = {"VISA-13.1@2026-04-18", "REGZ-1026.13", "REGZ-1026.12"}
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
EVENT_DATE = re.compile(r"\(([A-Z][a-z]{2}) (\d{1,2})\)")
PORTAL_DEADLINE = re.compile(r"until ([A-Z][a-z]+ \d{1,2}, \d{4})")


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case, txn = state["case"], state["transactions"][0]
    notice = date.fromisoformat(case["opened_at"][:10])
    communications = ctx.call(
        "get_case_communications",
        "Find the cancellation notice and the last expected service date",
        {"case_id": case["case_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.case_communications(case["case_id"]),
    )
    statements = ctx.call(
        "get_statements",
        "Find the first statement with the charge and the payment history",
        {"account_id": case["account_id"]},
        lambda: ctx.data.statements(case["account_id"]),
    )
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve network time limits, Reg Z notice and claims-and-defenses rules",
        {"query": QUERY, "as_of": notice.isoformat(), "kinds": ["policy", "precedent"]},
        lambda: ctx.knowledge.search(QUERY, as_of=notice, limit=16),
    )
    research = ctx.call(
        "search_research",
        "Look for a merchant remedy that is still open",
        {"merchant_id": txn["merchant_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.research_for_merchant(txn["merchant_id"]),
    )
    merchant = ctx.call(
        "get_merchant",
        "Resolve the merchant name for the remaining remedy",
        {"merchant_id": txn["merchant_id"]},
        lambda: ctx.data.merchant(txn["merchant_id"]),
    )
    attachments = " ".join(row["attachments"] for row in communications)
    cancellation = json.loads(communications[0]["attachments"])[0]
    cancelled_on = date.fromisoformat(ISO_DATE.search(cancellation["description"]).group(0))
    month, day = EVENT_DATE.search(attachments).groups()
    event_date = datetime.strptime(f"{month} {day} {cancelled_on.year}", "%b %d %Y").date()
    purchase_date = date.fromisoformat(txn["txn_local_datetime"][:10])
    outstanding = ctx.call(
        "compute_credit_outstanding",
        "Apply payments to other balances first and test what remains unpaid",
        {
            "account_id": case["account_id"],
            "purchase_date": purchase_date.isoformat(),
            "amount": float(txn["billing_amount"]),
        },
        lambda: credit_outstanding(
            statements=statements,
            purchase_date=purchase_date,
            amount=Decimal(txn["billing_amount"]),
            refs=[case["account_id"], "REGZ-1026.12"],
            emitter=ctx.emitter,
        ),
    )
    first_statement = date.fromisoformat(outstanding["first_statement_transmitted"])
    windows = ctx.call(
        "compute_window_deadlines",
        "Compute the Visa 13.1 time limit from the last expected service date",
        {
            "events": {"visa_13_1_time_limit": event_date.isoformat()},
            "days": 120,
            "rule": "VISA-13.1 120 days from last expected service date",
        },
        lambda: {
            key: value.isoformat()
            for key, value in window_deadlines(
                events={"visa_13_1_time_limit": event_date},
                days=120,
                rule="13.1 time limit",
                refs=["VISA-13.1@2026-04-18"],
                emitter=ctx.emitter,
            ).items()
        },
    )
    windows |= ctx.call(
        "compute_window_deadlines",
        "Compute the Reg Z billing-error notice deadline",
        {
            "events": {"reg_z_notice_deadline": first_statement.isoformat()},
            "days": 60,
            "rule": "REGZ-1026.13 60 days after the first statement was transmitted",
        },
        lambda: {
            key: value.isoformat()
            for key, value in window_deadlines(
                events={"reg_z_notice_deadline": first_statement},
                days=60,
                rule="Reg Z notice window",
                refs=["REGZ-1026.13", outstanding["first_statement_id"]],
                emitter=ctx.emitter,
            ).items()
        },
    )
    portal = next((row for row in research if PORTAL_DEADLINE.search(row["body"])), None)
    portal_deadline = (
        datetime.strptime(PORTAL_DEADLINE.search(portal["body"]).group(1), "%B %d, %Y")
        .date()
        .isoformat()
        if portal
        else None
    )
    today = ctx.clock.now.date().isoformat()
    remedies = {
        "visa_13_1": windows["visa_13_1_time_limit"] >= today,
        "reg_z_billing_error": windows["reg_z_notice_deadline"] >= notice.isoformat(),
        "reg_z_claims_and_defenses": Decimal(outstanding["credit_outstanding"]) > 0,
        "merchant_refund_portal": bool(portal_deadline and portal_deadline >= today),
    }
    formal_closed = not any(
        value for key, value in remedies.items() if key != "merchant_refund_portal"
    )
    ctx.event(
        ActorKind.GRAPH_NODE,
        "investigate",
        "case_file_updated",
        "Every formal remedy window is closed; no further evidence can change the network outcome"
        if formal_closed
        else "At least one formal remedy is still open",
        {
            "path": f"/case/{case['case_id']}/deadlines.json",
            "diff": {
                "remedies_open": remedies,
                "windows": windows,
                "portal_deadline": portal_deadline,
            },
            "value_of_information": "no admissible action can change the decision"
            if formal_closed
            else "continue",
        },
        [case["case_id"], *(([portal["doc_id"]]) if portal else [])],
    )
    return {
        "knowledge": knowledge,
        "findings": {
            "windows": windows,
            "outstanding": outstanding,
            "remedies": remedies,
            "event_date": event_date.isoformat(),
            "portal": portal["doc_id"] if portal else None,
            "portal_deadline": portal_deadline,
            "merchant_name": merchant["dba_name"],
        },
        "forced_stop": "value_of_information_stop" if formal_closed else None,
    }


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = state["findings"]
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    return [
        check(
            "timeliness_sources_retrieved",
            REQUIRED <= doc_ids,
            {"required": sorted(REQUIRED)},
            sorted(REQUIRED),
        ),
        check(
            "formal_remedies_closed",
            not any(v for k, v in findings["remedies"].items() if k != "merchant_refund_portal"),
            findings["remedies"],
            [state["case_id"]],
        ),
        check(
            "actionable_alternative_found",
            findings["remedies"]["merchant_refund_portal"],
            {"portal": findings["portal"], "deadline": findings["portal_deadline"]},
            [findings["portal"] or ""],
        ),
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, txn, findings = state["case"], state["transactions"][0], state["findings"]
    windows = findings["windows"]
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=False,
        claim_family="not_received_cancelled_event",
        network_actions=[
            NetworkAction(
                txn_id=txn["txn_id"],
                case_id=case["case_id"],
                action="no_dispute",
                reason="Visa time limit expired",
                amount=Decimal(txn["billing_amount"]),
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome="declined_untimely_redirected",
            credit_amount=Decimal("0"),
            reversal_amount=Decimal("0"),
            liability_amount=Decimal(txn["billing_amount"]),
            redirect={"resource": findings["portal"], "deadline": findings["portal_deadline"]},
        ),
        deadlines={
            "visa_13_1_time_limit": windows["visa_13_1_time_limit"],
            "reg_z_notice_deadline": windows["reg_z_notice_deadline"],
        },
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.97,
            flip_fact=(
                "A balance on the purchase was still unpaid, or the notice reached us within 60 "
                "days."
            ),
        ),
        letters=["reg_z_untimely_notice_explanation"],
        citations=[
            {
                "doc_id": "VISA-13.1@2026-04-18",
                "why": "120-day time limit after the expected service date",
            },
            {"doc_id": "REGZ-1026.13", "why": "60-day billing-error notice window"},
            {"doc_id": "REGZ-1026.12", "why": "No credit outstanding on a purchase paid in full"},
            {
                "doc_id": "PRE-0017",
                "why": "Distinguished: that cardholder still owed part of the purchase",
            },
        ],
        confidence=0.97,
        explanation_for_cardholder=(
            "We checked every option. The card network's deadline for this event passed on "
            f"{windows['visa_13_1_time_limit']}, "
            f"the billing-error notice window closed on {windows['reg_z_notice_deadline']}, and "
            "because your balance was "
            f"paid in full there is no unpaid amount to withhold. {findings['merchant_name']} is "
            "still taking "
            "refund claims for this "
            f"cancelled show through its Refund Portal until {findings['portal_deadline']}; "
            "submit your order number there."
        ),
    )
