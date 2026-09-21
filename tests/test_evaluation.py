from __future__ import annotations

from datetime import UTC, datetime

from test_runtime import CASE_ID, TXN_ID, report

from domain.events import Actor, ActorKind, EventEnvelope, RuntimeSnapshot
from evaluation import passed, score


class StubStore:
    """Knows one node and one decoy node; answers the existence and decoy queries."""

    def query(self, cypher: str, params: dict | None = None, row_cap: int = 50) -> dict:
        if "DECOY" in cypher:
            return {"rows": [], "node_ids": ["DEC-1"], "edge_ids": []}
        found = [[i] for i in params["ids"] if i == "TXN-TEST-1"] if "(n)" in cypher else []
        return {"rows": found, "node_ids": [], "edge_ids": []}


def event(type_: str, seq: int, **payload) -> EventEnvelope:
    return EventEnvelope(
        event_id=f"e{seq}",
        run_id="r",
        case_id=CASE_ID,
        seq=seq,
        span_id=f"s{seq}",
        parent_span_id=None,
        ts_wall=datetime.now(UTC),
        actor=Actor(kind=ActorKind.TOOL, name="graph_query"),
        type=type_,
        summary=type_,
        payload=payload,
        runtime=RuntimeSnapshot(config_hash="h", agent_runtime="x", provider="p", model="m"),
    )


def truth(**overrides) -> dict:
    base = {
        "case_id": CASE_ID,
        "missing_evidence": False,
        "solution_node_ids": [TXN_ID, "SOL-2"],
        "decoy_patterns": [{"cypher": "DECOY"}],
        "required_capabilities": [
            {"trajectory_signals": ["triage", "tool_call {tool: python}", "eval result"]}
        ],
        "expected": {
            "verdict": "accepted",
            "account_actions": ["card_reissue", "watchlist"],
            "transactions": [
                {"txn_id": TXN_ID, "verdict": "accepted", "credit_amount": 10.0},
            ],
        },
    }
    return base | overrides


def test_score_matching_report() -> None:
    events = [
        event("triage", 1),
        event("tool_result", 2, node_ids=[TXN_ID], edge_ids=[]),
        event("tool_call", 3, tool="graph_query"),
    ]
    result = score(truth(), report(), events, StubStore())
    assert passed(result)
    assert result["solution_coverage"] == 0.5
    assert result["grounding"]["missing"] == []
    assert result["grounding"]["solution_cited"] == 0.5
    assert result["account_actions"]["matched"] == []
    assert result["capability_signals"] == {"triage": True, "tool_call {tool: python}": False}


def test_score_wrong_amount_and_ungrounded_ids() -> None:
    wrong = truth()
    wrong["expected"]["transactions"][0]["credit_amount"] = 4.0
    result = score(wrong, report(), [], StubStore())
    assert result["verdict_ok"] and not result["amounts_ok"] and not passed(result)
    result = score(truth(), report(), [], StubStore())
    assert result["grounding"]["missing"] == []
    ghost = report()
    ghost.transactions[0].evidence[0].node_ids.append("GHOST-9")
    assert score(truth(), ghost, [], StubStore())["grounding"]["missing"] == ["GHOST-9"]


def test_missing_evidence_requires_documented_gap() -> None:
    result = score(truth(missing_evidence=True), report(), [], StubStore())
    assert result["missing_evidence_handled"] is False
