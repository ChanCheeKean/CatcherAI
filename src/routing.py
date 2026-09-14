from __future__ import annotations

from decimal import Decimal

from config import RoutesConfig
from domain.case import RouteDecision
from domain.events import Actor, ActorKind, EventDraft
from observability.emitter import EventEmitter


def route_case(
    case: dict[str, str],
    features: dict[str, object],
    config: RoutesConfig,
    emitter: EventEmitter,
) -> RouteDecision:
    """First matching configured route wins; every rule evaluation is recorded."""

    context: dict[str, object] = {
        **case,
        **features,
        "billing_total": Decimal(str(case.get("dispute_amount") or "0")),
    }
    evaluated: list[dict[str, object]] = []
    selected = None
    for candidate in config.routes:
        match = candidate.match
        matched = bool(match.get("fallback"))
        checks: list[dict[str, object]] = []
        if not matched:
            matched = True
            for expression, expected in match.items():
                field, operator = _parse_expression(expression)
                actual = context.get(field)
                result = _compare(actual, operator, expected)
                checks.append(
                    {
                        "field": field,
                        "operator": operator,
                        "value": actual,
                        "expected": expected,
                        "pass": result,
                    }
                )
                matched = matched and result
        evaluated.append({"route_id": candidate.id, "matched": matched, "checks": checks})
        if matched:
            selected = candidate
            break
    if selected is None:
        raise RuntimeError("route configuration has no matching or fallback route")
    method = "fallback" if selected.match.get("fallback") else "rule"
    decision = RouteDecision(
        route_id=selected.id,
        method=method,
        candidates=[item.id for item in config.routes],
        confidence=1.0 if method == "rule" else 0.0,
        depth=selected.output.depth,
        graph_path=selected.output.graph_path,
        budget=selected.output.budget,
        agents=selected.output.agents,
        skills=selected.output.skills,
        rationale=(
            "First matching deterministic route"
            if method == "rule"
            else "No deterministic route matched; conservative novel route"
        ),
    )
    emitter.emit(
        EventDraft(
            actor=Actor(kind=ActorKind.GRAPH_NODE, name="route"),
            type="route_decision",
            summary=f"Selected {decision.route_id} at depth {decision.depth}",
            payload={
                "candidate_routes": decision.candidates,
                "evaluated_rules": evaluated,
                "features": {key: value for key, value in features.items()},
                "method": decision.method,
                "confidence": decision.confidence,
                "chosen_route": decision.route_id,
                "depth": decision.depth,
                "budget": decision.budget.model_dump(mode="json"),
                "selected_subagents": decision.agents,
                "selected_skills": decision.skills,
                "rationale": decision.rationale,
            },
            refs=[case["case_id"]],
        )
    )
    return decision


def _parse_expression(expression: str) -> tuple[str, str]:
    for suffix, operator in (
        ("_min", "gte"),
        ("_max", "lte"),
        ("_in", "in"),
        ("_contains", "contains"),
    ):
        if expression.endswith(suffix):
            return expression.removesuffix(suffix), operator
    return expression, "eq"


def _compare(actual: object, operator: str, expected: object) -> bool:
    if operator == "eq":
        return actual == expected
    if operator == "gte":
        return actual is not None and float(actual) >= float(expected)  # type: ignore[arg-type]
    if operator == "lte":
        return actual is not None and float(actual) <= float(expected)  # type: ignore[arg-type]
    if operator == "in":
        return actual in expected  # type: ignore[operator]
    if operator == "contains":
        if isinstance(actual, list):
            return expected in actual
        return str(expected).casefold() in str(actual).casefold()
    raise ValueError(f"unknown route operator {operator}")
