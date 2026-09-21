"""C08: several stolen cards converge on one fuel terminal before later fraud."""

from __future__ import annotations

from graph_builder import Graph

from cases import CaseTruth, transaction_expected


def build(g: Graph, _rng) -> CaseTruth:
    merchant, terminal = "MER-C08-FUEL", "TRM-C08-PUMP6"
    g.node("Merchant", merchant, name="Red Mesa Fuel", mcc="5542", kind="fuel", country="US")
    g.node("Terminal", terminal, kind="physical", location="Red Mesa Fuel pump 6")
    g.edge("AT_MERCHANT", terminal, merchant)
    current_dispute = "DSP-2026-90008"
    current_fraud = "TXN-C08-FRAUD-1"
    solution = [current_dispute, current_fraud, terminal, merchant]
    for i in range(6):
        customer, account, card = f"CUS-C08-{i + 1}", f"ACC-C08-{i + 1}", f"CRD-C08-{i + 1}"
        exposure, fraud = f"TXN-C08-PUMP-{i + 1}", f"TXN-C08-FRAUD-{i + 1}"
        dispute = current_dispute if i == 0 else f"DSP-2026-908{i + 1:02d}"
        g.node(
            "Customer",
            customer,
            name=f"Pump Six claimant {i + 1}",
            segment="consumer",
            opened_at="2020-01-01",
        )
        g.node(
            "Account",
            account,
            kind="credit",
            status="open",
            opened_at="2020-01-01",
            credit_limit=6000.0,
        )
        g.node(
            "Card",
            card,
            last4=f"08{i + 1:02d}",
            network="visa",
            status="active",
            issued_at="2025-01-01",
        )
        g.edge("HOLDS", customer, account, role="primary", valid_from="2020-01-01", valid_to="")
        g.edge("ISSUED_ON", card, account)
        g.node(
            "Transaction",
            exposure,
            ts=f"2026-09-{10 + i:02d}T1{i}:00:00Z",
            amount=42.0 + i,
            currency="USD",
            kind="purchase",
            channel="card_present",
            status="posted",
        )
        g.edge("PAID_WITH", exposure, card)
        g.edge("AT_MERCHANT", exposure, merchant)
        g.edge("VIA_TERMINAL", exposure, terminal)
        amount = 642.90 if i == 0 else 300.0 + i * 37
        g.node(
            "Transaction",
            fraud,
            ts=f"2026-09-{20 + i:02d}T03:00:00Z",
            amount=amount,
            currency="USD",
            kind="purchase",
            channel="card_present",
            status="posted",
        )
        g.edge("PAID_WITH", fraud, card)
        case_intake = (
            "I still have my card and did not make the $642.90 purchase reported this week."
            if i == 0
            else "I did not make this cash-equivalent purchase."
        )
        g.node(
            "Dispute",
            dispute,
            filed_at=f"2026-09-{22 + i:02d}",
            claim_type="fraud",
            amount=amount,
            intake=case_intake,
            status="open",
        )
        g.edge("FILED_BY", dispute, customer)
        g.edge("DISPUTES", dispute, fraud, amount=amount)
        if i < 3:
            solution.extend([card, exposure])
    decoy_customer, decoy_account, decoy_card, decoy_txn = (
        "CUS-C08-DECOY",
        "ACC-C08-DECOY",
        "CRD-C08-DECOY",
        "TXN-C08-DECOY",
    )
    g.node(
        "Customer",
        decoy_customer,
        name="Early fuel customer",
        segment="consumer",
        opened_at="2019-01-01",
    )
    g.node(
        "Account",
        decoy_account,
        kind="credit",
        status="open",
        opened_at="2019-01-01",
        credit_limit=4000.0,
    )
    g.node(
        "Card", decoy_card, last4="0800", network="visa", status="active", issued_at="2024-01-01"
    )
    g.edge(
        "HOLDS", decoy_customer, decoy_account, role="primary", valid_from="2019-01-01", valid_to=""
    )
    g.edge("ISSUED_ON", decoy_card, decoy_account)
    g.node(
        "Transaction",
        decoy_txn,
        ts="2026-07-02T12:00:00Z",
        amount=51.20,
        currency="USD",
        kind="purchase",
        channel="card_present",
        status="posted",
    )
    g.edge("PAID_WITH", decoy_txn, decoy_card)
    g.edge("VIA_TERMINAL", decoy_txn, terminal)
    intake = "I still have my card and did not make the $642.90 purchase reported this week."
    return {
        "case_id": current_dispute,
        "code": "C08",
        "title": "Pump Six",
        "intake": intake,
        "misleading_surface": (
            "One unauthorized purchase appears isolated until earlier card histories are joined "
            "across disputes."
        ),
        "expected": {
            "verdict": "accepted",
            "claim_family": "fraud_card_present",
            "transactions": [
                transaction_expected(
                    current_fraud, "accepted", 642.90, 642.90, "file_dispute", "Visa 10.3"
                )
            ],
            "account_actions": ["card_reissue", "fraud_report", "flag_compromise_point"],
        },
        "solution_node_ids": solution,
        "proof_patterns": [
            {
                "name": "multiple disputed cards share recent terminal",
                "cypher": (
                    "MATCH (d:Dispute)-[:DISPUTES]->(fraud:Transaction)-[:PAID_WITH]->"
                    "(c:Card)<-[:PAID_WITH]-(prior:Transaction)-[:VIA_TERMINAL]->"
                    "(term:Terminal {id: 'TRM-C08-PUMP6'}) "
                    "WHERE prior.ts >= '2026-09-10' AND prior.ts <= '2026-09-16' "
                    "RETURN d, fraud, c, prior, term"
                ),
                "min_rows": 6,
            }
        ],
        "decoy_patterns": [
            {
                "name": "undisputed card used terminal before compromise window",
                "cypher": (
                    "MATCH (t:Transaction {id: 'TXN-C08-DECOY'})-[:VIA_TERMINAL]->"
                    "(term:Terminal), (t)-[:PAID_WITH]->(c:Card) RETURN t, term, c"
                ),
                "why_irrelevant": (
                    "Its July use predates the September compromise window and the card has no "
                    "linked dispute."
                ),
            }
        ],
        "missing_evidence": False,
        "human_effort": {
            "hops": 6,
            "entities": 15,
            "note": (
                "Pivot from six later fraud disputes back through their cards and earlier "
                "purchases, then compare a non-disputed out-of-window card."
            ),
        },
    }
