from __future__ import annotations

import json
import random

import pytest
from cases import build_cases
from validate import validate_cases, write_case_outputs
from world import build_world

import graph_store


@pytest.fixture(scope="module")
def built_cases(tmp_path_factory):
    root = tmp_path_factory.mktemp("cases")
    graph = build_world(
        seed=23,
        customer_count=120,
        merchant_count=20,
        transaction_count=500,
        dispute_count=30,
    )
    truths = build_cases(graph, random.Random(23))
    graph.write(root / "graph")
    store = graph_store.load(root / "graph", root / "evidence.lbug")
    validate_cases(store, truths)
    store.close()
    write_case_outputs(root, truths, graph)
    return graph, truths, root


def test_all_five_cases_validate_and_have_decoys(built_cases) -> None:
    _, truths, _ = built_cases

    assert [case["code"] for case in truths] == ["C02", "C04", "C08", "C10", "C11"]
    for case in truths:
        assert case["decoy_patterns"]
        assert 5 <= len(case["solution_node_ids"]) <= 25
        assert case["human_effort"]["hops"] > 0
        assert case["human_effort"]["entities"] >= len(case["solution_node_ids"])


def test_ground_truth_is_separate_from_graph_and_catalog_is_neutral(built_cases) -> None:
    graph, truths, root = built_cases
    graph_text = "\n".join(
        str(value)
        for node in graph.nodes.values()
        for value in node["props"].values()
        if isinstance(value, str)
    )

    for case in truths:
        expected_text = json.dumps(case["expected"], sort_keys=True)
        assert expected_text not in graph_text
        written = json.loads(
            (root / "ground_truth" / "cases" / f"{case['case_id']}.json").read_text()
        )
        assert written == case

    catalog = json.loads((root / "case_catalog.json").read_text())
    assert len(catalog) == 5
    forbidden = {"accepted", "rejected", "not_a_dispute", "compromise", "takeover"}
    assert all(not (forbidden & set(item["summary"].lower().split())) for item in catalog)
    assert [item["claim_type"] for item in catalog] == [
        "fraud",
        "duplicate",
        "fraud",
        "fraud",
        "fraud",
    ]
    assert all(
        set(item) == {"case_id", "title", "claim_type", "amount", "summary"} for item in catalog
    )


def test_validation_rejects_broken_proof_and_missing_solution_node(built_cases) -> None:
    _, truths, root = built_cases
    store = graph_store.GraphStore(root / "evidence.lbug")
    broken = dict(truths[0])
    broken["proof_patterns"] = [
        {"name": "broken", "cypher": "MATCH (n) WHERE false RETURN n", "min_rows": 1}
    ]
    with pytest.raises(ValueError, match="proof pattern"):
        validate_cases(store, [broken])

    broken = dict(truths[0])
    broken["solution_node_ids"] = [*broken["solution_node_ids"], "CUS-does-not-exist"]
    with pytest.raises(ValueError, match="solution node"):
        validate_cases(store, [broken])
