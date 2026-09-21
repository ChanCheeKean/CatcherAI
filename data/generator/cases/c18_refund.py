"""C18: an unlinked partial credit is matched through its order."""

from __future__ import annotations

from graph_builder import Graph

from cases import CaseTruth, transaction_expected


def build(g: Graph, _rng) -> CaseTruth:
    customer, account, card = "CUS-C18", "ACC-C18", "CRD-C18"
    merchant, purchase, credit = "MER-C18", "TXN-C18-PURCHASE", "TXN-C18-CREDIT"
    order, request, dispute = "ORD-C18", "ERQ-C18", "DSP-2026-90018"
    g.node("Customer", customer, name="Eli Navarro", segment="consumer", opened_at="2015-11-03")
    g.node(
        "Account",
        account,
        kind="credit",
        status="open",
        opened_at="2015-11-03",
        credit_limit=8500.0,
    )
    g.node("Card", card, last4="1818", network="visa", status="active", issued_at="2025-11-03")
    g.edge("HOLDS", customer, account, role="primary", valid_from="2015-11-03", valid_to="")
    g.edge("ISSUED_ON", card, account)
    g.node("Merchant", merchant, name="Maple & Loom", mcc="5651", kind="ecommerce", country="US")
    g.node(
        "PurchaseOrder",
        order,
        ts="2026-09-28T12:00:00Z",
        total=240.0,
        currency="USD",
        items="coat returned in full",
    )
    g.node(
        "Transaction",
        purchase,
        ts="2026-09-28T12:00:00Z",
        amount=240.0,
        currency="USD",
        kind="purchase",
        channel="ecommerce",
        status="posted",
    )
    g.edge("PAID_WITH", purchase, card)
    g.edge("AT_MERCHANT", purchase, merchant)
    g.edge("FOR_ORDER", purchase, order)
    g.node(
        "Transaction",
        credit,
        ts="2026-10-11T08:40:00Z",
        amount=-180.0,
        currency="USD",
        kind="refund",
        channel="ecommerce",
        status="posted",
    )
    g.edge("PAID_WITH", credit, card)
    g.edge("AT_MERCHANT", credit, merchant)
    g.edge("FOR_ORDER", credit, order)
    intake = "I returned the $240 coat but the merchant never credited my account."
    g.node(
        "Dispute",
        dispute,
        filed_at="2026-10-14",
        claim_type="refund",
        amount=240.0,
        intake=intake,
        status="open",
    )
    g.edge("FILED_BY", dispute, customer)
    g.edge("DISPUTES", dispute, purchase, amount=240.0)
    g.node(
        "EvidenceRequest",
        request,
        party="merchant",
        status="no_response",
        deadline="2026-10-24",
        deadline_passed=True,
        responded_at="",
    )
    g.edge("REQUESTED", dispute, request, requested_at="2026-10-14")

    g.node(
        "Transaction",
        "TXN-C18-DECOY-PURCHASE",
        ts="2026-09-26T10:00:00Z",
        amount=180.0,
        currency="USD",
        kind="purchase",
        channel="ecommerce",
        status="posted",
    )
    g.node(
        "Transaction",
        "TXN-C18-DECOY-CREDIT",
        ts="2026-10-10T10:00:00Z",
        amount=-180.0,
        currency="USD",
        kind="refund",
        channel="ecommerce",
        status="posted",
    )
    g.edge("REFUNDS", "TXN-C18-DECOY-CREDIT", "TXN-C18-DECOY-PURCHASE")
    return {
        "case_id": dispute,
        "code": "C18",
        "title": "The Refund That Crossed",
        "intake": intake,
        "misleading_surface": (
            "The statement lacks a direct refund link, but a credit for the same order already "
            "covered most of the claimed amount."
        ),
        "expected": {
            "verdict": "partially_accepted",
            "claim_family": "credit_not_processed_partial",
            "transactions": [
                transaction_expected(
                    purchase, "partially_accepted", 240.0, 60.0, "file_dispute", "Visa 13.6"
                )
            ],
            "account_actions": [],
        },
        "solution_node_ids": [
            dispute,
            customer,
            card,
            purchase,
            credit,
            order,
            merchant,
            request,
        ],
        "proof_patterns": [
            {
                "name": "unlinked credit matches purchase through order",
                "cypher": (
                    "MATCH (d:Dispute {id: 'DSP-2026-90018'})-[:DISPUTES]->"
                    "(purchase:Transaction)-[:FOR_ORDER]->(o:PurchaseOrder)<-[:FOR_ORDER]-"
                    "(credit:Transaction), (d)-[:REQUESTED]->(r:EvidenceRequest) "
                    "WHERE purchase.amount > 0 AND credit.amount < 0 AND "
                    "r.status = 'no_response' RETURN d, purchase, o, credit, r"
                ),
                "min_rows": 1,
            }
        ],
        "decoy_patterns": [
            {
                "name": "same-amount credit for another purchase",
                "cypher": (
                    "MATCH (credit:Transaction {id: 'TXN-C18-DECOY-CREDIT'})-[:REFUNDS]->"
                    "(purchase:Transaction {id: 'TXN-C18-DECOY-PURCHASE'}) RETURN credit, purchase"
                ),
                "why_irrelevant": (
                    "The equal-sized credit explicitly refunds another purchase and has no path "
                    "to the disputed order or card."
                ),
            }
        ],
        "missing_evidence": True,
        "human_effort": {
            "hops": 5,
            "entities": 8,
            "note": (
                "Search unlinked credits, match one through the order, reconcile the $180 credit "
                "against $240, and assess the $60 remainder after no merchant response."
            ),
        },
    }
