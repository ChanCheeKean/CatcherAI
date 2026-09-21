"""C13: an agent provider made a booking that exceeded its customer mandate."""

from __future__ import annotations

from graph_builder import Graph

from cases import CaseTruth, transaction_expected


def build(g: Graph, _rng) -> CaseTruth:
    customer, account, card = "CUS-C13", "ACC-C13", "CRD-C13"
    token = "TOK-C13"
    provider, mandate = "AGP-C13", "MDT-C13"
    merchant, txn, order, dispute = "MER-C13-HOTEL", "TXN-C13", "ORD-C13", "DSP-2026-90013"
    g.node("Customer", customer, name="Nora Okafor", segment="consumer", opened_at="2019-04-12")
    g.node(
        "Account",
        account,
        kind="credit",
        status="open",
        opened_at="2019-04-12",
        credit_limit=10000.0,
    )
    g.node("Card", card, last4="1313", network="visa", status="active", issued_at="2025-04-12")
    g.node("Token", token, wallet="agent_provider", created_at="2026-07-01")
    g.node("AgentProvider", provider, name="Voyager Assistant", kind="travel_agent")
    g.node(
        "Mandate",
        mandate,
        scope="hotel room only; no upgrades or transfers",
        max_amount=600.0,
        valid_from="2026-09-01",
        valid_to="2026-10-31",
    )
    g.edge("HOLDS", customer, account, role="primary", valid_from="2019-04-12", valid_to="")
    g.edge("ISSUED_ON", card, account)
    g.edge("TOKENIZED_AS", card, token)
    g.edge("ACTING_FOR", token, provider)
    g.edge("ACTING_FOR", provider, customer)
    g.edge("AUTHORIZED_BY_MANDATE", mandate, provider)
    g.node("Merchant", merchant, name="Sable Quay Hotel", mcc="7011", kind="lodging", country="US")
    g.node(
        "Transaction",
        txn,
        ts="2026-10-16T09:10:00Z",
        amount=780.0,
        currency="USD",
        kind="purchase",
        channel="agentic_commerce",
        status="posted",
    )
    g.edge("PAID_WITH", txn, token)
    g.edge("AT_MERCHANT", txn, merchant)
    g.edge("AUTHORIZED_BY_MANDATE", txn, mandate)
    g.node(
        "PurchaseOrder",
        order,
        ts="2026-10-16T09:10:00Z",
        total=780.0,
        currency="USD",
        items="hotel room $600; premium airport transfer $180",
    )
    g.edge("FOR_ORDER", txn, order)
    intake = "I never booked this $780 hotel charge and do not recognize the merchant."
    g.node(
        "Dispute",
        dispute,
        filed_at="2026-10-20",
        claim_type="fraud",
        amount=780.0,
        intake=intake,
        status="open",
    )
    g.edge("FILED_BY", dispute, customer)
    g.edge("DISPUTES", dispute, txn, amount=780.0)
    g.node("AgentProvider", "AGP-C13-DECOY", name="Voyage Assistant", kind="shopping_agent")
    return {
        "case_id": dispute,
        "code": "C13",
        "title": "The Agent Booked It",
        "intake": intake,
        "misleading_surface": (
            "The unfamiliar merchant looks wholly unauthorized, but the payment token belongs "
            "to a delegated agent that exceeded a narrower mandate."
        ),
        "expected": {
            "verdict": "partially_accepted",
            "claim_family": "agentic_transaction_mandate_exceeded",
            "transactions": [
                transaction_expected(
                    txn, "partially_accepted", 780.0, 180.0, "file_dispute", "Visa 10.4"
                )
            ],
            "account_actions": ["review_agent_mandate", "rotate_agent_token"],
        },
        "solution_node_ids": [
            dispute,
            customer,
            account,
            card,
            token,
            provider,
            mandate,
            txn,
            order,
            merchant,
        ],
        "proof_patterns": [
            {
                "name": "token and provider connect transaction to bounded mandate",
                "cypher": (
                    "MATCH (d:Dispute {id: 'DSP-2026-90013'})-[:FILED_BY]->"
                    "(c:Customer)<-[:ACTING_FOR]-(a:AgentProvider)<-[:ACTING_FOR]-"
                    "(tok:Token)<-[:PAID_WITH]-(t:Transaction)-[:AUTHORIZED_BY_MANDATE]->"
                    "(m:Mandate)-[:AUTHORIZED_BY_MANDATE]->(a), (t)-[:FOR_ORDER]->"
                    "(o:PurchaseOrder) WHERE t.amount > m.max_amount "
                    "RETURN d, c, a, tok, t, m, o"
                ),
                "min_rows": 1,
            }
        ],
        "decoy_patterns": [
            {
                "name": "similarly named agent provider",
                "cypher": "MATCH (a:AgentProvider {id: 'AGP-C13-DECOY'}) RETURN a",
                "why_irrelevant": (
                    "The similarly named provider has no path to the token, customer, mandate, "
                    "order, or transaction."
                ),
            }
        ],
        "missing_evidence": False,
        "human_effort": {
            "hops": 8,
            "entities": 10,
            "note": (
                "Trace the payment token through the agent provider to the mandate, compare its "
                "scope and ceiling with the order, and calculate the excess."
            ),
        },
    }
