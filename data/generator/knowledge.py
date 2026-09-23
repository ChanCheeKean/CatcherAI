"""Build the knowledge database: one search document per policy clause, plus precedent write-ups."""

from pathlib import Path

import yaml
from policies import PolicyDoc

from memory import retrieval


def clause_documents(docs: list[PolicyDoc]) -> list[dict[str, str]]:
    """One search document per clause, keyed by the clause id so a hit is also a graph node."""
    return [
        {
            "doc_id": clause.id,
            "kind": "policy",
            "title": f"{doc.title} — {clause.number} {clause.heading}",
            "body": clause.text,
        }
        for doc in docs
        for clause in doc.clauses
    ]


def load_precedents(path: Path) -> list[dict[str, str]]:
    """Read resolved-Dispute write-ups from one YAML file, numbering them PRC-001 upwards."""
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        {"doc_id": f"PRC-{n:03d}", "kind": "precedent", "title": e["title"], "body": e["body"]}
        for n, e in enumerate(entries, start=1)
    ]


def build_knowledge(docs: list[PolicyDoc], precedents: Path, db_path: Path) -> int:
    """Build the searchable knowledge database and return the number of documents indexed."""
    entries = clause_documents(docs) + load_precedents(precedents)
    retrieval.build(db_path, entries)
    return len(entries)
