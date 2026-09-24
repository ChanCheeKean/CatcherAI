import re

import ontology
import pytest
import yaml


def test_every_item_is_described_and_grouped():
    spec = ontology.load()
    for group in spec["groups"].values():
        assert group["title"] and group["description"]
    for label, node in spec["nodes"].items():
        assert node["description"] and node["group"] in spec["groups"], label
        assert re.fullmatch(r"[A-Z]{2,3}", node["prefix"])
        assert all(p["description"] for p in node["props"].values()), label
    for etype, edge in spec["edges"].items():
        assert edge["description"] and edge["pairs"], etype
        assert all(p["description"] for p in edge["props"].values()), etype


def test_prefixes_unique_and_pairs_reference_labels():
    spec = ontology.load()
    prefixes = [n["prefix"] for n in spec["nodes"].values()]
    assert len(prefixes) == len(set(prefixes))
    for edge in spec["edges"].values():
        for src, dst in edge["pairs"]:
            assert src in spec["nodes"] and dst in spec["nodes"]


def test_loader_rejects_missing_description(tmp_path):
    raw = yaml.safe_load(ontology.PATH.read_text())
    del raw["nodes"]["Card"]["description"]
    path = tmp_path / "o.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="Card"):
        ontology.load(path)


def test_descriptions_are_whole_sentences():
    spec = ontology.load()
    assert spec["groups"]["parties"]["description"].endswith("and Merchants.")
    product = spec["nodes"]["CardAccount"]["props"]["product"]["description"]
    assert product.endswith("Blue Cash.")


def test_loader_rejects_unknown_keys(tmp_path):
    raw = yaml.safe_load(ontology.PATH.read_text())
    raw["nodes"]["Card"]["props"]["last4"]["stray"] = None
    path = tmp_path / "o.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="Card.last4.*stray"):
        ontology.load(path)
