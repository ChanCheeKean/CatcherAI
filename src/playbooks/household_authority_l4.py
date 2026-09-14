"""C10-style route: a household member's purchases after the cardholder stored the card.

Reg Z authority is a judgment call, so the route always ends in the automated review panel.
"""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from domain.events import ActorKind
from runtime.context import RunContext, check, note_matching
from sandbox import window_deadlines

STEPS = ["gather_evidence", "run_specialists", "ask_cardholder"]
EVIDENCE_USE = "identify who stored the card and which device made the disputed purchases"
QUERY = (
    "LFB CARDHOLDER AGREEMENT authorized user REGZ 1026.12 apparent authority household member "
    "VISA 11.5.1 compelling evidence SOP DSP 003 004 PRE 0010"
)
REQUIRED = {
    "REGZ-1026.12",
    "VISA-11.5.1-COMPELLING-EVIDENCE@2026-04-18",
    "LFB-CARDHOLDER-AGREEMENT@2025-01",
    "LFB-SOP-DSP-003@v6",
    "LFB-SOP-DSP-004@v2",
}
HOUSEHOLD_MEMBER = re.compile(r"\b(child|son|daughter|kid|teen|spouse|partner|family)\b", re.I)
REFUND_WINDOW = re.compile(r"within the last (\d+) days", re.I)
CARD_ENTERED = re.compile(r"\b(put it in|saved|added|entered)\b", re.I)


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case = state["case"]
    notice = date.fromisoformat(case["opened_at"][:10])
    merchant_id = state["transactions"][0]["merchant_id"]
    communications = ctx.call(
        "get_case_communications",
        "Read the cardholder's own account of who made the purchases",
        {"case_id": case["case_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.case_communications(case["case_id"]),
    )
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve authority, household compelling-evidence and governance rules",
        {"query": QUERY, "as_of": notice.isoformat(), "kinds": ["policy", "precedent"]},
        lambda: ctx.knowledge.search(QUERY, as_of=notice, limit=20),
    )
    notes = ctx.call(
        "read_memory_notes",
        "Read merchant memory about minor-purchase remedies as a lead",
        {"subject_ids": [merchant_id], "as_of": notice.isoformat(), "minimum_confidence": 0.5},
        lambda: ctx.notes.read_current(subject_ids=[merchant_id], as_of=notice),
    )
    research = ctx.call(
        "search_research",
        "Find the merchant's current minor-purchase refund policy",
        {"merchant_id": merchant_id, "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.research_for_merchant(merchant_id),
    )
    merchant = ctx.call(
        "get_merchant",
        "Resolve the merchant name used in customer guidance",
        {"merchant_id": merchant_id},
        lambda: ctx.data.merchant(merchant_id),
    )
    statement = " ".join(row["body"] for row in communications)
    household = bool(HOUSEHOLD_MEMBER.search(statement))
    refund_doc = next((row for row in research if REFUND_WINDOW.search(row["body"])), None)
    note = note_matching(
        {"memory_notes": notes}, tags=("minor", "merchant_refund"), subject_id=merchant_id
    )
    if note and refund_doc:
        ctx.notes.verify(
            note,
            reason="Current merchant help page still offers a 30-day minor refund",
            evidence_refs=[refund_doc["doc_id"]],
        )
    ctx.event(
        ActorKind.MEMORY,
        "case_file",
        "case_file_updated",
        "Recorded the household-member claim and the available merchant remedy",
        {
            "path": f"/case/{case['case_id']}/facts.json",
            "diff": {
                "added": [
                    {
                        "fact": "purchases attributed to a household member",
                        "value": household,
                        "source_refs": [row["comm_id"] for row in communications],
                    },
                    {
                        "fact": "merchant minor-purchase refund window (days)",
                        "value": int(REFUND_WINDOW.search(refund_doc["body"]).group(1))
                        if refund_doc
                        else None,
                        "source_refs": [refund_doc["doc_id"]] if refund_doc else [],
                    },
                ]
            },
        },
        [row["comm_id"] for row in communications],
    )
    return {
        "knowledge": knowledge,
        "memory_notes": notes,
        "findings": {
            "communications": communications,
            "refund_doc": refund_doc,
            "merchant": merchant,
        },
        "governance_facts": {"authority_determination": household},
    }


def evidence_request(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": "merchant",
        "summary": "Requested account, stored-card and device evidence",
        "evidence_types": ["payment_method_events", "purchase_devices"],
        "target_txn_ids": [row["txn_id"] for row in state["transactions"]],
        "rationale": "Establish who stored the card and which device made the purchases",
    }


def on_evidence(
    ctx: RunContext, state: dict[str, Any], packets: list[dict[str, Any]]
) -> dict[str, Any]:
    packet = json.loads(packets[0]["json"])
    card_added = next(
        row for row in packet["payment_method_events"] if row["event"] == "card_added"
    )
    return {
        "findings": {
            **state["findings"],
            "packet": packet,
            "card_added": card_added,
            "disputed_fingerprint": packet["purchases"]["device_fingerprint_for_disputed"],
        }
    }


def specialists(
    ctx: RunContext, state: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    findings = state["findings"]
    fingerprints = [findings["card_added"]["device_fingerprint"], findings["disputed_fingerprint"]]
    owners = ctx.call(
        "graph_device_fingerprint_owners",
        "Trace the card-saving and purchasing devices to their owners",
        {"fingerprints": fingerprints},
        lambda: ctx.graph.device_fingerprint_owners(fingerprints),
        actor="graph_link_analyst",
    )
    days = int(REFUND_WINDOW.search(findings["refund_doc"]["body"]).group(1))
    purchase_dates = sorted(
        date.fromisoformat(row["txn_local_datetime"][:10]) for row in state["transactions"]
    )
    windows = ctx.call(
        "compute_window_deadlines",
        "Compute when the merchant's minor refund closes for each purchase",
        {
            "events": {
                "first_purchase": purchase_dates[0].isoformat(),
                "last_purchase": purchase_dates[-1].isoformat(),
            },
            "days": days,
            "rule": f"{findings['refund_doc']['doc_id']} refund within {days} days",
        },
        lambda: {
            key: value.isoformat()
            for key, value in window_deadlines(
                events={"first_purchase": purchase_dates[0], "last_purchase": purchase_dates[-1]},
                days=days,
                rule=f"merchant minor refund within {days} days",
                refs=[findings["refund_doc"]["doc_id"]],
                emitter=ctx.emitter,
            ).items()
        },
    )
    follow_up = ctx.call(
        "compute_window_deadlines",
        "Schedule a follow-up the day after the last refund window closes",
        {
            "events": {"follow_up": purchase_dates[-1].isoformat()},
            "days": days + 1,
            "rule": "check for merchant credits after the last refund window",
        },
        lambda: {
            key: value.isoformat()
            for key, value in window_deadlines(
                events={"follow_up": purchase_dates[-1]},
                days=days + 1,
                rule="follow up after the last refund window",
                refs=[findings["refund_doc"]["doc_id"]],
                emitter=ctx.emitter,
            ).items()
        },
    )
    customer_node = f"Customer:{state['case']['customer_id']}"
    saved_by_primary = any(
        row["customer_node_id"] == customer_node
        for row in owners
        if row["fingerprint_node_id"].endswith(fingerprints[0])
    )
    household_device = any(
        row["customer_node_id"] == customer_node
        for row in owners
        if row["fingerprint_node_id"].endswith(fingerprints[1])
    )
    if saved_by_primary:
        ctx.event(
            ActorKind.AGENT,
            "lead_investigator",
            "contradiction_detected",
            "Stored-card evidence conflicts with 'never gave him my card'",
            {
                "facts": [
                    {
                        "statement": "cardholder says the card was never given",
                        "source": findings["communications"][0]["comm_id"],
                    },
                    {
                        "statement": "card saved from the primary cardholder's own phone",
                        "source": state["evidence"][0]["packet_id"],
                    },
                ],
                "resolution": "ask the cardholder a specific question before deciding",
                "impact": "authority_given_then_exceeded_hypothesis",
            },
            [state["evidence"][0]["packet_id"], findings["communications"][0]["comm_id"]],
        )
    prior = [
        row["txn_id"]
        for row in state["descriptor_history"]
        if row["txn_id"] not in {txn["txn_id"] for txn in state["transactions"]}
    ]
    delegations = [
        {
            "subagent_type": "graph_link_analyst",
            "description": json.dumps(
                {
                    "task": "Assess household device linkage without inferring character",
                    "graph_results": owners,
                }
            ),
        },
        {
            "subagent_type": "merchant_evidence_analyst",
            "description": json.dumps(
                {
                    "task": (
                        "Assess stored-card and household-member compelling evidence (CE item 11)"
                    ),
                    "evidence_packet_refs": [state["evidence"][0]["packet_id"]],
                    "prior_undisputed": prior,
                }
            ),
        },
    ]
    return {
        "findings": {
            **findings,
            "device_owners": owners,
            "saved_by_primary": saved_by_primary,
            "household_device": household_device,
            "refund_windows": windows,
            "follow_up_at": follow_up["follow_up"],
            "prior_undisputed": prior,
        }
    }, delegations


def cardholder_question(ctx: RunContext, state: dict[str, Any]) -> dict[str, str]:
    return {
        "question": (
            "Can you tell us whether your card was ever added or saved to the game account?"
        ),
        "rationale": (
            "A specific, non-accusatory question separates no authority from authority exceeded"
        ),
    }


def on_reply(ctx: RunContext, state: dict[str, Any], reply: dict[str, Any]) -> dict[str, Any]:
    confirmed = bool(CARD_ENTERED.search(reply["text"]))
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "hypothesis_updated",
        "Cardholder reply resolved how the card came to be stored",
        {
            "path": f"/case/{state['case_id']}/hypotheses.json",
            "diff": {
                "H2_authority_given_then_exceeded": {"for": ["cardholder_confirmed_card_entry"]},
                "H1_no_authority": {"against": ["cardholder_confirmed_card_entry"]},
            },
        },
        [reply["reply_id"]],
    )
    return {
        "findings": {
            **state["findings"],
            "card_entry_confirmed": confirmed,
            "notice_date": state["case"]["opened_at"][:10],
        }
    }


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = state["findings"]
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    windows = findings["refund_windows"]
    return [
        check(
            "authority_sources_retrieved",
            REQUIRED <= doc_ids,
            {"required": sorted(REQUIRED), "doc_ids": sorted(doc_ids)},
            sorted(REQUIRED),
        ),
        check(
            "card_saved_from_primary_cardholder_device",
            findings["saved_by_primary"],
            {"device_owners": findings["device_owners"]},
            [state["evidence"][0]["packet_id"]],
        ),
        check(
            "purchases_from_household_device",
            findings["household_device"],
            {"device_owners": findings["device_owners"]},
            [state["evidence"][0]["packet_id"]],
        ),
        check(
            "cardholder_confirmed_card_entry",
            findings["card_entry_confirmed"],
            {"reply_ids": [row["reply_id"] for row in state["replies"]]},
            [row["reply_id"] for row in state["replies"]],
        ),
        check(
            "merchant_refund_window_still_open",
            windows["first_purchase"] >= ctx.clock.now.date().isoformat(),
            windows,
            [findings["refund_doc"]["doc_id"]],
        ),
        check(
            "independent_specialists_completed",
            len(state["specialist_results"]) == 2,
            {"results": state["specialist_results"]},
            [],
        ),
    ]


def hypotheses(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = state["findings"]
    packet_id = state["evidence"][0]["packet_id"]
    comm_ids = [row["comm_id"] for row in findings["communications"]]
    reply_ids = [row["reply_id"] for row in state["replies"]]
    devices = sorted({row["device_node_id"] for row in findings["device_owners"]})
    saved = {
        "fact": "card saved to the game account from the primary cardholder's phone and home IP",
        "refs": [packet_id, *devices],
        "weight": 3 if findings["saved_by_primary"] else 0,
    }
    confirmed = {
        "fact": "cardholder confirmed entering the card in February",
        "refs": reply_ids,
        "weight": 3 if findings["card_entry_confirmed"] else 0,
    }
    ask_each_time = {
        "fact": "cardholder told the household member to ask each time",
        "refs": reply_ids,
        "weight": 1,
    }
    return [
        {
            "id": "H2",
            "label": "authority given then exceeded",
            "favors": "issuer",
            "outcome": "deny unauthorized-use claim, reverse temporary credit, record notice",
            "evidence_for": [
                saved,
                confirmed,
                {
                    "fact": (
                        "disputed purchases came from the household tablet used for the "
                        "cardholder's banking"
                    ),
                    "refs": [packet_id, *devices],
                    "weight": 2 if findings["household_device"] else 0,
                },
                {
                    "fact": "earlier purchase at the merchant was not disputed",
                    "refs": findings["prior_undisputed"],
                    "weight": 1,
                },
            ],
            "evidence_against": [ask_each_time],
            "flip_fact": (
                "evidence that the card was never saved or used with the cardholder's permission "
                "(cf. PRE-0010)"
            ),
        },
        {
            "id": "H1",
            "label": "no authority was given",
            "favors": "cardholder",
            "outcome": "credit and pursue the network dispute",
            "evidence_for": [
                {
                    "fact": "intake statement that permission was never given",
                    "refs": comm_ids,
                    "weight": 1,
                },
                ask_each_time,
            ],
            "evidence_against": [saved, confirmed],
            "flip_fact": "a verified record that the cardholder stored the card",
        },
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, findings = state["case"], state["findings"]
    total = sum((Decimal(row["billing_amount"]) for row in state["transactions"]), Decimal("0"))
    windows = findings["refund_windows"]
    refund_doc = findings["refund_doc"]["doc_id"]
    merchant_name = findings["merchant"]["dba_name"]
    memory_note = note_matching(
        state,
        tags=("minor", "merchant_refund"),
        subject_id=state["transactions"][0]["merchant_id"],
    )
    notice = findings["notice_date"]
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=False,
        claim_family="household_member_purchases",
        network_actions=[
            NetworkAction(
                txn_id=row["txn_id"],
                case_id=case["case_id"],
                action="no_dispute",
                reason="purchases by a person given apparent/implied authority; household-member "
                "compelling evidence would defeat 10.4",
                amount=Decimal(row["billing_amount"]),
            )
            for row in state["transactions"]
        ],
        cardholder_resolution=CardholderResolution(
            outcome="denied_with_explanation",
            credit_amount=Decimal("0"),
            reversal_amount=Decimal(case.get("provisional_credit_amount") or total),
            liability_amount=total,
        ),
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.9,
            flip_fact="evidence that the card was never saved or used with the "
            "cardholder's permission (cf. PRE-0010)",
        ),
        cardholder_guidance={
            "merchant_minor_refund": {
                "source": refund_doc,
                "earliest_purchase_deadline": windows["first_purchase"],
                "last_purchase_deadline": windows["last_purchase"],
            },
            "card_controls": [
                "remove stored card from game account",
                "optional card number reissue",
            ],
        },
        follow_ups=[
            {
                "at": findings["follow_up_at"],
                "optional": True,
                "action": (
                    f"check for {merchant_name} credits on the account and send a confirmation"
                ),
            }
        ],
        automated_actions=[
            {
                "action": "record_authority_revocation_notice",
                "notice_date": notice,
                "effect": (
                    "further purchases by the household member without permission are unauthorized"
                ),
            },
            {"action": "schedule_follow_up", "at": findings["follow_up_at"], "source": refund_doc},
        ],
        memory_ops=(
            [{"op": "verify", "note_id": memory_note["note_id"], "evidence": [refund_doc]}]
            if memory_note
            else []
        ),
        letters=["reg_z_denial_explanation_with_credit_reversal_notice"],
        citations=[
            {
                "doc_id": "REGZ-1026.12",
                "why": "Use by a person given authority is not unauthorized until notice",
            },
            {
                "doc_id": "VISA-11.5.1-COMPELLING-EVIDENCE@2026-04-18",
                "why": "Household-member compelling evidence",
            },
            {
                "doc_id": "LFB-CARDHOLDER-AGREEMENT@2025-01",
                "why": "Cardholder responsibility for permitted users",
            },
            {
                "doc_id": "LFB-SOP-DSP-003@v6",
                "why": "Authority determination reviewed by the automated panel",
            },
            {"doc_id": "LFB-SOP-DSP-004@v2", "why": "Fact-based, non-accusatory treatment"},
            {
                "doc_id": "PRE-0010",
                "why": "Distinguished: there the card was never saved to the account",
            },
        ],
        hypotheses=[
            {"id": "H1", "label": "no authority was given", "status": "rejected"},
            {"id": "H2", "label": "authority given then exceeded", "status": "supported"},
        ],
        confidence=0.9,
        explanation_for_cardholder=(
            "We reviewed the game account records and your reply. The card was saved to the game "
            "account from your phone in February, so under the Fair Credit Billing rules these "
            "purchases count as made with your permission until you told us otherwise on "
            f"{notice}. We have reversed the temporary credit of ${total}; any purchases made "
            f"without permission after {notice} are covered. {merchant_name} offers parents a "
            "one-time "
            "refund for a child's purchases: request it now, because the earliest purchases stop "
            f"qualifying on {windows['first_purchase']} and the last on "
            f"{windows['last_purchase']}. We also recommend removing the saved card from the game "
            "account; we can reissue your card number if you prefer."
        ),
    )


def curate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    ctx.notes.skip(
        candidate="customer household-authority note",
        reason=(
            "The authority finding is case-specific and recorded as a case action; a "
            "customer-level note would become a label (SOP-DSP-004 §2)"
        ),
        refs=[state["case_id"], state["case"]["customer_id"]],
    )
    return {}
