"""D: the venue deposit was paid by bank transfer and the balance by Card, but the Card charge was
$500 more than the balance; the second transfer paid the affiliated caterer's own invoice."""

from __future__ import annotations

from graph_builder import Graph
from submissions import insert_submission
from world import add_installment, add_invoice, file_dispute, pay_other_means, post_charge

from cases import CaseTruth, basic_card, charge_expected
from extensions.merchant_agent.contract import MerchantSubmission, SubmittedItem

DISPUTE = "DSP-2026-91004"
INTAKE = (
    "I paid Willow Barn by bank transfer, $1,500 and then $4,500. The $5,000 card charge is a "
    "second payment for the same wedding."
)


def build(g: Graph, _rng) -> CaseTruth:
    member = g.node("CardMember", "CMB-D01", name="Elena Voss", member_since="2018-05-30")
    card = basic_card(g, member, "D01", "Gold", "4004")

    venue = add_invoice(
        g,
        "INV-D01",
        "MER-WBV",
        member,
        "POL-WBV-CONTRACT-V2",
        "2026-03-01",
        6000.0,
        "Wedding venue hire, 15 August 2026",
    )
    deposit = add_installment(g, venue, "INS-D01-DEP", "Deposit", 1500.0)
    balance = add_installment(g, venue, "INS-D01-BAL", "Balance", 4500.0)
    catering = add_invoice(
        g,
        "INV-D02",
        "MER-WBC",
        member,
        "POL-WBC-CATERING-V1",
        "2026-03-04",
        4500.0,
        "Wedding catering, 120 guests, 15 August 2026",
    )
    catering_due = add_installment(g, catering, "INS-D02-FULL", "Catering in full", 4500.0)
    deposit_paid = pay_other_means(
        g,
        "PAY-D01",
        member,
        "MER-WBV",
        "2026-03-02",
        "bank_transfer",
        1500.0,
        "WILLOW BARN DEP VOSS",
        deposit,
    )
    catering_paid = pay_other_means(
        g,
        "PAY-D02",
        member,
        "MER-WBC",
        "2026-07-20",
        "bank_transfer",
        4500.0,
        "WILLOW BARN VOSS",
        catering_due,
    )
    charge = post_charge(g, "CHG-D01", card, "MER-WBV", "2026-08-01", 5000.0, "purchase")
    g.edge("SETTLES", charge, balance)
    file_dispute(g, DISPUTE, member, {charge: 5000.0}, "2026-08-25", INTAKE, "open", "")
    insert_submission(
        g,
        MerchantSubmission(
            submission_id="MSB-D01",
            dispute_id=DISPUTE,
            merchant_id="MER-WBV",
            statement="The card charge paid the balance of the venue invoice; the deposit was "
            "paid by bank transfer.",
            items=[
                SubmittedItem(
                    kind="invoice_ledger",
                    text="Venue invoice: deposit $1,500 received by transfer 2026-03-02; balance "
                    "settled by Amex card 2026-08-01.",
                    asserts=[venue, balance],
                )
            ],
            messages=[],
            cited_ids=["CLS-WBV-CONTRACT-V2-3"],
        ),
    )

    return {
        "case_id": DISPUTE,
        "code": "D",
        "title": "Paid by Transfer",
        "claim": "Paid the same bill twice",
        "intake": INTAKE,
        "misleading_surface": "Two transfers to 'Willow Barn' add up to the venue invoice, so "
        "the whole card charge looks like a second payment.",
        "expected": {
            "verdict": "partially_accepted",
            "category": "PDD",
            "charges": [charge_expected(charge, "partially_accepted", 5000.0, 500.0)],
            "improvement_targets": ["process"],
        },
        "solution_node_ids": [
            DISPUTE,
            charge,
            venue,
            deposit,
            balance,
            deposit_paid,
            catering_paid,
            catering,
            "MER-WBC",
            "MER-WBV",
            "CLS-WBV-CONTRACT-V2-3",
            "CLS-AMX-MR-4.7",
        ],
        "proof_patterns": [
            {
                "name": "card charge settles the balance installment and exceeds it; a transfer "
                "settled the deposit",
                "cypher": (
                    f"MATCH (d:Dispute {{id: '{DISPUTE}'}})-[:DISPUTES]->(c:Charge)"
                    "-[:SETTLES]->(bal:Installment)<-[:HAS_INSTALLMENT]-(inv:Invoice)"
                    "-[:HAS_INSTALLMENT]->(dep:Installment)<-[:SETTLES]-(p:Payment) "
                    "WHERE c.amount > bal.amount RETURN d, c, bal, inv, dep, p"
                ),
            }
        ],
        "decoy_patterns": [
            {
                "name": "the second transfer paid the affiliated caterer's invoice",
                "cypher": (
                    "MATCH (p:Payment {id: 'PAY-D02'})-[:SETTLES]->(:Installment)"
                    "<-[:HAS_INSTALLMENT]-(:Invoice)-[:AT_MERCHANT]->(m:Merchant)"
                    "-[:AFFILIATE_OF]->(:Merchant {id: 'MER-WBV'}) RETURN p, m"
                ),
            }
        ],
    }
