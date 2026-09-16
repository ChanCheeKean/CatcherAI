from __future__ import annotations

from adapters.fake_routing import classify


def test_classify_matches_the_original_debit_fraud_rule() -> None:
    route_id, depth = classify({"regime": "REG_E", "claim_family_initial": "fraud_cnp"})
    assert route_id == "debit_fraud_l3"
    assert depth == "L3"


def test_classify_matches_the_original_high_value_ato_rule() -> None:
    route_id, depth = classify(
        {"regime": "REG_Z", "claim_family_initial": "fraud_cnp", "billing_total": 600}
    )
    assert route_id == "high_value_cnp_ato_l4"
    assert depth == "L4"


def test_classify_prefers_the_lowest_priority_number_on_overlap() -> None:
    # agentic_transaction_novel_l4 (priority 5) must win over any claim_family-based rule
    # when the transaction channel is agentic_commerce, exactly as the old engine did.
    route_id, _ = classify(
        {
            "claim_family_initial": "fraud_cnp",
            "regime": "REG_Z",
            "transaction_channels": ["agentic_commerce"],
        }
    )
    assert route_id == "agentic_transaction_novel_l4"


def test_classify_falls_back_to_novel_or_ambiguous() -> None:
    route_id, depth = classify({"claim_family_initial": "something_unmodeled"})
    assert route_id == "novel_or_ambiguous"
    assert depth == "L4"
