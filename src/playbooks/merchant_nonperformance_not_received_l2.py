"""C01-style route: goods never shipped and the merchant has stopped operating.

Dated research can change a rule's applicability: insolvency waives the 13.1 waiting period, so the
investigator files now instead of waiting or chasing a defunct merchant for evidence.
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
from sandbox import window_deadlines

STEPS = ["gather_evidence"]
EVIDENCE_USE = "confirm whether the merchant can still supply order or shipment data"
QUERY = (
    "VISA 13.1 merchandise services not received waiting period insolvent bankrupt REGZ 1026.13 "
    "billing error notice"
)
REQUIRED = {"VISA-13.1@2026-04-18", "REGZ-1026.13"}
INSOLVENCY = re.compile(r"\b(chapter 7|chapter 11|bankrupt\w*|insolven\w*|has closed)\b", re.I)
FILED_ON = re.compile(r"filed\b.*?\bon\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})", re.S)
EXPECTED_DELIVERY = re.compile(r"delivery[^0-9]*by ([A-Z][a-z]+ \d{1,2}, \d{4})", re.I)
WAITING_DAYS, TIME_LIMIT_DAYS, NOTICE_DAYS = 15, 120, 60


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case, txn = state["case"], state["transactions"][0]
    notice = date.fromisoformat(case["opened_at"][:10])
    communications = ctx.call(
        "get_case_communications",
        "Read the order terms and the cardholder's attempts to resolve",
        {"case_id": case["case_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.case_communications(case["case_id"]),
    )
    statements = ctx.call(
        "get_statements",
        "Find when the first statement showing the charge was transmitted",
        {"account_id": case["account_id"]},
        lambda: ctx.data.statements(case["account_id"]),
    )
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve 13.1 prerequisites and waivers and the Reg Z notice rule",
        {"query": QUERY, "as_of": notice.isoformat(), "kinds": ["policy", "precedent"]},
        lambda: ctx.knowledge.search(QUERY, as_of=notice, limit=16),
    )
    research = ctx.call(
        "search_research",
        "Check whether the merchant is still operating",
        {"merchant_id": txn["merchant_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.research_for_merchant(txn["merchant_id"]),
    )
    activity = ctx.call(
        "get_merchant_activity",
        "Look for other cardholders' disputes against the same merchant",
        {"merchant_ids": [txn["merchant_id"]], "since": txn["processing_date"]},
        lambda: ctx.data.merchant_activity([txn["merchant_id"]], since=txn["processing_date"]),
    )
    text = " ".join([row["body"] + row["attachments"] for row in communications])
    expected = datetime.strptime(EXPECTED_DELIVERY.search(text).group(1), "%B %d, %Y").date()
    attempts = sorted(
        set(re.findall(r"20\d\d-\d\d-\d\d", " ".join(row["attachments"] for row in communications)))
    )
    insolvency_docs = [row for row in research if INSOLVENCY.search(row["body"])]
    filed = next(
        (
            FILED_ON.search(row["body"]).group(1)
            for row in insolvency_docs
            if FILED_ON.search(row["body"])
        ),
        None,
    )
    filed_on = (
        datetime.strptime(" ".join(filed.split()), "%B %d, %Y").date().isoformat()
        if filed
        else None
    )
    cluster = sorted(
        {
            row["case_id"]
            for row in activity["disputes"]
            if row["case_id"] != case["case_id"]
            and row["claim_family_initial"] == case["claim_family_initial"]
            and row["status"] == "open"
        }
    )
    first = next(
        row
        for row in statements
        if row["cycle_start"] <= txn["processing_date"] <= row["cycle_end"]
    )
    transmitted = date.fromisoformat(first["transmitted_at"][:10])
    windows = ctx.call(
        "compute_window_deadlines",
        "Compute the Reg Z notice deadline from the first statement",
        {
            "events": {"reg_z_notice_deadline": transmitted.isoformat()},
            "days": NOTICE_DAYS,
            "rule": "REGZ-1026.13 60 days after first statement transmitted",
        },
        lambda: {
            k: v.isoformat()
            for k, v in window_deadlines(
                events={"reg_z_notice_deadline": transmitted},
                days=NOTICE_DAYS,
                rule="Reg Z notice window",
                refs=["REGZ-1026.13", first["statement_id"]],
                emitter=ctx.emitter,
            ).items()
        },
    )
    windows |= ctx.call(
        "compute_window_deadlines",
        "Compute the 13.1 time limit and the waiting period that would apply",
        {
            "events": {"visa_dispute_time_limit": expected.isoformat()},
            "days": TIME_LIMIT_DAYS,
            "rule": "VISA-13.1 120 days from the last expected receipt date",
        },
        lambda: {
            k: v.isoformat()
            for k, v in window_deadlines(
                events={"visa_dispute_time_limit": expected},
                days=TIME_LIMIT_DAYS,
                rule="13.1 time limit",
                refs=["VISA-13.1@2026-04-18"],
                emitter=ctx.emitter,
            ).items()
        },
    )
    waived = bool(insolvency_docs)
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "plan_updated",
        "Research shows the merchant is insolvent; the 13.1 waiting period no longer applies",
        {
            "plan_id": "plan-1",
            "full_plan": [
                *state["plan"],
                "Skip the 15-day wait (merchant insolvent)",
                "File 13.1 now",
            ],
            "diff": {"waiting_period_applies": {"before": True, "after": not waived}},
            "reason": "dated research reports bankruptcy and closure",
            "trigger_event_type": "tool_result",
        },
        [row["doc_id"] for row in insolvency_docs],
    )
    return {
        "knowledge": knowledge,
        "findings": {
            "communications": communications,
            "expected_delivery": expected.isoformat(),
            "resolution_attempts": attempts,
            "insolvency_docs": [row["doc_id"] for row in insolvency_docs],
            "bankruptcy_filed_on": filed_on,
            "cluster": cluster,
            "first_statement": first["statement_id"],
            "windows": windows,
            "waiting_period_waived": waived,
        },
        "candidate_condition": "13.1",
    }


def on_evidence(
    ctx: RunContext, state: dict[str, Any], packets: list[dict[str, Any]]
) -> dict[str, Any]:
    packet = json.loads(packets[0]["json"])
    no_data = packet.get("status") in {"no_data", "not_enrolled"}
    if no_data:
        ctx.event(
            ActorKind.GRAPH_NODE,
            "assess_progress",
            "case_file_updated",
            "Merchant returned no data; another evidence request cannot change the outcome",
            {
                "path": f"/case/{state['case_id']}/facts.json",
                "diff": {
                    "added": [
                        {
                            "fact": "merchant evidence unavailable",
                            "source_refs": [packets[0]["packet_id"]],
                        }
                    ]
                },
                "value_of_information": "stop requesting evidence from a defunct merchant",
            },
            [packets[0]["packet_id"]],
        )
    return {
        "findings": {**state["findings"], "merchant_evidence_status": packet.get("status")},
        "forced_stop": "value_of_information_stop" if no_data else None,
    }


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings, today = state["findings"], ctx.clock.now.date().isoformat()
    windows = findings["windows"]
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    return [
        check(
            "13_1_sources_retrieved",
            REQUIRED <= doc_ids,
            {"required": sorted(REQUIRED)},
            sorted(REQUIRED),
        ),
        check(
            "reg_z_notice_timely",
            state["case"]["opened_at"][:10] <= windows["reg_z_notice_deadline"],
            windows,
            [findings["first_statement"]],
        ),
        check(
            "expected_delivery_passed",
            findings["expected_delivery"] < today,
            {"expected": findings["expected_delivery"]},
            [row["comm_id"] for row in findings["communications"]],
        ),
        check(
            "attempted_to_resolve",
            len(findings["resolution_attempts"]) >= 1,
            {"attempts": findings["resolution_attempts"]},
            [row["comm_id"] for row in findings["communications"]],
        ),
        check(
            "waiting_period_waived_by_insolvency",
            findings["waiting_period_waived"] and bool(findings["bankruptcy_filed_on"]),
            {"sources": findings["insolvency_docs"], "filed_on": findings["bankruptcy_filed_on"]},
            findings["insolvency_docs"],
        ),
        check(
            "within_network_time_limit",
            today <= windows["visa_dispute_time_limit"],
            windows,
            ["VISA-13.1@2026-04-18"],
        ),
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, txn, findings = state["case"], state["transactions"][0], state["findings"]
    amount = Decimal(txn["billing_amount"])
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=True,
        claim_family="not_received",
        network_actions=[
            NetworkAction(
                txn_id=txn["txn_id"],
                case_id=case["case_id"],
                action="file_dispute",
                condition="13.1",
                amount=amount,
                reason="Made-to-order goods never shipped; merchant insolvent so no waiting period",
                earliest_filing_date=ctx.clock.now.date().isoformat(),
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome="provisional_credit_pending_network",
            credit_amount=amount,
            reversal_amount=Decimal("0"),
            liability_amount=Decimal("0"),
        ),
        deadlines={
            "reg_z_notice_deadline": findings["windows"]["reg_z_notice_deadline"],
            "visa_dispute_time_limit": findings["windows"]["visa_dispute_time_limit"],
        },
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.96,
            flip_fact="Shipment evidence or a merchant still able to deliver the order.",
        ),
        memory_ops=[
            {
                "op": "write",
                "scope": "merchant",
                "subject_id": txn["merchant_id"],
                "content": (
                    f"Merchant bankrupt: Chapter 7 filed {findings['bankruptcy_filed_on']}; open "
                    "non-receipt cluster."
                ),
            }
        ],
        letters=["reg_z_billing_error_acknowledgment"],
        citations=[
            {
                "doc_id": "VISA-13.1@2026-04-18",
                "why": "Waiting period does not apply when the merchant is insolvent",
            },
            {"doc_id": "REGZ-1026.13", "why": "Timely billing-error notice and provisional credit"},
        ],
        confidence=0.96,
        explanation_for_cardholder=(
            f"The table was due by {findings['expected_delivery']} and never shipped, and the "
            "merchant filed for "
            f"bankruptcy on {findings['bankruptcy_filed_on']}. Your notice reached us before the "
            f"{findings['windows']['reg_z_notice_deadline']} deadline. We credited ${amount} and "
            "are filing the network "
            "dispute now, because the usual waiting period does not apply to a merchant that has "
            "closed."
        ),
    )


def curate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    findings, txn = state["findings"], state["transactions"][0]
    note_id = ctx.notes.write(
        kind="semantic",
        scope="merchant",
        subject_ids=[txn["merchant_id"]],
        content=(
            f"Merchant is bankrupt: Chapter 7 petition filed {findings['bankruptcy_filed_on']} "
            "and the business has "
            f"closed. {len(findings['cluster']) + 1} open non-receipt disputes were active on "
            f"{ctx.clock.now.date().isoformat()}; the 13.1 waiting period does not apply."
        ),
        source_refs=[*findings["insolvency_docs"], state["case_id"], *findings["cluster"]],
        valid_from=date.fromisoformat(findings["bankruptcy_filed_on"]),
        confidence=0.95,
        tags=["insolvency", "cluster"],
    )
    return {"memory_correction_ids": [note_id] if note_id else []}
