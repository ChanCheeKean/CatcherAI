"""C19-style route: a non-receipt claim against a merchant that memory says "never ships".

Memory is only a lead. The route verifies the pattern against current evidence, lets the
cardholder confirm delivery, then time-bounds the stale pattern instead of deleting history.
"""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from domain.events import ActorKind
from runtime.context import RunContext, check
from sandbox import pattern_validity_window

STEPS = ["gather_evidence", "ask_cardholder"]
EVIDENCE_USE = "test delivery with carrier scans and proof of delivery"
QUERY = (
    "VISA 13.1 merchandise not received proof of delivery REGZ 1026.13 LFB SOP DSP 005 memory "
    "governance"
)
REQUIRED = {"VISA-13.1@2026-04-18", "REGZ-1026.13", "LFB-SOP-DSP-005@v1"}
OPERATIONAL_CHANGE = re.compile(r"\b(moved|switched|changed)\b.*\bfulfil?ment\b", re.I)
CONFIRMS_RECEIPT = re.compile(r"\b(yes|arrived|received|it was on)\b", re.I)


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case = state["case"]
    merchant_id = state["transactions"][0]["merchant_id"]
    today = ctx.clock.now.date()
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve non-receipt, billing-error and memory-governance rules",
        {"query": QUERY, "as_of": case["opened_at"][:10], "kinds": ["policy", "precedent"]},
        lambda: ctx.knowledge.search(
            QUERY, as_of=date.fromisoformat(case["opened_at"][:10]), limit=12
        ),
    )
    related = ctx.call(
        "find_related_merchants",
        "Resolve near-duplicate merchant IDs before reading merchant memory",
        {"merchant_id": merchant_id},
        lambda: ctx.data.related_merchants(merchant_id),
    )
    merchant_ids = [merchant_id, *[row["merchant_id"] for row in related]]
    notes = ctx.call(
        "read_memory_notes",
        "Read merchant memory for every resolved merchant ID as leads",
        {"subject_ids": merchant_ids, "as_of": today.isoformat(), "minimum_confidence": 0.5},
        lambda: ctx.notes.read_current(subject_ids=merchant_ids, as_of=today),
    )
    research = ctx.call(
        "search_research",
        "Look for dated merchant changes that could end the pattern",
        {"merchant_id": merchant_id, "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.research_for_merchant(merchant_id),
    )
    change = next((row for row in research if OPERATIONAL_CHANGE.search(row["body"])), None)
    changed_on = json.loads(change["meta_json"])["published_at"] if change else None
    activity = ctx.call(
        "get_merchant_activity",
        "Compare dispute history with orders since the documented change",
        {"merchant_ids": merchant_ids, "since": changed_on or "2026-01-01"},
        lambda: ctx.data.merchant_activity(merchant_ids, since=changed_on or "2026-01-01"),
    )
    patterns = [note for note in notes if "pattern" in note["tags"]]
    observations = [note for note in notes if note["kind"] == "episodic"]
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "hypothesis_updated",
        "Opened reputation-versus-current-evidence hypotheses",
        {
            "path": f"/case/{case['case_id']}/hypotheses.json",
            "diff": {
                "H1_merchant_failed_to_ship": {
                    "memory_leads": [note["note_id"] for note in patterns]
                },
                "H2_delivered_late": {"for": [change["doc_id"]] if change else []},
            },
        },
        [note["note_id"] for note in notes],
    )
    return {
        "knowledge": knowledge,
        "memory_notes": notes,
        "findings": {
            "merchant_ids": merchant_ids,
            "related_merchants": related,
            "research": research,
            "change_doc": change["doc_id"] if change else None,
            "changed_on": changed_on,
            "activity": activity,
            "pattern_note_ids": [note["note_id"] for note in patterns],
            "observation_note_ids": [note["note_id"] for note in observations],
        },
    }


def on_evidence(
    ctx: RunContext, state: dict[str, Any], packets: list[dict[str, Any]]
) -> dict[str, Any]:
    packet = json.loads(packets[0]["json"])
    packet_id = packets[0]["packet_id"]
    customer = ctx.call(
        "get_customer_with_address",
        "Compare the delivery address with the home address on file",
        {"customer_id": state["case"]["customer_id"]},
        lambda: ctx.data.customer_with_address(state["case"]["customer_id"]),
    )
    shipment = packet["shipments"][0]
    delivered = next(
        (event for event in shipment["events"] if event["status"] == "delivered"), None
    )
    full_address = bool(delivered) and customer["line1"] in shipment["proof_of_delivery"]["address"]
    findings = {
        **state["findings"],
        "delivered_at": delivered["ts"] if delivered else None,
        "full_address_match": full_address,
        "customer": customer,
    }
    changed_on = findings["changed_on"]
    for note in state["memory_notes"]:
        if (
            note["note_id"] in findings["pattern_note_ids"]
            and changed_on
            and note["valid_to"] is None
        ):
            ctx.notes.reject(
                note,
                reason=f"Pattern has no validity bound and stopped being true on {changed_on}; "
                "the current order was delivered",
                evidence_refs=[packet_id, findings["change_doc"]],
            )
        elif note["note_id"] in findings["observation_note_ids"]:
            ctx.notes.verify(
                note,
                reason="Observation predates the documented change and remains true for its date",
                evidence_refs=[*note["source_refs"], findings["change_doc"]],
            )
    if full_address and findings["pattern_note_ids"]:
        ctx.event(
            ActorKind.AGENT,
            "verifier",
            "contradiction_detected",
            "Consolidated merchant reputation conflicts with current delivery evidence",
            {
                "facts": [
                    {
                        "statement": "memory: merchant rarely ships",
                        "source": findings["pattern_note_ids"][0],
                    },
                    {
                        "statement": f"delivered {delivered['ts'][:10]} to the full home address",
                        "source": packet_id,
                    },
                    {
                        "statement": f"fulfilment changed {changed_on}",
                        "source": findings["change_doc"],
                    },
                ],
                "resolution": "memory stale after the documented change",
                "impact": "ask cardholder; time-bound memory",
            },
            [*findings["pattern_note_ids"], packet_id, findings["change_doc"] or ""],
        )
    return {"findings": findings}


def cardholder_question(ctx: RunContext, state: dict[str, Any]) -> dict[str, str]:
    delivered = state["findings"]["delivered_at"][:10]
    return {
        "question": f"Our delivery scan shows your package was delivered on {delivered}. "
        "Has the package arrived since October 16?",
        "rationale": "Delivery evidence exists; only the cardholder can confirm receipt",
    }


def on_reply(ctx: RunContext, state: dict[str, Any], reply: dict[str, Any]) -> dict[str, Any]:
    return {
        "findings": {
            **state["findings"],
            "receipt_confirmed": bool(CONFIRMS_RECEIPT.search(reply["text"])),
            "validity_window": _validity_window(ctx, state),
        }
    }


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = state["findings"]
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    changed_on = findings["changed_on"]
    disputes_after = [
        row["case_id"]
        for row in findings["activity"]["disputes"]
        if changed_on
        and row["processing_date"] >= changed_on
        and row["case_id"] != state["case_id"]
    ]
    orders_after = [
        row["txn_id"]
        for row in findings["activity"]["orders_since"]
        if row["txn_id"] not in {txn["txn_id"] for txn in state["transactions"]}
    ]
    return [
        check(
            "delivery_sources_retrieved",
            REQUIRED <= doc_ids,
            {"required": sorted(REQUIRED), "doc_ids": sorted(doc_ids)},
            sorted(REQUIRED),
        ),
        check(
            "delivered_to_full_home_address",
            findings["full_address_match"],
            {"delivered_at": findings["delivered_at"]},
            [state["evidence"][0]["packet_id"]],
        ),
        check(
            "pattern_ended_after_documented_change",
            bool(changed_on) and not disputes_after and len(orders_after) >= 3,
            {
                "changed_on": changed_on,
                "orders_after": orders_after,
                "disputes_after": disputes_after,
            },
            [findings["change_doc"] or "", *orders_after],
        ),
        check(
            "cardholder_confirmed_receipt",
            findings.get("receipt_confirmed", False),
            {"reply_ids": [row["reply_id"] for row in state["replies"]]},
            [row["reply_id"] for row in state["replies"]],
        ),
        check(
            "near_duplicate_merchants_resolved",
            len(findings["merchant_ids"]) > 1,
            {"merchant_ids": findings["merchant_ids"]},
            findings["merchant_ids"],
        ),
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, transaction, findings = state["case"], state["transactions"][0], state["findings"]
    amount = Decimal(transaction["billing_amount"])
    window = findings["validity_window"]
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=False,
        claim_family="not_received",
        network_actions=[
            NetworkAction(
                txn_id=transaction["txn_id"],
                case_id=case["case_id"],
                action="no_dispute",
                reason="delivered; cardholder withdrew",
                amount=amount,
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome="withdrawn_after_clarification",
            credit_amount=Decimal("0"),
            reversal_amount=Decimal(case.get("provisional_credit_amount") or "0"),
            liability_amount=amount,
        ),
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.97,
            flip_fact="Carrier scans or the cardholder show the parcel did not arrive.",
        ),
        memory_ops=[
            {
                "op": "consolidate",
                "from_notes": findings["observation_note_ids"],
                "into_scope": "merchant",
                "subject_ids": findings["merchant_ids"],
                "valid_from": window["valid_from"],
                "valid_to": window["valid_to"],
                "source_refs": [findings["change_doc"]],
            },
            *[
                {
                    "op": "supersede",
                    "note_id": note_id,
                    "reason": f"pattern ended {findings['changed_on']}",
                    "source_refs": [findings["change_doc"], state["evidence"][0]["packet_id"]],
                }
                for note_id in findings["pattern_note_ids"]
            ],
        ],
        letters=["reg_z_withdrawal_confirmation_with_credit_reversal"],
        citations=[
            {"doc_id": "VISA-13.1@2026-04-18", "why": "Merchandise was delivered"},
            {
                "doc_id": "REGZ-1026.13",
                "why": "Withdrawn billing-error notice and temporary credit reversal",
            },
            {"doc_id": "LFB-SOP-DSP-005@v1", "why": "Memory is a lead; time-bound stale patterns"},
        ],
        hypotheses=[
            {"id": "H1", "label": "merchant failed to ship", "status": "rejected"},
            {"id": "H2", "label": "delivered one day late", "status": "supported"},
        ],
        confidence=0.97,
        explanation_for_cardholder=(
            "Thanks for confirming the poster arrived. The carrier delivered it on "
            f"{findings['delivered_at'][:10]}, so we closed your claim at your request and "
            f"reversed the temporary credit of ${amount}."
        ),
    )


def curate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    findings = state["findings"]
    window = findings["validity_window"]
    observations = [
        note
        for note in state["memory_notes"]
        if note["note_id"] in findings["observation_note_ids"]
    ]
    source_cases = sorted({ref for note in observations for ref in note["source_refs"]})
    consolidated = ctx.notes.consolidate(
        observations,
        content=(
            f"Non-receipt claims against {' / '.join(findings['merchant_ids'])} from "
            f"{window['valid_from']} to {window['valid_to']} showed parcels stuck at "
            "'label created'. "
            "The pattern ended when fulfilment moved to a new carrier; verify current evidence."
        ),
        subject_ids=findings["merchant_ids"],
        source_refs=[
            *[note["note_id"] for note in observations],
            *source_cases,
            findings["change_doc"],
        ],
        valid_from=date.fromisoformat(window["valid_from"]),
        valid_to=date.fromisoformat(window["valid_to"]),
        confidence=0.9,
        entity_merge_evidence=[
            f"near_duplicate_merchants:{row['merchant_id']} same acquirer {row['acquirer_id']} "
            f"and MCC {row['mcc']}"
            for row in findings["related_merchants"]
        ],
    )
    for note in state["memory_notes"]:
        if note["note_id"] in findings["pattern_note_ids"] and consolidated:
            ctx.notes.supersede(
                note,
                replaced_by=consolidated,
                valid_to=date.fromisoformat(window["valid_to"]),
                source_refs=[findings["change_doc"], state["evidence"][0]["packet_id"]],
                reason=f"pattern ended {findings['changed_on']}",
            )
    return {"memory_correction_ids": [consolidated] if consolidated else []}


def _validity_window(ctx: RunContext, state: dict[str, Any]) -> dict[str, str]:
    findings = state["findings"]
    observed = {
        ref
        for note in state["memory_notes"]
        if note["note_id"] in findings["observation_note_ids"]
        for ref in note["source_refs"]
    }
    dates = [
        row["processing_date"]
        for row in findings["activity"]["disputes"]
        if row["case_id"] in observed
    ]
    return ctx.call(
        "compute_pattern_validity",
        "Bound the merchant pattern to the period it was observed",
        {"observation_dates": dates, "ended_on": findings["changed_on"]},
        lambda: pattern_validity_window(
            observation_dates=[date.fromisoformat(value) for value in dates],
            ended_on=date.fromisoformat(findings["changed_on"]),
            refs=sorted(observed),
            emitter=ctx.emitter,
        ),
    )
