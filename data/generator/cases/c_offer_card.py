"""C: an Amex Offer enrolled on the Card Member's Platinum Card, the purchase paid with their Gold
Card; the Merchant priced it correctly, and the Dispute Guide allows one Offer goodwill credit."""

from __future__ import annotations

from graph_builder import Graph
from submissions import insert_submission
from world import add_offer, file_dispute, post_charge

from cases import CaseTruth, basic_card, charge_expected
from extensions.merchant_agent.contract import MerchantSubmission, SubmittedItem

DISPUTE = "DSP-2026-91003"
INTAKE = (
    "I spent $540 at Northwind with the $100-off Amex Offer and never got the $100. They "
    "overcharged me."
)


def build(g: Graph, _rng) -> CaseTruth:
    g.node("CardMember", "CMB-C01", name="Daniel Okafor", member_since="2014-03-08")
    platinum = basic_card(g, "CMB-C01", "C01", "Platinum", "3003")
    gold = basic_card(g, "CMB-C01", "C02", "Gold", "3017")
    offer = add_offer(
        g,
        "OFR-NWO-100",
        "MER-NWO",
        "Spend $500 or more at Northwind Outfitters, get $100 back",
        500,
        100,
        "amex",
    )
    g.edge("ENROLLED_ON", offer, platinum)

    order = g.node(
        "Order",
        "ORD-C01",
        date="2026-07-09",
        kind="retail",
        total=540.0,
        currency="USD",
        summary="Storm parka and trail boots",
    )
    g.edge("AT_MERCHANT", order, "MER-NWO")
    g.edge("ACCEPTED", order, "POL-NWO-SALE-V1", method="checkout")
    lines = (
        ("LIN-C01", "Storm parka", 390.0, "Navy, M", "PRD-NWO-PARKA", "Navy; Olive; S; M; L; XL"),
        ("LIN-C02", "Trail boots", 150.0, "Size 10", "PRD-NWO-BOOT", "Size 8; Size 9; Size 10"),
    )
    for line, name, price, option, product, standard in lines:
        g.node("LineItem", line, description=name, quantity=1, unit_price=price, option=option)
        g.edge("HAS_LINE", order, line)
        g.node("Product", product, name=name, standard_options=standard, custom_options="")
        g.edge("SOLD_BY", product, "MER-NWO")
        g.edge("OF_PRODUCT", line, product)
    charge = post_charge(g, "CHG-C01", gold, "MER-NWO", "2026-07-09", 540.0, "purchase")
    g.edge("FOR_ORDER", charge, order)
    file_dispute(g, DISPUTE, "CMB-C01", {charge: 100.0}, "2026-09-01", INTAKE, "open", "")
    insert_submission(
        g,
        MerchantSubmission(
            submission_id="MSB-C01",
            dispute_id=DISPUTE,
            merchant_id="MER-NWO",
            statement="Order charged at our listed prices. Northwind ran no promotion on this "
            "order; Amex Offers are credited by American Express, not by Northwind.",
            items=[
                SubmittedItem(
                    kind="invoice",
                    text="Invoice: parka $390 + boots $150 = $540; no promo code applied.",
                    asserts=[order],
                )
            ],
            messages=[],
            cited_ids=["CLS-NWO-SALE-V1-2"],
        ),
    )
    # The Card Member's own history holds no earlier Offer goodwill.
    meal = post_charge(g, "CHG-C02", gold, "MER-BG-0021", "2026-02-14", 64.0, "purchase")
    file_dispute(
        g,
        "DSP-HIST-C01",
        "CMB-C01",
        {meal: 64.0},
        "2026-02-27",
        "Charged twice for one order at a restaurant.",
        "resolved",
        "rejected",
    )

    # Decoy: a namesake Card Member already received an Offer goodwill credit for the same slip.
    g.node("CardMember", "CMB-C02", name="Daniel Okafor", member_since="2020-11-19")
    green = basic_card(g, "CMB-C02", "C03", "Green", "3090")
    namesake_platinum = basic_card(g, "CMB-C02", "C04", "Platinum", "3068")
    past_offer = add_offer(
        g,
        "OFR-C02",
        "MER-BG-0005",
        "Spend $250 or more at Linen & Loom, get $75 back",
        250,
        75,
        "amex",
    )
    g.edge("ENROLLED_ON", past_offer, namesake_platinum)
    past_charge = post_charge(g, "CHG-C03", green, "MER-BG-0005", "2026-04-18", 310.0, "purchase")
    file_dispute(
        g,
        "DSP-HIST-C02",
        "CMB-C02",
        {past_charge: 75.0},
        "2026-05-06",
        "Added the Offer to my Platinum but paid with my Green card; no credit.",
        "resolved",
        "goodwill_credit",
    )

    return {
        "case_id": DISPUTE,
        "code": "C",
        "title": "The Offer on the Other Card",
        "claim": "Promised discount not applied",
        "intake": INTAKE,
        "misleading_surface": "The Card Member calls the missing Offer credit a Merchant "
        "overcharge, and a Daniel Okafor already received an Offer goodwill credit.",
        "expected": {
            "verdict": "goodwill_credit",
            "category": "OVR",
            "charges": [charge_expected(charge, "goodwill_credit", 100.0, 100.0)],
            "improvement_targets": ["process"],
        },
        "solution_node_ids": [
            DISPUTE,
            charge,
            gold,
            offer,
            platinum,
            "CMB-C01",
            "CLS-AMX-OFFER-1",
            "CLS-AMX-OFFER-3",
            "CLS-AMX-DG-G-2",
            "DSP-HIST-C01",
            "MSB-C01",
        ],
        "proof_patterns": [
            {
                "name": "Amex Offer enrolled on another of the Card Member's own Cards, "
                "purchase met the threshold",
                "cypher": (
                    f"MATCH (d:Dispute {{id: '{DISPUTE}'}})-[:DISPUTES]->(c:Charge)"
                    "-[:CHARGED_TO]->(paid:Card)-[:CARRIED_BY]->(cm:CardMember), "
                    "(o:Offer)-[:ENROLLED_ON]->(enrolled:Card)-[:CARRIED_BY]->(cm), "
                    "(c)-[:AT_MERCHANT]->(m:Merchant)<-[:OFFER_AT]-(o) "
                    "WHERE paid.id <> enrolled.id AND c.amount >= o.spend_threshold "
                    "AND o.funded_by = 'amex' "
                    "RETURN d, c, paid, enrolled, o, cm"
                ),
            }
        ],
        "decoy_patterns": [
            {
                "name": "the earlier Offer goodwill went to a namesake, not this Card Member",
                "cypher": (
                    "MATCH (h:Dispute {id: 'DSP-HIST-C02'})-[:FILED_BY]->(x:CardMember), "
                    "(y:CardMember {id: 'CMB-C01'}) "
                    "WHERE x.name = y.name AND x.id <> y.id AND h.outcome = 'goodwill_credit' "
                    "RETURN h, x, y"
                ),
            }
        ],
    }
