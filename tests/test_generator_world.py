from collections import Counter

import pytest
import world


@pytest.fixture(scope="module")
def built():
    return world.build_world()


def test_world_is_deterministic(tmp_path):
    a, _ = world.build_world(seed=7)
    b, _ = world.build_world(seed=7)
    a.write(tmp_path / "a")
    b.write(tmp_path / "b")
    for name in ("nodes.jsonl", "edges.jsonl"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_world_scale_and_policies(built):
    g, docs = built
    labels = [n["label"] for n in g.nodes.values()]
    assert 120 <= labels.count("CardMember") <= 200
    assert 2000 <= labels.count("Charge") <= 5000
    assert labels.count("Dispute") >= 50
    assert {"POL-AMX-MR", "POL-AMX-DG", "POL-HGF-CO-V4"} <= {d.id for d in docs}
    assert any(d.id.startswith("POL-BG-") for d in docs)
    names = Counter(n["props"]["name"] for n in g.nodes.values() if n["label"] == "CardMember")
    assert sum(1 for c in names.values() if c > 1) >= 3


def test_every_merchant_bound_by_amex_regulations(built):
    g, _ = built
    merchants = {i for i, n in g.nodes.items() if n["label"] == "Merchant"}
    bound = {e["src"] for e in g.edges if e["type"] == "BOUND_BY" and e["dst"] == "POL-AMX-MR"}
    assert merchants <= bound


def test_corpus_publishers_and_program_are_in_the_world(built):
    g, docs = built
    assert {d.publisher for d in docs if d.publisher} <= g.nodes.keys()
    hotels = {e["src"] for e in g.edges if e["type"] == "PARTICIPATES_IN"}
    assert "MER-HPH" in hotels and len(hotels) == 6
    governs = {
        e["src"] for e in g.edges if e["type"] == "GOVERNS" and e["dst"] == world.PLATINUM_STAYS
    }
    assert governs == {world.AMEX_PLAT_BEN, world.AMEX_PS_PART}


def test_installments_add_up_and_are_settled_in_full(built):
    g, _ = built
    parts: dict[str, float] = Counter()
    settled: dict[str, float] = Counter()
    for e in g.edges:
        if e["type"] == "HAS_INSTALLMENT":
            parts[e["src"]] += g.nodes[e["dst"]]["props"]["amount"]
        if e["type"] == "SETTLES":
            settled[e["dst"]] += g.nodes[e["src"]]["props"]["amount"]
    assert len(parts) >= 8
    for invoice, total in parts.items():
        assert round(total, 2) == g.nodes[invoice]["props"]["total"]
    for installment, paid in settled.items():
        assert round(paid, 2) == g.nodes[installment]["props"]["amount"]
