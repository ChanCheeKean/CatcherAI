"""C13-style route: an AI agent's purchase disputed as unauthorized, where no network rule fits.

The route suspends for the Agentic Payment Provider's instruction record, decides the cardholder
outcome under Reg Z, takes no network action, and records a machine-readable policy gap.
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

STEPS = ["gather_evidence"]
EVIDENCE_USE = "separate the cardholder's hard constraints from preferences and check disclosures"
POLICY_QUERY = (
    "VISA 4.1.24 agentic payment provider VISA 10.4 13.1 13.5 13.7 REGZ 1026.13 billing error "
    "SOP DSP 003 no applicable rule"
)
PRECEDENT_QUERY = "agentic payment provider AI agent booked instruction preference refundable"
REQUIRED = {
    "VISA-4.1.24-AGENTIC@2026-04-18",
    "VISA-10.4@2026-04-18",
    "VISA-13.1@2026-04-18",
    "VISA-13.5@2026-04-18",
    "VISA-13.7@2026-04-18",
    "REGZ-1026.13",
    "LFB-SOP-DSP-003@v6",
}
CANDIDATES = ("10.4", "13.1", "13.5", "13.7")
AGENTIC = re.compile(r"\bagentic|\bAI (travel )?(agent|assistant)", re.I)
PROVIDER_BASIS = "VISA-4.1.24-AGENTIC@2026-04-18 written request"


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case = state["case"]
    notice = date.fromisoformat(case["opened_at"][:10])
    communications = ctx.call(
        "get_case_communications",
        "Read the cardholder's instruction screenshot and booking emails",
        {"case_id": case["case_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.case_communications(case["case_id"]),
    )
    since, until = "2026-09-01T00:00:00Z", ctx.clock.now.isoformat()
    events = ctx.call(
        "get_account_events",
        "Check how the agent's token was provisioned and verified",
        {"account_id": case["account_id"], "since": since, "until": until},
        lambda: ctx.data.account_events(
            case["account_id"], since=since, until=until.replace("+00:00", "Z")
        ),
    )
    policies = ctx.call(
        "retrieve_knowledge",
        "Retrieve agentic, candidate-condition and Reg Z rules as of notice",
        {"query": POLICY_QUERY, "as_of": notice.isoformat(), "kinds": ["policy"]},
        lambda: ctx.knowledge.search(POLICY_QUERY, as_of=notice, kinds=("policy",), limit=16),
    )
    precedents = ctx.call(
        "retrieve_knowledge",
        "Search for any precedent on agent-made purchases",
        {"query": PRECEDENT_QUERY, "as_of": notice.isoformat(), "kinds": ["precedent"]},
        lambda: ctx.knowledge.search(PRECEDENT_QUERY, as_of=notice, kinds=("precedent",), limit=8),
    )
    conditions = ctx.call(
        "list_dispute_conditions",
        "Enumerate the network's dispute conditions before choosing one",
        {"network": case["network"]},
        lambda: ctx.data.dispute_conditions(),
    )
    token_event = next((row for row in events if row["event_type"] == "token_provisioned"), None)
    token_detail = (
        json.loads(token_event["detail"]) if token_event and token_event.get("detail") else {}
    )
    provider = token_detail.get("requestor", "agentic payment provider")
    research_query = f"{provider} booking guarantee hard constraints preferences fare rules"
    research = ctx.call(
        "retrieve_knowledge",
        "Retrieve the provider's terms and applicable fare rules",
        {"query": research_query, "as_of": ctx.clock.now.date().isoformat(), "kinds": ["research"]},
        lambda: ctx.knowledge.search(
            research_query, as_of=ctx.clock.now.date(), kinds=("research",), limit=4
        ),
    )
    agentic_precedents = [row["doc_id"] for row in precedents if AGENTIC.search(row["body"])]
    ctx.event(
        ActorKind.MEMORY,
        "case_file",
        "case_file_updated",
        "Recorded the agentic context and the absence of an applicable precedent",
        {
            "path": f"/case/{case['case_id']}/facts.json",
            "diff": {
                "added": [
                    {
                        "fact": "transaction initiated by an agentic payment provider token",
                        "source_refs": [token_event["event_id"]] if token_event else [],
                    },
                    {
                        "fact": "precedents addressing agent-made purchases",
                        "value": agentic_precedents,
                        "considered": [row["doc_id"] for row in precedents],
                    },
                ]
            },
        },
        [row["comm_id"] for row in communications],
    )
    return {
        "knowledge": [*policies, *precedents, *research],
        "findings": {
            "communications": communications,
            "token_event": token_event,
            "provider": provider,
            "agentic_precedents": agentic_precedents,
            "precedents_considered": [row["doc_id"] for row in precedents],
            "research_ids": [row["doc_id"] for row in research],
            "conditions": [row for row in conditions if row["condition"] in CANDIDATES],
            "instruction_record": None,
        },
        "governance_facts": {"novel_transaction_type": True},
    }


def evidence_request(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": "request_record",
        "wait_kind": "provider_record",
        "provider": state["findings"]["provider"],
        "basis": PROVIDER_BASIS,
        "summary": "Requested the cardholder instruction record from the agentic payment provider",
        "evidence_types": [
            "instruction_record",
            "consent",
            "options_evaluated",
            "booking_notification",
        ],
        "target_txn_ids": [row["txn_id"] for row in state["transactions"]],
        "rationale": "Only the provider's record shows whether 'refundable' was a hard constraint",
    }


def on_evidence(
    ctx: RunContext, state: dict[str, Any], packets: list[dict[str, Any]]
) -> dict[str, Any]:
    record = json.loads(packets[0]["json"])
    instruction = record["instruction"]
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "plan_updated",
        "Resumed with the instruction record and moved to condition evaluation",
        {
            "plan_id": "plan-1",
            "full_plan": [
                *state["plan"],
                "Evaluate conditions against the instruction record",
                "Decide under Reg Z and record the policy gap",
            ],
            "diff": {"awaited_record": {"before": "requested", "after": packets[0]["packet_id"]}},
            "reason": "determinative provider record arrived before the latest safe decision time",
            "trigger_event_type": "evidence_arrived",
        },
        [packets[0]["packet_id"]],
    )
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "hypothesis_updated",
        "Instruction record separates hard constraints from preferences",
        {
            "path": f"/case/{state['case_id']}/hypotheses.json",
            "diff": {
                "hard_constraints": instruction["parsed"]["hard_constraints"],
                "preferences": instruction["parsed"]["preferences"],
                "confirmation_shown": instruction["parsed_confirmation_shown_to_user"],
            },
        },
        [packets[0]["packet_id"]],
    )
    return {"findings": {**state["findings"], "instruction_record": record}}


def _conditions(state: dict[str, Any]) -> list[dict[str, str]]:
    """Why each candidate condition fails, with the sources that show it."""

    findings = state["findings"]
    comm_ids = [row["comm_id"] for row in findings["communications"]]
    record_ids = [row["packet_id"] for row in state["evidence"]]
    token_ids = [findings["token_event"]["event_id"]] if findings["token_event"] else []
    fare_rule_refs = findings["research_ids"][-1:]
    return [
        {
            "condition": "10.4",
            "sources": [*record_ids, *token_ids],
            "fails_because": (
                "cardholder authorized the agent and acknowledged responsibility; tokenized, "
                "verified"
            ),
        },
        {
            "condition": "13.1",
            "sources": comm_ids,
            "fails_because": "service was available; cardholder cancelled",
        },
        {
            "condition": "13.5",
            "sources": ["VISA-4.1.24-AGENTIC@2026-04-18"],
            "fails_because": (
                "misrepresentation by merchant not alleged; agentic provider is not a merchant"
            ),
        },
        {
            "condition": "13.7",
            "sources": [*fare_rule_refs, *comm_ids],
            "fails_because": "merchant disclosed and applied its fare rules",
        },
    ]


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = state["findings"]
    fare_rule_refs = findings["research_ids"][-1:]
    record = findings["instruction_record"]
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    conditions = _conditions(state)
    checks = [
        check(
            "agentic_sources_retrieved_as_of_notice",
            REQUIRED <= doc_ids,
            {"required": sorted(REQUIRED), "doc_ids": sorted(doc_ids)},
            sorted(REQUIRED),
        ),
        check(
            "every_candidate_condition_evaluated",
            {row["condition"] for row in findings["conditions"]} == set(CANDIDATES),
            {"conditions": conditions},
            ["VISA-4.1.24-AGENTIC@2026-04-18"],
        ),
        check(
            "no_precedent_stretched",
            not findings["agentic_precedents"],
            {
                "considered": findings["precedents_considered"],
                "applicable": findings["agentic_precedents"],
            },
            findings["precedents_considered"],
        ),
        check(
            "instruction_record_reviewed",
            record is not None,
            {
                "awaited": [wait["awaited_ref"] for wait in state["waits"]],
                "resolutions": [wait.get("resolution") for wait in state["waits"]],
            },
            [wait["awaited_ref"] for wait in state["waits"]],
        ),
    ]
    if record:
        amount = Decimal(state["transactions"][0]["billing_amount"])
        maximum = Decimal(
            next(
                item.split("=")[1]
                for item in record["instruction"]["parsed"]["hard_constraints"]
                if item.startswith("max_total_usd")
            )
        )
        refundable_options = [
            Decimal(row["total"]) for row in record["options_evaluated"] if row["refundable"]
        ]
        checks.extend(
            [
                check(
                    "purchase_within_hard_constraints",
                    amount <= maximum,
                    {"amount": str(amount), "max_total_usd": str(maximum)},
                    [state["evidence"][0]["packet_id"]],
                ),
                check(
                    "refundable_was_preference_and_shown",
                    "fare_refundable=true" in record["instruction"]["parsed"]["preferences"]
                    and record["instruction"]["parsed_confirmation_shown_to_user"],
                    record["instruction"]["parsed"],
                    [state["evidence"][0]["packet_id"]],
                ),
                check(
                    "refundable_options_exceeded_budget",
                    all(total > maximum for total in refundable_options),
                    {
                        "refundable_totals": [str(total) for total in refundable_options],
                        "max": str(maximum),
                    },
                    [state["evidence"][0]["packet_id"]],
                ),
                check(
                    "booking_disclosed_fare_rules",
                    "non-refundable" in record["booking_notification"]["text"].casefold(),
                    record["booking_notification"],
                    [state["evidence"][0]["packet_id"], *fare_rule_refs],
                ),
            ]
        )
    return checks


def hypotheses(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = state["findings"]
    comm_ids = [row["comm_id"] for row in findings["communications"]]
    token = [findings["token_event"]["event_id"]] if findings["token_event"] else []
    statement = {
        "fact": "cardholder states the instruction required a refundable fare",
        "refs": comm_ids,
        "weight": 1,
    }
    flip = (
        "instruction record showing 'refundable' parsed as a hard constraint, or no booking "
        "disclosure"
    )
    if findings["instruction_record"]:
        packet = state["evidence"][0]["packet_id"]
        fare_rule_refs = findings["research_ids"][-1:]
        maximum = next(
            item.split("=", 1)[1]
            for item in findings["instruction_record"]["instruction"]["parsed"]["hard_constraints"]
            if item.startswith("max_total_usd=")
        )
        record_facts = [
            {
                "fact": (
                    "record parsed 'refundable' as a preference and showed that parse to the "
                    "cardholder"
                ),
                "refs": [packet],
                "weight": 3,
            },
            {
                "fact": f"every refundable option exceeded the ${maximum} hard maximum",
                "refs": [packet],
                "weight": 2,
            },
            {
                "fact": (
                    "booking push and airline rules disclosed non-refundable fare and 24h "
                    "cancellation"
                ),
                "refs": [packet, *fare_rule_refs],
                "weight": 2,
            },
            {
                "fact": (
                    "cardholder acknowledged responsibility for agent purchases; token verified "
                    "biometrically"
                ),
                "refs": [packet, *token],
                "weight": 2,
            },
        ]
        return [
            {
                "id": "H1",
                "label": "no billing error: purchase within cardholder-defined hard constraints",
                "favors": "issuer",
                "outcome": "deny with explanation; no network action; record policy gap",
                "evidence_for": record_facts,
                "evidence_against": [statement],
                "flip_fact": flip,
            },
            {
                "id": "H2",
                "label": "agent exceeded the cardholder's instructions",
                "favors": "cardholder",
                "outcome": "credit the cardholder",
                "evidence_for": [statement],
                "evidence_against": record_facts[:2],
                "flip_fact": "a record showing the purchase met every hard constraint",
            },
        ]
    pending = [wait["wait_id"] for wait in state["waits"]]
    visible = [
        {
            "fact": "screenshot wording says refundable was 'preferred' with a $450 maximum",
            "refs": comm_ids,
            "weight": 2,
        },
        {
            "fact": "airline confirmation disclosed a non-refundable Basic Economy fare",
            "refs": comm_ids,
            "weight": 2,
        },
        {
            "fact": "agent token provisioned with issuer biometric verification",
            "refs": token,
            "weight": 1,
        },
    ]
    unknown = {
        "fact": "provider instruction record not received; parse and consent unverified",
        "refs": pending,
        "weight": 3,
    }
    return [
        {
            "id": "H1",
            "label": "no billing error: purchase within cardholder-defined hard constraints",
            "favors": "issuer",
            "outcome": "deny with explanation",
            "evidence_for": visible,
            "evidence_against": [statement, unknown],
            "flip_fact": flip,
        },
        {
            "id": "H2",
            "label": "agent exceeded the cardholder's instructions",
            "favors": "cardholder",
            "outcome": "credit the cardholder",
            "evidence_for": [statement, unknown],
            "evidence_against": visible[:2],
            "flip_fact": "the provider's record showing a preference only",
        },
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, transaction = state["case"], state["transactions"][0]
    amount = Decimal(transaction["billing_amount"])
    record = state["findings"]["instruction_record"] or {}
    provider = record.get("provider", {}).get("name", state["findings"]["provider"])
    hard_constraints = record.get("instruction", {}).get("parsed", {}).get("hard_constraints", [])
    maximum = next(
        (item.split("=", 1)[1] for item in hard_constraints if item.startswith("max_total_usd=")),
        "the stated",
    )
    notice_text = record.get("booking_notification", {}).get("text", "")
    cancellation_match = re.search(r"free cancellation for (\d+)h", notice_text, re.I)
    cancellation_hours = cancellation_match.group(1) if cancellation_match else "the disclosed"
    guarantee_ref = state["findings"]["research_ids"][:1]
    guarantee_citation = f" ({guarantee_ref[0]})" if guarantee_ref else ""
    wait = state["waits"][-1] if state["waits"] else {}
    conditions = _conditions(state)
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=False,
        claim_family="agentic_transaction_instruction_dispute",
        network_actions=[
            NetworkAction(
                txn_id=transaction["txn_id"],
                case_id=case["case_id"],
                action="no_dispute",
                reason=(
                    "no Visa condition fits; cardholder authorized the agent within hard "
                    "constraints"
                ),
                amount=amount,
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome="denied_with_explanation",
            credit_amount=Decimal("0"),
            reversal_amount=Decimal(case.get("provisional_credit_amount") or "0"),
            liability_amount=amount,
        ),
        wait={
            "for": wait.get("awaited_ref"),
            "available_at": wait.get("expected_at"),
            "latest_safe_decision_date": wait.get("latest_safe_decision_date"),
            "resolution": wait.get("resolution"),
        },
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.9,
            flip_fact=(
                "instruction record showing 'refundable' parsed as a hard constraint, or no "
                "booking disclosure"
            ),
        ),
        cardholder_guidance={
            "booking_guarantee": (
                f"{provider} Booking Guarantee covers hard constraints only{guarantee_citation}"
            ),
            "next_step": f"{provider} complaint process",
        },
        conditions_considered=[
            {key: row[key] for key in ("condition", "fails_because")} for row in conditions
        ],
        automated_actions=[
            {
                "action": "request_record",
                "target": provider,
                "basis": PROVIDER_BASIS,
                "record_id": wait.get("awaited_ref"),
            },
            {
                "action": "policy_gap_record",
                "topic": "agentic transaction outside cardholder preference",
                "conditions_considered": list(CANDIDATES),
                "reasons": {row["condition"]: row["fails_because"] for row in conditions},
                "fallback": "REGZ-1026.13 billing-error rules decide the cardholder outcome",
            },
        ],
        letters=["reg_z_no_billing_error_explanation"],
        citations=[
            {
                "doc_id": "VISA-4.1.24-AGENTIC@2026-04-18",
                "why": "Provider duties; a provider is not a merchant",
            },
            {"doc_id": "VISA-10.4@2026-04-18", "why": "Cardholder authorized the agent's token"},
            {"doc_id": "VISA-13.1@2026-04-18", "why": "Service was available"},
            {"doc_id": "VISA-13.5@2026-04-18", "why": "No merchant misrepresentation alleged"},
            {"doc_id": "VISA-13.7@2026-04-18", "why": "Fare rules were disclosed and applied"},
            {"doc_id": "REGZ-1026.13", "why": "No billing error under Regulation Z"},
            {"doc_id": "LFB-SOP-DSP-003@v6", "why": "No-applicable-rule governance and policy gap"},
        ],
        hypotheses=[
            {"id": "H1", "label": "within hard constraints", "status": "supported"},
            {"id": "H2", "label": "agent exceeded instructions", "status": "rejected"},
        ],
        confidence=0.9,
        explanation_for_cardholder=(
            f"We reviewed {provider}'s record of your request. It treated 'refundable' as a "
            "preference "
            "and showed you that before booking; the only refundable fares cost more than your"
            f" ${maximum} "
            "maximum, and the booking notice said the fare was non-refundable with free "
            "cancellation "
            f"for {cancellation_hours} hours. Because the purchase stayed within the limits you "
            "set, we found no "
            "billing "
            f"error. {provider}'s Booking Guarantee covers hard constraints only; you can raise "
            f"the preference through {provider}'s complaint process."
        ),
    )


def curate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    note_id = ctx.notes.write(
        kind="semantic",
        scope="policy_gap",
        subject_ids=["VISA-4.1.24-AGENTIC"],
        content=(
            "No Visa dispute condition covers an agentic purchase made within the cardholder's"
            " hard "
            "constraints but against a stated preference; 10.4, 13.1, 13.5 and 13.7 were evaluated "
            "and do not fit. Decide the cardholder outcome under Reg Z."
        ),
        source_refs=[
            state["case_id"],
            "VISA-4.1.24-AGENTIC@2026-04-18",
            *[row["packet_id"] for row in state["evidence"]],
        ],
        valid_from=date.fromisoformat(state["case"]["opened_at"][:10]),
        confidence=0.9,
        tags=["policy_gap", "agentic"],
    )
    return {"memory_correction_ids": [note_id] if note_id else []}
