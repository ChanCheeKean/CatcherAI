"""A hermetic API for the browser E2E: a tiny graph and scripted agents that call the real tools.

Run from the repo root:
    PYTHONPATH=data/generator:tests uv run uvicorn e2e_server:app --app-dir tests --port 8100
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from graph_builder import Graph
from test_runtime import (
    CASE_ID,
    TXN_ID,
    AgentStub,
    StructuredModel,
    decide_turn,
    delegate_turn,
    empty_findings,
    finding,
    report,
    triage,
)

import graph_store
from api.app import create_app
from api.context import ApiContext
from memory import retrieval
from runtime import RuntimePaths
from schemas import CaseReport, SupervisorTurn, Triage

RUNS = 20  # the scripted model answers this many runs before it runs dry
HOME = "ADR-TEST-1"


def build_graph(jsonl: Path) -> None:
    graph = Graph()
    graph.node("Customer", "CUS-TEST-1", name="Test Customer")
    graph.node("Customer", "CUS-TEST-2", name="Second Customer")
    graph.node(
        "Address", HOME, street="100 Amber Street", unit="1A", city="Austin", postcode="10000"
    )
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
    graph.edge("LIVES_AT", "CUS-TEST-1", HOME, valid_from="2026-01-01", valid_to="")
    graph.edge("LIVES_AT", "CUS-TEST-2", HOME, valid_from="2026-03-01", valid_to="")
    graph.edge("FILED_BY", CASE_ID, "CUS-TEST-1")
    graph.edge("DISPUTES", CASE_ID, TXN_ID, amount=10.0)
    graph.write(jsonl)


class ToolCallingAgent(AgentStub):
    """Calls real tools (so the trajectory carries graph ids), then answers with a fixed result."""

    def __init__(self, response: Any, tools: list, calls: list[tuple[str, dict]]) -> None:
        super().__init__(response)
        self.tools = {tool.name: tool for tool in tools}
        self.calls = calls

    def invoke(self, messages: list[Any]) -> dict[str, Any]:
        for name, args in self.calls:
            self.tools[name].invoke(args)
        return super().invoke(messages)


def scripted_agents(cited: CaseReport):
    calls = {
        "graph_analyst": [
            (
                "graph_query",
                {"cypher": "MATCH (c:Customer)-[l:LIVES_AT]->(a:Address) RETURN c, l, a"},
            )
        ],
        "evidence_analyst": [("graph_neighbors", {"id": TXN_ID})],
    }
    findings = {
        "graph_analyst": finding("Two customers share one address.", HOME),
        "evidence_analyst": finding("The transaction is disputed.", TXN_ID),
    }

    def build(**kwargs: Any) -> AgentStub:
        name = kwargs["name"]
        if kwargs["response_format"].schema is CaseReport:
            return AgentStub(cited)
        return ToolCallingAgent(
            findings.get(name, empty_findings()), kwargs["tools"], calls.get(name, [])
        )

    return build


def create() -> Any:
    root = Path(tempfile.mkdtemp(prefix="catcher-e2e-"))
    build_graph(root / "jsonl")
    source_graph = root / "evidence.lbug"
    graph_store.load(root / "jsonl", source_graph).close()
    knowledge = root / "knowledge.sqlite"
    retrieval.build(knowledge, [])
    catalog = root / "catalog.json"
    catalog.write_text(
        json.dumps(
            [
                {
                    "case_id": CASE_ID,
                    "title": "Shared address",
                    "claim_type": "fraud",
                    "amount": 10.0,
                    "summary": "I do not recognize this charge.",
                }
            ]
        )
    )
    cited = report()
    evidence = cited.transactions[0].evidence[0]
    evidence.node_ids = [HOME, "CUS-TEST-1", "CUS-TEST-2"]
    evidence.claim = "Both customers live at the same address."
    model = StructuredModel(
        {
            Triage: [triage() for _ in range(RUNS)],
            SupervisorTurn: [
                turn
                for _ in range(RUNS)
                for turn in (delegate_turn(), decide_turn(close_plan=True))
            ],
        }
    )
    paths = RuntimePaths(
        source_graph=source_graph,
        knowledge_db=knowledge,
        run_dir=root / "runs",
        trajectory_db=root / "trajectory.sqlite",
        checkpoint_db=root / "checkpoints.sqlite",
        agents_config=Path("config/agents.yaml"),
        models_config=Path("config/models.yaml"),
        skills_dir=Path("skills"),
    )
    context = ApiContext(
        paths=paths,
        catalog=catalog,
        ground_truth_dir=root / "truth",
        eval_dir=root / "eval",
        model=model,
        agent_builder=scripted_agents(cited),
    )
    return create_app(context)


app = create()
