"""Showcase-case contract and deterministic case builder."""

from __future__ import annotations

import random
from typing import TypedDict

from capabilities import required_capabilities
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
    missing_evidence: bool
    human_effort: dict
    required_capabilities: list[dict]


def transaction_expected(
    txn_id: str,
    verdict: str,
    amount: float,
    credit: float,
    network_action: str,
    reason_code: str | None,
) -> dict:
    return {
        "txn_id": txn_id,
        "verdict": verdict,
        "credit_amount": credit,
        "cardholder_liability": round(amount - credit, 2),
        "network_action": network_action,
        "reason_code": reason_code,
    }


def build_cases(g: Graph, rng: random.Random) -> list[CaseTruth]:
    """Add every showcase case to an existing world in stable presentation order."""
    from . import (
        c02_descriptor,
        c04_split,
        c08_pump,
        c10_tablet,
        c11_ato,
        c12_porch,
        c12b_wrong_house,
        c13_agent,
        c18_refund,
        c19_reputation,
    )

    builders = (
        c02_descriptor.build,
        c04_split.build,
        c08_pump.build,
        c10_tablet.build,
        c11_ato.build,
        c12_porch.build,
        c12b_wrong_house.build,
        c13_agent.build,
        c18_refund.build,
        c19_reputation.build,
    )
    cases = []
    for build in builders:
        case = build(g, rng)
        case["required_capabilities"] = required_capabilities(case["code"])
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
