"""C06-style route: a trial renewal where the obvious 13.2 route is invalid and is re-planned."""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from domain.events import ActorKind
from runtime.context import RunContext, check, note_matching
from sandbox import unused_portion

STEPS = ["gather_evidence"]
EVIDENCE_USE = "test 13.2 timing, 13.5 disclosure, and unused service"
QUERY = (
    "cancelled recurring trial cancellation after transaction misrepresentation renewal notice "
    "unused portion"
)


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case, merchant_id = state["case"], state["transactions"][0]["merchant_id"]
    governing = date.fromisoformat(
        (case.get("dispute_processing_date") or ctx.clock.now.date().isoformat())[:10]
    )
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve current recurring, trial, and comparable precedent sources",
        {"query": QUERY, "as_of": governing.isoformat(), "kinds": ["policy", "precedent"]},
        lambda: ctx.knowledge.search(QUERY, as_of=governing, limit=12),
    )
    notes = ctx.call(
        "read_memory_notes",
        "Read scoped merchant memory as an unverified lead",
        {"subject_ids": [merchant_id], "as_of": governing.isoformat(), "minimum_confidence": 0.5},
        lambda: ctx.notes.read_current(subject_ids=[merchant_id], as_of=governing),
    )
    return {
        "knowledge": knowledge,
        "memory_notes": notes,
        "candidate_condition": "13.2",
        "findings": {"governing_date": governing.isoformat()},
    }


def evidence_request(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": "merchant",
        "summary": "Requested subscription and trial-disclosure evidence",
        "evidence_types": ["subscription", "trial_notice", "usage"],
        "target_txn_ids": [row["txn_id"] for row in state["transactions"]],
        "rationale": "Test cancellation eligibility and trial representations",
    }


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    packet_id = state["evidence"][0]["packet_id"]
    packet = json.loads(state["evidence"][0]["json"])
    subscription = packet["subscription"]
    billing = date.fromisoformat(subscription["first_billing"][:10])
    cancelled = date.fromisoformat(subscription["cancelled_at"][:10])
    if state["candidate_condition"] == "13.2":
        note = note_matching(state, tags=("recurring",), content_terms=("13.2",))
        if note:
            ctx.notes.reject(
                note,
                reason="It relies on a pre-18-April precedent; current 13.2 is invalid when "
                "cancellation follows the transaction",
                evidence_refs=["VISA-13.2@2026-04-18", "PRE-0012"],
            )
        ctx.event(
            ActorKind.AGENT,
            "verifier",
            "contradiction_detected",
            "Current 13.2 invalidity conflicts with the stale precedent lead",
            {
                "facts": [
                    {"statement": "cancellation followed billing", "source": packet_id},
                    {"statement": "PRE-0012 won under the prior rule", "source": "PRE-0012"},
                ],
                "resolution": "current_policy_controls",
                "impact": "reject_13.2_and_replan",
            },
            ["VISA-13.2@2026-04-18", "PRE-0012", packet_id],
        )
        return [
            check(
                "current_13.2_and_outdated_precedent_retrieved",
                {"VISA-13.2@2026-04-18", "PRE-0012"} <= doc_ids,
                {
                    "doc_ids": sorted(doc_ids),
                    "precedent_treatment": "historical_lead_not_current_rule",
                },
                ["VISA-13.2@2026-04-18", "PRE-0012"],
            ),
            check(
                "13.2_cancellation_before_transaction",
                cancelled <= billing,
                {
                    "billing_date": billing.isoformat(),
                    "cancellation_date": cancelled.isoformat(),
                    "invalid_when_after": True,
                },
                ["VISA-13.2@2026-04-18", packet_id],
            ),
        ]
    email = packet["emails_sent"][0]
    notice_complete = all(
        email[key] for key in ("included_price", "included_renewal_date", "included_cancel_link")
    )
    start, end = subscription["service_period"].split(" to ")
    used_through = cancelled - timedelta(days=1)
    computed = state["findings"]["unused_portion"]
    required = {"VISA-13.5@2026-04-18", "VISA-5-RECURRING-MERCHANT-DUTIES@2026-04-18"}
    return [
        check(
            "13.5_trial_notice_incomplete",
            not notice_complete,
            {"email": email},
            ["VISA-13.5@2026-04-18", packet_id],
        ),
        check(
            "13.5_and_merchant_duties_retrieved",
            required <= doc_ids,
            {"doc_ids": sorted(doc_ids)},
            sorted(required),
        ),
        check(
            "unused_portion_computed",
            computed["service_start"] == start
            and computed["service_end"] == end
            and computed["used_through"] == used_through.isoformat(),
            computed,
            ["VISA-13.5@2026-04-18"],
        ),
    ]


def replan(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    packet = json.loads(state["evidence"][0]["json"])
    subscription = packet["subscription"]
    start, end = subscription["service_period"].split(" to ")
    used_through = date.fromisoformat(subscription["cancelled_at"][:10]) - timedelta(days=1)
    plan = [
        *state["plan"],
        "Reject 13.2 and test the trial disclosures under current 13.5",
        "Compute the unused service portion and re-run verification",
    ]
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "plan_updated",
        "Re-planned from invalid 13.2 to trial misrepresentation",
        {
            "plan_id": "plan-1",
            "full_plan": plan,
            "diff": {
                "added": plan[len(state["plan"]) :],
                "candidate_condition": {"before": "13.2", "after": "13.5"},
            },
            "reason": "verifier rejected post-transaction cancellation under 13.2",
            "trigger_event_type": "verifier_check",
        },
        ["VISA-13.2@2026-04-18", "VISA-13.5@2026-04-18"],
    )
    result = ctx.call(
        "compute_unused_portion",
        "Compute the 13.5 unused portion with an explicit day count",
        {
            "amount": subscription["price"],
            "service_start": start,
            "service_end": end,
            "used_through": used_through.isoformat(),
        },
        lambda: unused_portion(
            amount=Decimal(subscription["price"]),
            service_start=date.fromisoformat(start),
            service_end=date.fromisoformat(end),
            used_through=used_through,
            emitter=ctx.emitter,
        ).model_dump(mode="json"),
    )
    result.update(service_start=start, service_end=end, used_through=used_through.isoformat())
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "todo_updated",
        "Updated bounded investigation tasks after verifier feedback",
        {
            "completed": ["test_13.2_eligibility", "compute_unused_portion"],
            "added": ["test_13.5_trial_notice"],
        },
    )
    return {
        "candidate_condition": "13.5",
        "plan": plan,
        "findings": {**state["findings"], "unused_portion": result},
    }


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, transaction = state["case"], state["transactions"][0]
    unused = state["findings"]["unused_portion"]
    amount = Decimal(unused["unused_portion"])
    provisional = Decimal(case.get("provisional_credit_amount") or "0")
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=True,
        claim_family="misrepresentation_trial",
        network_actions=[
            NetworkAction(
                txn_id=transaction["txn_id"],
                case_id=case["case_id"],
                action="file_dispute",
                condition="13.5",
                amount=amount,
                reason="Trial-end notice omitted amount, date, and cancellation link",
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome="partial",
            credit_amount=amount,
            reversal_amount=provisional - amount,
            liability_amount=provisional - amount,
        ),
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.94,
            flip_fact="A compliant pre-renewal notice documented all required terms.",
        ),
        memory_ops=(
            [
                {
                    "op": "supersede",
                    "note_id": note["note_id"],
                    "reason": "VISA-13.2 changed 2026-04-18",
                    "source_refs": ["VISA-13.2@2026-04-18", "PRE-0012"],
                }
            ]
            if (note := note_matching(state, tags=("recurring",), content_terms=("13.2",)))
            else []
        ),
        citations=[
            {
                "doc_id": "VISA-13.2@2026-04-18",
                "why": "Post-transaction cancellation is invalid under 13.2",
            },
            {"doc_id": "VISA-13.5@2026-04-18", "why": "Trial terms were materially misrepresented"},
            {
                "doc_id": "VISA-5-RECURRING-MERCHANT-DUTIES@2026-04-18",
                "why": "Required renewal notice elements",
            },
        ],
        letters=["reg_z_partial_resolution"],
        confidence=0.94,
        explanation_for_cardholder=(
            "Cancellation occurred after billing, so 13.2 does not apply. Because the "
            "required trial-end notice was missing, we disputed $118.24 under 13.5 and "
            "reversed only the $1.64 used portion."
        ),
    )


def curate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    note = note_matching(state, tags=("recurring",), content_terms=("13.2",))
    if not note:
        return {}
    correction = ctx.notes.supersede(
        note,
        content=(
            "For disputes processed on or after 2026-04-18, Visa 13.2 is invalid when "
            "cancellation occurs after the transaction date."
        ),
        source_refs=["VISA-13.2@2026-04-18", "PRE-0012"],
        valid_from=date(2026, 4, 18),
        confidence=0.99,
        reason="VISA-13.2 changed on 2026-04-18",
    )
    return {"memory_correction_ids": [correction]}
