from collections import Counter

from graph_builder import Graph
from policies import Clause, PolicyDoc, add_to_graph
from submissions import insert_submission, load_saved

from extensions.merchant_agent.contract import (
    MerchantSubmission,
    SubmittedItem,
    SubmittedMessage,
)

SUBMISSION = MerchantSubmission(
    submission_id="MSB-A01",
    dispute_id="DSP-1",
    merchant_id="MER-1",
    statement="Custom orders are final sale.",
    items=[SubmittedItem(kind="acceptance_log", text="Checkbox ticked.", asserts=["ORD-1"])],
    messages=[
        SubmittedMessage(
            channel="email", sender="Shop", date="2026-07-02", text="Final sale.", asserts=["ORD-1"]
        )
    ],
    cited_ids=["CLS-SHOP-1"],
)


def _graph() -> Graph:
    g = Graph()
    g.node("CardMember", "CMB-1", name="Ann")
    g.node("Card", "CRD-1", product="Gold")
    g.node("Merchant", "MER-1", name="Shop")
    g.node("Order", "ORD-1", total=10.0)
    g.node("Charge", "CHG-1", amount=10.0)
    g.node("Dispute", "DSP-1", amount=10.0)
    g.edge("CARRIED_BY", "CRD-1", "CMB-1")
    g.edge("CHARGED_TO", "CHG-1", "CRD-1")
    g.edge("FOR_ORDER", "CHG-1", "ORD-1")
    g.edge("DISPUTES", "DSP-1", "CHG-1", amount=10.0)
    clause = Clause("CLS-SHOP-1", "1", "Final sale", "Custom orders are final sale.")
    doc = PolicyDoc(
        "POL-SHOP", "Shop Terms", "merchant", "returns", "1", "card_member", "", "MER-1", (clause,)
    )
    add_to_graph(g, doc)
    return g


def test_insert_submission_writes_evidence_and_citations():
    g = _graph()
    before = len(g.edges)
    insert_submission(g, SUBMISSION)
    assert {"MSB-A01", "EVI-A01-1", "COM-A01-1"} <= g.nodes.keys()
    types = Counter(e["type"] for e in g.edges[before:])
    assert types == {"HAS_SUBMISSION": 1, "HAS_EVIDENCE": 2, "ASSERTS": 2, "CITES": 1}
    assert g.nodes["EVI-A01-1"]["props"]["source"] == "merchant"


def test_load_saved_round_trips(tmp_path):
    assert load_saved(tmp_path / "missing") == []
    (tmp_path / "DSP-1.json").write_text(SUBMISSION.model_dump_json())
    assert load_saved(tmp_path) == [SUBMISSION]
