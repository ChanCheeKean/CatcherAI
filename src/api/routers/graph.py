"""Evidence-graph lookups for the frontend and the evaluation overlay."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, Query

from api.context import ApiContext, Ctx
from api.errors import not_found
from api.models import (
    EvalCase,
    EvalLatest,
    GraphEdge,
    GraphElements,
    GraphNode,
    GraphOntology,
    Neighbors,
)
from graph_store import GraphStore

router = APIRouter(tags=["graph"])
ROW_CAP = 10_000


@contextmanager
def _store(ctx: ApiContext) -> Iterator[GraphStore]:
    """Open the shared static evidence graph."""

    path = ctx.paths.source_graph
    if not path.exists():
        raise not_found("graph_not_found", "evidence graph is missing")
    store = GraphStore(path, read_only=True)
    try:
        yield store
    finally:
        store.close()


@router.get("/graph/nodes", response_model=GraphElements)
def graph_elements(
    ctx: Ctx,
    ids: str = Query(description="Comma-separated node and edge ids"),
) -> GraphElements:
    wanted = sorted({i for i in ids.split(",") if i})
    with _store(ctx) as store:
        node_rows = store.query(
            "MATCH (n) WHERE n.id IN $ids RETURN n", {"ids": wanted}, row_cap=ROW_CAP
        )["rows"]
        edge_rows = store.query(
            "MATCH (a)-[r]->(b) WHERE r.id IN $ids RETURN r, a.id, b.id",
            {"ids": wanted},
            row_cap=ROW_CAP,
        )["rows"]
    nodes = [
        GraphNode(
            id=row["id"],
            label=row["_label"],
            properties={k: v for k, v in row.items() if k not in {"id", "_label"}},
        )
        for (row,) in node_rows
    ]
    edges = [
        GraphEdge(
            id=edge["id"],
            type=edge["_type"],
            src=src,
            dst=dst,
            properties={k: v for k, v in edge.items() if k not in {"id", "_type"}},
        )
        for edge, src, dst in edge_rows
    ]
    found = {n.id for n in nodes} | {e.id for e in edges}
    return GraphElements(nodes=nodes, edges=edges, missing=[i for i in wanted if i not in found])


@router.get("/graph/ontology", response_model=GraphOntology)
def graph_ontology(ctx: Ctx) -> dict:
    with _store(ctx) as store:
        ontology = store.ontology
        size = store.size()
    return {
        "groups": ontology["groups"],
        "labels": {
            label: {"group": spec["group"], "description": spec["description"]}
            for label, spec in ontology["nodes"].items()
        },
        "edges": {
            edge: {"description": spec["description"]} for edge, spec in ontology["edges"].items()
        },
        "node_count": size["nodes"],
        "edge_count": size["edges"],
    }


@router.get("/graph/neighbors/{node_id}", response_model=Neighbors)
def graph_neighbors(
    ctx: Ctx,
    node_id: str,
    limit: int = Query(200, ge=1, le=1000),
) -> dict:
    with _store(ctx) as store:
        try:
            return store.neighbors(node_id, limit=limit)
        except ValueError as error:
            raise not_found("node_not_found", str(error), node_id=node_id) from error


@router.get("/eval/latest", response_model=EvalLatest)
def latest_eval(ctx: Ctx) -> EvalLatest:
    """Solution and decoy ids per case from the newest evaluation batch (empty before any)."""

    summaries = sorted(ctx.eval_dir.glob("*/summary.json")) if ctx.eval_dir.exists() else []
    if not summaries:
        return EvalLatest()
    latest = summaries[-1]
    summary = json.loads(latest.read_text())
    truths = {
        truth["code"]: truth
        for truth in (json.loads(p.read_text()) for p in ctx.ground_truth_dir.glob("*.json"))
    }
    cases: list[EvalCase] = []
    with _store(ctx) as store:
        for case in summary["cases"]:
            truth = truths.get(case["code"])
            if truth is None:
                continue
            solutions = truth["solution_node_ids"]
            decoys: set[str] = set()
            for decoy in truth["decoy_patterns"]:
                decoys |= set(store.query(decoy["cypher"], row_cap=ROW_CAP)["node_ids"])
            cases.append(
                EvalCase(
                    case_id=truth["case_id"],
                    code=case["code"],
                    title=case["title"],
                    passed=case["pass_at_k"],
                    solution_node_ids=solutions,
                    decoy_node_ids=sorted(decoys - set(solutions)),
                )
            )
    return EvalLatest(
        batch=latest.parent.name,
        k=summary["k"],
        pass_at_1=summary["pass_at_1"],
        pass_at_k=summary["pass_at_k"],
        cases=cases,
    )
