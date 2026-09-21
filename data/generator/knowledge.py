"""Build the knowledge database (policy corpus + precedent write-ups) for hybrid retrieval."""

from pathlib import Path

import yaml

from memory import retrieval


def load_policies(policies_dir: Path) -> list[dict[str, str]]:
    """Read one document per markdown file with YAML front matter."""
    docs = []
    for path in sorted(policies_dir.rglob("*.md")):
        _, front, body = path.read_text(encoding="utf-8").split("---", 2)
        meta = yaml.safe_load(front)
        docs.append(
            {
                "doc_id": meta["doc_id"],
                "kind": "policy",
                "title": meta["title"],
                "body": body.strip(),
                "valid_from": str(meta.get("effective_from") or ""),
                "valid_to": str(meta.get("effective_to") or ""),
                "status": meta.get("status", "active"),
            }
        )
    return docs


def load_precedents(path: Path) -> list[dict[str, str]]:
    """Read resolved-case write-ups from one YAML file, numbering them PRC-001 upwards."""
    entries = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        {
            "doc_id": f"PRC-{n:03d}",
            "kind": "precedent",
            "title": entry["title"],
            "body": entry["body"],
            "valid_from": "2026-01-01",
            "valid_to": "",
            "status": "active",
        }
        for n, entry in enumerate(entries, start=1)
    ]


def build_knowledge(root: Path, db_path: Path) -> int:
    """Build the searchable knowledge database and return the number of documents indexed."""
    corpus = root / "data" / "corpus"
    docs = load_policies(corpus / "policies") + load_precedents(corpus / "precedents.yaml")
    retrieval.build(db_path, docs)
    return len(docs)
