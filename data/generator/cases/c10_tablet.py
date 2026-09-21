"""C10: an authorized family member used the shared household tablet."""

from __future__ import annotations

from graph_builder import Graph

from cases import CaseTruth, transaction_expected


def build(g: Graph, _rng) -> CaseTruth:
    primary, family, account, card = "CUS-C10-PRIMARY", "CUS-C10-FAMILY", "ACC-C10", "CRD-C10"
    tablet, merchant, txn, dispute = "DEV-C10-TABLET", "MER-C10-GAMES", "TXN-C10", "DSP-2026-90010"
    home, nearby = "ADR-C10-HOME", "ADR-C10-DECOY"
    g.node("Customer", primary, name="Morgan Reed", segment="consumer", opened_at="2018-03-12")
    g.node("Customer", family, name="Jamie Reed", segment="student", opened_at="2022-06-01")
    g.node(
        "Account",
        account,
        kind="credit",
        status="open",
        opened_at="2018-03-12",
        credit_limit=9000.0,
    )
    g.node("Card", card, last4="1010", network="visa", status="active", issued_at="2025-03-12")
    g.node("Device", tablet, kind="tablet", fingerprint="family-tablet-c10")
    g.node("Address", home, street="84 Linden Road", unit="4A", city="Austin", postcode="78701")
    g.node("Address", nearby, street="84 Linden Road", unit="4B", city="Austin", postcode="78701")
    g.edge("HOLDS", primary, account, role="primary", valid_from="2018-03-12", valid_to="")
    g.edge("HOLDS", family, account, role="authorized", valid_from="2025-02-01", valid_to="")
    g.edge("ISSUED_ON", card, account)
    g.edge("CARRIES", primary, tablet)
    g.edge("CARRIES", family, tablet)
    g.edge("LOGGED_IN_FROM", family, tablet, ts="2026-10-11T19:03:00Z", ip="198.51.100.24")
    g.edge("LIVES_AT", primary, home, valid_from="2021-01-01", valid_to="")
    g.edge("LIVES_AT", family, home, valid_from="2021-01-01", valid_to="")
    g.node(
        "Merchant", merchant, name="Northstar Game Market", mcc="5816", kind="digital", country="US"
    )
    g.node(
        "Transaction",
        txn,
        ts="2026-10-11T19:05:00Z",
        amount=486.77,
        currency="USD",
        kind="purchase",
        channel="ecommerce",
        status="posted",
    )
    g.edge("PAID_WITH", txn, card)
    g.edge("AT_MERCHANT", txn, merchant)
    g.edge("FROM_DEVICE", txn, tablet)
    intake = "I did not make these game purchases totaling $486.77; the card never left my wallet."
    g.node(
        "Dispute",
        dispute,
        filed_at="2026-10-14",
        claim_type="fraud",
        amount=486.77,
        intake=intake,
        status="open",
    )
    g.edge("FILED_BY", dispute, primary)
    g.edge("DISPUTES", dispute, txn, amount=486.77)
    g.node(
        "Customer", "CUS-C10-DECOY", name="Taylor Reid", segment="consumer", opened_at="2024-01-01"
    )
    g.edge("LIVES_AT", "CUS-C10-DECOY", nearby, valid_from="2025-01-01", valid_to="")
    return {
        "case_id": dispute,
        "code": "C10",
        "title": "Family Tablet",
        "intake": intake,
        "misleading_surface": (
            "Possession of the physical card distracts from an authorized user acting on a "
            "shared device."
        ),
        "expected": {
            "verdict": "rejected",
            "claim_family": "household_authority",
            "transactions": [
                transaction_expected(txn, "rejected", 486.77, 0.0, "no_dispute", None)
            ],
            "account_actions": [],
        },
        "solution_node_ids": [dispute, txn, tablet, family, primary, account, card, home],
        "proof_patterns": [
            {
                "name": "transaction device reaches authorized user",
                "cypher": (
                    "MATCH (d:Dispute {id: 'DSP-2026-90010'})-[:DISPUTES]->"
                    "(t:Transaction)-[:FROM_DEVICE]->(dev:Device)<-[:LOGGED_IN_FROM]-"
                    "(u:Customer)-[h:HOLDS]->(a:Account)<-[:ISSUED_ON]-(c:Card)"
                    "<-[:PAID_WITH]-(t) WHERE h.role = 'authorized' "
                    "RETURN d, t, dev, u, h, a, c"
                ),
                "min_rows": 1,
            }
        ],
        "decoy_patterns": [
            {
                "name": "same-street different-unit resident",
                "cypher": (
                    "MATCH (c:Customer {id: 'CUS-C10-DECOY'})-[:LIVES_AT]->"
                    "(a:Address {id: 'ADR-C10-DECOY'}) RETURN c, a"
                ),
                "why_irrelevant": (
                    "The similarly named neighbor is in unit 4B and has no path to the account, "
                    "card, tablet, or transaction."
                ),
            }
        ],
        "missing_evidence": False,
        "human_effort": {
            "hops": 7,
            "entities": 8,
            "note": (
                "Follow the purchase to a device, identify the recent household login, and verify "
                "that person's active authorized-user role on the card account."
            ),
        },
    }
