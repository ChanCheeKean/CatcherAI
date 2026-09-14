"""Bounded, read-only projections of the generated operational entity graph."""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from api.errors import not_found
from api.models import GraphEdge, GraphNode, GraphResponse


def case_neighborhood(root: Path, case_id: str, *, depth: int, limit: int) -> GraphResponse:
    graph_root = root / "data/generated/graph"
    start = f"Dispute:{case_id}"
    nodes_by_id: dict[str, dict[str, Any]] = {}
    with (graph_root / "nodes.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            nodes_by_id[item["node_id"]] = item
    if start not in nodes_by_id:
        raise not_found(
            "graph_case_not_found",
            f"case {case_id} is not in the operational graph",
            case_id=case_id,
        )

    adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with (graph_root / "edges.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            edge = json.loads(line)
            adjacency[edge["src"]].append(edge)
            adjacency[edge["dst"]].append(edge)

    discovered = {start}
    selected_edges: dict[str, dict[str, Any]] = {}
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    while queue and len(discovered) < limit:
        current, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        for edge in adjacency[current]:
            other = edge["dst"] if edge["src"] == current else edge["src"]
            edge_id = f"{edge['src']}|{edge['rel']}|{edge['dst']}"
            selected_edges[edge_id] = edge
            if other not in discovered and len(discovered) < limit:
                discovered.add(other)
                queue.append((other, current_depth + 1))

    nodes = []
    for node_id in sorted(discovered):
        item = nodes_by_id[node_id]
        refs = [node_id]
        nodes.append(
            GraphNode(
                id=node_id,
                label=str(item.get("key", node_id)),
                kind=str(item.get("label", "Entity")),
                properties=item.get("props", {}),
                source_refs=refs,
            )
        )
    edges = []
    for edge_id, item in sorted(selected_edges.items()):
        if item["src"] not in discovered or item["dst"] not in discovered:
            continue
        source = item.get("props", {}).get("source")
        refs = [str(source)] if source else [item["src"], item["dst"]]
        edges.append(
            GraphEdge(
                id=edge_id,
                source=item["src"],
                target=item["dst"],
                label=item["rel"],
                properties=item.get("props", {}),
                source_refs=refs,
            )
        )
    kinds = sorted({node.kind for node in nodes})
    return GraphResponse(nodes=nodes, edges=edges, legend={kind: kind for kind in kinds})
