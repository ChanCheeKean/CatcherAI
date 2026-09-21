"""C04: two clearing records for one two-item order, not duplicate billing."""

from __future__ import annotations

from graph_builder import Graph

from cases import CaseTruth, transaction_expected


def build(g: Graph, _rng) -> CaseTruth:
    customer, account, card = "CUS-C04", "ACC-C04", "CRD-C04"
    merchant, auth, order = "MER-C04", "AUT-C04", "ORD-C04"
    first, second = "TXN-C04-FIRST", "TXN-C04-SECOND"
    shipment_a, shipment_b = "SHP-C04-A", "SHP-C04-B"
    home, nearby = "ADR-C04-HOME", "ADR-C04-NEARBY"
    dispute = "DSP-2026-90004"
    g.node(
        "Customer", customer, name="Remy Achebe-Lowe", segment="consumer", opened_at="2012-02-10"
    )
    g.node(
        "Account",
        account,
        kind="credit",
        status="open",
        opened_at="2012-02-10",
        credit_limit=12000.0,
    )
    g.node("Card", card, last4="0404", network="visa", status="active", issued_at="2025-02-10")
    g.node(
        "Address", home, street="417 Parcel Street", unit="2A", city="Pittsburgh", postcode="15222"
    )
    g.node(
        "Address",
        nearby,
        street="417 Parcel Street",
        unit="2B",
        city="Pittsburgh",
        postcode="15222",
    )
    g.edge("HOLDS", customer, account, role="primary", valid_from="2012-02-10", valid_to="")
    g.edge("ISSUED_ON", card, account)
    g.edge("LIVES_AT", customer, home, valid_from="2022-01-01", valid_to="")
    g.node("Merchant", merchant, name="Parcelwick Home", mcc="5719", kind="ecommerce", country="US")
    g.node(
        "Authorization",
        auth,
        ts="2026-10-03T20:12:31Z",
        amount=128.36,
        currency="USD",
        status="approved",
    )
    g.edge("PAID_WITH", auth, card)
    g.node(
        "PurchaseOrder",
        order,
        ts="2026-10-03T20:12:31Z",
        total=128.36,
        currency="USD",
        items="2 x Harlow brass floor lamp",
    )
    for txn_id, seq, ts in (
        (first, 1, "2026-10-05T09:30:00Z"),
        (second, 2, "2026-10-09T09:30:00Z"),
    ):
        g.node(
            "Transaction",
            txn_id,
            ts=ts,
            amount=64.18,
            currency="USD",
            kind="purchase",
            channel="ecommerce",
            status="posted",
        )
        g.edge("PAID_WITH", txn_id, card)
        g.edge("AT_MERCHANT", txn_id, merchant)
        g.edge("CLEARS", txn_id, auth, seq=seq)
        g.edge("FOR_ORDER", txn_id, order)
    for shipment, shipped, signer in (
        (shipment_a, "2026-10-05", "resident"),
        (shipment_b, "2026-10-09", "front desk"),
    ):
        g.node(
            "Shipment",
            shipment,
            carrier="ParcelPath",
            tracking=f"PP-{shipment}",
            shipped_at=shipped,
        )
        g.edge("SHIPPED_AS", order, shipment)
        g.edge("DELIVERED_TO", shipment, home, pod="photo", signer=signer)
    g.node(
        "Shipment",
        "SHP-C04-DECOY",
        carrier="ParcelPath",
        tracking="PP-WRONG-UNIT",
        shipped_at="2026-10-08",
    )
    g.edge("DELIVERED_TO", "SHP-C04-DECOY", nearby, pod="photo", signer="neighbor")
    intake = "Parcelwick charged me $64.18 twice for the one lamp I ordered."
    g.node(
        "Dispute",
        dispute,
        filed_at="2026-10-13",
        claim_type="duplicate",
        amount=64.18,
        intake=intake,
        status="open",
    )
    g.edge("FILED_BY", dispute, customer)
    g.edge("DISPUTES", dispute, second, amount=64.18)
    return {
        "case_id": dispute,
        "code": "C04",
        "title": "Split, Not Double",
        "intake": intake,
        "misleading_surface": (
            "Equal statement amounts look duplicated until the shared authorization, quantity, "
            "and shipments are joined."
        ),
        "expected": {
            "verdict": "rejected",
            "claim_family": "duplicate",
            "transactions": [
                transaction_expected(second, "rejected", 64.18, 0.0, "no_dispute", None)
            ],
            "account_actions": [],
        },
        "solution_node_ids": [dispute, first, second, auth, order, shipment_a, shipment_b, home],
        "proof_patterns": [
            {
                "name": "split clearing and shipment proof",
                "cypher": (
                    "MATCH (a:Transaction {id: 'TXN-C04-FIRST'})-[:CLEARS]->"
                    "(auth:Authorization)<-[:CLEARS]-(b:Transaction {id: 'TXN-C04-SECOND'}), "
                    "(a)-[:FOR_ORDER]->(o:PurchaseOrder)<-[:FOR_ORDER]-(b), "
                    "(o)-[:SHIPPED_AS]->(s:Shipment)-[:DELIVERED_TO]->(addr:Address) "
                    "RETURN a, b, auth, o, s, addr"
                ),
                "min_rows": 2,
            }
        ],
        "decoy_patterns": [
            {
                "name": "same-street wrong-unit delivery",
                "cypher": (
                    "MATCH (s:Shipment {id: 'SHP-C04-DECOY'})-[:DELIVERED_TO]->"
                    "(a:Address {id: 'ADR-C04-NEARBY'}) RETURN s, a"
                ),
                "why_irrelevant": (
                    "That shipment has no edge to the disputed order and went to unit 2B, not 2A."
                ),
            }
        ],
        "missing_evidence": False,
        "human_effort": {
            "hops": 4,
            "entities": 8,
            "note": (
                "Reconcile two clearings to one authorization and order, then verify both item "
                "shipments and delivery unit."
            ),
        },
    }
