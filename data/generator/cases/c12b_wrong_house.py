"""C12b: a genuine wrong-house delivery only appears linked through a recycled phone."""

from __future__ import annotations

from graph_builder import Graph

from cases import CaseTruth, transaction_expected


def build(g: Graph, _rng) -> CaseTruth:
    customer, account, card = "CUS-C12B", "ACC-C12B", "CRD-C12B"
    home, wrong = "ADR-C12B-HOME", "ADR-C12B-WRONG"
    merchant, txn, order = "MER-C12B-HOME", "TXN-C12B", "ORD-C12B"
    shipment, request, dispute = "SHP-C12B", "ERQ-C12B", "DSP-2026-90122"
    g.node("Customer", customer, name="Ari Bell", segment="consumer", opened_at="2017-08-09")
    g.node(
        "Account",
        account,
        kind="credit",
        status="open",
        opened_at="2017-08-09",
        credit_limit=7500.0,
    )
    g.node("Card", card, last4="1220", network="visa", status="active", issued_at="2025-08-09")
    g.node("Address", home, street="610 Grove Lane", unit="3C", city="Queens", postcode="11372")
    g.node("Address", wrong, street="601 Grove Lane", unit="3C", city="Queens", postcode="11372")
    g.edge("HOLDS", customer, account, role="primary", valid_from="2017-08-09", valid_to="")
    g.edge("ISSUED_ON", card, account)
    g.edge("LIVES_AT", customer, home, valid_from="2021-06-01", valid_to="")
    g.edge(
        "HAS_PHONE",
        customer,
        "PHN-C12-SHARED",
        valid_from="2023-03-01",
        valid_to="2025-12-31",
    )
    g.node("Merchant", merchant, name="Hearthline Home", mcc="5712", kind="ecommerce", country="US")
    g.node(
        "Transaction",
        txn,
        ts="2026-10-02T14:05:00Z",
        amount=284.20,
        currency="USD",
        kind="purchase",
        channel="ecommerce",
        status="posted",
    )
    g.edge("PAID_WITH", txn, card)
    g.edge("AT_MERCHANT", txn, merchant)
    g.node(
        "PurchaseOrder",
        order,
        ts="2026-10-02T14:05:00Z",
        total=284.20,
        currency="USD",
        items="two bedside lamps",
    )
    g.edge("FOR_ORDER", txn, order)
    g.node(
        "Shipment",
        shipment,
        carrier="ParcelPath",
        tracking="PP-C12B-8841",
        shipped_at="2026-10-04",
    )
    g.edge("SHIPPED_AS", order, shipment)
    g.edge("DELIVERED_TO", shipment, wrong, pod="door photo", signer="none")
    intake = "Tracking shows delivered but the photo is not my house and I never received it."
    g.node(
        "Dispute",
        dispute,
        filed_at="2026-10-09",
        claim_type="not_received",
        amount=284.20,
        intake=intake,
        status="open",
    )
    g.edge("FILED_BY", dispute, customer)
    g.edge("DISPUTES", dispute, txn, amount=284.20)
    g.node(
        "EvidenceRequest",
        request,
        party="merchant",
        status="no_response",
        deadline="2026-10-19",
        deadline_passed=True,
        responded_at="",
    )
    g.edge("REQUESTED", dispute, request, requested_at="2026-10-09")
    return {
        "case_id": dispute,
        "code": "C12b",
        "title": "The Wrong House",
        "intake": intake,
        "misleading_surface": (
            "A recycled phone number creates an apparent porch-ring link even though ownership "
            "ended before the purchase."
        ),
        "expected": {
            "verdict": "accepted",
            "claim_family": "not_received_wrong_address",
            "transactions": [
                transaction_expected(txn, "accepted", 284.20, 284.20, "file_dispute", "Visa 13.1")
            ],
            "account_actions": [],
        },
        "solution_node_ids": [
            dispute,
            customer,
            txn,
            order,
            shipment,
            home,
            wrong,
            request,
            "PHN-C12-SHARED",
        ],
        "proof_patterns": [
            {
                "name": "delivery address differs from current residence",
                "cypher": (
                    "MATCH (d:Dispute {id: 'DSP-2026-90122'})-[:FILED_BY]->"
                    "(c:Customer)-[l:LIVES_AT]->(home:Address), (d)-[:DISPUTES]->"
                    "(t:Transaction)-[:FOR_ORDER]->(o:PurchaseOrder)-[:SHIPPED_AS]->"
                    "(s:Shipment)-[:DELIVERED_TO]->(wrong:Address) "
                    "WHERE home.id <> wrong.id AND l.valid_to IS NULL "
                    "RETURN d, c, home, t, o, s, wrong"
                ),
                "min_rows": 1,
            },
            {
                "name": "merchant missed evidence deadline",
                "cypher": (
                    "MATCH (d:Dispute {id: 'DSP-2026-90122'})-[:REQUESTED]->"
                    "(r:EvidenceRequest) WHERE r.status = 'no_response' AND "
                    "r.deadline_passed = true RETURN d, r"
                ),
                "min_rows": 1,
            },
        ],
        "decoy_patterns": [
            {
                "name": "expired recycled-phone link to porch ring",
                "cypher": (
                    "MATCH (c:Customer {id: 'CUS-C12B'})-[old:HAS_PHONE]->"
                    "(p:Phone {id: 'PHN-C12-SHARED'})<-[current:HAS_PHONE]-"
                    "(ring:Customer) WHERE old.valid_to < current.valid_from "
                    "RETURN c, old, p, current, ring"
                ),
                "why_irrelevant": (
                    "The control customer stopped owning the number before any ring member's "
                    "ownership began and before this purchase."
                ),
            }
        ],
        "missing_evidence": True,
        "human_effort": {
            "hops": 7,
            "entities": 9,
            "note": (
                "Compare the delivery and residence addresses, inspect the missed merchant "
                "deadline, then check both sides of the recycled phone's validity window."
            ),
        },
    }
