"""Policy documents: one markdown source per version, projected into the graph and search."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from graph_builder import Graph

_HEADING = re.compile(r"^## (\S+) (.+)$", re.M)


@dataclass(frozen=True)
class Clause:
    id: str
    number: str
    heading: str
    text: str


@dataclass(frozen=True)
class PolicyDoc:
    id: str
    title: str
    owner: str
    kind: str
    version: str
    audience: str
    source_url: str
    publisher: str
    clauses: tuple[Clause, ...]


def parse(path: Path) -> PolicyDoc:
    """Read front matter and split the body into clauses at each `## <number> <heading>`."""
    _, front, body = path.read_text(encoding="utf-8").split("---", 2)
    meta = yaml.safe_load(front)
    parts = _HEADING.split(body)[1:]
    suffix = meta["doc_id"].removeprefix("POL-")
    clauses = tuple(
        Clause(f"CLS-{suffix}-{number}", number, heading.strip(), text.strip())
        for number, heading, text in zip(parts[::3], parts[1::3], parts[2::3], strict=True)
    )
    return PolicyDoc(
        id=meta["doc_id"],
        title=meta["title"],
        owner=meta["owner"],
        kind=meta["kind"],
        version=str(meta["version"]),
        audience=meta["audience"],
        source_url=meta.get("source_url") or "",
        publisher=meta.get("publisher") or "",
        clauses=clauses,
    )


def load_policies(root: Path) -> list[PolicyDoc]:
    return sorted((parse(p) for p in root.rglob("*.md")), key=lambda d: d.id)


def add_to_graph(g: Graph, doc: PolicyDoc) -> None:
    g.node(
        "PolicyDocument",
        doc.id,
        title=doc.title,
        owner=doc.owner,
        kind=doc.kind,
        version=doc.version,
        audience=doc.audience,
        source_url=doc.source_url,
    )
    for clause in doc.clauses:
        g.node("Clause", clause.id, number=clause.number, heading=clause.heading, text=clause.text)
        g.edge("HAS_CLAUSE", doc.id, clause.id)
    if doc.publisher:
        g.edge("PUBLISHED_BY", doc.id, doc.publisher)
