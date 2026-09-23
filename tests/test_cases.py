import random

import pytest
from cases import build_cases
from validate import validate_cases, write_case_outputs
from world import build_world

import graph_store


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("gen")
    g, _ = build_world()
    cases = build_cases(g, random.Random(42))
    g.write(out / "graph")
    store = graph_store.load(out / "graph", out / "g.lbug")
    yield g, cases, store, out
    store.close()


def test_cases_validate_with_proofs_and_decoys(built):
    _, cases, store, _ = built
    validate_cases(store, cases)
    assert [case["code"] for case in cases] == ["A", "B"]
    assert all(case["required_capabilities"] for case in cases)


def test_catalog_never_reveals_category_or_verdict(built):
    g, cases, _, out = built
    write_case_outputs(out, cases, g)
    catalog = (out / "case_catalog.json").read_text()
    for case in cases:
        assert case["expected"]["verdict"] not in catalog
        assert f'"{case["expected"]["category"]}"' not in catalog


def test_ground_truth_not_in_graph(built):
    g, cases, _, _ = built
    text = "\n".join(str(n["props"]) for n in g.nodes.values())
    for case in cases:
        assert case["misleading_surface"] not in text
