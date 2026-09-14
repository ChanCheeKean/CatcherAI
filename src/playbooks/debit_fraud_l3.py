"""C08-style route: Reg E card-not-present fraud with a cross-customer compromise point."""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from runtime.context import RunContext, check, compact_id_ranges, note_matching
from sandbox import reg_e_deadlines

STEPS = ["gather_evidence", "run_specialists"]
QUERY = (
    "REGE 1005.11 1005.6 LFB CB 2025 09 SOP DSP 006 008 VISA 10.4 new account business days "
    "fraud recovery"
)
REQUIRED = {
    "REGE-1005.11",
    "REGE-1005.6",
    "LFB-SOP-DSP-006@v4",
    "LFB-CB-2025-09",
    "LFB-SOP-DSP-008@v3",
    "VISA-10.4@2026-04-18",
}


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    notice = date.fromisoformat(state["case"]["opened_at"][:10])
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve the Reg E, fraud-recovery and Visa rules as of notice",
        {"query": QUERY, "as_of": notice.isoformat(), "kinds": ["policy", "precedent"]},
        lambda: ctx.knowledge.search(QUERY, as_of=notice, limit=32),
    )
    notes = ctx.call(
        "read_memory_notes",
        "Read the scoped Reg E clock note only as a lead",
        {"subject_ids": ["REGE-1005.11"], "as_of": notice.isoformat(), "minimum_confidence": 0.5},
        lambda: ctx.notes.read_current(subject_ids=["REGE-1005.11"], as_of=notice),
    )
    return {"knowledge": knowledge, "memory_notes": notes, "candidate_condition": "10.4"}


def specialists(
    ctx: RunContext, state: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    case, transactions = state["case"], state["transactions"]
    account = ctx.call(
        "get_account",
        "Verify account opening and first-deposit dates",
        {"account_id": case["account_id"]},
        lambda: ctx.data.account(case["account_id"]),
        actor="reg_e_clock_analyst",
    )
    since, until = account["opened_at"] + "T00:00:00Z", ctx.clock.now.isoformat()
    events = ctx.call(
        "get_account_events",
        "Verify deposit and notice-adjacent account events",
        {"account_id": case["account_id"], "since": since, "until": until},
        lambda: ctx.data.account_events(
            case["account_id"], since=since, until=until.replace("+00:00", "Z")
        ),
        actor="reg_e_clock_analyst",
    )
    holidays = ctx.call(
        "get_bank_holidays",
        "Use the issuer bank calendar for business-day arithmetic",
        {"since": "2026-10-13", "until": "2026-11-30"},
        lambda: ctx.data.bank_holidays(since="2026-10-13", until="2026-11-30"),
        actor="reg_e_clock_analyst",
    )
    fraud_date = transactions[0]["processing_date"]
    cpp = ctx.call(
        "graph_common_compromise_points",
        "Traverse prior card-present use to later fraud across customers",
        {"customer_id": case["customer_id"], "fraud_date": fraud_date, "lookback_days": 30},
        lambda: ctx.graph.common_compromise_points(
            customer_id=case["customer_id"], fraud_date=date.fromisoformat(fraud_date)
        ),
        actor="graph_link_analyst",
    )
    compromise_point = cpp[0]["merchant_id"] if cpp else None
    visit_txn_ids = [node.split(":", 1)[1] for node in cpp[0]["visit_txn_node_ids"]] if cpp else []
    compromise_visits = ctx.call(
        "get_transactions_by_ids",
        "Derive the compromise window from observed card-present visits",
        {"txn_ids": visit_txn_ids, "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.transactions_by_ids(visit_txn_ids),
        actor="graph_link_analyst",
    )
    research = ctx.call(
        "search_research",
        "Corroborate the graph hypothesis with public reporting",
        {"merchant_id": compromise_point, "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.research_for_merchant(compromise_point) if compromise_point else [],
        actor="graph_link_analyst",
    )
    computed = ctx.call(
        "compute_reg_e_deadlines",
        "Compute new-account clocks and liability without free-form arithmetic",
        {
            "notice_date": case["opened_at"][:10],
            "first_deposit_date": account["first_deposit_date"],
            "transaction_dates": [row["processing_date"] for row in transactions],
            "holidays": [row["date"] for row in holidays],
            "card_lost_or_stolen": False,
        },
        lambda: reg_e_deadlines(
            notice_date=date.fromisoformat(case["opened_at"][:10]),
            first_deposit_date=date.fromisoformat(account["first_deposit_date"]),
            transaction_dates=[date.fromisoformat(row["processing_date"]) for row in transactions],
            holidays=[date.fromisoformat(row["date"]) for row in holidays],
            card_lost_or_stolen=False,
            emitter=ctx.emitter,
        ).model_dump(mode="json"),
        actor="reg_e_clock_analyst",
    )
    findings = {
        **state["findings"],
        "account": account,
        "account_events": events,
        "common_compromise_points": cpp,
        "compromise_point": compromise_point,
        "compromise_research": research,
        "compromise_visits": compromise_visits,
        "reg_e_deadlines": computed,
    }
    delegations = [
        {
            "subagent_type": "reg_e_clock_analyst",
            "description": json.dumps(
                {
                    "task": "Independently verify Reg E new-account clocks and liability",
                    "account": account,
                    "events": events,
                    "computed": computed,
                    "source_refs": ["REGE-1005.6", "REGE-1005.11"],
                }
            ),
        },
        {
            "subagent_type": "graph_link_analyst",
            "description": json.dumps(
                {
                    "task": "Assess the common-compromise-point hypothesis",
                    "graph_results": cpp,
                    "research": research,
                }
            ),
        },
    ]
    facts = {**state.get("governance_facts", {}), "cross_customer_finding": bool(cpp)}
    return {"findings": findings, "governance_facts": facts}, delegations


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    note = note_matching(state, tags=("reg_e", "deadline"), subject_id="REGE-1005.11")
    if note:
        ctx.notes.reject(
            note,
            reason="The note uses calendar days and omits the new-account "
            "20-business-day extension",
            evidence_refs=["LFB-CB-2025-09", "REGE-1005.11"],
        )
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    cpp = state["findings"]["common_compromise_points"]
    compromise_point = state["findings"]["compromise_point"]
    research_refs = [row["doc_id"] for row in state["findings"]["compromise_research"]]
    computed = state["findings"]["reg_e_deadlines"]
    return [
        check(
            "reg_e_sources_retrieved_as_of_notice",
            REQUIRED <= doc_ids,
            {"required": sorted(REQUIRED), "doc_ids": sorted(doc_ids)},
            sorted(REQUIRED),
        ),
        check(
            "new_account_business_day_clock",
            computed["new_account"],
            computed,
            ["REGE-1005.11", "LFB-CB-2025-09"],
        ),
        check(
            "card_in_possession_zero_liability",
            computed["liability_amount"] == "0",
            computed,
            ["REGE-1005.6"],
        ),
        check(
            "common_compromise_point_supported",
            bool(cpp)
            and cpp[0]["merchant_id"] == compromise_point
            and cpp[0]["victim_count"] >= 3
            and bool(research_refs),
            {"graph_results": cpp},
            ([compromise_point] if compromise_point else []) + research_refs,
        ),
        check(
            "independent_specialists_completed",
            len(state["specialist_results"]) == 2,
            {"results": state["specialist_results"]},
            [],
        ),
    ]


def hypotheses(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    cpp = state["findings"]["common_compromise_points"][0]
    victims = [node.split(":", 1)[1] for node in cpp["dispute_node_ids"]]
    research_refs = [row["doc_id"] for row in state["findings"]["compromise_research"]]
    return [
        {
            "id": "H1",
            "label": "third-party fraud after a common compromise point",
            "favors": "cardholder",
            "outcome": "credit, zero liability, file 10.4 above the recovery threshold",
            "evidence_for": [
                {
                    "fact": (
                        f"{cpp['victim_count']} other cardholders used the same merchant before "
                        "fraud"
                    ),
                    "refs": victims,
                    "weight": 3,
                },
                {
                    "fact": "public reporting corroborates skimming at the merchant",
                    "refs": research_refs,
                    "weight": 2,
                },
                {
                    "fact": "card remained in the cardholder's possession",
                    "refs": [state["case_id"]],
                    "weight": 2,
                },
            ],
            "evidence_against": [
                {
                    "fact": "orders used the cardholder's card credentials",
                    "refs": [row["txn_id"] for row in state["transactions"]],
                    "weight": 1,
                }
            ],
            "flip_fact": "Evidence that the cardholder possessed or authorized the online orders.",
        },
        {
            "id": "H2",
            "label": "cardholder authorized the online orders",
            "favors": "issuer",
            "outcome": "deny and reverse provisional credit",
            "evidence_for": [
                {
                    "fact": "orders used the cardholder's card credentials",
                    "refs": [row["txn_id"] for row in state["transactions"]],
                    "weight": 1,
                }
            ],
            "evidence_against": [
                {
                    "fact": "shared compromise point across unrelated cardholders",
                    "refs": victims,
                    "weight": 3,
                }
            ],
            "flip_fact": "Device, delivery or login evidence tying the cardholder to the orders.",
        },
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case = state["case"]
    deadlines = state["findings"]["reg_e_deadlines"]
    cpp = state["findings"]["common_compromise_points"][0]
    compromise_point = cpp["merchant_id"]
    research_refs = [row["doc_id"] for row in state["findings"]["compromise_research"]]
    dispute_refs = [node.split(":", 1)[1] for node in cpp["dispute_node_ids"]]
    clustered_refs = max(
        (group for group in _consecutive_groups(dispute_refs) if len(group) >= 3),
        key=len,
        default=dispute_refs,
    )
    visit_dates = [
        date.fromisoformat(row["processing_date"]) for row in state["findings"]["compromise_visits"]
    ]
    notice = date.fromisoformat(case["opened_at"][:10])
    window_start = (
        min(visit_dates) - timedelta(days=7) if visit_dates else notice - timedelta(days=30)
    )
    window = f"{window_start.isoformat()}..{notice.isoformat()}"
    clock_note = note_matching(state, tags=("reg_e", "deadline"), subject_id="REGE-1005.11")
    actions, credited = [], Decimal("0")
    for row in state["transactions"]:
        amount = Decimal(row["billing_amount"])
        credited += amount
        recover = amount >= Decimal("100")
        actions.append(
            NetworkAction(
                txn_id=row["txn_id"],
                case_id=case["case_id"],
                action="file_dispute" if recover else "write_off_no_chargeback",
                reason="Unauthorized CNP debit transaction; fraud reported"
                if recover
                else "Below the current $100 fraud-recovery threshold",
                condition="10.4" if recover else None,
                amount=amount,
                certification=["fraud_reported"],
            )
        )
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=True,
        claim_family="fraud_cnp",
        network_actions=actions,
        cardholder_resolution=CardholderResolution(
            outcome="credited",
            credit_amount=credited,
            reversal_amount=Decimal("0"),
            liability_amount=Decimal(deadlines["liability_amount"]),
        ),
        deadlines={
            key: deadlines[key]
            for key in (
                "provisional_credit_deadline",
                "investigation_deadline",
                "written_confirmation_due_if_bank_requires",
            )
        },
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.97,
            flip_fact="Evidence that the cardholder possessed or authorized the online orders.",
        ),
        automated_actions=[
            {
                "action": "graph_write",
                "edge": "SUSPECTED_COMPROMISE_POINT",
                "subject_id": compromise_point,
                "status": "active",
                "evidence": [*compact_id_ranges(clustered_refs), *research_refs],
            },
            {
                "action": "watchlist_add",
                "list": "merchant_compromise_points",
                "subject_id": compromise_point,
                "window": window,
            },
            {
                "action": "enhanced_monitoring",
                "optional": True,
                "scope": (
                    f"cards with card-present use at {compromise_point} in {window} and no fraud "
                    "claim yet"
                ),
            },
        ],
        account_actions=["fraud_report_tc40", "card_reissue"],
        memory_ops=(
            [
                {
                    "op": "supersede",
                    "note_id": clock_note["note_id"],
                    "replaced_by": "LFB-CB-2025-09",
                    "source_refs": ["LFB-CB-2025-09", "REGE-1005.11"],
                }
            ]
            if clock_note
            else []
        ),
        citations=[
            {"doc_id": "REGE-1005.11", "why": "New-account investigation clocks"},
            {"doc_id": "REGE-1005.6", "why": "Unauthorized transfer liability"},
            {"doc_id": "LFB-SOP-DSP-006@v4", "why": "Reg E investigation"},
            {"doc_id": "LFB-CB-2025-09", "why": "Business-day clarification"},
            {"doc_id": "LFB-SOP-DSP-008@v3", "why": "Fraud recovery threshold"},
            {"doc_id": "VISA-10.4@2026-04-18", "why": "Other fraud—card absent"},
        ],
        hypotheses=[
            {
                "id": "H1",
                "label": "third_party_fraud_after_common_compromise",
                "status": "supported",
            }
        ],
        confidence=0.97,
        explanation_for_cardholder=(
            "We found unauthorized online purchases after a common card-compromise point. Your"
            " card remained in your possession, so your liability is $0; we credited "
            f"${credited:,.2f} and reported the fraud."
        ),
    )


def curate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    corrections = []
    note = note_matching(state, tags=("reg_e", "deadline"), subject_id="REGE-1005.11")
    if note:
        corrections.append(
            ctx.notes.supersede(
                note,
                content=(
                    "Reg E provisional-credit clocks use business days; qualifying new accounts "
                    "receive a 20-business-day investigation period."
                ),
                source_refs=["LFB-CB-2025-09", "REGE-1005.11"],
                valid_from=date(2026, 10, 13),
                confidence=0.99,
                reason="LFB-CB-2025-09 clarified business-day clocks",
            )
        )
    cpp = state["findings"]["common_compromise_points"][0]
    compromise_point = cpp["merchant_id"]
    research_refs = [row["doc_id"] for row in state["findings"]["compromise_research"]]
    visit_dates = [
        date.fromisoformat(row["processing_date"]) for row in state["findings"]["compromise_visits"]
    ]
    notice = date.fromisoformat(state["case"]["opened_at"][:10])
    window_start = (
        min(visit_dates) - timedelta(days=7) if visit_dates else notice - timedelta(days=30)
    )
    window = f"{window_start.isoformat()}..{notice.isoformat()}"
    ctx.graph.write_hypothesis(
        hypothesis_id=f"SuspectedCompromisePoint:{compromise_point}:{window.split('..')[0]}",
        kind="SuspectedCompromisePoint",
        subject_ids=[compromise_point],
        relationship="SUSPECTED_COMPROMISE_POINT",
        evidence_refs=[
            *[
                node.split(":", 1)[1]
                for node in cpp["dispute_node_ids"]
                if node.split(":", 1)[1] != state["case_id"]
            ],
            *research_refs,
        ],
        confidence=0.96,
        properties={"window": window},
    )
    return {"memory_correction_ids": corrections}


def _consecutive_groups(values: list[str]) -> list[list[str]]:
    """Group IDs by prefix and consecutive numeric suffix for evidence summarization."""

    groups: dict[str, list[tuple[int, str]]] = {}
    for value in values:
        prefix = value.rstrip("0123456789")
        suffix = value[len(prefix) :]
        if suffix:
            groups.setdefault(prefix, []).append((int(suffix), value))
    result: list[list[str]] = []
    for entries in groups.values():
        run: list[tuple[int, str]] = []
        for entry in sorted(entries):
            if run and entry[0] != run[-1][0] + 1:
                result.append([value for _, value in run])
                run = []
            run.append(entry)
        if run:
            result.append([value for _, value in run])
    return result
