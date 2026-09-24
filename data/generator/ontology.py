"""Load and validate the evidence graph schema from ontology.yaml."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

PATH = Path(__file__).with_name("ontology.yaml")
TYPES = {"STRING", "INT64", "DOUBLE", "BOOLEAN"}


def load(path: Path = PATH) -> dict:
    spec = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    groups, nodes, edges = spec["groups"], spec["nodes"], spec["edges"]
    for group, details in groups.items():
        _check(group, details, {"title", "description"})
    prefixes: set[str] = set()
    for label, node in nodes.items():
        node.setdefault("props", {})
        _check(label, node, {"description", "group", "prefix"}, optional={"props"})
        if node["group"] not in groups:
            raise ValueError(f"{label}: unknown group {node['group']!r}")
        if not re.fullmatch(r"[A-Z]{2,3}", node["prefix"]) or node["prefix"] in prefixes:
            raise ValueError(f"{label}: prefix must be 2-3 unique uppercase letters")
        prefixes.add(node["prefix"])
        _check_props(label, node["props"])
    for etype, edge in edges.items():
        edge.setdefault("props", {})
        _check(etype, edge, {"description", "pairs"}, optional={"props"})
        for src, dst in edge["pairs"]:
            if src not in nodes or dst not in nodes:
                raise ValueError(f"{etype}: pair {src}->{dst} names an unknown label")
        _check_props(etype, edge["props"])
    return spec


def _check(name: str, item: dict, required: set[str], optional: frozenset = frozenset()) -> None:
    """Every required key present and non-empty, and no keys beyond required and optional.

    An unquoted comma inside a YAML flow mapping splits a description into
    extra keys, so unknown keys are rejected rather than ignored.
    """
    if unknown := set(item) - required - optional:
        raise ValueError(f"{name}: unknown keys {sorted(unknown)}")
    for key in sorted(required):
        if not item.get(key):
            raise ValueError(f"{name}: missing {key}")


def _check_props(owner: str, props: dict) -> None:
    for prop, spec in props.items():
        _check(f"{owner}.{prop}", spec, {"type", "description"})
        if spec["type"] not in TYPES:
            raise ValueError(f"{owner}.{prop}: unknown type {spec['type']!r}")
