import re
from pathlib import Path

from knowledge import build_knowledge
from policies import load_policies

from memory import retrieval

CORPUS = Path("data/corpus/policies")


def _db(tmp_path):
    precedents = tmp_path / "precedents.yaml"
    precedents.write_text(
        "- {title: Clearance item refused, body: A disclosed final sale clearance lamp.}\n"
        "- {title: Restocking fee, body: A restocking fee not shown at checkout was credited.}\n"
    )
    db = tmp_path / "knowledge.sqlite"
    assert build_knowledge(load_policies(CORPUS), precedents, db) > 40
    return db


def test_clause_search(tmp_path):
    db = _db(tmp_path)
    hits = retrieval.search(db, "custom order final sale")
    assert hits[0]["doc_id"] == "CLS-HGF-CO-V4-4.3"
    assert hits[0]["title"].startswith("Hearth & Grain Furniture Checkout Terms — 4.3")


def test_kind_filter(tmp_path):
    db = _db(tmp_path)
    hits = retrieval.search(db, "restocking fee", kinds=("precedent",))
    assert hits and {hit["doc_id"] for hit in hits} <= {"PRC-001", "PRC-002"}


def test_memory_notes(tmp_path):
    db = _db(tmp_path)
    note = retrieval.add_note(
        db,
        "Offer credits are Amex-funded; check the enrolled Card.",
        ["CLS-AMX-OFFER-1"],
        "run-1",
        0.8,
    )
    assert note.startswith("MEM-")
    hits = retrieval.search(db, "offer enrolled card", kinds=("memory_note",))
    assert [hit["doc_id"] for hit in hits] == [note]
    assert hits[0]["sources"] == '["CLS-AMX-OFFER-1"]' and hits[0]["run_id"] == "run-1"
    retrieval.set_status(db, note, "retracted")
    assert retrieval.search(db, "offer enrolled card", kinds=("memory_note",)) == []


def test_precedents_cite_existing_clauses():
    clauses = {c.id for d in load_policies(CORPUS) for c in d.clauses}
    text = Path("data/corpus/precedents.yaml").read_text()
    cited = set(re.findall(r"CLS-[A-Z0-9.-]*[A-Z0-9]", text))
    assert cited and cited <= clauses
