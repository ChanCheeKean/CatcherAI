"""Showcase-case contract and deterministic case builder."""

from __future__ import annotations

import random
from typing import TypedDict

from graph_builder import Graph


class CaseTruth(TypedDict):
    case_id: str
    code: str
    title: str
    intake: str
    misleading_surface: str
    expected: dict
    solution_node_ids: list[str]
    proof_patterns: list[dict]
    decoy_patterns: list[dict]
    required_capabilities: list[dict]


def charge_expected(
    charge_id: str,
    verdict: str,
    disputed: float,
    credit: float,
) -> dict:
    return {
        "charge_id": charge_id,
        "verdict": verdict,
        "disputed_amount": disputed,
        "credit_amount": credit,
        "card_member_liability": round(disputed - credit, 2),
    }


def build_cases(g: Graph, rng: random.Random) -> list[CaseTruth]:
    """Add every showcase case to an existing world in stable presentation order."""
    builders = ()
    cases = []
    for build in builders:
        case = build(g, rng)
        cases.append(_check_case(case))
    return cases


def _check_case(case: dict) -> CaseTruth:
    required = set(CaseTruth.__required_keys__)
    missing = required - case.keys()
    extra = case.keys() - required
    if missing or extra:
        raise ValueError(f"invalid case contract: missing={sorted(missing)}, extra={sorted(extra)}")
    if not 5 <= len(case["solution_node_ids"]) <= 25:
        raise ValueError(f"{case['code']} solution_node_ids must contain 5-25 IDs")
    if not case["proof_patterns"] or not case["decoy_patterns"]:
        raise ValueError(f"{case['code']} needs proof and decoy patterns")
    return case
