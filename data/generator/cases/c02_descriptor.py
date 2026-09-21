"""C02: a familiar coffee shop hidden behind a new facilitator descriptor."""

from __future__ import annotations

from graph_builder import Graph

from cases import CaseTruth, transaction_expected


def build(g: Graph, _rng) -> CaseTruth:
    customer, account, card = "CUS-C02", "ACC-C02", "CRD-C02"
    merchant, decoy_merchant = "MER-C02", "MER-C02-DECOY"
    descriptor, old_descriptor = "DSC-C02-TAPR", "DSC-C02-OLD"
    disputed, prior_a, prior_b = "TXN-C02-DISPUTED", "TXN-C02-PRIOR-A", "TXN-C02-PRIOR-B"
    dispute = "DSP-2026-90002"
    g.node(
        "Customer", customer, name="Hollis Marchetti", segment="consumer", opened_at="2016-05-02"
    )
    g.node(
        "Account",
        account,
        kind="credit",
        status="open",
        opened_at="2016-05-02",
        credit_limit=8000.0,
    )
    g.node("Card", card, last4="0202", network="visa", status="active", issued_at="2025-05-02")
    g.edge("HOLDS", customer, account, role="primary", valid_from="2016-05-02", valid_to="")
    g.edge("ISSUED_ON", card, account)
    g.node(
        "Merchant",
        merchant,
        name="Bluefern Coffee Roasters",
        mcc="5814",
        kind="retail",
        country="US",
    )
    g.node(
        "Merchant", decoy_merchant, name="Blue Fern Books", mcc="5942", kind="retail", country="US"
    )
    g.node("Descriptor", old_descriptor, text="BLUEFERN COFFEE ROASTERS")
    g.node("Descriptor", descriptor, text="TAPR* BLUEFERN CAFE BOSTON")
    g.edge("DESCRIBES", old_descriptor, merchant, valid_from="2018-09-10", valid_to="2026-09-02")
    g.edge("SUB_MERCHANT_OF", descriptor, merchant)
    for txn_id, ts, amount, shown in (
        (prior_a, "2026-08-04T08:12:00Z", 9.75, old_descriptor),
        (prior_b, "2026-08-27T08:19:00Z", 12.60, old_descriptor),
        (disputed, "2026-10-14T08:12:00Z", 11.40, descriptor),
    ):
        g.node(
            "Transaction",
            txn_id,
            ts=ts,
            amount=amount,
            currency="USD",
            kind="purchase",
            channel="card_present",
            status="posted",
        )
        g.edge("PAID_WITH", txn_id, card)
        g.edge("AT_MERCHANT", txn_id, merchant)
        g.edge("DESCRIBES", shown, txn_id, valid_from=ts[:10], valid_to="")
    g.node("Descriptor", "DSC-C02-DECOY", text="BLUE FERN")
    g.edge("DESCRIBES", "DSC-C02-DECOY", decoy_merchant, valid_from="2024-01-01", valid_to="")
    intake = "I do not recognize the $11.40 TAPR* BLUEFERN CAFE BOSTON charge on October 14."
    g.node(
        "Dispute",
        dispute,
        filed_at="2026-10-19",
        claim_type="fraud",
        amount=11.40,
        intake=intake,
        status="open",
    )
    g.edge("FILED_BY", dispute, customer)
    g.edge("DISPUTES", dispute, disputed, amount=11.40)
    return {
        "case_id": dispute,
        "code": "C02",
        "title": "Coffee by Another Name",
        "intake": intake,
        "misleading_surface": "The facilitator prefix makes a regular merchant look unfamiliar.",
        "expected": {
            "verdict": "not_a_dispute",
            "claim_family": "descriptor_confusion",
            "transactions": [
                transaction_expected(disputed, "not_a_dispute", 11.40, 0.0, "none", None)
            ],
            "account_actions": [],
        },
        "solution_node_ids": [dispute, disputed, descriptor, merchant, prior_a, prior_b, card],
        "proof_patterns": [
            {
                "name": "new descriptor reaches cardholder history",
                "cypher": (
                    "MATCH (d:Dispute {id: 'DSP-2026-90002'})-[:DISPUTES]->"
                    "(t:Transaction)<-[:DESCRIBES]-(x:Descriptor)-[:SUB_MERCHANT_OF]->"
                    "(m:Merchant)<-[:AT_MERCHANT]-(prior:Transaction)-[:PAID_WITH]->(c:Card) "
                    "WHERE (t)-[:PAID_WITH]->(c) AND prior.ts < t.ts "
                    "RETURN d, t, x, m, prior, c"
                ),
                "min_rows": 2,
            }
        ],
        "decoy_patterns": [
            {
                "name": "similarly named merchant",
                "cypher": (
                    "MATCH (x:Descriptor {id: 'DSC-C02-DECOY'})-[:DESCRIBES]->"
                    "(m:Merchant) RETURN x, m"
                ),
                "why_irrelevant": (
                    "It has a similar name but no transaction or cardholder-history path."
                ),
            }
        ],
        "missing_evidence": False,
        "human_effort": {
            "hops": 5,
            "entities": 7,
            "note": (
                "Trace the statement descriptor through its facilitator parent and compare the "
                "card's earlier merchant history."
            ),
        },
    }
