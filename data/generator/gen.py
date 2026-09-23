"""Generate the evidence world, showcase cases, and evaluator/UI artifacts."""

import random
from pathlib import Path

from cases import CaseTruth, build_cases
from graph_builder import Graph
from knowledge import build_knowledge
from policies import PolicyDoc
from submissions import insert_submission, load_saved
from validate import validate_cases, write_case_outputs
from world import build_world, stats

import graph_store

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "data" / "corpus"


def build() -> tuple[Graph, list[PolicyDoc], list[CaseTruth]]:
    """The world, the showcase cases, then every saved Merchant Submission."""
    graph, docs = build_world()
    cases = build_cases(graph, random.Random(42))
    for submission in load_saved(CORPUS / "submissions"):
        insert_submission(graph, submission)
    return graph, docs, cases


def main() -> None:
    output = ROOT / "data" / "generated"
    graph_dir = output / "graph"
    graph, docs, cases = build()
    graph.write(graph_dir)
    store = graph_store.load(graph_dir, output / "evidence.lbug")
    validate_cases(store, cases)
    store.close()
    write_case_outputs(output, cases, graph)
    indexed = build_knowledge(docs, CORPUS / "precedents.yaml", output / "knowledge.sqlite")
    print(f"knowledge documents: {indexed}")
    stats(graph)


if __name__ == "__main__":
    main()
