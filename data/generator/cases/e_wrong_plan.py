"""E: the Card Member cancelled their own StreamCo plan; the charges they dispute are a separate
Family plan started with the Additional Card on their account."""

from __future__ import annotations

from graph_builder import Graph
from submissions import insert_submission
from world import add_subscription, bill_subscription, file_dispute, issue_card, post_charge

from cases import CaseTruth, basic_card, charge_expected
from extensions.merchant_agent.contract import MerchantSubmission, SubmittedItem

DISPUTE = "DSP-2026-91005"
INTAKE = (
    "I cancelled StreamCo in May and got a confirmation email, but SC*DIGITAL SVCS keeps "
    "charging me $22.99 every month."
)
_MERCHANT, _TERMS = "MER-STC", "POL-STC-SUB-V3"


def build(g: Graph, _rng) -> CaseTruth:
    basic = g.node("CardMember", "CMB-E01", name="Tom Lindqvist", member_since="2012-02-17")
    additional = g.node("CardMember", "CMB-E02", name="Maya Lindqvist", member_since="2024-09-01")
    own_card = basic_card(g, basic, "E01", "Blue Cash", "5005")
    account = "ACC-E01"
    g.edge("HOLDS", additional, account, role="additional")
    additional_card = issue_card(
        g, "CRD-E02", account, additional, "Blue Cash", "5013", "additional"
    )

    individual = add_subscription(
        g, "SUB-E01", _MERCHANT, own_card, _TERMS, "Individual", 12.99, "cancelled"
    )
    family = add_subscription(
        g, "SUB-E02", _MERCHANT, additional_card, _TERMS, "Family", 22.99, "active"
    )
    last_individual = bill_subscription(
        g, "CHG-E01", individual, own_card, _MERCHANT, "2026-05-03", 12.99
    )
    refund = post_charge(g, "CHG-E01R", own_card, _MERCHANT, "2026-05-06", -12.99, "credit")
    g.edge("REFUNDS", refund, last_individual)
    charges = [
        bill_subscription(g, f"CHG-E0{n}", family, additional_card, _MERCHANT, day, 22.99)
        for n, day in ((2, "2026-06-12"), (3, "2026-07-12"), (4, "2026-08-12"))
    ]
    file_dispute(g, DISPUTE, basic, dict.fromkeys(charges, 22.99), "2026-08-20", INTAKE, "open", "")
    confirmation = g.node(
        "Communication",
        "COM-E01",
        channel="email",
        sender="StreamCo",
        date="2026-05-04",
        text="Your StreamCo Individual plan has been cancelled. You won't be charged again for "
        "this plan.",
    )
    g.edge("HAS_EVIDENCE", DISPUTE, confirmation)
    g.edge("ASSERTS", confirmation, individual)
    insert_submission(
        g,
        MerchantSubmission(
            submission_id="MSB-E01",
            dispute_id=DISPUTE,
            merchant_id=_MERCHANT,
            statement="The Family plan is active and in regular use. It was started with the "
            "card ending 5013 and has never been cancelled.",
            items=[
                SubmittedItem(
                    kind="usage_log",
                    text="Family plan: 4 profiles, streamed on 41 days since June.",
                    asserts=[family],
                )
            ],
            messages=[],
            cited_ids=["CLS-STC-SUB-V3-5"],
        ),
    )

    return {
        "case_id": DISPUTE,
        "code": "E",
        "title": "Cancelled the Wrong Plan",
        "claim": "Billed again after cancelling",
        "intake": INTAKE,
        "misleading_surface": "A genuine cancellation confirmation, and the statement name does "
        "not say StreamCo.",
        "expected": {
            "verdict": "not_a_dispute",
            "category": "CNR",
            "charges": [charge_expected(c, "not_a_dispute", 22.99, 0.0) for c in charges],
            "improvement_targets": [],
        },
        "solution_node_ids": [
            DISPUTE,
            charges[0],
            family,
            additional_card,
            additional,
            account,
            individual,
            confirmation,
            "DSC-STC",
            "CLS-STC-SUB-V3-5",
            "CLS-AMX-CMA-5.1",
        ],
        "proof_patterns": [
            {
                "name": "disputed charges bill a different plan on the Additional Card; the "
                "cancellation was for the Card Member's own plan",
                "cypher": (
                    f"MATCH (d:Dispute {{id: '{DISPUTE}'}})-[:DISPUTES]->(c:Charge)"
                    "-[:FOR_SUBSCRIPTION]->(s:Subscription)-[:SUBSCRIBED_WITH]->(card:Card)"
                    "-[:CARRIED_BY]->(add:CardMember), "
                    "(card)-[:ISSUED_ON]->(a:CardAccount)<-[h:HOLDS]-(add), "
                    "(d)-[:HAS_EVIDENCE]->(:Communication)-[:ASSERTS]->(cancelled:Subscription) "
                    "WHERE h.role = 'additional' AND s.id <> cancelled.id "
                    "RETURN d, c, s, card, add, cancelled"
                ),
            }
        ],
        "decoy_patterns": [
            {
                "name": "the cancelled plan's last charge was already refunded",
                "cypher": (
                    "MATCH (cr:Charge {id: 'CHG-E01R'})-[:REFUNDS]->(c:Charge)"
                    "-[:FOR_SUBSCRIPTION]->(s:Subscription {id: 'SUB-E01'}) RETURN cr, c, s"
                ),
            }
        ],
    }
