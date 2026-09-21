from __future__ import annotations

import ast
import os
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from graph_builder import Graph

import graph_store
from config import load_agents_config
from domain.events import event_from_row
from memory import retrieval
from runtime import RuntimePaths, run_case
from schemas import (
    AccountAction,
    CaseReport,
    Citation,
    Decide,
    Delegate,
    EvidenceLink,
    Fact,
    Findings,
    Hypothesis,
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
TXN_ID = "TXN-TEST-1"


class StructuredModel:
    def __init__(self, responses: dict[type, list[Any]]) -> None:
        self.responses = {schema: list(values) for schema, values in responses.items()}
        self.schemas: list[type] = []
        self._schema: type | None = None

    def with_structured_output(self, schema: type, *, strict: bool):
        assert strict
        bound = StructuredModel(self.responses)
        bound.responses = self.responses
        bound.schemas = self.schemas
        bound._schema = schema
        return bound

    def invoke(self, messages: list[Any]) -> Any:
        assert messages and self._schema is not None
        self.schemas.append(self._schema)
        return self.responses[self._schema].pop(0)


class AgentStub:
    def __init__(self, response: Any) -> None:
        self.response = response

    def invoke(self, messages: list[Any]) -> dict[str, Any]:
        assert messages
        return {"structured_response": self.response}


class AgentBuilder:
    def __init__(self, findings: dict[str, Findings], report: CaseReport) -> None:
        self.findings = findings
        self.report = report
        self.schemas: list[type] = []
        self.tool_names: dict[str, list[str]] = {}

    def __call__(self, **kwargs: Any) -> AgentStub:
        name = kwargs["name"]
        schema = kwargs["response_format"].schema
        self.schemas.append(schema)
        self.tool_names[name] = [tool.name for tool in kwargs["tools"]]
        if schema is CaseReport:
            return AgentStub(self.report)
        return AgentStub(self.findings.get(name, empty_findings()))


@pytest.fixture
def runtime_paths(tmp_path: Path) -> RuntimePaths:
    graph = Graph()
    graph.node("Customer", "CUS-TEST-1", name="Test Customer")
    graph.node(
        "Transaction",
        TXN_ID,
        ts="2026-09-01T10:00:00Z",
        amount=10.0,
        currency="USD",
        kind="purchase",
        channel="card_present",
        status="posted",
    )
    graph.node(
        "Dispute",
        CASE_ID,
        filed_at="2026-09-02",
        claim_type="fraud",
        amount=10.0,
        intake="I do not recognize this charge.",
        status="open",
    )
    graph.edge("FILED_BY", CASE_ID, "CUS-TEST-1")
    graph.edge("DISPUTES", CASE_ID, TXN_ID, amount=10.0)
    jsonl = tmp_path / "jsonl"
    graph.write(jsonl)
    source_graph = tmp_path / "evidence.lbug"
    graph_store.load(jsonl, source_graph).close()
    knowledge = tmp_path / "knowledge.sqlite"
    retrieval.build(knowledge, [])
    return RuntimePaths(
        source_graph=source_graph,
        knowledge_db=knowledge,
        run_dir=tmp_path / "runs",
        trajectory_db=tmp_path / "trajectory.sqlite",
        checkpoint_db=tmp_path / "checkpoints.sqlite",
        agents_config=Path("config/agents.yaml"),
        models_config=Path("config/models.yaml"),
        skills_dir=Path("skills"),
    )


def triage() -> Triage:
    return Triage(
        case_type="compromise_point",
        case_type_description=None,
        suggested_skills=["graph-investigation"],
        suggested_roles=["graph_analyst", "evidence_analyst"],
        hypotheses=[Hypothesis(label="fraud", status="open", support=[], against=[])],
        plan=[
            PlanItem(
                id="P1",
                question="Who made the transaction?",
                status="open",
                evidence_refs=[],
                waiver_reason=None,
            )
        ],
        rationale="Investigate the connected evidence.",
    )


def summary() -> InvestigationSummary:
    return InvestigationSummary(
        hypotheses=[Hypothesis(label="fraud", status="supported", support=[TXN_ID], against=[])],
        key_facts=[Fact(statement="The transaction is disputed.", node_ids=[TXN_ID], edge_ids=[])],
        open_questions=[],
        contradictions=[],
    )


def delegate_turn() -> SupervisorTurn:
    return SupervisorTurn(
        reasoning="Use two independent specialists.",
        plan_edits=[],
        summary=summary(),
        action=Delegate(
            tasks=[
                Task(
                    role="graph_analyst",
                    instructions=None,
                    objective="Trace identities.",
                    skills=["graph-investigation"],
                    plan_item_ids=["P1"],
                ),
                Task(
                    role="evidence_analyst",
                    instructions=None,
                    objective="Check evidence.",
                    skills=[],
                    plan_item_ids=["P1"],
                ),
            ]
        ),
    )


def decide_turn(*, close_plan: bool) -> SupervisorTurn:
    edits = (
        [PlanEdit(operation="mark_done", plan_item_id="P1", evidence_refs=[TXN_ID])]
        if close_plan
        else []
    )
    return SupervisorTurn(
        reasoning="The evidence is sufficient.",
        plan_edits=edits,
        summary=summary(),
        action=Decide(reason="Investigation complete."),
    )


def empty_findings() -> Findings:
    return Findings(facts=[], hypothesis_updates=[], suggested_next=[], node_ids=[], edge_ids=[])


def finding(statement: str, node_id: str) -> Findings:
    return Findings(
        facts=[Fact(statement=statement, node_ids=[node_id], edge_ids=[])],
        hypothesis_updates=[],
        suggested_next=[],
        node_ids=[node_id],
        edge_ids=[],
    )


def report() -> CaseReport:
    evidence = EvidenceLink(
        claim="The disputed transaction was examined.",
        node_ids=[TXN_ID],
        edge_ids=[],
        source_excerpt=None,
    )
    return CaseReport(
        case_id=CASE_ID,
        verdict=Verdict.ACCEPTED,
        claim_family="fraud",
        headline="The claim is accepted.",
        executive_summary="The connected evidence supports the claim.",
        detailed_reasoning="The transaction and dispute were checked.",
        transactions=[
            TransactionDecision(
                txn_id=TXN_ID,
                verdict=Verdict.ACCEPTED,
                disputed_amount=Decimal("10"),
                credit_amount=Decimal("10"),
                cardholder_liability=Decimal("0"),
                network_action="file_dispute",
                reason_code="10.4",
                rationale="The evidence supports unauthorized use.",
                evidence=[evidence],
            )
        ],
        hypotheses=[
            HypothesisAssessment(
                hypothesis="Unauthorized use",
                status="accepted",
                why="The transaction evidence supports it.",
                evidence=[evidence],
            )
        ],
        decoys_ruled_out=[],
        missing_evidence=[],
        policy_basis=[Citation(document_id="P1", why="It governs the claim.")],
        account_actions=[AccountAction(action="reissue", target_id=None, reason="Protect account")],
        confidence=0.9,
        flip_fact="Proof of cardholder authorization.",
        cardholder_letter="We accepted your claim.",
    )


def events(path: Path) -> list:
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM run_events ORDER BY seq").fetchall()
    return [event_from_row(row) for row in rows]


def test_agent_graph_parallel_delegation_rejects_premature_decide_and_replays(
    runtime_paths: RuntimePaths,
) -> None:
    model = StructuredModel(
        {
            Triage: [triage()],
            SupervisorTurn: [
                delegate_turn(),
                decide_turn(close_plan=False),
                decide_turn(close_plan=True),
            ],
        }
    )
    builder = AgentBuilder(
        {
            "graph_analyst": finding("Identity path checked.", "CUS-TEST-1"),
            "evidence_analyst": finding("Transaction checked.", TXN_ID),
        },
        report(),
    )

    result = run_case(
        CASE_ID,
        paths=runtime_paths,
        run_id="run-main",
        model=model,
        agent_builder=builder,
    )

    assert result.verdict == Verdict.ACCEPTED
    trajectory = events(runtime_paths.trajectory_db)
    types = [event.type for event in trajectory]
    assert types.index("delegation_started") < types.index("delegation_finished")
    assert sum(event.type == "delegation_started" for event in trajectory) == 2
    starts = [event for event in trajectory if event.type == "delegation_started"]
    finishes = [event for event in trajectory if event.type == "delegation_finished"]
    assert all(event.payload["task"]["objective"] for event in starts)
    assert {event.parent_id for event in starts} == {event.parent_id for event in finishes}
    assert all(event.payload["findings"]["facts"] for event in finishes)
    assert all(event.parent_id for event in starts + finishes)
    assert all("output" in event.payload for event in trajectory if event.type == "node_exited")
    assert any(
        event.type == "edge_taken"
        and event.payload["source"] == event.payload["target"] == "supervisor"
        for event in trajectory
    )
    assert [event.payload["reason"] for event in trajectory if event.type == "termination"] == [
        "decided"
    ]
    assert any(
        event.type == "edge_taken"
        and event.payload["source"] == "consolidate_memory"
        and event.payload["target"] == "end"
        for event in trajectory
    )
    loaded_by = {event.actor.name for event in trajectory if event.type == "skill_loaded"}
    assert {"graph_analyst", "evidence_analyst", "adjudicator", "memory_keeper"} <= loaded_by
    assert all(event.visit >= 1 and event.turn >= 0 for event in trajectory)
    assert [event.seq for event in trajectory] == list(range(1, len(trajectory) + 1))
    assert all(schema in {Triage, SupervisorTurn} for schema in model.schemas)
    assert set(builder.schemas) == {Findings, CaseReport}
    assert set(builder.tool_names["adjudicator"]) == {
        "graph_schema",
        "graph_query",
        "graph_neighbors",
        "search_knowledge",
    }


@pytest.mark.parametrize(
    ("reason", "runtime_updates", "worker_finding"),
    [
        ("max_turns", {"max_turns": 1}, finding("New evidence.", TXN_ID)),
        ("no_progress", {"no_progress_turns": 1}, empty_findings()),
    ],
)
def test_forced_termination(
    runtime_paths: RuntimePaths,
    reason: str,
    runtime_updates: dict[str, int],
    worker_finding: Findings,
) -> None:
    base = load_agents_config(Path("config/agents.yaml"))
    config = base.model_copy(update={"runtime": base.runtime.model_copy(update=runtime_updates)})
    model = StructuredModel({Triage: [triage()], SupervisorTurn: [delegate_turn()]})
    builder = AgentBuilder(
        {"graph_analyst": worker_finding, "evidence_analyst": worker_finding}, report()
    )

    run_case(
        CASE_ID,
        paths=runtime_paths,
        run_id=f"run-{reason}",
        model=model,
        agent_builder=builder,
        agents_config=config,
    )

    trajectory = events(runtime_paths.trajectory_db)
    terminations = [event for event in trajectory if event.type == "termination"]
    assert terminations[-1].payload["reason"] == reason
    assert any(
        event.type == "edge_taken" and event.payload["reason"] == f"forced: {reason}"
        for event in trajectory
    )


def test_only_structured_boundary_invokes_models() -> None:
    violations: list[str] = []
    for path in Path("src").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"invoke", "ainvoke"}:
                continue
            if path.name == "models.py":
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

    for path in Path("src").rglob("*.py"):
        source = path.read_text()
        assert "json.loads(model" not in source
        assert "json.loads(response" not in source


@pytest.mark.llm
def test_real_llm_smoke_c04() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is not configured")
    if not Path("data/generated/evidence.lbug").exists():
        pytest.skip("generated evidence graph is absent")
    result = run_case("DSP-2026-90004", run_id=f"llm-{os.getpid()}")
    assert result.case_id == "DSP-2026-90004"
