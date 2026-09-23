import pytest

import notebook


def test_write_and_read_in_order(tmp_path):
    db = tmp_path / "nb.sqlite"
    first = notebook.write_entry(
        db, "run-1", "graph_analyst", "fact", "Accepted terms.", ["ORD-1"], []
    )
    notebook.write_entry(db, "run-2", "critic", "fact", "Other run.", ["ORD-9"], [])
    second = notebook.write_entry(
        db,
        "run-1",
        "policy_analyst",
        "conflict",
        "Conflicting clauses.",
        ["CLS-1", "CLS-2"],
        ["E-4"],
    )
    rows = notebook.read_entries(db, "run-1")
    assert [row["entry_id"] for row in rows] == [first["entry_id"], second["entry_id"]]
    assert [row["seq"] for row in rows] == [1, 2]
    assert rows[1]["edge_ids"] == ["E-4"]
    assert len(notebook.read_entries(db, "run-1", kinds=["conflict"])) == 1
    assert len(notebook.read_entries(db, "run-1", author="graph_analyst")) == 1
    assert notebook.read_entries(tmp_path / "missing.sqlite", "run-1") == []


def test_rejects_unknown_kind_and_uncited(tmp_path):
    db = tmp_path / "nb.sqlite"
    with pytest.raises(ValueError):
        notebook.write_entry(db, "r", "a", "gossip", "x", ["ORD-1"], [])
    with pytest.raises(ValueError):
        notebook.write_entry(db, "r", "a", "fact", "x", [], [])
