import gen
import pytest
from validate import validate_cases, write_case_outputs

import graph_store


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("gen")
    g, _, cases = gen.build()
    g.write(out / "graph")
    store = graph_store.load(out / "graph", out / "g.lbug")
    yield g, cases, store, out
    store.close()


def test_cases_validate_with_proofs_and_decoys(built):
    _, cases, store, _ = built
    validate_cases(store, cases)
    assert [case["code"] for case in cases] == ["A", "B", "C", "D", "E"]
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


def test_every_label_and_edge_type_is_used(built):
    g, *_ = built
    assert {n["label"] for n in g.nodes.values()} == set(g.spec["nodes"])
    assert {e["type"] for e in g.edges} == set(g.spec["edges"])


def test_five_cases_cover_verdicts_and_categories(built):
    _, cases, _, _ = built
    assert {c["expected"]["verdict"] for c in cases} == {
        "rejected",
        "accepted",
        "goodwill_credit",
        "partially_accepted",
        "not_a_dispute",
    }
    assert {c["expected"]["category"] for c in cases} == {"RET", "OVR", "PDD", "CNR"}
