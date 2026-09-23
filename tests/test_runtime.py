from __future__ import annotations

import ast
import json
from decimal import Decimal
from pathlib import Path

import pytest
from graph_builder import Graph

from config import load_agents_config
from graph_store import load
from memory import retrieval
from notebook import read_entries
from replay import load_events
from runtime import RuntimePaths, run_case
from schemas import (
    CaseReport,
    Citation,
    Decide,
    Delegate,
    EvidenceLink,
    Fact,
    Findings,
    HypothesisAssessment,
    InvestigationSummary,
    PlanEdit,
    PlanItem,
    SupervisorTurn,
    Task,
    TransactionDecision,
    Triage,
    Verdict,
)

CASE_ID = "DSP-TEST-1"
CHARGE_ID = "CHG-TEST-1"


@pytest.fixture
def paths(tmp_path):
    graph = Graph()
    graph.node("CardMember", "CMB-TEST-1", name="Test Member")
    graph.node("CardAccount", "ACC-TEST-1", product="Gold")
    graph.node("Card", "CRD-TEST-1", product="Gold")
    graph.node("Merchant", "MER-TEST-1", name="Test Merchant")
    graph.node("Charge", CHARGE_ID, amount=10.0)
    graph.node("Dispute", CASE_ID, amount=10.0, status="open", intake="Wrong amount")
    graph.edge("HOLDS", "CMB-TEST-1", "ACC-TEST-1", role="basic")
    graph.edge("ISSUED_ON", "CRD-TEST-1", "ACC-TEST-1")
    graph.edge("CHARGED_TO", CHARGE_ID, "CRD-TEST-1")
    graph.edge("AT_MERCHANT", CHARGE_ID, "MER-TEST-1")
    graph.edge("FILED_BY", CASE_ID, "CMB-TEST-1")
    graph.edge("DISPUTES", CASE_ID, CHARGE_ID, amount=10.0)
    graph.write(tmp_path / "jsonl")
    source = tmp_path / "evidence.lbug"
    load(tmp_path / "jsonl", source).close()
    knowledge = tmp_path / "knowledge.sqlite"
    retrieval.build(knowledge, [])
    return RuntimePaths(
        source_graph=source,
        knowledge_db=knowledge,
        notebook_db=tmp_path / "notebook.sqlite",
        trajectory_db=tmp_path / "events.sqlite",
        checkpoint_db=tmp_path / "checkpoints.sqlite",
    )


def triage():
    return Triage(
        case_type="amount",
        hypotheses=[],
        plan=[
            PlanItem(id="P1", question="Why?", status="open", evidence_refs=[], waiver_reason=None)
        ],
        rationale="Investigate",
    )


def summary():
    return InvestigationSummary(
        hypotheses=[],
        key_facts=[Fact(statement="Charge exists", node_ids=[CHARGE_ID], edge_ids=[])],
        open_questions=[],
        contradictions=[],
    )


def delegate():
    return SupervisorTurn(
        reasoning="Investigate",
        plan_edits=[],
        summary=summary(),
        action=Delegate(
            tasks=[
                Task(
                    role=role,
                    instructions=None,
                    objective="Check charge",
                    skills=[],
                    plan_item_ids=["P1"],
                )
                for role in ("graph_analyst", "evidence_analyst")
            ]
        ),
    )


def decide(close=True):
    edits = (
        [PlanEdit(operation="mark_done", plan_item_id="P1", evidence_refs=[CHARGE_ID])]
        if close
        else []
    )
    return SupervisorTurn(
        reasoning="Done",
        plan_edits=edits,
        summary=summary(),
        action=Decide(reason="Enough evidence"),
    )


def report():
    evidence = EvidenceLink(
        claim="Charge checked", node_ids=[CHARGE_ID], edge_ids=[], source_excerpt=None
    )
    return CaseReport(
        case_id=CASE_ID,
        verdict=Verdict.ACCEPTED,
        claim_family="amount",
        headline="Accepted",
        executive_summary="Charge checked",
        detailed_reasoning="Charge checked",
        transactions=[
            TransactionDecision(
                txn_id=CHARGE_ID,
                verdict=Verdict.ACCEPTED,
                disputed_amount=Decimal("10"),
                credit_amount=Decimal("10"),
                cardholder_liability=Decimal("0"),
                network_action="file_dispute",
                rationale="Charge checked",
                evidence=[evidence],
            )
        ],
        hypotheses=[
            HypothesisAssessment(
                hypothesis="Wrong amount", status="accepted", why="Checked", evidence=[evidence]
            )
        ],
        decoys_ruled_out=[],
        missing_evidence=[],
        policy_basis=[Citation(document_id="CLS-1", why="Applicable")],
        account_actions=[],
        confidence=0.9,
        flip_fact="Different charge",
        cardholder_letter="Accepted",
    )


class Model:
    def __init__(self, turns):
        self.responses = {Triage: [triage()], SupervisorTurn: list(turns)}
        self.inputs = []
        self.schema = None

    def with_structured_output(self, schema, *, strict):
        assert strict
        self.schema = schema
        return self

    def invoke(self, messages):
        self.inputs.append(json.loads(messages[0].content))
        return self.responses[self.schema].pop(0)


class Agent:
    def __init__(self, name, tools, result, inputs):
        self.name, self.tools, self.result, self.inputs = name, tools, result, inputs

    def invoke(self, messages):
        self.inputs[self.name] = json.loads(messages[0].content)
        if self.name == "graph_analyst":
            tool = next(t for t in self.tools if t.name == "notebook_write")
            tool.invoke({"kind": "fact", "text": "Charge checked", "node_ids": [CHARGE_ID]})
        return {"structured_response": self.result}


class Builder:
    def __init__(self):
        self.inputs = {}
        self.tools = {}

    def __call__(self, **kwargs):
        name = kwargs["name"]
        self.tools[name] = {tool.name for tool in kwargs["tools"]}
        result = (
            report()
            if name == "adjudicator"
            else Findings(
                facts=[], hypothesis_updates=[], suggested_next=[], node_ids=[], edge_ids=[]
            )
        )
        return Agent(name, kwargs["tools"], result, self.inputs)


def test_parallel_delegation_notebook_and_static_graph(paths):
    model, builder = Model([delegate(), decide(False), decide(True)]), Builder()
    result = run_case(CASE_ID, paths=paths, run_id="run-test", model=model, agent_builder=builder)
    assert result.verdict == Verdict.ACCEPTED
    entries = read_entries(paths.notebook_db, "run-test")
    assert entries[0]["node_ids"] == [CHARGE_ID]
    assert entries[0] in builder.inputs["adjudicator"]["notebook"]
    assert any(
        entry in item.get("notebook", [])
        for item in model.inputs
        if "notebook" in item
        for entry in entries
    )
    assert set(paths.source_graph.parent.glob("*.lbug")) == {paths.source_graph}
    assert builder.tools["adjudicator"] == {
        "graph_schema",
        "graph_query",
        "graph_neighbors",
        "graph_find",
        "search_knowledge",
        "notebook_read",
    }
    events = load_events(paths.trajectory_db, "run-test")
    assert sum(event.type == "delegation_started" for event in events) == 2
    assert any(event.type == "notebook_write" for event in events)
    assert any(
        event.type == "edge_taken"
        and event.payload["source"] == event.payload["target"] == "supervisor"
        for event in events
    )


@pytest.mark.parametrize(
    "reason,limits", [("max_turns", {"max_turns": 1}), ("no_progress", {"no_progress_turns": 1})]
)
def test_forced_termination(paths, reason, limits):
    base = load_agents_config(Path("config/agents.yaml"))
    config = base.model_copy(update={"runtime": base.runtime.model_copy(update=limits)})
    run_case(
        CASE_ID,
        paths=paths,
        run_id=reason,
        model=Model([delegate()]),
        agent_builder=Builder(),
        agents_config=config,
    )
    assert [
        e.payload["reason"]
        for e in load_events(paths.trajectory_db, reason)
        if e.type == "termination"
    ] == [reason]


def test_only_structured_boundary_invokes_models():
    violations = []
    for path in Path("src").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                not isinstance(node, ast.Call)
                or not isinstance(node.func, ast.Attribute)
                or node.func.attr not in {"invoke", "ainvoke"}
                or path.name == "models.py"
            ):
                continue
            receiver = node.func.value
            if (
                path.name in {"runtime.py", "runtime_entry.py"}
                and isinstance(receiver, ast.Name)
                and receiver.id == "graph"
            ):
                continue
            violations.append(f"{path}:{node.lineno}")
    assert not violations
