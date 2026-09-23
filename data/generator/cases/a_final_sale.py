"""A: the Card Member returned a custom (COM) sofa; the checkout terms they accepted make it final
sale."""

from __future__ import annotations

from graph_builder import Graph
from submissions import insert_submission
from world import file_dispute, issue_card, open_account, post_charge

from cases import CaseTruth, charge_expected
from extensions.merchant_agent.contract import MerchantSubmission, SubmittedItem, SubmittedMessage

DISPUTE = "DSP-2026-91001"
INTAKE = (
    "I returned the sofa within 30 days like Hearth & Grain's website says, and they refused "
    "to refund my $2,400."
)


def _card_member(g: Graph, n: str, name: str, since: str, last4: str) -> str:
    member = g.node("CardMember", f"CMB-A{n}", name=name, member_since=since)
    account = open_account(g, member, f"ACC-A{n}", "Gold")
    return issue_card(g, f"CRD-A{n}", account, member, "Gold", last4, "basic")


def _sofa_order(g: Graph, n: str, card: str, option: str, date: str) -> tuple[str, str]:
    order, charge = f"ORD-A{n}", f"CHG-A{n}"
    g.node(
        "Order",
        order,
        date=date,
        kind="retail",
        total=2400.0,
        currency="USD",
        summary=f"Alder three-seat sofa ({option})",
    )
    g.edge("AT_MERCHANT", order, "MER-HGF")
    g.node(
        "LineItem",
        f"LIN-A{n}",
        description="Alder three-seat sofa",
        quantity=1,
        unit_price=2400.0,
        option=option,
    )
    g.edge("HAS_LINE", order, f"LIN-A{n}")
    g.edge("OF_PRODUCT", f"LIN-A{n}", "PRD-ALDER")
    g.edge("ACCEPTED", order, "POL-HGF-CO-V4", method="checkbox at checkout")
    post_charge(g, charge, card, "MER-HGF", date, 2400.0, "purchase")
    g.edge("FOR_ORDER", charge, order)
    return order, charge


def build(g: Graph, _rng) -> CaseTruth:
    g.node(
        "Product",
        "PRD-ALDER",
        name="Alder three-seat sofa",
        standard_options="Sage linen; Oat linen; Charcoal linen",
        custom_options="Customer's Own Material (COM); made to measure",
    )
    g.edge("SOLD_BY", "PRD-ALDER", "MER-HGF")

    card = _card_member(g, "01", "Priya Raman", "2019-04-02", "1004")
    order, charge = _sofa_order(g, "01", card, "Customer's Own Material (COM)", "2026-07-02")
    g.node(
        "Return",
        "RTN-A01",
        method="customer freight",
        status="refused",
        note="Delivery of the return refused by the Merchant; sofa sent back to the customer.",
    )
    g.edge("RETURNED_AS", order, "RTN-A01")
    file_dispute(g, DISPUTE, "CMB-A01", charge, "2026-08-20", 2400.0, INTAKE, "open", "")
    insert_submission(
        g,
        MerchantSubmission(
            submission_id="MSB-A01",
            dispute_id=DISPUTE,
            merchant_id="MER-HGF",
            statement="This was a custom COM order. Checkout Terms 4.3, accepted at checkout, "
            "make custom orders final sale, so we refused the return.",
            items=[
                SubmittedItem(
                    kind="acceptance_log",
                    text="Checkbox 'I agree to the Checkout Terms (v4)' ticked on 2026-07-02 "
                    "14:03 before payment.",
                    asserts=[order],
                )
            ],
            messages=[
                SubmittedMessage(
                    channel="email",
                    sender="Hearth & Grain",
                    date="2026-07-02",
                    text="Thanks for your order of the Alder sofa in your own material (COM). "
                    "Custom orders are final sale (Checkout Terms 4.3).",
                    asserts=[order],
                )
            ],
            cited_ids=["CLS-HGF-CO-V4-4.3"],
        ),
    )

    # Decoy: a standard-fabric sofa under the same terms, returned and refunded.
    decoy_card = _card_member(g, "02", "Jonah Pike", "2021-01-15", "1027")
    decoy_order, decoy_charge = _sofa_order(g, "02", decoy_card, "Oat linen", "2026-06-11")
    g.node(
        "Return",
        "RTN-A02",
        method="customer freight",
        status="received and refunded",
        note="Standard item returned within 30 days.",
    )
    g.edge("RETURNED_AS", decoy_order, "RTN-A02")
    refund = post_charge(g, "CHG-A02R", decoy_card, "MER-HGF", "2026-06-30", -2400.0, "credit")
    g.edge("REFUNDS", refund, decoy_charge)

    return {
        "case_id": DISPUTE,
        "code": "A",
        "title": "Final Sale Means Final",
        "claim": "Refund refused after return",
        "intake": INTAKE,
        "misleading_surface": "The website promises 30-day returns and another customer's "
        "identical sofa was refunded.",
        "expected": {
            "verdict": "rejected",
            "category": "RET",
            "charges": [charge_expected(charge, "rejected", 2400.0, 0.0)],
            "improvement_targets": [],
        },
        "solution_node_ids": [
            DISPUTE,
            charge,
            order,
            "LIN-A01",
            "PRD-ALDER",
            "POL-HGF-CO-V4",
            "CLS-HGF-CO-V4-4.3",
            "RTN-A01",
            "MSB-A01",
            "CLS-AMX-MR-4.2",
        ],
        "proof_patterns": [
            {
                "name": "COM option is a custom option under the accepted final-sale clause",
                "cypher": (
                    f"MATCH (d:Dispute {{id: '{DISPUTE}'}})-[:DISPUTES]->(:Charge)-[:FOR_ORDER]->"
                    "(o:`Order`)-[:HAS_LINE]->(l:LineItem)-[:OF_PRODUCT]->(p:Product), "
                    "(o)-[:ACCEPTED]->(:PolicyDocument)-[:HAS_CLAUSE]->"
                    "(c:Clause {id: 'CLS-HGF-CO-V4-4.3'}) "
                    "WHERE p.custom_options CONTAINS 'COM' AND l.option CONTAINS 'COM' "
                    "RETURN d, o, l, p, c"
                ),
            }
        ],
        "decoy_patterns": [
            {
                "name": "standard sofa under the same terms was refunded",
                "cypher": (
                    "MATCH (o:`Order` {id: 'ORD-A02'})-[:HAS_LINE]->(l:LineItem), "
                    "(o)-[:RETURNED_AS]->(r:Return), "
                    "(cr:Charge)-[:REFUNDS]->(:Charge)-[:FOR_ORDER]->(o) "
                    "WHERE r.status CONTAINS 'refunded' RETURN o, l, r, cr"
                ),
            }
        ],
    }
