import re
from datetime import date
from pathlib import Path

import yaml
from knowledge import load_policies, load_precedents

from memory import retrieval

ROOT = Path(__file__).resolve().parents[1]


def _db(tmp_path):
    db = tmp_path / "knowledge.sqlite"
    retrieval.build(
        db,
        load_policies(ROOT / "data/corpus/policies")
        + load_precedents(ROOT / "data/corpus/precedents.yaml"),
    )
    return db


def test_search_returns_relevant_policy(tmp_path):
    db = _db(tmp_path)
    hits = retrieval.search(
        db, "Regulation E liability lost or stolen device", as_of=date(2026, 6, 1)
    )
    assert any(hit["doc_id"].startswith("REGE-1005.6") for hit in hits[:3])
    hits = retrieval.search(db, "duplicate dispute same transaction twice", as_of=date(2026, 6, 1))
    assert hits


def test_kind_filter(tmp_path):
    db = _db(tmp_path)
    hits = retrieval.search(db, "refund", as_of=date(2026, 6, 1), kinds=("precedent",))
    assert hits and {hit["kind"] for hit in hits} == {"precedent"}


def test_as_of_filters_validity(tmp_path):
    db = _db(tmp_path)
    before = retrieval.search(db, "10.4 other fraud card-absent", as_of=date(2026, 6, 1), limit=20)
    after = retrieval.search(db, "10.4 other fraud card-absent", as_of=date(2026, 11, 1), limit=20)
    before_ids = {hit["doc_id"] for hit in before}
    after_ids = {hit["doc_id"] for hit in after}
    assert "VISA-10.4@2026-10-24" not in before_ids
    assert "VISA-10.4@2026-10-24" in after_ids
    assert "VISA-10.4@2026-04-18" in before_ids


def test_skills_are_generic_and_parse():
    skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
    assert len(skills) >= 8
    for path in skills:
        _, front, body = path.read_text().split("---", 2)
        meta = yaml.safe_load(front)
        assert meta["name"] == path.parent.name and meta["description"]
        assert not re.search(r"\b(DSP|TXN|CUS|ACC)-", body), path
