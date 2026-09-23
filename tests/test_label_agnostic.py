"""Prompts, skills and runtime code must not depend on graph model names."""

import re
from pathlib import Path

import ontology

SCANNED = [
    *Path("src").rglob("*.py"),
    *Path("skills").rglob("*.md"),
    *Path("config").glob("*.yaml"),
]
EXEMPT = {Path("src/graph_store.py")}
CONTRACT_NAMES = {
    Path("src/schemas.py"): {"ACCEPTED"},
    Path("src/extensions/merchant_agent/contract.py"): {"MerchantSubmission"},
    Path("src/extensions/merchant_agent/agent.py"): {"MerchantSubmission"},
    Path("src/extensions/merchant_agent/store.py"): {"MerchantSubmission"},
}


def _names() -> list[str]:
    spec = ontology.load()
    labels = [label for label in spec["nodes"] if re.search(r"[a-z][A-Z]", label)]
    return labels + [f"(:{label}" for label in spec["nodes"]] + list(spec["edges"])


def test_no_label_or_edge_names_outside_the_ontology():
    hits = [
        f"{path}: {name}"
        for path in SCANNED
        if path not in EXEMPT
        for name in _names()
        if name not in CONTRACT_NAMES.get(path, set())
        if re.search(rf"(?<![A-Za-z_]){re.escape(name)}(?![A-Za-z_])", path.read_text())
    ]
    assert hits == []
