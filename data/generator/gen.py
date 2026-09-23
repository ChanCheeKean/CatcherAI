"""Generate the evidence world, showcase cases, and evaluator/UI artifacts."""

import random
from pathlib import Path

from cases import build_cases
from knowledge import build_knowledge
from policies import add_to_graph, load_policies
from validate import validate_cases, write_case_outputs
from world import build_world, stats

import graph_store


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    output = root / "data" / "generated"
    graph_dir = output / "graph"
    corpus = root / "data" / "corpus"
    docs = load_policies(corpus / "policies")
    graph = build_world()
    cases = build_cases(graph, random.Random(42))
    for doc in docs:
        add_to_graph(graph, doc)
    graph.write(graph_dir)
    store = graph_store.load(graph_dir, output / "evidence.lbug")
    validate_cases(store, cases)
    store.close()
    write_case_outputs(output, cases, graph)
    indexed = build_knowledge(docs, corpus / "precedents.yaml", output / "knowledge.sqlite")
    print(f"knowledge documents: {indexed}")
    stats(graph)


if __name__ == "__main__":
    main()
