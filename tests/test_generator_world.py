from __future__ import annotations

import json
from pathlib import Path

import pytest
from ontology import EDGES, NODES
from world import build_world, stats


def _small_world():
    return build_world(
        seed=17,
        customer_count=120,
        merchant_count=20,
        transaction_count=500,
        dispute_count=30,
    )


@pytest.fixture(scope="module")
def small_world():
    return _small_world()


def test_world_is_byte_deterministic(tmp_path: Path) -> None:
    first = _small_world()
    second = _small_world()
    first.write(tmp_path / "first")
    second.write(tmp_path / "second")

    for name in ("nodes.jsonl", "edges.jsonl", "ontology.json"):
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()


def test_world_uses_every_label_and_edge_type(small_world) -> None:
    assert {node["label"] for node in small_world.nodes.values()} == NODES.keys()
    assert {edge["type"] for edge in small_world.edges} == EDGES.keys()


def test_world_has_no_dangling_edges_and_valid_temporal_ranges(small_world) -> None:
    for edge in small_world.edges:
        assert edge["src"] in small_world.nodes
        assert edge["dst"] in small_world.nodes
        props = edge["props"]
        if props.get("valid_from") and props.get("valid_to"):
            assert props["valid_from"] <= props["valid_to"]


def test_stats_reports_every_label_and_edge_type(small_world, capsys) -> None:
    result = stats(small_world)

    assert set(result["nodes"]) == set(NODES)
    assert set(result["edges"]) == set(EDGES)
    rendered = capsys.readouterr().out
    assert json.dumps(result["nodes"], sort_keys=True) in rendered
    assert json.dumps(result["edges"], sort_keys=True) in rendered
