"""Showcase-case contract and deterministic case builder."""

from __future__ import annotations

import random
from typing import TypedDict

from capabilities import required_capabilities
from graph_builder import Graph
from world import issue_card, open_account


class CaseTruth(TypedDict):
    case_id: str
    code: str
    title: str
    claim: str  # neutral phrase for the case card; never the category or the verdict
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


def basic_card(g: Graph, member: str, suffix: str, product: str, last4: str) -> str:
    """Open account `ACC-<suffix>` for `member` and issue them its basic Card `CRD-<suffix>`."""
    account = open_account(g, member, f"ACC-{suffix}", product)
    return issue_card(g, f"CRD-{suffix}", account, member, product, last4, "basic")


def build_cases(g: Graph, rng: random.Random) -> list[CaseTruth]:
    """Add every showcase case to an existing world in stable presentation order."""
    from . import a_final_sale, b_platinum_rate, c_offer_card, d_paid_transfer, e_wrong_plan

    builders = (
        a_final_sale.build,
        b_platinum_rate.build,
        c_offer_card.build,
        d_paid_transfer.build,
        e_wrong_plan.build,
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
