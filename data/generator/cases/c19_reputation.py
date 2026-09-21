"""C19: newer delivery facts overturn an old merchant-reputation memory."""

from __future__ import annotations

from graph_builder import Graph

from cases import CaseTruth, transaction_expected


def build(g: Graph, _rng) -> CaseTruth:
    merchant, stale, finding = "MER-C19", "MEM-C19-RELIABLE", "FND-C19-SURGE"
    depot = "ADR-C19-DEPOT"
    hero_dispute, hero_txn = "DSP-2026-90019", "TXN-C19-01"
    hero_intake = "The merchant says my $412 order was delivered but nothing arrived at my home."
    g.node("Merchant", merchant, name="Yesterday Goods", mcc="5942", kind="ecommerce", country="US")
    g.node(
        "Address",
        depot,
        street="4 Foundry Access Road",
        unit="Dock 9",
        city="Newark",
        postcode="07102",
    )
    g.node(
        "MemoryNote",
        stale,
        text="As of May Yesterday Goods had reliable delivery and very low dispute volume.",
        status="active",
        created_at="2026-05-31",
        run_id="merchant-review-2026-05",
        confidence=0.91,
    )
    g.edge(
        "ABOUT",
        stale,
        merchant,
        run_id="merchant-review-2026-05",
        confidence=0.91,
        evidence_path=f"{stale}>{merchant}",
    )
    g.node(
        "Finding",
        finding,
        text="Observed September surge: eight claimed home deliveries route to one Newark depot.",
        kind="merchant_delivery_pattern",
        run_id="merchant-monitor-2026-09",
        confidence=0.96,
        evidence_path="DSP-C19*>TXN-C19*>ORD-C19*>SHP-C19*>ADR-C19-DEPOT",
    )
    g.edge(
        "ABOUT",
        finding,
        merchant,
        run_id="merchant-monitor-2026-09",
        confidence=0.96,
        evidence_path=f"{finding}>{merchant}",
    )
    g.edge(
        "CONTRADICTS",
        finding,
        stale,
        run_id="merchant-monitor-2026-09",
        confidence=0.96,
        evidence_path=f"{finding}>{stale}",
    )

    solution = [hero_dispute, hero_txn, merchant, stale, finding, depot]
    for index in range(1, 9):
        customer, account, card = (
            f"CUS-C19-{index:02d}",
            f"ACC-C19-{index:02d}",
            f"CRD-C19-{index:02d}",
        )
        txn, order, shipment = (
            f"TXN-C19-{index:02d}",
            f"ORD-C19-{index:02d}",
            f"SHP-C19-{index:02d}",
        )
        dispute = hero_dispute if index == 1 else f"DSP-2026-919{index:02d}"
        amount = 412.0 if index == 1 else float(90 + index * 24)
        g.node(
            "Customer",
            customer,
            name=f"Yesterday claimant {index}",
            segment="consumer",
            opened_at="2020-01-01",
        )
        g.node(
            "Account",
            account,
            kind="credit",
            status="open",
            opened_at="2020-01-01",
            credit_limit=5000.0,
        )
        g.node(
            "Card",
            card,
            last4=f"19{index:02d}",
            network="visa",
            status="active",
            issued_at="2025-01-01",
        )
        home = f"ADR-C19-HOME-{index:02d}"
        g.node(
            "Address",
            home,
            street=f"{200 + index} Orchard Street",
            unit=f"{index}A",
            city="Brooklyn",
            postcode="11211",
        )
        g.edge("HOLDS", customer, account, role="primary", valid_from="2020-01-01", valid_to="")
        g.edge("ISSUED_ON", card, account)
        g.edge("LIVES_AT", customer, home, valid_from="2022-01-01", valid_to="")
        g.node(
            "Transaction",
            txn,
            ts=f"2026-09-{index + 2:02d}T11:00:00Z",
            amount=amount,
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
            ts=f"2026-09-{index + 2:02d}T11:00:00Z",
            total=amount,
            currency="USD",
            items="household goods",
        )
        g.edge("FOR_ORDER", txn, order)
        g.node(
            "Shipment",
            shipment,
            carrier="QuickShip",
            tracking=f"QS-C19-{index:04d}",
            shipped_at=f"2026-09-{index + 4:02d}",
        )
        g.edge("SHIPPED_AS", order, shipment)
        g.edge("DELIVERED_TO", shipment, depot, pod="warehouse scan", signer="dock clerk")
        intake = (
            hero_intake
            if index == 1
            else "The merchant says delivered but nothing arrived at my home."
        )
        g.node(
            "Dispute",
            dispute,
            filed_at=f"2026-09-{index + 10:02d}",
            claim_type="not_received",
            amount=amount,
            intake=intake,
            status="open",
        )
        g.edge("FILED_BY", dispute, customer)
        g.edge("DISPUTES", dispute, txn, amount=amount)
        if index <= 4:
            solution.extend([dispute, txn, order, shipment])

    g.node(
        "Transaction",
        "TXN-C19-DECOY",
        ts="2026-03-12T10:00:00Z",
        amount=72.0,
        currency="USD",
        kind="purchase",
        channel="ecommerce",
        status="posted",
    )
    g.edge("PAID_WITH", "TXN-C19-DECOY", "CRD-C19-01")
    g.edge("AT_MERCHANT", "TXN-C19-DECOY", merchant)
    return {
        "case_id": hero_dispute,
        "code": "C19",
        "title": "Yesterday's Reputation",
        "intake": hero_intake,
        "misleading_surface": (
            "A high-confidence reputation note and prior legitimate purchase predate a new "
            "multi-customer delivery pattern."
        ),
        "expected": {
            "verdict": "accepted",
            "claim_family": "not_received_merchant_pattern",
            "transactions": [
                transaction_expected(
                    hero_txn, "accepted", 412.0, 412.0, "file_dispute", "Visa 13.1"
                )
            ],
            "account_actions": ["supersede_merchant_memory", "review_linked_disputes"],
        },
        "solution_node_ids": solution,
        "proof_patterns": [
            {
                "name": "new dispute surge routes shipments away from homes",
                "cypher": (
                    "MATCH (d:Dispute)-[:FILED_BY]->(c:Customer)-[:LIVES_AT]->(home:Address), "
                    "(d)-[:DISPUTES]->(t:Transaction)-[:AT_MERCHANT]->"
                    "(m:Merchant {id: 'MER-C19'}), (t)-[:FOR_ORDER]->"
                    "(o:PurchaseOrder)-[:SHIPPED_AS]->(s:Shipment)-[:DELIVERED_TO]->"
                    "(depot:Address {id: 'ADR-C19-DEPOT'}) WHERE home.id <> depot.id "
                    "RETURN d, c, home, t, m, o, s, depot"
                ),
                "min_rows": 8,
            },
            {
                "name": "new finding contradicts old reputation note",
                "cypher": (
                    "MATCH (f:Finding {id: 'FND-C19-SURGE'})-[:CONTRADICTS]->"
                    "(note:MemoryNote {id: 'MEM-C19-RELIABLE'}), (f)-[:ABOUT]->"
                    "(m:Merchant {id: 'MER-C19'}) RETURN f, note, m"
                ),
                "min_rows": 1,
            },
        ],
        "decoy_patterns": [
            {
                "name": "old reputation and legitimate purchase",
                "cypher": (
                    "MATCH (note:MemoryNote {id: 'MEM-C19-RELIABLE'})-[:ABOUT]->"
                    "(m:Merchant)<-[:AT_MERCHANT]-(t:Transaction {id: 'TXN-C19-DECOY'}) "
                    "RETURN note, m, t"
                ),
                "why_irrelevant": (
                    "Both facts predate the September surge and do not validate the current "
                    "shipment destination."
                ),
            }
        ],
        "missing_evidence": False,
        "human_effort": {
            "hops": 7,
            "entities": 38,
            "note": (
                "Verify an old note against eight newer disputes, customer homes, orders, and "
                "shipments that converge on a non-customer depot."
            ),
        },
    }
