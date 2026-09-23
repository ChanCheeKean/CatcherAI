from pathlib import Path

import policies
from graph_builder import Graph

CORPUS = Path("data/corpus/policies")


def test_clause_ids_and_owner():
    docs = {d.id: d for d in policies.load_policies(CORPUS)}
    assert len(docs) == 14
    hgf = docs["POL-HGF-CO-V4"]
    assert hgf.owner == "merchant" and hgf.publisher == "MER-HGF"
    assert [c.id for c in hgf.clauses] == [
        "CLS-HGF-CO-V4-4.1",
        "CLS-HGF-CO-V4-4.2",
        "CLS-HGF-CO-V4-4.3",
    ]
    assert "final sale" in hgf.clauses[2].text.lower()
    assert docs["POL-AMX-OFFER"].source_url.startswith("https://")
    assert "CLS-AMX-DG-G-2" in {c.id for c in docs["POL-AMX-DG"].clauses}


def test_add_to_graph_links_clauses_and_publisher():
    g = Graph()
    g.node(
        "Merchant",
        "MER-HGF",
        name="Hearth & Grain Furniture",
        category="furniture",
        channel="online",
    )
    doc = policies.parse(CORPUS / "merchant" / "hgf-checkout-v4.md")
    policies.add_to_graph(g, doc)
    types = sorted(e["type"] for e in g.edges)
    assert types.count("HAS_CLAUSE") == 3 and "PUBLISHED_BY" in types
