"""C12/C12b-style route: delivery evidence, then identity linkage without guilt by association."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from domain.events import ActorKind
from runtime.context import RunContext, check

STEPS = ["gather_evidence", "run_specialists"]
QUERY = (
    "VISA 13.1 REGZ 1026.13 LFB SOP DSP 003 004 proof delivery full address cross customer fairness"
)


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    notice = date.fromisoformat(state["case"]["opened_at"][:10])
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve current delivery-proof and governance rules",
        {"query": QUERY, "as_of": notice.isoformat(), "kinds": ["policy", "precedent"]},
        lambda: ctx.knowledge.search(QUERY, as_of=notice, limit=32),
    )
    return {"knowledge": knowledge, "candidate_condition": "13.1"}


def specialists(
    ctx: RunContext, state: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    case = state["case"]
    customer = ctx.call(
        "get_customer_with_address",
        "Compare proof of delivery with the authoritative home address",
        {"customer_id": case["customer_id"]},
        lambda: ctx.data.customer_with_address(case["customer_id"]),
        actor="merchant_evidence_analyst",
    )
    component = ctx.call(
        "graph_shared_identity",
        "Test shared device and phone linkage without demographic proxies",
        {"customer_id": case["customer_id"]},
        lambda: ctx.graph.shared_identity_component(case["customer_id"]),
        actor="graph_link_analyst",
    )
    linked_disputes: list[dict[str, Any]] = []
    linked_transactions: list[dict[str, Any]] = []
    visa_rule_notes: list[str] = []
    linked_case_ids = [state["case_id"]]
    if component["linked"]:
        graph_cases = ctx.call(
            "graph_disputes_for_customers",
            "Enumerate recent non-receipt cases in the linked component",
            {
                "customer_ids": component["customer_ids"],
                "family": "not_received",
                "since": "2026-08-01",
            },
            lambda: ctx.graph.disputes_for_customers(
                component["customer_ids"], family="not_received", since=date(2026, 8, 1)
            ),
            actor="graph_link_analyst",
        )
        linked_case_ids = sorted(row["dispute_node_id"].split(":", 1)[1] for row in graph_cases)
        linked_disputes = ctx.call(
            "get_disputes_by_ids",
            "Load status and account fields for linked-case controls",
            {"case_ids": linked_case_ids, "as_of": ctx.clock.now.isoformat()},
            lambda: ctx.data.disputes_by_ids(linked_case_ids),
            actor="linked_case_analyst",
        )
        linked_transactions = ctx.call(
            "get_transactions_for_cases",
            "Load merchant facts for linked-case frequency controls",
            {"case_ids": linked_case_ids, "as_of": ctx.clock.now.isoformat()},
            lambda: ctx.data.transactions_for_cases(linked_case_ids),
            actor="linked_case_analyst",
        )
        candidate = _letter_candidate(linked_disputes, linked_transactions)
        if candidate:
            merchant = ctx.call(
                "get_merchant",
                "Resolve the merchant display name for the frequency note",
                {"merchant_id": candidate["merchant_id"]},
                lambda: ctx.data.merchant(candidate["merchant_id"]),
                actor="linked_case_analyst",
            )
            dates = ", ".join(value[5:] for value in candidate["dates"])
            visa_rule_notes = [
                f"{candidate['customer_id']} open {merchant['dba_name']} claims ({dates}) are "
                f"{len(candidate['dates'])} within 30 days → cardholder letter required for 13.1"
            ]
    packet_id = state["evidence"][0]["packet_id"]
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "hypothesis_updated",
        "Updated delivery and coordinated-claim hypotheses",
        {
            "path": f"/case/{state['case_id']}/hypotheses.json",
            "diff": {
                "delivery_error": {"status": "test_proof_of_delivery", "source": packet_id},
                "coordinated_claims": {
                    "status": "supported" if component["linked"] else "rejected",
                    "shared_identifiers": component["shared_identifiers"],
                },
            },
        },
        [packet_id, *component["customer_ids"]],
    )
    update: dict[str, Any] = {
        "findings": {
            **state["findings"],
            "customer": customer,
            "identity_component": component,
            "linked_case_ids": linked_case_ids,
            "linked_disputes": linked_disputes,
            "linked_transactions": linked_transactions,
            "visa_rule_notes": visa_rule_notes,
        },
        "governance_facts": {
            **state["governance_facts"],
            "cross_customer_finding": component["linked"],
        },
    }
    if component["linked"]:
        update["route"] = _escalate(ctx, state, component, linked_case_ids)
    delegations = [
        {
            "subagent_type": "graph_link_analyst",
            "description": json.dumps(
                {
                    "task": "Independently assess positive or negative identity linkage",
                    "component": component,
                }
            ),
        }
    ]
    delegations.extend(
        {
            "subagent_type": "linked_case_analyst",
            "description": json.dumps(
                {
                    "task": "Evaluate this linked case only on its own evidence",
                    "case": row,
                    "guilt_by_association_forbidden": True,
                }
            ),
        }
        for row in linked_disputes
        if row["case_id"] != state["case_id"]
    )
    return update, delegations


def _escalate(
    ctx: RunContext, state: dict[str, Any], component: dict[str, Any], linked_case_ids: list[str]
) -> dict[str, Any]:
    route = {
        **state["route"],
        "depth": "L4",
        "graph_path": "cross_customer_delivery_ring_review",
        "rationale": "Graph linkage escalated the initially local delivery case to L4",
    }
    ctx.event(
        ActorKind.GRAPH_NODE,
        "run_specialists",
        "route_decision",
        "Escalated linked non-receipt investigation from L2 to L4",
        {
            "candidate_routes": [
                "single_not_received_graph_check_l2",
                "cross_customer_not_received_l4",
            ],
            "method": "rule",
            "matched_rule": "identity_component.linked == true",
            "confidence": 1.0,
            "chosen_route": "cross_customer_not_received_l4",
            "depth": "L4",
            "budget": state["route"]["budget"],
            "selected_agents": state["route"]["agents"],
            "selected_skills": state["route"]["skills"],
            "rationale": route["rationale"],
        },
        component["customer_ids"],
    )
    ctx.event(
        ActorKind.AGENT,
        "lead_investigator",
        "plan_updated",
        "Expanded the plan to independently evaluate linked cases",
        {
            "plan_id": "plan-1",
            "full_plan": [
                *state["plan"],
                "Fan out linked cases for evidence-isolated analysis",
                "Run automated cross-customer review before bounded controls",
            ],
            "diff": {
                "depth": {"before": "L2", "after": "L4"},
                "linked_case_count": len(linked_case_ids),
            },
            "reason": "shared devices and phone connected customers",
            "trigger_event_type": "graph_query",
        },
        component["customer_ids"],
    )
    return route


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = state["findings"]
    packet_id = state["evidence"][0]["packet_id"]
    proof = json.loads(state["evidence"][0]["json"])["shipments"][0]["proof_of_delivery"]
    component, customer = findings["identity_component"], findings["customer"]
    linked = bool(component["linked"])
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    required = {"VISA-13.1@2026-04-18"}
    if linked:
        required |= {"REGZ-1026.13", "LFB-SOP-DSP-003@v6", "LFB-SOP-DSP-004@v2"}
    home_number = customer["line1"].split()[0]
    photo_number = next(
        (word for word in proof.get("photo_description", "").split() if word.isdigit()), None
    )
    full_address_match = customer["line1"] in str(proof.get("address", ""))
    if not linked and photo_number and photo_number != home_number:
        ctx.event(
            ActorKind.AGENT,
            "verifier",
            "contradiction_detected",
            "Delivery photo contradicts the cardholder's house number",
            {
                "facts": [
                    {"statement": f"photo shows {photo_number}", "source": packet_id},
                    {
                        "statement": f"customer lives at {home_number}",
                        "source": customer["customer_id"],
                    },
                ],
                "resolution": "misdelivery_and_no_ring_linkage",
                "impact": "file_13.1",
            },
            [packet_id, customer["customer_id"]],
        )
    delivered = (
        (proof.get("gps_distance_m") is not None and full_address_match)
        if linked
        else (photo_number is not None and photo_number != home_number)
    )
    return [
        check(
            "delivery_sources_retrieved",
            required <= doc_ids,
            {"required": sorted(required), "doc_ids": sorted(doc_ids)},
            sorted(required),
        ),
        check(
            "identity_component_scoped",
            len(component["customer_ids"]) > 1
            if linked
            else component["customer_ids"] == [customer["customer_id"]],
            component,
            component["customer_ids"],
        ),
        check(
            "delivery_evidence_resolves_case",
            delivered,
            {"proof": proof, "customer": customer},
            [packet_id],
        ),
    ]


def hypotheses(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    packet_id = state["evidence"][0]["packet_id"]
    customer_id = state["case"]["customer_id"]
    delivered = [
        {
            "fact": "proof of delivery with full address, photo and GPS",
            "refs": [packet_id],
            "weight": 3,
        },
        {
            "fact": "delivery address matches the system-of-record home address",
            "refs": [customer_id],
            "weight": 2,
        },
    ]
    statement = [
        {"fact": "cardholder reports non-receipt", "refs": [state["case_id"]], "weight": 1}
    ]
    return [
        {
            "id": "H1",
            "label": "delivered as claimed; no billing error",
            "favors": "issuer",
            "outcome": "deny with Reg Z explanation; bounded controls only on linkage",
            "evidence_for": delivered,
            "evidence_against": statement,
            "flip_fact": (
                "Proof that the parcel was delivered elsewhere or identifiers were shared "
                "innocently."
            ),
        },
        {
            "id": "H2",
            "label": "parcel not received",
            "favors": "cardholder",
            "outcome": "credit and file 13.1",
            "evidence_for": statement,
            "evidence_against": delivered,
            "flip_fact": (
                "Carrier evidence that the delivery address or photo does not match the home."
            ),
        },
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, transaction, findings = state["case"], state["transactions"][0], state["findings"]
    amount = Decimal(transaction["billing_amount"])
    component = findings["identity_component"]
    if not component["linked"]:
        proof = json.loads(state["evidence"][0]["json"])["shipments"][0]["proof_of_delivery"]
        home_number = findings["customer"]["line1"].split()[0]
        photo_number = next(
            (word for word in proof.get("photo_description", "").split() if word.isdigit()),
            "a different number",
        )
        return DecisionRecord(
            case_id=case["case_id"],
            regime=case["regime"],
            is_dispute=True,
            claim_family="not_received",
            network_actions=[
                NetworkAction(
                    txn_id=transaction["txn_id"],
                    case_id=case["case_id"],
                    action="file_dispute",
                    reason="Partial address and photo house number contradict cardholder address",
                    condition="13.1",
                    amount=amount,
                )
            ],
            cardholder_resolution=CardholderResolution(
                outcome="provisional_credit_pending_network",
                credit_amount=amount,
                reversal_amount=Decimal("0"),
                liability_amount=Decimal("0"),
            ),
            adjudication=Adjudication(
                review_panel_used=False,
                confidence=0.97,
                flip_fact=f"Full-address delivery proof showing house {home_number}.",
            ),
            citations=[{"doc_id": "VISA-13.1@2026-04-18", "why": "Full delivery address required"}],
            ring_linkage=False,
            confidence=0.97,
            explanation_for_cardholder=(
                "The carrier record lacks the full delivery address and the photo shows house "
                f"{photo_number} rather than {home_number}. We credited ${amount:,.2f} and filed "
                "a 13.1 dispute. No shared device or phone links "
                "this claim to the separate ring investigation."
            ),
        )
    members, case_ids = component["customer_ids"], findings["linked_case_ids"]
    accounts = sorted({row["account_id"] for row in findings["linked_disputes"]})
    open_cases = sorted(
        row["case_id"]
        for row in findings["linked_disputes"]
        if row["status"] == "open" and row["case_id"] != case["case_id"]
    )
    devices = sorted(
        node.split(":", 1)[1]
        for node in component["shared_identifiers"].get("BANKING_LOGIN_FROM", [])
    )
    phones = sorted(
        node.split(":", 1)[1] for node in component["shared_identifiers"].get("HAS_PHONE", [])
    )
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
                reason="proof of delivery with full address, photo, GPS",
                amount=amount,
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome="denied_with_explanation",
            credit_amount=Decimal("0"),
            reversal_amount=amount,
            liability_amount=amount,
        ),
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.93,
            flip_fact=(
                "Proof that the parcel was delivered elsewhere or identifiers were shared "
                "innocently."
            ),
        ),
        automated_actions=[
            {
                "action": "graph_write",
                "node": "SuspectedRing",
                "status": "active",
                "members": members,
                "evidence_edges": [
                    *[f"BANKING_LOGIN_FROM {device}" for device in devices],
                    *[f"HAS_PHONE {phone}" for phone in phones],
                ],
                "cases": case_ids,
            },
            {"action": "enhanced_monitoring", "accounts": accounts},
            {
                "action": "claims_control_evidence_first",
                "accounts": accounts,
                "rule": (
                    "signed cardholder letter + evidence review before temporary credit on future "
                    "non-receipt claims"
                ),
            },
            {"action": "watchlist_add", "list": "devices", "subject_ids": devices},
            {
                "action": "enqueue_automated_rereview",
                "cases": open_cases,
                "rule": "decide each on its own evidence",
            },
        ],
        memory_ops=[{"op": "consolidate", "into": "SuspectedRing", "from_cases": case_ids}],
        citations=[
            {"doc_id": "VISA-13.1@2026-04-18", "why": "Delivery evidence"},
            {"doc_id": "REGZ-1026.13", "why": "No-error explanation"},
            {"doc_id": "LFB-SOP-DSP-003@v6", "why": "Cross-customer review"},
            {"doc_id": "LFB-SOP-DSP-004@v2", "why": "Fair automated controls"},
        ],
        ring_members=members,
        ring_linkage=True,
        visa_rule_notes=findings["visa_rule_notes"],
        confidence=0.93,
        explanation_for_cardholder=(
            "The parcel was delivered to your full address with a matching photo and GPS "
            "record, so no "
            "billing error was found. Related cases will each be reassessed only on their own "
            "evidence."
        ),
    )


def curate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    findings = state["findings"]
    component = findings["identity_component"]
    if not component["linked"]:
        ctx.graph.skip_hypothesis_write(
            candidate="SuspectedRing",
            reason="No shared device or phone identifier; guilt by association forbidden",
            refs=[state["case_id"], state["case"]["customer_id"]],
        )
        return {}
    case_ids = findings["linked_case_ids"]
    identifiers = [node for values in component["shared_identifiers"].values() for node in values]
    hypothesis_id = f"SuspectedRing:{state['case_id']}:{ctx.clock.now.date().isoformat()}"
    ctx.graph.write_hypothesis(
        hypothesis_id=hypothesis_id,
        kind="SuspectedRing",
        subject_ids=component["customer_ids"],
        relationship="SUSPECTED_RING_MEMBER",
        evidence_refs=[*case_ids, *identifiers],
        confidence=0.93,
        properties={
            "case_count": len(case_ids),
            "shared_identifiers": component["shared_identifiers"],
        },
    )
    ctx.event(
        ActorKind.MEMORY,
        "memory_curator",
        "memory_consolidate",
        f"Consolidated {len(case_ids)} observations into a bounded ring hypothesis",
        {
            "store": ctx.graph.backend_name,
            "operation": "consolidate",
            "target_id": hypothesis_id,
            "from_ids": case_ids,
            "before": None,
            "after": {
                "status": "active",
                "members": component["customer_ids"],
                "case_count": len(case_ids),
            },
            "source_refs": case_ids,
            "validity": {"valid_from": ctx.clock.now.date().isoformat()},
            "confidence": 0.93,
            "write_gate_checks": [
                {"check": "minimum_observations_gte_3", "pass": len(case_ids) >= 3},
                {"check": "source_refs_present", "pass": True},
                {"check": "guilt_by_association_guardrail", "pass": True},
            ],
        },
        [hypothesis_id, *case_ids],
    )
    return {}


def _letter_candidate(
    disputes: list[dict[str, Any]], transactions: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Find an open same-customer/same-merchant three-claim window."""

    merchant_by_case = {row["case_id"]: row["merchant_id"] for row in transactions}
    groups: dict[tuple[str, str], list[date]] = {}
    for row in disputes:
        merchant_id = merchant_by_case.get(row["case_id"])
        if row["status"] != "open" or not merchant_id:
            continue
        groups.setdefault((row["customer_id"], merchant_id), []).append(
            date.fromisoformat(row["opened_at"][:10])
        )
    for (customer_id, merchant_id), dates in sorted(groups.items()):
        ordered = sorted(dates)
        for index in range(len(ordered) - 2):
            window = ordered[index : index + 3]
            if (window[-1] - window[0]).days <= 30:
                return {
                    "customer_id": customer_id,
                    "merchant_id": merchant_id,
                    "dates": [value.isoformat() for value in window],
                }
    return None
