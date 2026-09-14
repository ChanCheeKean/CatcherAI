"""C11-style route: high-value CNP fraud where merchant CE hides an account takeover."""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from domain.events import ActorKind
from runtime.context import RunContext, check, note_matching

STEPS = ["gather_evidence", "run_specialists"]
QUERY = (
    "VISA 10.4 11.2 lifecycle REGZ 1026.12 LFB SOP DSP 003 005 account takeover full clear text "
    "IP reopen"
)
REQUIRED = {
    "VISA-10.4@2026-04-18",
    "VISA-11.2-LIFECYCLE@2026-04-18",
    "REGZ-1026.12",
    "LFB-SOP-DSP-003@v6",
    "LFB-SOP-DSP-005@v1",
}
TAKEOVER_EVENTS = {"phone_changed", "password_reset", "login_failed"}


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    notice = date.fromisoformat(state["case"]["opened_at"][:10])
    customer_id = state["case"]["customer_id"]
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve CE format, ATO, reopening and Reg Z rules",
        {"query": QUERY, "as_of": notice.isoformat(), "kinds": ["policy", "precedent"]},
        lambda: ctx.knowledge.search(QUERY, as_of=notice, limit=32),
    )
    notes = ctx.call(
        "read_memory_notes",
        "Read the customer note as an unverified lead",
        {"subject_ids": [customer_id], "as_of": notice.isoformat(), "minimum_confidence": 0.5},
        lambda: ctx.notes.read_current(subject_ids=[customer_id], as_of=notice),
    )
    return {"knowledge": knowledge, "memory_notes": notes, "candidate_condition": "10.4"}


def specialists(
    ctx: RunContext, state: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    case = state["case"]
    transaction_date = date.fromisoformat(state["transactions"][0]["processing_date"])
    since = f"{(transaction_date - timedelta(days=7)).isoformat()}T00:00:00Z"
    until = ctx.clock.now.isoformat()
    events = ctx.call(
        "get_account_events",
        "Reconstruct the issuer-side account takeover sequence",
        {"account_id": case["account_id"], "since": since, "until": until},
        lambda: ctx.data.account_events(
            case["account_id"], since=since, until=until.replace("+00:00", "Z")
        ),
        actor="security_events_analyst",
    )
    shared = ctx.call(
        "graph_shared_delivery",
        "Find other disputes shipped to the same delivery address",
        {"case_id": state["case_id"]},
        lambda: ctx.graph.shared_delivery_network(state["case_id"]),
        actor="graph_link_analyst",
    )
    shared_cases = sorted({row["dispute_node_id"].split(":", 1)[1] for row in shared})
    related_disputes = ctx.call(
        "get_disputes_by_ids",
        "Identify prior outcomes linked by the shared delivery address",
        {"case_ids": shared_cases, "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.disputes_by_ids(shared_cases),
        actor="graph_link_analyst",
    )
    related_transactions = ctx.call(
        "get_transactions_for_cases",
        "Load transaction amounts for linked prior cases",
        {"case_ids": shared_cases, "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.transactions_for_cases(shared_cases),
        actor="graph_link_analyst",
    )
    prior_denials = [
        row
        for row in related_disputes
        if row["case_id"] != case["case_id"]
        and row["customer_id"] == case["customer_id"]
        and row["cardholder_outcome"] == "denied"
    ]
    prior_denial = max(prior_denials, key=lambda row: row["opened_at"], default=None)
    prior_transaction = next(
        (
            row
            for row in related_transactions
            if prior_denial and row["case_id"] == prior_denial["case_id"]
        ),
        None,
    )
    drop_address = next(
        (row["address_node_id"].split(":", 1)[1] for row in shared if row["address_node_id"]),
        None,
    )
    memory_note = note_matching(
        state, tags=("risk", "first_party_misuse"), subject_id=case["customer_id"]
    )
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "hypothesis_updated",
        "Added evidence for and against friendly fraud and account takeover",
        {
            "path": f"/case/{state['case_id']}/hypotheses.json",
            "diff": {
                "H1_first_party_misuse": {
                    "for": ["merchant_CE_assertion"],
                    "memory_leads": [memory_note["note_id"]] if memory_note else [],
                    "against": ["issuer_security_events", "shared_drop_address"],
                },
                "H2_account_takeover": {
                    "for": ["issuer_security_events", "shared_drop_address"],
                    "against": ["matching_login_id"],
                },
            },
        },
        [
            *([memory_note["note_id"]] if memory_note else []),
            *[row["event_id"] for row in events],
            *shared_cases,
        ],
    )
    packet_refs = [row["packet_id"] for row in state["evidence"]]
    delegations = [
        {
            "subagent_type": "security_events_analyst",
            "description": json.dumps(
                {"task": "Test account takeover chronology", "events": events}
            ),
        },
        {
            "subagent_type": "merchant_evidence_analyst",
            "description": json.dumps(
                {
                    "task": "Challenge the merchant CE 3.0 assertion and IP format",
                    "evidence_packet_refs": packet_refs,
                }
            ),
        },
        {
            "subagent_type": "graph_link_analyst",
            "description": json.dumps(
                {"task": "Assess the shared delivery network", "graph_results": shared}
            ),
        },
    ]
    facts = {**state["governance_facts"], "cross_customer_finding": len(shared_cases) >= 3}
    findings = {
        **state["findings"],
        "account_events": events,
        "shared_delivery": shared,
        "shared_cases": shared_cases,
        "prior_denial": prior_denial,
        "prior_transaction": prior_transaction,
        "drop_address": drop_address,
    }
    return {"findings": findings, "governance_facts": facts}, delegations


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = state["findings"]
    shared_cases = findings["shared_cases"]
    packet_id = state["evidence"][0]["packet_id"]
    note = note_matching(
        state,
        tags=("risk", "first_party_misuse"),
        subject_id=state["case"]["customer_id"],
    )
    if note:
        ctx.notes.reject(
            note,
            reason="Current ATO evidence and the shared drop address contradict it",
            evidence_refs=[packet_id, *shared_cases],
        )
    packet = json.loads(state["evidence"][0]["json"])
    session, activity = packet["session"], packet["account_activity_last_24h"]
    event_types = {row["event_type"] for row in findings["account_events"]}
    ctx.event(
        ActorKind.AGENT,
        "verifier",
        "contradiction_detected",
        "Issuer and merchant logs overturn the friendly-fraud hypothesis",
        {
            "facts": [
                {"statement": "merchant asserts CE match", "source": packet_id},
                {
                    "statement": "IP is truncated and account changed before order",
                    "source": packet_id,
                },
                {
                    "statement": "issuer logs show phone change and password reset",
                    "source": "account_events",
                },
            ],
            "resolution": "account_takeover_supported",
            "impact": "retract_memory_and_reopen_prior_denial",
        },
        [packet_id, *([note["note_id"]] if note else []), *shared_cases],
    )
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "plan_updated",
        "Revised the plan from friendly-fraud screening to ATO remediation",
        {
            "plan_id": "plan-1",
            "full_plan": [
                *state["plan"],
                "Reject the malformed CE assertion",
                "Secure the account and test prior denial for automated reopening",
            ],
            "diff": {
                "candidate_hypothesis": {
                    "before": "first_party_misuse",
                    "after": "account_takeover",
                }
            },
            "reason": "issuer and merchant event sequences contradict CE claim",
            "trigger_event_type": "contradiction_detected",
        },
        [packet_id, *([note["note_id"]] if note else []), *shared_cases],
    )
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    return [
        check(
            "ato_sources_retrieved",
            REQUIRED <= doc_ids,
            {"required": sorted(REQUIRED), "doc_ids": sorted(doc_ids)},
            sorted(REQUIRED),
        ),
        check(
            "ce_ip_format_invalid",
            str(session.get("ip_match", "")).endswith(".x"),
            session,
            [packet_id, "VISA-10.4@2026-04-18"],
        ),
        check(
            "merchant_packet_contains_takeover_sequence",
            {"login_new_device", "password_reset", "email_changed"}
            <= {row["event"] for row in activity},
            {"activity": activity},
            [packet_id],
        ),
        check(
            "issuer_events_support_takeover",
            TAKEOVER_EVENTS <= event_types,
            {"event_types": sorted(event_types)},
            [row["event_id"] for row in findings["account_events"]],
        ),
        check(
            "shared_drop_address_prior_denial",
            findings["prior_denial"] is not None and len(shared_cases) >= 3,
            {"shared_cases": shared_cases, "prior_denial": findings["prior_denial"]},
            shared_cases,
        ),
        check(
            "independent_specialists_completed",
            len(state["specialist_results"]) == 3,
            {"results": state["specialist_results"]},
            [],
        ),
    ]


def hypotheses(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    events = [row["event_id"] for row in state["findings"]["account_events"]]
    shared = state["findings"]["shared_cases"]
    packet_id = state["evidence"][0]["packet_id"]
    takeover = [
        {
            "fact": "issuer logs: phone change, hosting-IP failures, OTP reset before the order",
            "refs": events,
            "weight": 3,
        },
        {
            "fact": "merchant packet: password reset, email change and new device before checkout",
            "refs": [packet_id],
            "weight": 3,
        },
        {
            "fact": "IP supplied as a truncated range, not a full clear-text IP",
            "refs": [packet_id],
            "weight": 2,
        },
        {
            "fact": f"shipping address shared by {len(shared)} disputed orders across customers",
            "refs": shared,
            "weight": 3,
        },
    ]
    login = [
        {
            "fact": "merchant login matches two undisputed 2026 purchases",
            "refs": [packet_id],
            "weight": 1,
        }
    ]
    return [
        {
            "id": "H2",
            "label": "account takeover",
            "favors": "cardholder",
            "outcome": "credit, file 10.4, secure account, reopen prior denial",
            "evidence_for": takeover,
            "evidence_against": login,
            "flip_fact": (
                "Evidence the customer made the phone-number change and received the goods."
            ),
        },
        {
            "id": "H1",
            "label": "first-party use",
            "favors": "issuer",
            "outcome": "deny on merchant CE",
            "evidence_for": login,
            "evidence_against": takeover,
            "flip_fact": "Verified cardholder control of the phone change and delivery address.",
        },
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, transaction = state["case"], state["transactions"][0]
    amount = Decimal(transaction["billing_amount"])
    shared = state["findings"]["shared_cases"]
    prior = state["findings"]["prior_denial"]
    prior_transaction = state["findings"]["prior_transaction"]
    drop_address = state["findings"]["drop_address"]
    memory_note = note_matching(
        state, tags=("risk", "first_party_misuse"), subject_id=case["customer_id"]
    )
    prior_amount = Decimal(prior_transaction["billing_amount"]) if prior_transaction else None
    ip_match = json.loads(state["evidence"][0]["json"])["session"].get("ip_match")
    remediation_actions = []
    if prior:
        remediation_actions.append(
            {
                "action": "reopen_case",
                "case_id": prior["case_id"],
                "reason": (
                    "prior denial contradicted by account-takeover indicators and shared drop "
                    "address"
                ),
            }
        )
        remediation_actions.append(
            {
                "action": "credit_reopened_case",
                "case_id": prior["case_id"],
                "amount": f"{prior_amount:.2f}"
                if prior_amount is not None
                else prior["dispute_amount"],
                "note": (
                    "plus related finance charges; no network action: transaction already disputed "
                    "once and Visa time limit passed"
                ),
            }
        )
    if drop_address:
        remediation_actions.append(
            {
                "action": "watchlist_add",
                "list": "ship_to_addresses",
                "subject_id": drop_address,
                "evidence": shared,
            }
        )
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=True,
        claim_family="fraud_cnp_account_takeover",
        network_actions=[
            NetworkAction(
                txn_id=transaction["txn_id"],
                case_id=case["case_id"],
                action="file_dispute",
                reason="Account-takeover evidence defeats the merchant CE assertion",
                condition="10.4",
                amount=amount,
                certification=["fraud_reported"],
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome="credited",
            credit_amount=amount,
            reversal_amount=Decimal("0"),
            liability_amount=Decimal("0"),
        ),
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.96,
            flip_fact="Evidence the customer made the phone-number change and received the goods.",
        ),
        automated_actions=[
            {"action": "lock_digital_banking_pending_step_up"},
            {"action": "revert_unverified_phone_change"},
            *remediation_actions,
        ],
        account_actions=[
            "fraud_report_tc40",
            "card_reissue",
            "revert_phone_change_and_secure_online_banking",
        ],
        memory_ops=(
            [
                {
                    "op": "retract",
                    "note_id": memory_note["note_id"],
                    "reason": "contradicted by ATO evidence and shared drop address",
                }
            ]
            if memory_note
            else []
        ),
        citations=[
            {"doc_id": "VISA-10.4@2026-04-18", "why": "Fraud and CE data format"},
            {
                "doc_id": "VISA-11.2-LIFECYCLE@2026-04-18",
                "why": "One network dispute per transaction",
            },
            {"doc_id": "REGZ-1026.12", "why": "Unauthorized-use liability"},
            {"doc_id": "LFB-SOP-DSP-003@v6", "why": "Automated reopening panel"},
            {"doc_id": "LFB-SOP-DSP-005@v1", "why": "Account takeover controls"},
        ],
        hypotheses=[
            {"id": "H1", "label": "first-party misuse", "status": "rejected"},
            {"id": "H2", "label": "account takeover", "status": "supported"},
        ],
        ce3_assessment={
            "met": False,
            "reasons": [
                f"IP provided as {ip_match} (not full clear-text public IP)",
                "delivery address differs from prior transactions",
                "device fingerprint new (first seen 2026-10-14)",
            ],
        },
        confidence=0.96,
        explanation_for_cardholder=(
            "Issuer and merchant logs show an account takeover before the purchase. We credited "
            f"${amount:,.2f}, secured digital banking, and "
            + (
                f"automatically reopened the earlier ${prior_amount:,.2f} denial because the "
                "same drop address was used."
                if prior_amount is not None
                else "reviewed linked prior cases for the same drop address."
            )
        ),
    )


def curate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    shared = state["findings"]["shared_cases"]
    corrections = []
    note = note_matching(
        state,
        tags=("risk", "first_party_misuse"),
        subject_id=state["case"]["customer_id"],
    )
    packet_id = state["evidence"][0]["packet_id"]
    prior = state["findings"]["prior_denial"]
    drop_address = state["findings"]["drop_address"]
    if note:
        corrections.append(
            ctx.notes.retract(
                note,
                correction=(
                    "Issuer, merchant and delivery-network evidence shows the 2026-10-14 order"
                    " was an "
                    "account takeover; the earlier first-party inference"
                    + (f" from {prior['case_id']}" if prior else "")
                    + " is withdrawn."
                ),
                source_refs=[packet_id, *shared, "LFB-SOP-DSP-005@v1"],
                valid_from=ctx.clock.now.date(),
                confidence=0.99,
            )
        )
    if drop_address:
        ctx.graph.write_hypothesis(
            hypothesis_id=f"SuspectedDropAddress:{drop_address}",
            kind="SuspectedDropAddress",
            subject_ids=[drop_address],
            relationship="SUSPECTED_DROP_ADDRESS",
            evidence_refs=shared,
            confidence=0.96,
        )
    return {"memory_correction_ids": corrections}
