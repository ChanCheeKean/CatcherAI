"""C16-style route: merchandise not as described, where the merchant changed its listing later.

Selective read: the listing that governs is the snapshot captured on the purchase date; the current
page is retrieved but explicitly rejected.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from domain.events import ActorKind
from runtime.context import RunContext, check
from sandbox import window_deadlines

STEPS = ["gather_evidence"]
POLICY_QUERY = "VISA 13.3 not as described VISA 13.7 cancelled merchandise return refused policy"
SNAPSHOT_QUERY = "refurbished UltraBook listing battery health returns"
GUARANTEE = re.compile(r"battery health guaranteed\s*≥\s*(\d+)%", re.I)
RETURN_DAYS = re.compile(r"(\d+)-day [\w-]* ?returns", re.I)
MEASURED = re.compile(r"\((\d+)%\)")
REFUSED = re.compile(r"final sale|can't issue an RMA", re.I)
DATED = re.compile(r"(20\d\d-\d\d-\d\d)")


def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case, txn = state["case"], state["transactions"][0]
    purchase = date.fromisoformat(txn["txn_local_datetime"][:10])
    communications = ctx.call(
        "get_case_communications",
        "Read the battery report, return request and delivery proof",
        {"case_id": case["case_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.case_communications(case["case_id"]),
    )
    policies = ctx.call(
        "retrieve_knowledge",
        "Retrieve not-as-described and cancelled-merchandise rules",
        {"query": POLICY_QUERY, "as_of": case["opened_at"][:10], "kinds": ["policy", "precedent"]},
        lambda: ctx.knowledge.search(
            POLICY_QUERY, as_of=date.fromisoformat(case["opened_at"][:10]), limit=16
        ),
    )
    snapshots = ctx.call(
        "retrieve_knowledge",
        "Retrieve the listing as it was on the purchase date",
        {"query": SNAPSHOT_QUERY, "as_of": purchase.isoformat(), "kinds": ["research"]},
        lambda: ctx.knowledge.search(SNAPSHOT_QUERY, as_of=purchase, kinds=("research",), limit=3),
    )
    current = ctx.call(
        "search_research",
        "Retrieve today's listing to see whether terms changed",
        {"merchant_id": txn["merchant_id"], "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.research_for_merchant(txn["merchant_id"]),
    )
    listing = next(row for row in snapshots if GUARANTEE.search(row["body"]))
    for row in current:
        if row["doc_id"] != listing["doc_id"] and row["valid_from"] > purchase.isoformat():
            ctx.knowledge.reject(
                row,
                reason=(
                    f"captured {row['valid_from']}, after the {purchase} purchase; terms at sale "
                    "govern"
                ),
                evidence_refs=[listing["doc_id"]],
            )
            ctx.event(
                ActorKind.AGENT,
                "lead_investigator",
                "contradiction_detected",
                (
                    "Merchant's current 'final sale' terms conflict with the listing at the time "
                    "of sale"
                ),
                {
                    "facts": [
                        {
                            "statement": "listing at purchase: 30-day returns",
                            "source": listing["doc_id"],
                        },
                        {
                            "statement": "current page: all refurbished sales final",
                            "source": row["doc_id"],
                        },
                    ],
                    "resolution": "policy as of purchase date governs",
                    "impact": "return refusal was improper",
                },
                [listing["doc_id"], row["doc_id"]],
            )
    text = " ".join(row["body"] + " " + row["attachments"] for row in communications)
    delivered = date.fromisoformat(DATED.findall(re.search(r"delivered[^\"]*", text).group(0))[0])
    return_request = date.fromisoformat(
        re.search(r"renewtek_chat_(20\d\d-\d\d-\d\d)", text).group(1)
    )
    days = int(RETURN_DAYS.search(listing["body"]).group(1))
    window = ctx.call(
        "compute_window_deadlines",
        "Compute the return window promised by the listing at sale",
        {
            "events": {"return_window_end": delivered.isoformat()},
            "days": days,
            "rule": f"{listing['doc_id']} {days}-day returns",
        },
        lambda: {
            k: v.isoformat()
            for k, v in window_deadlines(
                events={"return_window_end": delivered},
                days=days,
                rule="listing return window",
                refs=[listing["doc_id"]],
                emitter=ctx.emitter,
            ).items()
        },
    )
    return {
        "knowledge": [*policies, *snapshots],
        "findings": {
            "listing": listing["doc_id"],
            "guaranteed": int(GUARANTEE.search(listing["body"]).group(1)),
            "measured": int(MEASURED.search(text).group(1)),
            "return_requested": return_request.isoformat(),
            "return_refused": bool(REFUSED.search(text)),
            "delivered": delivered.isoformat(),
            "return_window_end": window["return_window_end"],
            "rejected_pages": [
                row["doc_id"] for row in current if row["doc_id"] != listing["doc_id"]
            ],
        },
        "candidate_condition": "13.3",
    }


def verify(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    findings = state["findings"]
    doc_ids = {row["doc_id"] for row in state["knowledge"]}
    return [
        check(
            "conditions_retrieved",
            {"VISA-13.3@2026-04-18", "VISA-13.7@2026-04-18"} <= doc_ids,
            {},
            ["VISA-13.3@2026-04-18"],
        ),
        check(
            "listing_as_of_purchase_used",
            findings["listing"] in doc_ids,
            {"used": findings["listing"], "rejected": findings["rejected_pages"]},
            [findings["listing"]],
        ),
        check(
            "merchandise_not_as_described",
            findings["measured"] < findings["guaranteed"],
            {"measured_pct": findings["measured"], "guaranteed_pct": findings["guaranteed"]},
            [findings["listing"]],
        ),
        check(
            "return_attempted_within_window_and_refused",
            findings["return_requested"] <= findings["return_window_end"]
            and findings["return_refused"],
            {
                "requested": findings["return_requested"],
                "window_end": findings["return_window_end"],
            },
            [findings["listing"]],
        ),
    ]


def decide(ctx: RunContext, state: dict[str, Any]) -> DecisionRecord:
    case, txn, findings = state["case"], state["transactions"][0], state["findings"]
    amount = Decimal(txn["billing_amount"])
    return DecisionRecord(
        case_id=case["case_id"],
        regime=case["regime"],
        is_dispute=True,
        claim_family="not_as_described",
        network_actions=[
            NetworkAction(
                txn_id=txn["txn_id"],
                case_id=case["case_id"],
                action="file_dispute",
                condition="13.3",
                amount=amount,
                reason="battery below the guaranteed level; return refused contrary to the listing",
                certification=[
                    f"return attempted {findings['return_requested']}; merchant refused RMA",
                    "merchandise at cardholder address",
                ],
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome="provisional_credit_pending_network",
            credit_amount=amount,
            reversal_amount=Decimal("0"),
            liability_amount=Decimal("0"),
        ),
        conditions_considered=[
            {
                "condition": "13.7",
                "fails_because": "acceptable alternative: return refused contrary "
                "to the disclosed return policy; 13.3 fits the defect more directly",
            }
        ],
        adjudication=Adjudication(
            review_panel_used=False,
            confidence=0.94,
            flip_fact="A listing captured on the purchase date without the battery guarantee.",
        ),
        citations=[
            {"doc_id": "VISA-13.3@2026-04-18", "why": "Merchandise did not match its description"},
            {
                "doc_id": "VISA-13.7@2026-04-18",
                "why": "Attempted return refused; alternative condition",
            },
            {"doc_id": findings["listing"], "why": "Listing terms captured on the purchase date"},
        ],
        confidence=0.94,
        explanation_for_cardholder=(
            "On the day you bought it, the listing guaranteed battery health of at least "
            f"{findings['guaranteed']}% "
            f"and 30-day returns. Your report shows {findings['measured']}%, and the seller "
            "refused your return on "
            f"{findings['return_requested']}. The seller's later 'final sale' page does not apply "
            "to your purchase. "
            f"We credited ${amount} and filed a dispute; please keep the laptop and packaging "
            "until it is resolved."
        ),
    )
