"""Response models of the two-page frontend API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from schemas import CaseReport


class CaseSummary(BaseModel):
    case_id: str
    title: str
    claim: str
    amount: float
    summary: str
    latest_run_id: str | None = None
    latest_verdict: str | None = None


class StartRun(BaseModel):
    case_id: str


class RunStatus(BaseModel):
    run_id: str
    case_id: str
    status: Literal["running", "completed", "failed"]
    error: str | None = None
    report: CaseReport | None = None


class GraphNode(BaseModel):
    id: str
    label: str
    properties: dict[str, Any]


class GraphEdge(BaseModel):
    id: str
    type: str
    src: str
    dst: str
    properties: dict[str, Any]


class GraphElements(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    missing: list[str]


class OntologyGroup(BaseModel):
    title: str
    description: str


class OntologyLabel(BaseModel):
    group: str
    description: str


class OntologyEdge(BaseModel):
    description: str


class GraphOntology(BaseModel):
    groups: dict[str, OntologyGroup]
    labels: dict[str, OntologyLabel]
    edges: dict[str, OntologyEdge]


class Neighbor(BaseModel):
    type: str
    direction: Literal["out", "in"]
    edge: dict[str, Any]
    node: dict[str, Any]


class Neighbors(BaseModel):
    neighbors: list[Neighbor]
    truncated: bool
    node_ids: list[str]
    edge_ids: list[str]


class EvalCase(BaseModel):
    case_id: str
    code: str
    title: str
    passed: bool
    solution_node_ids: list[str]
    decoy_node_ids: list[str]


class EvalLatest(BaseModel):
    """The newest evaluation batch; `batch` is null and `cases` empty when none has run."""

    batch: str | None = None
    k: int | None = None
    pass_at_1: int | None = None
    pass_at_k: int | None = None
    cases: list[EvalCase] = []
