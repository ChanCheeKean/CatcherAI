"""Build an evidence graph in memory, validated against the ontology, and write it as JSONL."""

from __future__ import annotations

import json
from pathlib import Path

import ontology


class Graph:
    def __init__(self) -> None:
        self.spec = ontology.load()
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []

    def node(self, label: str, id: str, **props) -> str:
        spec = self.spec["nodes"].get(label)
        if spec is None:
            raise ValueError(f"unknown node label {label!r}")
        if not id.startswith(spec["prefix"] + "-"):
            raise ValueError(f"{label} id {id!r} must start with {spec['prefix']}-")
        if id in self.nodes:
            raise ValueError(f"duplicate node id {id!r}")
        _check_props(f"node {label}", props, spec["props"].keys())
        self.nodes[id] = {"label": label, "id": id, "props": props}
        return id

    def edge(self, type: str, src: str, dst: str, **props) -> str:
        spec = self.spec["edges"].get(type)
        if spec is None:
            raise ValueError(f"unknown edge type {type!r}")
        if src not in self.nodes or dst not in self.nodes:
            raise ValueError(f"dangling {type} edge {src!r} -> {dst!r}")
        pair = (self.nodes[src]["label"], self.nodes[dst]["label"])
        if pair not in [tuple(p) for p in spec["pairs"]]:
            raise ValueError(f"{type} cannot connect {pair[0]} -> {pair[1]}")
        _check_props(f"edge {type}", props, spec["props"].keys())
        id = f"E-{len(self.edges) + 1:07d}"
        self.edges.append({"type": type, "id": id, "src": src, "dst": dst, "props": props})
        return id

    def write(self, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_jsonl(out_dir / "nodes.jsonl", self.nodes.values())
        _write_jsonl(out_dir / "edges.jsonl", self.edges)
        (out_dir / "ontology.json").write_text(json.dumps(self.spec, indent=1, sort_keys=True))


def _check_props(what: str, props: dict, allowed: dict) -> None:
    unknown = sorted(set(props) - set(allowed))
    if unknown:
        raise ValueError(f"unknown properties {unknown} on {what}")


def _write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
