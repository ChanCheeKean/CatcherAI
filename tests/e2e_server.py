"""Hermetic browser E2E API with a small ontology-valid graph and scripted agents."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from conftest import StructuredModel
from graph_builder import Graph
from test_runtime import CASE_ID, CHARGE_ID, decide, delegate, report, triage

import graph_store
from api.app import create_app
from api.context import ApiContext
from memory import retrieval
from runtime import RuntimePaths
from schemas import CaseReport, Findings, SupervisorTurn, Triage

RUNS = 20
CARD_MEMBER = "CMB-TEST-1"
MERCHANT = "MER-TEST-1"


def build_graph(jsonl: Path) -> None:
    graph = Graph()
    graph.node("CardMember", CARD_MEMBER, name="Test Card Member")
    graph.node("CardAccount", "ACC-TEST-1", product="Gold")
    graph.node("Card", "CRD-TEST-1", product="Gold")
    graph.node("Merchant", MERCHANT, name="Test Merchant")
    graph.node("Charge", CHARGE_ID, amount=10.0)
    graph.node("Dispute", CASE_ID, amount=10.0, status="open", intake="Wrong amount")
    graph.edge("HOLDS", CARD_MEMBER, "ACC-TEST-1", role="basic")
    graph.edge("ISSUED_ON", "CRD-TEST-1", "ACC-TEST-1")
    graph.edge("CHARGED_TO", CHARGE_ID, "CRD-TEST-1")
    graph.edge("AT_MERCHANT", CHARGE_ID, MERCHANT)
    graph.edge("FILED_BY", CASE_ID, CARD_MEMBER)
    graph.edge("DISPUTES", CASE_ID, CHARGE_ID, amount=10.0)
    graph.write(jsonl)


class Agent:
    def __init__(self, name: str, tools: list, answer: Any):
        self.name = name
        self.tools = {tool.name: tool for tool in tools}
        self.answer = answer

    def invoke(self, messages: list[Any]) -> dict[str, Any]:
        if self.name == "graph_analyst":
            self.tools["graph_query"].invoke(
                {"cypher": "MATCH (c:CardMember)-[h:HOLDS]->(a:CardAccount) RETURN c, h, a"}
            )
            self.tools["notebook_write"].invoke(
                {
                    "kind": "fact",
                    "text": "The Card Member holds this account.",
                    "node_ids": [CARD_MEMBER],
                }
            )
        elif self.name == "evidence_analyst":
            self.tools["graph_neighbors"].invoke({"id": CHARGE_ID})
        return {"structured_response": self.answer}


def scripted_agents(cited: CaseReport):
    def build(**kwargs: Any) -> Agent:
        name = kwargs["name"]
        answer = (
            cited
            if kwargs["response_format"].schema is CaseReport
            else Findings(
                facts=[], hypothesis_updates=[], suggested_next=[], node_ids=[], edge_ids=[]
            )
        )
        return Agent(name, kwargs["tools"], answer)

    return build


def create() -> Any:
    root = Path(tempfile.mkdtemp(prefix="disputeai-e2e-"))
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
                    "title": "Wrong amount",
                    "claim": "Charged too much",
                    "amount": 10.0,
                    "summary": "The Card Member questions the amount.",
                }
            ]
        )
    )
    cited = report()
    cited.charges[0].evidence[0].node_ids = [CHARGE_ID, CARD_MEMBER, MERCHANT]
    cited.charges[0].evidence[0].claim = "The charge and Card Member are linked."
    model = StructuredModel(
        {
            Triage: [triage() for _ in range(RUNS)],
            SupervisorTurn: [turn for _ in range(RUNS) for turn in (delegate(), decide())],
        }
    )
    paths = RuntimePaths(
        source_graph=source_graph,
        knowledge_db=knowledge,
        notebook_db=root / "notebook.sqlite",
        trajectory_db=root / "trajectory.sqlite",
        checkpoint_db=root / "checkpoints.sqlite",
        agents_config=Path("config/agents.yaml"),
        models_config=Path("config/models.yaml"),
        skills_dir=Path("skills"),
    )
    return create_app(
        ApiContext(
            paths=paths,
            catalog=catalog,
            ground_truth_dir=root / "truth",
            eval_dir=root / "eval",
            model=model,
            agent_builder=scripted_agents(cited),
        )
    )


app = create()
