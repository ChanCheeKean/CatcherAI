"""C09-style route: a card-not-present "fraud" claim on digital goods from a familiar merchant.

Network liability is decided by the CE 3.0 version in force on the projected processing date, while
the Reg Z outcome rests on the evidence review. When shown the evidence the cardholder admits the
purchase, so the claim is re-routed to a quality complaint that belongs with the merchant first.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from domain.events import ActorKind
from runtime.context import RunContext, check
from sandbox import business_day_offset, ce3_prior_transactions

STEPS = ["gather_evidence", "ask_cardholder"]
EVIDENCE_USE = "test participation: account, IP, device and usage after purchase"
QUERY = (
    "VISA 10.4 compelling evidence 3.0 prior transactions REGZ 1026.12 REGZ 1026.13 INTERP "
    "reasonable "
    "investigation LFB SOP DSP 004 fair treatment"
)
VERSION_QUERY = (
    "VISA 10.4 compelling evidence 3.0 prior transactions same acquirer device fingerprint"
)
REQUIRED = {
    "VISA-10.4@2026-04-18",
    "VISA-10.4@2026-10-24",
    "REGZ-1026.12",
    "REGZ-1026.13-INTERP",
    "LFB-SOP-DSP-004@v2",
}
ADMISSION = re.compile(r"\b(might have bought|i bought|i did buy|ok, fine)\b", re.I)
PREPARATION_BUSINESS_DAYS = 2
SIMILAR_ELEMENTS = [{"device_id", "device_fingerprint"}]


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case, txn = state["case"], state["transactions"][0]
    notice = date.fromisoformat(case["opened_at"][:10])
    communications = ctx.call(
        "get_case_communications",
        "Read the cardholder's statement",
        {"case_id": case["case_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.case_communications(case["case_id"]),
    )
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve fraud, CE 3.0, reasonable-investigation and fairness rules as of notice",
        {"query": QUERY, "as_of": notice.isoformat(), "kinds": ["policy", "precedent"]},
        lambda: ctx.knowledge.search(QUERY, as_of=notice, limit=20),
    )
    notes = ctx.call(
        "read_memory_notes",
        "Read customer memory only as a lead",
        {
            "subject_ids": [case["customer_id"]],
            "as_of": notice.isoformat(),
            "minimum_confidence": 0.5,
        },
        lambda: ctx.notes.read_current(subject_ids=[case["customer_id"]], as_of=notice),
    )
    purchase_day = txn["txn_local_datetime"][:10]
    since, until = (
        f"{purchase_day}T00:00:00Z",
        (date.fromisoformat(purchase_day) + timedelta(days=2)).isoformat() + "T00:00:00Z",
    )
    events = ctx.call(
        "get_account_events",
        "Check issuer-side logins around the purchase",
        {"account_id": case["account_id"], "since": since, "until": until},
        lambda: ctx.data.account_events(case["account_id"], since=since, until=until),
    )
    history = ctx.call(
        "get_account_transactions",
        "Find prior purchases on this card, including sister merchants",
        {
            "account_id": case["account_id"],
            "since": (notice - timedelta(days=365)).isoformat(),
            "until": txn["processing_date"],
        },
        lambda: ctx.data.account_transactions(
            case["account_id"],
            since=(notice - timedelta(days=365)).isoformat(),
            until=txn["processing_date"],
        ),
    )
    research = ctx.call(
        "search_research",
        "Find current merchant support guidance for the quality complaint",
        {"merchant_id": txn["merchant_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.research_for_merchant(txn["merchant_id"]),
    )
    for note in notes:
        ctx.notes.reject(
            note,
            reason="Past dispute outcomes are history, not evidence about this purchase "
            "(SOP-DSP-004: same evidence standard)",
            evidence_refs=["LFB-SOP-DSP-004@v2"],
        )
    disputed = next(row for row in history if row["txn_id"] == txn["txn_id"])
    priors = [
        row
        for row in history
        if row["txn_id"] != txn["txn_id"]
        and row["acquirer_id"] == disputed["acquirer_id"]
        and row["txn_type"] == "purchase"
    ]
    return {
        "knowledge": knowledge,
        "memory_notes": notes,
        "findings": {
            "communications": communications,
            "issuer_events": events,
            "disputed": disputed,
            "priors": priors,
            "research_ids": [row["doc_id"] for row in research],
        },
    }


def on_evidence(
    ctx: RunContext, state: dict[str, Any], packets: list[dict[str, Any]]
) -> dict[str, Any]:
    packet = json.loads(packets[0]["json"])
    packet_id, findings = packets[0]["packet_id"], state["findings"]
    session, usage = packet["session"], packet["digital_usage"]
    issuer_ips = {
        row["ip"] for row in findings["issuer_events"] if row["event_type"] == "login_success"
    }
    claimed = packet["compelling_evidence_claim"]["matching_elements"]
    counted = [
        element
        for element in claimed
        if not any(
            element in group and element != sorted(group & set(claimed))[0]
            for group in SIMILAR_ELEMENTS
        )
    ]
    participation = "same login, home IP, device; {hours}h played".format(
        hours=usage["total_playtime_hours"]
    )
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "contradiction_detected",
        (
            "Participation evidence contradicts the unauthorized-use claim; merchant "
            "double-counts device elements"
        ),
        {
            "facts": [
                {
                    "statement": "cardholder: did not authorize",
                    "source": findings["communications"][0]["comm_id"],
                },
                {
                    "statement": participation,
                    "source": packet_id,
                },
                {
                    "statement": "issuer login from the same IP that evening",
                    "source": ", ".join(row["event_id"] for row in findings["issuer_events"]),
                },
                {
                    "statement": (
                        f"merchant claims {len(claimed)} elements; device ID and fingerprint "
                        "count once"
                    ),
                    "source": "VISA-10.4@2026-10-24",
                },
            ],
            "resolution": "share the specific evidence with the cardholder before deciding",
            "impact": "fraud hypothesis weakened; merchant element count reduced",
        },
        [packet_id, *[row["event_id"] for row in findings["issuer_events"]]],
    )
    return {
        "findings": {
            **findings,
            "packet": packet,
            "issuer_ip_match": session["ip"] in issuer_ips,
            "elements_claimed": claimed,
            "elements_counted_once": counted,
        }
    }


def cardholder_question(ctx: RunContext, state: dict[str, Any]) -> dict[str, str]:
    packet = state["findings"]["packet"]
    return {
        "question": (
            "We reviewed specific evidence: the purchase came from your account login "
            f"{packet['customer_account']['login_id']}, your home IP address and your usual "
            "device, with "
            f"{packet['digital_usage']['total_playtime_hours']} hours of playtime since. Can you "
            "help us explain this?"
        ),
        "rationale": (
            "Reg Z requires a reasonable investigation; sharing the evidence lets the cardholder "
            "respond"
        ),
    }


def on_reply(ctx: RunContext, state: dict[str, Any], reply: dict[str, Any]) -> dict[str, Any]:
    findings, txn = state["findings"], state["transactions"][0]
    admitted = bool(ADMISSION.search(reply["text"]))
    reply_day = date.fromisoformat(reply["available_at"][:10])
    route = state["route"]
    if admitted:
        ctx.event(
            ActorKind.GRAPH_NODE,
            "apply_external_event",
            "route_decision",
            "Re-routed the withdrawn fraud claim to a merchant quality complaint",
            {
                "candidate_routes": [route["route_id"], "quality_complaint_merchant_first"],
                "method": "rule",
                "matched_rule": "cardholder admits purchase after evidence review",
                "confidence": 1.0,
                "chosen_route": "quality_complaint_merchant_first",
                "depth": route["depth"],
                "budget": route["budget"],
                "selected_agents": route["agents"],
                "selected_skills": route["skills"],
                "rationale": "claim family changed from fraud to a product-quality complaint",
            },
            [reply["reply_id"]],
        )
        ctx.event(
            ActorKind.AGENT,
            "lead_investigator",
            "plan_updated",
            "Replaced the fraud plan with a quality-complaint plan",
            {
                "plan_id": "plan-1",
                "full_plan": [
                    *state["plan"],
                    "Record CE 3.0 analysis for the network record",
                    "Direct the quality complaint to the merchant's support/refund policy",
                ],
                "diff": {"claim_family": {"before": "fraud_cnp", "after": "quality_complaint"}},
                "reason": "cardholder admitted the purchase",
                "trigger_event_type": "persona_reply",
            },
            [reply["reply_id"]],
        )
    holidays = [
        date.fromisoformat(row["date"])
        for row in ctx.data.bank_holidays(
            since=reply_day.isoformat(), until=(reply_day + timedelta(days=30)).isoformat()
        )
    ]
    projected = ctx.call(
        "compute_business_days",
        "Project the earliest realistic dispute processing date after the evidence review",
        {"start": reply_day.isoformat(), "days": PREPARATION_BUSINESS_DAYS},
        lambda: business_day_offset(
            start=reply_day,
            days=PREPARATION_BUSINESS_DAYS,
            holidays=holidays,
            rule="filing preparation after cardholder evidence review",
            refs=[reply["reply_id"]],
            emitter=ctx.emitter,
        ).isoformat(),
    )
    versions = ctx.call(
        "retrieve_knowledge",
        "Retrieve the CE 3.0 version in force on the projected processing date",
        {"query": VERSION_QUERY, "as_of": projected, "kinds": ["policy"]},
        lambda: ctx.knowledge.search(
            VERSION_QUERY, as_of=date.fromisoformat(projected), kinds=("policy",), limit=6
        ),
    )
    analyses = {}
    for version, same_acquirer in (("VISA-10.4@2026-04-18", False), ("VISA-10.4@2026-10-24", True)):
        analyses[version] = ctx.call(
            "compute_ce3_priors",
            f"Age prior transactions under {version}",
            {"disputed_txn_id": txn["txn_id"], "processing_date": projected, "version": version},
            lambda same_acquirer=same_acquirer, version=version: ce3_prior_transactions(
                disputed=findings["disputed"],
                priors=findings["priors"],
                processing_date=date.fromisoformat(projected),
                same_acquirer_counts=same_acquirer,
                min_age_days=120,
                max_age_days=365,
                refs=[version],
                emitter=ctx.emitter,
            ),
        )
    in_force = next(row["doc_id"] for row in versions if row["doc_id"].startswith("VISA-10.4@"))
    return {
        "knowledge": [*state["knowledge"], *versions],
        "findings": {
            **findings,
            "admitted": admitted,
            "reply_day": reply_day.isoformat(),
            "projected_processing_date": projected,
            "version_in_force": in_force,
            "ce3": analyses,
        },
    }


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = state["findings"]
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    old, new = findings["ce3"]["VISA-10.4@2026-04-18"], findings["ce3"]["VISA-10.4@2026-10-24"]
    return [
        check(
            "both_ce3_versions_retrieved_as_of",
            REQUIRED <= doc_ids,
            {"required": sorted(REQUIRED)},
            sorted(REQUIRED),
        ),
        check(
            "version_selected_by_projected_processing_date",
            findings["version_in_force"] == "VISA-10.4@2026-10-24",
            {
                "projected": findings["projected_processing_date"],
                "version": findings["version_in_force"],
            },
            [findings["version_in_force"]],
        ),
        check(
            "ce3_priors_analyzed",
            not old["two_priors_met"] and new["two_priors_met"],
            {"old": old, "new": new},
            ["VISA-10.4@2026-04-18", "VISA-10.4@2026-10-24"],
        ),
        check(
            "device_elements_counted_once",
            len(findings["elements_counted_once"]) == len(findings["elements_claimed"]) - 1,
            {"claimed": findings["elements_claimed"], "counted": findings["elements_counted_once"]},
            ["VISA-10.4@2026-10-24"],
        ),
        check(
            "participation_evidence_and_admission",
            findings["issuer_ip_match"] and findings["admitted"],
            {"issuer_ip_match": findings["issuer_ip_match"], "admitted": findings["admitted"]},
            [row["reply_id"] for row in state["replies"]],
        ),
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, txn, findings = state["case"], state["transactions"][0], state["findings"]
    amount = Decimal(txn["billing_amount"])
    merchant_name = findings["disputed"]["merchant_name"]
    support_ref = findings.get("research_ids", ["merchant support"])[0]
    old, new = findings["ce3"]["VISA-10.4@2026-04-18"], findings["ce3"]["VISA-10.4@2026-10-24"]
    note = (
        f"Fraud claim {case['case_id']} retracted by the cardholder after evidence review on "
        f"{findings['reply_day']}; "
        "the complaint is about game quality."
    )
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=False,
        claim_family="fraud_cnp_withdrawn_then_quality_complaint",
        network_actions=[
            NetworkAction(
                txn_id=txn["txn_id"],
                case_id=case["case_id"],
                action="no_dispute",
                amount=amount,
                reason=(
                    "cardholder participated; fraud claim withdrawn; quality complaint requires "
                    "merchant contact first"
                ),
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome="denied_with_explanation",
            credit_amount=Decimal("0"),
            reversal_amount=Decimal(case.get("provisional_credit_amount") or amount),
            liability_amount=amount,
        ),
        ce3_analysis={
            "projected_processing_date": findings["projected_processing_date"],
            "version_if_processed_by_2026_10_23": "VISA-10.4@2026-04-18",
            "qualifies_old": old["two_priors_met"],
            "version_if_processed_from_2026_10_24": "VISA-10.4@2026-10-24",
            "qualifies_new": new["two_priors_met"],
            "qualifying_priors": [row["txn_id"] for row in new["qualifying"]],
            "excluded_priors": new["excluded"],
            "matching_elements_counted": ["ip_address", "login_id"],
            "note": "device ID and device fingerprint count as one element under the new version",
        },
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.95,
            flip_fact="Evidence that someone else used the account, device or IP for the purchase.",
        ),
        memory_ops=[
            {"op": "write", "scope": "customer", "subject_id": case["customer_id"], "content": note}
        ],
        cardholder_guidance={
            "merchant_support": (
                f"{merchant_name} support for crashes on supported hardware ({support_ref})"
            )
        },
        letters=["reg_z_no_error_explanation_with_credit_reversal"],
        citations=[
            {
                "doc_id": "VISA-10.4@2026-04-18",
                "why": "CE 3.0 version for disputes processed before 2026-10-24",
            },
            {
                "doc_id": "VISA-10.4@2026-10-24",
                "why": "CE 3.0 version in force on the projected processing date",
            },
            {"doc_id": "REGZ-1026.12", "why": "Liability for authorized use"},
            {
                "doc_id": "REGZ-1026.13-INTERP",
                "why": "Reasonable investigation and cardholder response",
            },
            {
                "doc_id": "LFB-SOP-DSP-004@v2",
                "why": "Facts, not labels; same standard for everyone",
            },
        ],
        confidence=0.95,
        explanation_for_cardholder=(
            f"Thanks for your reply on {findings['reply_day']}. The purchase came from your game "
            "account, home internet "
            "connection and usual computer, and you confirmed you bought the game, so we can't "
            "treat it as unauthorized "
            f"and are reversing the temporary credit of ${amount}. For the crashes, contact "
            f"{merchant_name} support: they "
            "troubleshoot technical problems and may offer a refund or store credit if the game "
            "can't run on your hardware."
        ),
    )


def curate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case, findings = state["case"], state["findings"]
    note_id = ctx.notes.write(
        kind="episodic",
        scope="customer",
        subject_ids=[case["customer_id"]],
        content=(
            f"Fraud claim {case['case_id']} retracted by the cardholder after evidence review on "
            f"{findings['reply_day']}; the remaining complaint concerns game quality."
        ),
        source_refs=[case["case_id"], *[row["reply_id"] for row in state["replies"]]],
        valid_from=date.fromisoformat(findings["reply_day"]),
        confidence=0.95,
        tags=["factual_event"],
    )
    return {"memory_correction_ids": [note_id] if note_id else []}
