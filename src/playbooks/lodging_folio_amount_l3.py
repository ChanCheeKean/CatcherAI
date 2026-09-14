"""C05-style route: a hotel folio above the quoted rate, decided line by line.

Two conditions look applicable but are invalid for T&E price differences, so the folio is
decomposed and each line is tested by an isolated specialist against disclosures, initials and the
hotel's logs.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from domain.events import ActorKind
from runtime.context import RunContext, check
from sandbox import folio_line_amounts

STEPS = ["gather_evidence", "run_specialists"]
EVIDENCE_USE = "compare folio lines with the registration card and the valet log"
QUERY = (
    "VISA 12.5 incorrect amount T&E quoted VISA 13.3 price discrepancy VISA 13.1 services not "
    "provided "
    "REGZ 1026.13 PRE 0007 hotel upgrade"
)
REQUIRED = {"VISA-12.5@2026-04-18", "VISA-13.3@2026-04-18", "VISA-13.1@2026-04-18", "REGZ-1026.13"}
RIDE_HAIL = ("RIDEHOP", "UBER", "LYFT")


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case, txn = state["case"], state["transactions"][0]
    communications = ctx.call(
        "get_case_communications",
        "Read the booking disclosures, folio and merchant correspondence",
        {"case_id": case["case_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.case_communications(case["case_id"]),
    )
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve amount, price-discrepancy and not-provided rules plus precedent",
        {"query": QUERY, "as_of": case["opened_at"][:10], "kinds": ["policy", "precedent"]},
        lambda: ctx.knowledge.search(
            QUERY, as_of=date.fromisoformat(case["opened_at"][:10]), limit=20
        ),
    )
    stay_end = date.fromisoformat(txn["txn_local_datetime"][:10])
    activity = ctx.call(
        "get_account_transactions",
        "Check the cardholder's own card activity around the stay",
        {
            "account_id": case["account_id"],
            "since": (stay_end - timedelta(days=5)).isoformat(),
            "until": (stay_end + timedelta(days=1)).isoformat(),
        },
        lambda: ctx.data.account_transactions(
            case["account_id"],
            since=(stay_end - timedelta(days=5)).isoformat(),
            until=(stay_end + timedelta(days=1)).isoformat(),
        ),
    )
    attachments = " ".join(
        item["description"]
        for row in communications
        for item in json.loads(row["attachments"] or "[]")
    )
    return {
        "knowledge": knowledge,
        "findings": {
            "communications": communications,
            "activity": activity,
            "disclosures": attachments,
        },
    }


def on_evidence(
    ctx: RunContext, state: dict[str, Any], packets: list[dict[str, Any]]
) -> dict[str, Any]:
    return {"findings": {**state["findings"], "packet": json.loads(packets[0]["json"])}}


def specialists(
    ctx: RunContext, state: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    findings = state["findings"]
    packet, case = findings["packet"], state["case"]
    packet_id = state["evidence"][0]["packet_id"]
    registration = packet["registration_card"]["text"]
    stay = packet["reservation"]
    rides = [
        row
        for row in findings["activity"]
        if any(name in row["descriptor"] for name in RIDE_HAIL)
        and row["txn_local_datetime"][:10] in {stay["arrival"], stay["departure"]}
    ]
    disclosures = findings["disclosures"].casefold()
    lines = {line["code"]: line for line in packet["folio"]["lines"]}
    decisions = {
        "DEST": {
            "decision": "valid_charge",
            "reason": "disclosed in confirmation and initialed",
            "evidence": [packet_id, *[row["comm_id"] for row in findings["communications"]]],
            "supported": "destination fee" in disclosures
            and "destination fee acknowledged [initials" in registration.casefold(),
        },
        "UPG": {
            "decision": "valid_charge",
            "reason": "initialed on registration card despite cardholder testimony",
            "evidence": [packet_id],
            "supported": "upg" in registration.casefold()
            and "[initials" in registration.casefold(),
        },
        "VALET": {
            "decision": "dispute",
            "reason": "no vehicle; hotel valet log empty; rideshare trips at arrival/departure",
            "evidence": [packet_id, *[row["txn_id"] for row in rides]],
            "supported": not packet["valet_log"]["entries"] and len(rides) >= 2,
        },
    }
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "contradiction_detected",
        (
            "Cardholder testimony conflicts with the initialed upgrade; the folio conflicts with "
            "the valet log"
        ),
        {
            "facts": [
                {"statement": "cardholder: upgrade was complimentary", "source": case["case_id"]},
                {
                    "statement": "registration card initialed beside the paid upgrade",
                    "source": packet_id,
                },
                {"statement": "folio bills valet 3 nights", "source": packet_id},
                {"statement": "valet log has no vehicle for the room", "source": packet_id},
            ],
            "resolution": (
                "documented acknowledgment prevails for the upgrade; merchant's own log defeats "
                "parking"
            ),
            "impact": "partial outcome",
        },
        [case["case_id"], packet_id, *[row["txn_id"] for row in rides]],
    )
    delegations = [
        {
            "subagent_type": "folio_line_analyst",
            "description": json.dumps(
                {
                    "task": f"Assess folio line {code} only",
                    "line": lines[code],
                    "proposed": decision,
                }
            ),
        }
        for code, decision in decisions.items()
    ]
    update = {**findings, "line_decisions": decisions, "rides": [row["txn_id"] for row in rides]}
    update["amounts"] = _amounts(ctx, {**state, "findings": update})
    return {"findings": update}, delegations


def _amounts(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    findings = state["findings"]
    disputed = [
        code for code, row in findings["line_decisions"].items() if row["decision"] == "dispute"
    ]
    return ctx.call(
        "compute_folio_lines",
        "Recompute folio taxes and split the disputed amount from supported lines",
        {"disputed_codes": disputed, "claimed_amount": float(state["case"]["dispute_amount"])},
        lambda: folio_line_amounts(
            lines=findings["packet"]["folio"]["lines"],
            disputed_codes=disputed,
            claimed_amount=Decimal(state["case"]["dispute_amount"]),
            refs=[state["evidence"][0]["packet_id"]],
            emitter=ctx.emitter,
        ),
    )


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = state["findings"]
    folio = findings["packet"]["folio"]
    amounts = findings["amounts"]
    folio_taxes = {
        line["code"]: line["amount"] for line in folio["lines"] if line["code"].startswith("TAX")
    }
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    precedent = next((row for row in state["knowledge"] if row["doc_id"] == "PRE-0007"), None)
    if precedent:
        ctx.knowledge.reject(
            precedent,
            reason="PRE-0007 had no initials beside the upgrade; this card is initialed",
            evidence_refs=[state["evidence"][0]["packet_id"]],
        )
    return [
        check(
            "t_and_e_conditions_retrieved",
            REQUIRED <= doc_ids,
            {"required": sorted(REQUIRED)},
            sorted(REQUIRED),
        ),
        check(
            "folio_reconciles",
            amounts["folio_total"] == folio["total"]
            and set(amounts["tax_by_rate"].values()) == set(folio_taxes.values()),
            {"computed": amounts, "folio_taxes": folio_taxes},
            [state["evidence"][0]["packet_id"]],
        ),
        check(
            "every_line_decision_supported",
            all(row["supported"] for row in findings["line_decisions"].values()),
            findings["line_decisions"],
            [state["evidence"][0]["packet_id"]],
        ),
        check(
            "line_specialists_completed",
            len(state["specialist_results"]) == len(findings["line_decisions"]),
            {"results": len(state["specialist_results"])},
            [],
        ),
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, txn, findings = state["case"], state["transactions"][0], state["findings"]
    amounts = findings["amounts"]
    credit, denied = Decimal(amounts["disputed_with_tax"]), Decimal(amounts["denied_portion"])
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=True,
        claim_family="services_not_received_partial",
        network_actions=[
            NetworkAction(
                txn_id=txn["txn_id"],
                case_id=case["case_id"],
                action="file_dispute",
                condition="13.1",
                amount=credit,
                reason="valet parking billed with no vehicle; parking tax included",
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome="partial", credit_amount=credit, reversal_amount=denied, liability_amount=denied
        ),
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.9,
            flip_fact=(
                "Evidence the upgrade initials were not the guest's, or a valet ticket for the "
                "room."
            ),
        ),
        conditions_considered=[
            {
                "condition": "12.5",
                "fails_because": (
                    "invalid for a T&E difference between quoted price and actual charges"
                ),
            },
            {"condition": "13.3", "fails_because": "invalid for a price discrepancy"},
        ],
        hypotheses=[
            {"id": code, "label": row["reason"], "status": row["decision"]}
            for code, row in findings["line_decisions"].items()
        ],
        letters=["reg_z_partial_denial_explanation"],
        citations=[
            {
                "doc_id": "VISA-12.5@2026-04-18",
                "why": "Quoted-versus-actual T&E differences are excluded",
            },
            {"doc_id": "VISA-13.3@2026-04-18", "why": "Price discrepancies are excluded"},
            {"doc_id": "VISA-13.1@2026-04-18", "why": "Parking service was not provided"},
            {"doc_id": "REGZ-1026.13", "why": "Partial resolution and explanation"},
            {
                "doc_id": "PRE-0007",
                "why": "Distinguished: that upgrade had no guest acknowledgment",
            },
        ],
        confidence=0.9,
        explanation_for_cardholder=(
            "We reviewed your folio line by line. The hotel's own valet log shows no car for "
            "your room, and your card "
            f"shows ride-hail trips on arrival and departure, so we credited ${credit} for "
            "parking and its tax and filed a "
            "dispute. The destination fee was disclosed when you booked, and the registration "
            "card shows initials beside "
            f"the paid upgrade, so we are reversing the remaining ${denied} of the temporary "
            "credit. We understand you were "
            "told the upgrade was complimentary; if you have anything showing that, send it and "
            "we will review it."
        ),
    )
