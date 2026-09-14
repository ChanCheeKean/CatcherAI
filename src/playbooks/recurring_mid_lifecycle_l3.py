"""C15-style route: a recurring charge already in the network lifecycle plus a newer related charge.

A late Dispute Response contradicts the intake statement, so the investigator re-plans, asks the
cardholder to review the evidence, then fans out one LangGraph branch per charge. Each branch keeps
its own lifecycle stage, clocks and decision.
"""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from domain.events import ActorKind
from memory.curator import duplicate_groups
from runtime.context import RunContext, check
from sandbox import case_clocks, window_deadlines

STEPS = ["gather_evidence"]
EVIDENCE_USE = "test the merchant's notice-period and usage evidence against the intake statement"
QUERY = (
    "VISA 13.2 cancelled recurring VISA 11.2 lifecycle dispute response pre-arbitration REGZ "
    "1026.13 "
    "billing error VISA cardholder letter certification"
)
REQUIRED = {
    "VISA-13.2@2026-04-18",
    "VISA-11.2-LIFECYCLE@2026-04-18",
    "REGZ-1026.13",
    "VISA-CARDHOLDER-LETTER-CERTIFICATION@2026-04-18",
}
CERTIFICATION = "cardholder contacted to review evidence"
NO_VISITS = re.compile(r"haven'?t been since", re.I)
CONFIRMS_VISITS = re.compile(r"\b(yes|went|visited)\b", re.I)


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case = state["case"]
    related = [
        case["case_id"],
        *[value for value in (case.get("related_case_ids") or "").split(",") if value],
    ]
    notice = date.fromisoformat(case["opened_at"][:10])
    lifecycle = ctx.call(
        "get_dispute_events",
        "Load where each related case sits in the network lifecycle",
        {"case_ids": related, "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.dispute_events(related),
    )
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve lifecycle, 13.2, certification and Reg Z rules",
        {"query": QUERY, "as_of": notice.isoformat(), "kinds": ["policy", "precedent"]},
        lambda: ctx.knowledge.search(QUERY, as_of=notice, limit=24),
    )
    communications = ctx.call(
        "get_case_communications",
        "Read the cancellation email, the merchant auto-reply and intake notes",
        {"case_id": case["case_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.case_communications(case["case_id"]),
    )
    notes = ctx.call(
        "read_memory_notes",
        "Read customer contact preferences as leads",
        {
            "subject_ids": [case["customer_id"]],
            "as_of": ctx.clock.now.date().isoformat(),
            "minimum_confidence": 0.5,
        },
        lambda: ctx.notes.read_current(
            subject_ids=[case["customer_id"]], as_of=ctx.clock.now.date()
        ),
    )
    merchant_id = state["transactions"][0]["merchant_id"]
    merchant = ctx.call(
        "get_merchant",
        "Resolve the merchant name for the cardholder explanation",
        {"merchant_id": merchant_id},
        lambda: ctx.data.merchant(merchant_id),
    )
    stages = {row["case_id"]: row["event_type"] for row in lifecycle}
    ctx.event(
        ActorKind.MEMORY,
        "case_file",
        "case_file_updated",
        "Loaded the lifecycle stage of every related charge",
        {"path": f"/case/{case['case_id']}/tracks.json", "diff": {"latest_event_by_case": stages}},
        [row["event_id"] for row in lifecycle],
    )
    return {
        "knowledge": knowledge,
        "memory_notes": notes,
        "findings": {
            "related_case_ids": related,
            "lifecycle": lifecycle,
            "communications": communications,
            "merchant_name": merchant["dba_name"],
        },
    }


def on_evidence(
    ctx: RunContext, state: dict[str, Any], packets: list[dict[str, Any]]
) -> dict[str, Any]:
    packet = json.loads(packets[0]["json"])
    packet_id = packets[0]["packet_id"]
    comms = state["findings"]["communications"]
    intake = next(row for row in comms if NO_VISITS.search(row["body"]))
    notice_sent = date.fromisoformat(
        re.search(r"\d{4}-\d{2}-\d{2}", intake["attachments"]).group(0)
    )
    notice_period = ctx.call(
        "compute_window_deadlines",
        "Compute when the agreement's 30-day written notice period ends",
        {
            "events": {"cancellation_notice": notice_sent.isoformat()},
            "days": 30,
            "rule": "membership agreement clause 7: thirty days' written notice",
        },
        lambda: {
            key: value.isoformat()
            for key, value in window_deadlines(
                events={"cancellation_notice": notice_sent},
                days=30,
                rule="clause 7 written notice",
                refs=[packet_id, intake["comm_id"]],
                emitter=ctx.emitter,
            ).items()
        },
    )
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "contradiction_detected",
        "Badge scans contradict the cardholder's statement about September use",
        {
            "facts": [
                {"statement": "haven't been since August", "source": intake["comm_id"]},
                {
                    "statement": "badge scans on "
                    + ", ".join(scan["ts"][:10] for scan in packet["badge_scans"]),
                    "source": packet_id,
                },
            ],
            "resolution": "cardholder must review the evidence before any response decision",
            "impact": "contact_cardholder_then_decide_each_charge",
        },
        [intake["comm_id"], packet_id],
    )
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "plan_updated",
        "Re-planned after the late Dispute Response",
        {
            "plan_id": "plan-1",
            "full_plan": [
                *state["plan"],
                "Share badge scans with the cardholder",
                "Decide each charge on its own lifecycle track",
            ],
            "diff": {"added_steps": ["ask_cardholder"]},
            "reason": (
                "merchant evidence contradicts the intake statement; certification duty applies"
            ),
            "trigger_event_type": "contradiction_detected",
        },
        [packet_id],
    )
    return {
        "steps": [*state["steps"], "ask_cardholder"],
        "findings": {
            **state["findings"],
            "response": packet,
            "notice_period": notice_period,
            "final_billing_date": packet["cancellation"]["auto_reply_final_billing_date"],
            "intake_comm_id": intake["comm_id"],
        },
    }


def cardholder_question(ctx: RunContext, state: dict[str, Any]) -> dict[str, str]:
    scans = [scan["ts"][:10] for scan in state["findings"]["response"]["badge_scans"]]
    prefers_email = any("email" in note["content"].casefold() for note in state["memory_notes"])
    return {
        "question": (
            f"The club's Dispute Response includes badge scans on {' and '.join(scans)}. "
            "Can you explain those visits?"
        ),
        "rationale": (
            "The issuer must let the cardholder review contradicting evidence before responding"
        ),
        "channel": "email" if prefers_email else "secure_message",
    }


def on_reply(ctx: RunContext, state: dict[str, Any], reply: dict[str, Any]) -> dict[str, Any]:
    confirmed = bool(CONFIRMS_VISITS.search(reply["text"]))
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "plan_updated",
        "Cardholder reviewed the evidence; analyze each charge independently",
        {
            "plan_id": "plan-1",
            "full_plan": [*state["plan"], "Fan out one track per charge"],
            "diff": {"added_steps": ["analyze_tracks"], "cardholder_confirmed_visits": confirmed},
            "reason": "certification complete",
            "trigger_event_type": "persona_reply",
        },
        [reply["reply_id"]],
    )
    return {
        "steps": [*state["steps"], "analyze_tracks"],
        "findings": {
            **state["findings"],
            "cardholder_confirmed_visits": confirmed,
            "certification": CERTIFICATION,
        },
    }


def tracks(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"branch_id": f"track-{case_id}", "case_id": case_id}
        for case_id in state["findings"]["related_case_ids"]
    ]


async def analyze_track(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    """One charge, one lifecycle stage, one set of clocks; no facts borrowed from sibling tracks."""

    case_id, findings = state["track"]["case_id"], state["findings"]
    case = ctx.call(
        "get_case",
        f"Load lifecycle fields for {case_id}",
        {"case_id": case_id, "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.get_case(case_id),
        actor="lifecycle_track_analyst",
    )
    transactions = ctx.call(
        "get_case_transactions",
        f"Load the charge disputed in {case_id}",
        {"case_id": case_id, "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.get_case_transactions(case_id),
        actor="lifecycle_track_analyst",
    )
    account = ctx.data.account(case["account_id"])
    holidays = [
        date.fromisoformat(row["date"])
        for row in ctx.data.bank_holidays(since=case["opened_at"][:10], until="2027-12-31")
    ]
    clocks = ctx.call(
        "compute_case_clocks",
        f"Compute {case_id}'s own network and Reg Z clocks",
        {
            "case_id": case_id,
            "notice_date": case["opened_at"][:10],
            "statement_cycle_day": int(account["statement_cycle_day"]),
            "response_processing_date": case.get("response_processing_date") or None,
            "dispute_processing_date": case.get("dispute_processing_date") or None,
        },
        lambda: case_clocks(
            case=case,
            account=account,
            transactions=transactions,
            holidays=holidays,
            emitter=ctx.emitter,
        ).model_dump(mode="json"),
        actor="lifecycle_track_analyst",
    )
    charge = transactions[0]
    charge_date = charge["txn_local_datetime"][:10]
    amount = Decimal(charge["billing_amount"])
    if case.get("response_processing_date"):
        within_notice = charge_date <= findings["notice_period"]["cancellation_notice"]
        outcome = {
            "action": "accept_dispute_response"
            if within_notice and findings["cardholder_confirmed_visits"]
            else "pre_arbitration",
            "condition": None,
            "certification": [findings["certification"]],
            "reason": (
                "charge falls inside the disclosed 30-day notice period; cardholder confirmed use"
            ),
            "resolution": {
                "outcome": "denied_with_explanation",
                "credit_amount": "0",
                "reversal_amount": str(Decimal(case.get("provisional_credit_amount") or amount)),
                "liability_amount": str(amount),
            },
        }
    else:
        after_final_billing = charge_date > findings["final_billing_date"]
        outcome = {
            "action": "file_dispute" if after_final_billing else "no_dispute",
            "condition": "13.2" if after_final_billing else None,
            "certification": [],
            "reason": "charged after the merchant's own stated final billing date",
            "resolution": {
                "outcome": "provisional_credit_pending_network",
                "credit_amount": str(amount),
                "reversal_amount": "0",
                "liability_amount": "0",
            },
        }
    await ctx.delegate(
        case_id,
        [
            {
                "subagent_type": "lifecycle_track_analyst",
                "description": json.dumps(
                    {
                        "task": "Check this track's lifecycle action and clocks in isolation",
                        "case_id": case_id,
                        "stage": case["stage"],
                        "clocks": clocks,
                        "proposed": outcome,
                    }
                ),
            }
        ],
    )
    return {
        "branch_id": state["track"]["branch_id"],
        "case_id": case_id,
        "txn_id": charge["txn_id"],
        "stage": case["stage"],
        "charge_date": charge_date,
        "amount": str(amount),
        "deadlines": clocks["deadlines"],
        **outcome,
    }


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = state["findings"]
    results = {row["case_id"]: row for row in findings["tracks"]}
    primary = results[state["case_id"]]
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    reply_ids = [row["reply_id"] for row in state["replies"]]
    return [
        check(
            "lifecycle_sources_retrieved",
            REQUIRED <= doc_ids,
            {"required": sorted(REQUIRED), "doc_ids": sorted(doc_ids)},
            sorted(REQUIRED),
        ),
        check(
            "tracks_kept_separate",
            len(results) == len(findings["related_case_ids"])
            and len({row["txn_id"] for row in results.values()}) == len(results),
            {"tracks": {case_id: row["txn_id"] for case_id, row in results.items()}},
            list(results),
        ),
        check(
            "pre_arb_deadline_not_missed",
            primary["deadlines"].get("pre_arb_deadline", "") >= ctx.clock.now.date().isoformat(),
            primary["deadlines"],
            [state["case_id"]],
        ),
        check(
            "cardholder_reviewed_evidence_before_response",
            bool(reply_ids) and findings["cardholder_confirmed_visits"],
            {"reply_ids": reply_ids},
            reply_ids,
        ),
        check(
            "later_charge_after_stated_final_billing",
            all(
                row["charge_date"] > findings["final_billing_date"]
                for row in results.values()
                if row["action"] == "file_dispute"
            ),
            {
                "final_billing_date": findings["final_billing_date"],
                "charges": {row["case_id"]: row["charge_date"] for row in results.values()},
            },
            [findings["intake_comm_id"], state["evidence"][0]["packet_id"]],
        ),
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case = state["case"]
    results = sorted(state["findings"]["tracks"], key=lambda row: row["case_id"])
    primary = next(row for row in results if row["case_id"] == case["case_id"])
    merchant_name = state["findings"]["merchant_name"]
    final_billing = date.fromisoformat(state["findings"]["final_billing_date"])
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=True,
        claim_family="cancelled_recurring",
        network_actions=[
            NetworkAction(
                txn_id=row["txn_id"],
                case_id=row["case_id"],
                action=row["action"],
                condition=row["condition"],
                amount=Decimal(row["amount"]),
                reason=row["reason"],
                certification=row["certification"],
            )
            for row in results
        ],
        cardholder_resolution=CardholderResolution(**primary["resolution"]),
        case_resolutions=[{"case_id": row["case_id"], **row["resolution"]} for row in results],
        deadlines={row["case_id"]: row["deadlines"] for row in results},
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.93,
            flip_fact=(
                "The cardholder denies the September visits or the notice term was not disclosed."
            ),
        ),
        memory_ops=[
            {
                "op": "dedupe",
                "subject_id": case["customer_id"],
                "scope": "customer",
                "tags": ["contact_preference"],
            }
        ],
        letters=["reg_z_denial_with_rebill_notice", "reg_z_dispute_filed_notice"],
        citations=[
            {
                "doc_id": "VISA-13.2@2026-04-18",
                "why": "Cancelled recurring transaction requirements",
            },
            {
                "doc_id": "VISA-11.2-LIFECYCLE@2026-04-18",
                "why": "Dispute Response and pre-arbitration stages",
            },
            {
                "doc_id": "VISA-CARDHOLDER-LETTER-CERTIFICATION@2026-04-18",
                "why": "Cardholder review before responding",
            },
            {"doc_id": "REGZ-1026.13", "why": "Billing-error resolution and re-billing notice"},
        ],
        hypotheses=[
            {
                "id": "H1",
                "label": "September dues fall inside the disclosed notice period",
                "status": "supported",
            },
            {
                "id": "H2",
                "label": "October charge billed after the stated final billing date",
                "status": "supported",
            },
        ],
        confidence=0.93,
        explanation_for_cardholder=(
            "Thank you for confirming the September visits. Your agreement required 30 days' "
            "notice, so the September 1 dues stand and we will re-bill "
            f"${primary['amount']} with a written notice. "
            f"The later charge came after {merchant_name}'s own stated final billing date of "
            f"{final_billing.strftime('%B %-d')}, so "
            "we credited it and opened a separate dispute for that charge."
        ),
    )


def curate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    groups = duplicate_groups(state.get("memory_notes", []))
    kept = [ctx.notes.dedupe(group) for group in groups]
    if not kept:
        ctx.notes.skip(
            candidate="customer contact preference",
            reason="no duplicate notes to consolidate",
            refs=[state["case"]["customer_id"]],
        )
    return {"memory_correction_ids": kept}
