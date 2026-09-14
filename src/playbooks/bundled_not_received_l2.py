"""C03-style route: several low-value non-receipt charges split by the write-off SOP."""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from runtime.context import RunContext, check, note_matching
from sandbox import write_off_eligibility

STEPS = ["gather_evidence"]
EVIDENCE_USE = "test successful delivery for the transaction requiring 13.1"
QUERY = (
    "goodwill write-off threshold not received digital goods immediate delivery dispute lifecycle"
)


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case = state["case"]
    intake = date.fromisoformat(case["opened_at"][:10])
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve the write-off and not-received rules effective at intake",
        {"query": QUERY, "as_of": intake.isoformat(), "kinds": ["policy", "precedent"]},
        lambda: ctx.knowledge.search(QUERY, as_of=intake, limit=12),
    )
    notes = ctx.call(
        "read_memory_notes",
        "Read only current procedural notes as leads to verify",
        {
            "subject_ids": ["LFB-SOP-DSP-002"],
            "as_of": intake.isoformat(),
            "minimum_confidence": 0.5,
        },
        lambda: ctx.notes.read_current(subject_ids=["LFB-SOP-DSP-002"], as_of=intake),
    )
    account = ctx.call(
        "get_account",
        "Verify the account-status write-off prerequisite",
        {"account_id": case["account_id"]},
        lambda: ctx.data.account(case["account_id"]),
    )
    since = intake.replace(year=intake.year - 1)
    prior = ctx.call(
        "get_prior_disputes",
        "Verify the twelve-month prior-dispute prerequisite",
        {
            "customer_id": case["customer_id"],
            "current_case_id": case["case_id"],
            "since": since.isoformat(),
            "as_of": ctx.clock.now.isoformat(),
        },
        lambda: ctx.data.prior_disputes(case["customer_id"], case["case_id"], since.isoformat()),
    )
    threshold = _policy_threshold(knowledge, "LFB-SOP-DSP-002@v4")
    delinquency = 0 if account["status"] == "open" else 31
    results = [
        ctx.call(
            "compute_write_off_eligibility",
            f"Apply the current per-transaction threshold to {row['txn_id']}",
            {
                "txn_id": row["txn_id"],
                "amount": row["billing_amount"],
                "threshold": str(threshold),
                "prior_dispute_count": len(prior),
                "delinquency_days": delinquency,
                "merchant_cluster_open": False,
            },
            lambda row=row: write_off_eligibility(
                txn_id=row["txn_id"],
                amount=Decimal(row["billing_amount"]),
                threshold=threshold,
                prior_dispute_count=len(prior),
                delinquency_days=delinquency,
                merchant_cluster_open=False,
                emitter=ctx.emitter,
            ).model_dump(mode="json"),
        )
        for row in state["transactions"]
    ]
    return {
        "findings": {"write_off_results": results},
        "knowledge": knowledge,
        "memory_notes": notes,
        "candidate_condition": "13.1",
    }


def evidence_request(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": "merchant",
        "summary": "Requested digital-delivery evidence for the disputable item",
        "evidence_types": ["order", "digital_delivery", "license_activation"],
        "target_txn_ids": [
            row["txn_id"] for row in state["findings"]["write_off_results"] if not row["eligible"]
        ],
        "rationale": "Verify non-receipt only for transactions above the write-off threshold",
    }


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    note = note_matching(state, tags=("write_off", "threshold"))
    if note:
        ctx.notes.reject(
            note,
            reason="The note's $25 threshold cites superseded SOP v3; SOP v4 sets $15 as of intake",
            evidence_refs=["LFB-SOP-DSP-002@v4"],
        )
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    eligible = {row["txn_id"]: row["eligible"] for row in state["findings"]["write_off_results"]}
    amounts = {row["txn_id"]: Decimal(row["billing_amount"]) for row in state["transactions"]}
    eligible_amounts = sorted(amounts[txn] for txn, ok in eligible.items() if ok)
    ineligible_amounts = sorted(amounts[txn] for txn, ok in eligible.items() if not ok)
    packets = [json.loads(row["json"]) for row in state["evidence"]]
    downloads = sum(int(packet.get("successful_downloads", 0)) for packet in packets)
    required = {"LFB-SOP-DSP-002@v4", "VISA-13.1@2026-04-18", "VISA-11.2-LIFECYCLE@2026-04-18"}
    return [
        check(
            "current_write_off_policy_retrieved",
            required <= doc_ids,
            {"doc_ids": sorted(doc_ids)},
            ["LFB-SOP-DSP-002@v4"],
        ),
        check(
            "transaction_level_split",
            bool(eligible_amounts)
            and bool(ineligible_amounts)
            and max(eligible_amounts) < min(ineligible_amounts),
            {
                "eligibility_by_txn": eligible,
                "eligible_amounts": [str(v) for v in eligible_amounts],
                "ineligible_amounts": [str(v) for v in ineligible_amounts],
            },
            list(eligible),
        ),
        check(
            "digital_non_receipt_evidence",
            downloads == 0,
            {"successful_downloads": downloads},
            [row["packet_id"] for row in state["evidence"]],
        ),
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case = state["case"]
    results = {row["txn_id"]: row for row in state["findings"]["write_off_results"]}
    network_actions, credited = [], Decimal("0")
    for row in state["transactions"]:
        amount = Decimal(row["billing_amount"])
        credited += amount
        eligible = results[row["txn_id"]]["eligible"]
        network_actions.append(
            NetworkAction(
                txn_id=row["txn_id"],
                case_id=case["case_id"],
                action="write_off_no_chargeback" if eligible else "file_dispute",
                reason="Current per-transaction goodwill threshold and prerequisites"
                if eligible
                else "Immediate digital goods were not delivered",
                condition=None if eligible else "13.1",
                amount=amount,
            )
        )
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=True,
        claim_family="not_received",
        split_case_required=True,
        network_actions=network_actions,
        cardholder_resolution=CardholderResolution(
            outcome="credited",
            credit_amount=credited,
            reversal_amount=Decimal("0"),
            liability_amount=Decimal("0"),
        ),
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.96,
            flip_fact="A successful download or a prior-dispute disqualifier existed.",
        ),
        memory_ops=(
            [
                {
                    "op": "supersede",
                    "note_id": note["note_id"],
                    "replaced_by": "LFB-SOP-DSP-002@v4",
                    "source_refs": ["LFB-SOP-DSP-002@v4"],
                }
            ]
            if (note := note_matching(state, tags=("write_off", "threshold")))
            else []
        ),
        citations=[
            {
                "doc_id": "LFB-SOP-DSP-002@v4",
                "why": "Current per-transaction $15 write-off threshold",
            },
            {"doc_id": "VISA-13.1@2026-04-18", "why": "Digital goods not received"},
            {
                "doc_id": "VISA-11.2-LIFECYCLE@2026-04-18",
                "why": "Transaction-level network dispute lifecycle",
            },
        ],
        letters=["reg_z_credit_and_dispute_notice"],
        confidence=0.96,
        explanation_for_cardholder=(
            "We credited both failed font purchases. The $12.49 item qualifies for a "
            "per-transaction goodwill write-off; we filed a separate 13.1 dispute for "
            "the $19.99 item after confirming no successful download."
        ),
    )


def curate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    note = note_matching(state, tags=("write_off", "threshold"))
    if not note:
        return {}
    correction = ctx.notes.supersede(
        note,
        content=(
            "Non-fraud claims at or below $15 may qualify for a per-transaction goodwill "
            "write-off when all SOP v4 checks pass."
        ),
        source_refs=["LFB-SOP-DSP-002@v4"],
        valid_from=date(2026, 7, 1),
        confidence=0.99,
        reason="LFB-SOP-DSP-002 v4 replaced the v3 threshold",
    )
    return {"memory_correction_ids": [correction]}


def _policy_threshold(rows: list[dict[str, Any]], doc_id: str) -> Decimal:
    document = next((row for row in rows if row["doc_id"] == doc_id), None)
    if document is None:
        raise RuntimeError(f"required policy was not retrieved: {doc_id}")
    match = re.search(r"(?:≤|at or below)\s*\$?([0-9]+(?:\.[0-9]+)?)", document["body"])
    if match is None:
        raise RuntimeError(f"policy threshold is not machine-readable: {doc_id}")
    return Decimal(match.group(1))
