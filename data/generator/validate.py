"""Validate generated showcase cases and write evaluator/UI artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from capabilities import coverage
from cases import CaseTruth


def validate_cases(store, cases: list[CaseTruth]) -> None:
    """Fail when a solution node, proof path, or required decoy is absent."""
    for case in cases:
        for node_id in case["solution_node_ids"]:
            store.node(node_id)  # raises when the node is absent
        for pattern in case["proof_patterns"]:
            if not store.query(pattern["cypher"])["rows"]:
                raise ValueError(
                    f"{case['code']} proof pattern {pattern['name']!r} returned no rows"
                )
        for pattern in case["decoy_patterns"]:
            if not store.query(pattern["cypher"])["rows"]:
                raise ValueError(
                    f"{case['code']} decoy pattern {pattern['name']!r} returned no rows"
                )


def write_case_outputs(output_dir: Path, cases: list[CaseTruth], graph) -> None:
    """Write private evaluator truth and answer-free case-card data."""
    truth_dir = Path(output_dir) / "ground_truth" / "cases"
    truth_dir.mkdir(parents=True, exist_ok=True)
    for stale in truth_dir.glob("*.json"):
        stale.unlink()
    for case in cases:
        (truth_dir / f"{case['case_id']}.json").write_text(
            json.dumps(case, indent=2, sort_keys=True) + "\n"
        )
    catalog = [
        {
            "case_id": case["case_id"],
            "title": case["title"],
            "claim": case["claim"],
            "amount": graph.nodes[case["case_id"]]["props"]["amount"],
            "summary": case["intake"],
        }
        for case in cases
    ]
    (Path(output_dir) / "case_catalog.json").write_text(
        json.dumps(catalog, indent=2, sort_keys=True) + "\n"
    )
    (Path(output_dir) / "ground_truth" / "capability_coverage.json").write_text(
        json.dumps(coverage(), indent=2, sort_keys=True) + "\n"
    )
