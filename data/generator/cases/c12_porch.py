"""C12: coordinated non-receipt claims form a shared identity component."""

from __future__ import annotations

from graph_builder import Graph

from cases import CaseTruth, transaction_expected


def build(g: Graph, _rng) -> CaseTruth:
    phone, device = "PHN-C12-SHARED", "DEV-C12-SHARED"
    address, nearby = "ADR-C12-RING", "ADR-C12-DECOY"
    merchant = "MER-C12-MARKET"
    hero_dispute, hero_txn = "DSP-2026-90012", "TXN-C12-01"
    hero_intake = (
        "The $319.75 parcel never arrived even though tracking says it was left at my door."
    )
    g.node("Phone", phone, number="+1-646-555-1212")
    g.node("Device", device, kind="phone", fingerprint="c12-porch-ring-device")
    g.node("Address", address, street="29 Lantern Court", unit="1", city="Queens", postcode="11372")
    g.node("Address", nearby, street="29 Lantern Court", unit="7", city="Queens", postcode="11372")
    g.node(
        "Merchant", merchant, name="Harborlane Market", mcc="5399", kind="ecommerce", country="US"
    )

    solution = [hero_dispute, hero_txn, phone, device, address, merchant]
    for index in range(1, 5):
        customer, account, card = (
            f"CUS-C12-{index:02d}",
            f"ACC-C12-{index:02d}",
            f"CRD-C12-{index:02d}",
        )
        txn, order, shipment = (
            f"TXN-C12-{index:02d}",
            f"ORD-C12-{index:02d}",
            f"SHP-C12-{index:02d}",
        )
        dispute = hero_dispute if index == 1 else f"DSP-2026-912{index:02d}"
        amount = 319.75 if index == 1 else float(145 + index * 37)
        g.node(
            "Customer",
            customer,
            name=f"Lantern claimant {index}",
            segment="consumer",
            opened_at="2025-02-01",
        )
        g.node(
            "Account",
            account,
            kind="credit",
            status="open",
            opened_at="2025-02-01",
            credit_limit=4000.0,
        )
        g.node(
            "Card",
            card,
            last4=f"12{index:02d}",
            network="visa",
            status="active",
            issued_at="2025-02-01",
        )
        g.edge("HOLDS", customer, account, role="primary", valid_from="2025-02-01", valid_to="")
        g.edge("ISSUED_ON", card, account)
        g.edge("CARRIES", customer, device)
        g.edge("HAS_PHONE", customer, phone, valid_from="2026-01-01", valid_to="")
        g.edge("LIVES_AT", customer, address, valid_from="2026-01-01", valid_to="")
        g.node(
            "Transaction",
            txn,
            ts=f"2026-09-{10 + index:02d}T18:20:00Z",
            amount=amount,
            currency="USD",
            kind="purchase",
            channel="ecommerce",
            status="posted",
        )
        g.edge("PAID_WITH", txn, card)
        g.edge("AT_MERCHANT", txn, merchant)
        g.edge("FROM_DEVICE", txn, device)
        g.node(
            "PurchaseOrder",
            order,
            ts=f"2026-09-{10 + index:02d}T18:20:00Z",
            total=amount,
            currency="USD",
            items="consumer electronics",
        )
        g.edge("FOR_ORDER", txn, order)
        g.edge("FROM_DEVICE", order, device)
        g.node(
            "Shipment",
            shipment,
            carrier="CityPost",
            tracking=f"CP-C12-{index:04d}",
            shipped_at=f"2026-09-{12 + index:02d}",
        )
        g.edge("SHIPPED_AS", order, shipment)
        g.edge("DELIVERED_TO", shipment, address, pod="door photo", signer="resident")
        intake = (
            hero_intake
            if index == 1
            else "The parcel never arrived even though tracking says it was left at my door."
        )
        g.node(
            "Dispute",
            dispute,
            filed_at=f"2026-09-{18 + index:02d}",
            claim_type="not_received",
            amount=amount,
            intake=intake,
            status="open",
        )
        g.edge("FILED_BY", dispute, customer)
        g.edge("DISPUTES", dispute, txn, amount=amount)
        if index <= 3:
            solution.extend([customer, txn, dispute])

    g.node(
        "Customer",
        "CUS-C12-DECOY",
        name="Lantern neighbor",
        segment="consumer",
        opened_at="2020-01-01",
    )
    g.edge("LIVES_AT", "CUS-C12-DECOY", nearby, valid_from="2024-01-01", valid_to="")
    return {
        "case_id": hero_dispute,
        "code": "C12",
        "title": "The Porch Ring",
        "intake": hero_intake,
        "misleading_surface": (
            "A routine porch-theft story hides four claimants sharing a phone, device, address, "
            "merchant, and delivery pattern."
        ),
        "expected": {
            "verdict": "rejected",
            "claim_family": "coordinated_not_received_abuse",
            "transactions": [
                transaction_expected(hero_txn, "rejected", 319.75, 0.0, "no_dispute", None)
            ],
            "account_actions": ["record_ring_finding", "review_linked_disputes"],
        },
        "solution_node_ids": solution,
        "proof_patterns": [
            {
                "name": "four claimants share identity and delivery component",
                "cypher": (
                    "MATCH (d:Dispute)-[:FILED_BY]->(c:Customer)-[:HAS_PHONE]->"
                    "(p:Phone {id: 'PHN-C12-SHARED'}), (c)-[:CARRIES]->"
                    "(dev:Device {id: 'DEV-C12-SHARED'}), (c)-[:LIVES_AT]->"
                    "(a:Address {id: 'ADR-C12-RING'}), (d)-[:DISPUTES]->"
                    "(t:Transaction)-[:FOR_ORDER]->(o:PurchaseOrder)-[:SHIPPED_AS]->"
                    "(s:Shipment)-[:DELIVERED_TO]->(a) RETURN d, c, p, dev, a, t, o, s"
                ),
                "min_rows": 4,
            }
        ],
        "decoy_patterns": [
            {
                "name": "same-street neighbor",
                "cypher": (
                    "MATCH (c:Customer {id: 'CUS-C12-DECOY'})-[:LIVES_AT]->"
                    "(a:Address {id: 'ADR-C12-DECOY'}) RETURN c, a"
                ),
                "why_irrelevant": (
                    "The neighbor is in unit 7 and has no shared phone, device, order, or dispute."
                ),
            }
        ],
        "missing_evidence": False,
        "human_effort": {
            "hops": 8,
            "entities": 21,
            "note": (
                "Trace four disputes through claimant identities, order devices, and proof-of-"
                "delivery addresses while excluding a same-street neighbor."
            ),
        },
    }
