import time
from decimal import Decimal
from types import SimpleNamespace

import evaluation
from evaluation import _attempt, _trajectory_ids, passed, score
from schemas import (
    CaseReport,
    ChargeDecision,
    DisputeCategory,
    EvidenceLink,
    SystemImprovement,
    Verdict,
)


class Store:
    def query(self, cypher, params=None, row_cap=None):
        return {"rows": [["CHG-1"]] if "MATCH (n)" in cypher else [], "node_ids": []}


def report(*, category=DisputeCategory.OVR, improvements=None):
    evidence = EvidenceLink(claim="Checked", node_ids=["CHG-1"], edge_ids=[], source_excerpt=None)
    return CaseReport(
        case_id="DSP-1",
        verdict=Verdict.ACCEPTED,
        category=category,
        headline="Checked",
        executive_summary="Checked",
        detailed_reasoning="Checked",
        charges=[
            ChargeDecision(
                charge_id="CHG-1",
                verdict=Verdict.ACCEPTED,
                category=category,
                disputed_amount=Decimal("10"),
                credit_amount=Decimal("10"),
                card_member_liability=Decimal("0"),
                rationale="Checked",
                evidence=[evidence],
            )
        ],
        hypotheses=[],
        decoys_ruled_out=[],
        policy_basis=[],
        system_improvements=[
            SystemImprovement(target=t, issue="Gap", suggestion="Clarify", evidence=[evidence])
            for t in (improvements or [])
        ],
        confidence=0.8,
        flip_fact="Different amount",
        card_member_letter="We checked.",
    )


def truth():
    return {
        "expected": {
            "verdict": "accepted",
            "category": "OVR",
            "charges": [{"charge_id": "CHG-1", "verdict": "accepted", "credit_amount": 10}],
            "improvement_targets": ["process"],
        },
        "solution_node_ids": ["CHG-1"],
        "decoy_patterns": [],
        "required_capabilities": [],
    }


def test_scoring_category_charges_and_improvement_alternative():
    events = [
        SimpleNamespace(type="notebook_write", payload={"node_ids": ["CHG-1"], "edge_ids": []})
    ]
    result = score(truth(), report(improvements=["merchant_policy"]), events, Store())
    assert result["category_ok"]
    assert result["charges"]["CHG-1"] == {"verdict": True, "credit": True}
    assert result["improvements"]["ok"]
    assert result["solution_coverage"] == 1
    assert passed(result)
    assert not passed(score(truth(), report(category=DisputeCategory.RET), events, Store()))
    assert not passed(score(truth(), report(), events, Store()))


def test_notebook_events_contribute_ids():
    events = [
        SimpleNamespace(type="notebook_write", payload={"node_ids": ["CHG-1"], "edge_ids": ["E-1"]})
    ]
    assert _trajectory_ids(events) == ({"CHG-1"}, {"CHG-1", "E-1"})


def test_timeout_is_not_swallowed_by_broad_handlers(monkeypatch):
    def swallowing_run(*_, **__):
        while True:
            try:
                time.sleep(0.05)
            except Exception:  # noqa: BLE001 - like a model client's retry loop
                pass

    monkeypatch.setattr(evaluation, "run_case", swallowing_run)
    monkeypatch.setattr(evaluation, "ATTEMPT_TIMEOUT_SECONDS", 1)
    result = _attempt({"code": "A", "case_id": "DSP-1"}, 1, "t", None)
    assert result["passed"] is False
    assert result["error"].startswith("AttemptTimeout")
