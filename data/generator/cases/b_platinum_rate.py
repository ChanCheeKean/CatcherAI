"""B: a Platinum Stays booking guaranteed with the Platinum Card, settled with the Card Member's
Gold Card and re-rated under the hotel's folio clause that the program terms forbid."""

from __future__ import annotations

from graph_builder import Graph
from submissions import insert_submission
from world import PLATINUM_STAYS, file_dispute, issue_card, open_account, post_charge

from cases import CaseTruth, charge_expected
from extensions.merchant_agent.contract import MerchantSubmission, SubmittedItem

DISPUTE = "DSP-2026-91002"
INTAKE = (
    "Harbor Point charged me $1,300 for a two-night stay I booked at the $1,000 Platinum Stays "
    "rate."
)
_STAY = "2 nights, Platinum Stays rate $500/night"


def _account(g: Graph, member: str, n: str, product: str, last4: str) -> str:
    account = open_account(g, member, f"ACC-B{n}", product)
    return issue_card(g, f"CRD-B{n}", account, member, product, last4, "basic")


def _stay(g: Graph, n: str, booked: str, arrival: str, guarantee: str, paid_with: str, day: str):
    order, charge = f"ORD-B{n}", f"CHG-B{n}"
    g.node(
        "Order",
        order,
        date=booked,
        kind="lodging",
        total=1000.0,
        currency="USD",
        summary=f"{_STAY}, arriving {arrival}",
    )
    g.edge("AT_MERCHANT", order, "MER-HPH")
    g.edge("UNDER_PROGRAM", order, PLATINUM_STAYS)
    g.edge("GUARANTEED_WITH", order, guarantee)
    g.edge("ACCEPTED", order, "POL-HPH-RES-V2", method="booking confirmation")
    post_charge(g, charge, paid_with, "MER-HPH", day, 1300.0, "purchase")
    g.edge("FOR_ORDER", charge, order)
    return order, charge


def build(g: Graph, _rng) -> CaseTruth:
    g.node("CardMember", "CMB-B01", name="Marcus Bell", member_since="2016-09-12")
    platinum = _account(g, "CMB-B01", "01", "Platinum", "2002")
    gold = _account(g, "CMB-B01", "02", "Gold", "2031")
    order, charge = _stay(g, "01", "2026-06-10", "2026-07-18", platinum, gold, "2026-07-20")
    file_dispute(g, DISPUTE, "CMB-B01", charge, "2026-08-02", 300.0, INTAKE, "open", "")
    insert_submission(
        g,
        MerchantSubmission(
            submission_id="MSB-B01",
            dispute_id=DISPUTE,
            merchant_id="MER-HPH",
            statement="The guest settled the folio with a Gold Card, so under our folio terms "
            "clause 7 the stay was re-rated to the Best Available Rate of $650 per night.",
            items=[
                SubmittedItem(
                    kind="folio",
                    text="Folio: 2 nights re-rated to Best Available Rate $650/night; settled "
                    "with Amex Gold ending 2031.",
                    asserts=[charge],
                ),
                SubmittedItem(
                    kind="booking_confirmation",
                    text="Platinum Stays rate $500/night, 2 nights, guaranteed with Amex "
                    "Platinum ending 2002.",
                    asserts=[order],
                ),
            ],
            messages=[],
            cited_ids=["CLS-HPH-FOLIO-V1-7"],
        ),
    )

    # Decoy: another guest's program booking guaranteed with a Gold Card, rightly charged the
    # Best Available Rate, and the past Dispute over it was rejected.
    g.node("CardMember", "CMB-B02", name="Ana Ruiz", member_since="2020-03-08")
    decoy_gold = _account(g, "CMB-B02", "03", "Gold", "2044")
    decoy_order, decoy_charge = _stay(
        g, "02", "2026-05-04", "2026-06-12", decoy_gold, decoy_gold, "2026-06-14"
    )
    file_dispute(
        g,
        "DSP-HIST-B02",
        "CMB-B02",
        decoy_charge,
        "2026-06-25",
        300.0,
        "Hotel charged the full rate instead of the Platinum rate.",
        "resolved",
        "rejected",
    )
    insert_submission(
        g,
        MerchantSubmission(
            submission_id="MSB-HIST-B02",
            dispute_id="DSP-HIST-B02",
            merchant_id="MER-HPH",
            statement="The booking was guaranteed with an Amex Gold Card, which is not eligible "
            "for the Platinum Stays rate, so the stay was charged at the Best Available Rate.",
            items=[
                SubmittedItem(
                    kind="reservation_record",
                    text="Booking guaranteed with Amex Gold ending 2044; Platinum Stays rate "
                    "requested but the Card is not eligible; charged $650/night.",
                    asserts=[decoy_order],
                )
            ],
            messages=[],
            cited_ids=["CLS-AMX-PS-PART-3.2"],
        ),
    )

    return {
        "case_id": DISPUTE,
        "code": "B",
        "title": "Platinum Rate, Gold Card",
        "claim": "Charged more than the booked rate",
        "intake": INTAKE,
        "misleading_surface": "The hotel's own folio terms say the Platinum rate needs a "
        "Platinum Card at checkout, and a similar past Dispute was rejected.",
        "expected": {
            "verdict": "accepted",
            "category": "OVR",
            "charges": [charge_expected(charge, "accepted", 300.0, 300.0)],
            "improvement_targets": ["amex_policy", "merchant_policy"],
        },
        "solution_node_ids": [
            DISPUTE,
            charge,
            gold,
            order,
            platinum,
            PLATINUM_STAYS,
            "MER-HPH",
            "CLS-HPH-FOLIO-V1-7",
            "CLS-AMX-PS-PART-3.2",
            "CLS-AMX-PS-PART-3.4",
            "CLS-AMX-PLAT-BEN-2.1",
            "MSB-B01",
        ],
        "proof_patterns": [
            {
                "name": "booked with Platinum, charged to Gold, at a hotel bound by the program's "
                "no-added-conditions clause",
                "cypher": (
                    f"MATCH (d:Dispute {{id: '{DISPUTE}'}})-[:DISPUTES]->(c:Charge)-[:FOR_ORDER]->"
                    "(o:`Order`)-[:GUARANTEED_WITH]->(g:Card), (c)-[:CHARGED_TO]->(p:Card), "
                    "(o)-[:UNDER_PROGRAM]->(prg:Program)<-[:PARTICIPATES_IN]-(m:Merchant)"
                    "-[:BOUND_BY]->(:PolicyDocument)-[:HAS_CLAUSE]->"
                    "(cl:Clause {id: 'CLS-AMX-PS-PART-3.4'}) "
                    "WHERE g.product = 'Platinum' AND p.product = 'Gold' "
                    "RETURN d, o, g, p, prg, cl"
                ),
            }
        ],
        "decoy_patterns": [
            {
                "name": "past program booking guaranteed with a Gold Card was rightly rejected",
                "cypher": (
                    "MATCH (o:`Order` {id: 'ORD-B02'})-[:GUARANTEED_WITH]->(g:Card) "
                    "WHERE g.product = 'Gold' "
                    "MATCH (h:Dispute {id: 'DSP-HIST-B02'}) WHERE h.outcome = 'rejected' "
                    "RETURN o, g, h"
                ),
            }
        ],
    }
