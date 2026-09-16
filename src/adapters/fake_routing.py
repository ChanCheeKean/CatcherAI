"""Deterministic route classification used only by FakeModelGateway in tests.

This is the old field-matching engine and the old per-route budget numbers, preserved
here so tests keep exercising every route and every budget boundary exactly as before —
production code (`routing.py`) no longer does field matching; it always asks the model.
"""

from __future__ import annotations

from typing import Any

# (route_id, match) in the original routes.yaml priority order — first match wins.
_RULES: list[tuple[str, dict[str, Any]]] = [
    ("agentic_transaction_novel_l4", {"transaction_channels_contains": "agentic_commerce"}),
    ("descriptor_confusion_l1", {"claim_family_initial": "fraud_card_present", "descriptor_history_count_min": 1}),
    ("reg_e_not_received_credit_check_l1", {"regime": "REG_E", "claim_family_initial": "not_received"}),
    ("bundled_not_received_l2", {"claim_family_initial": "not_received", "transaction_count_min": 2}),
    ("credit_shortfall_fx_l2", {"claim_family_initial": "credit_not_processed"}),
    ("lodging_folio_amount_l3", {"claim_family_initial": "incorrect_amount"}),
    ("lodging_cancellation_l2", {"claim_family_initial": "cancelled_merch"}),
    ("duplicate_processing_l2", {"claim_family_initial": "duplicate"}),
    ("not_as_described_l2", {"claim_family_initial": "not_as_described"}),
    ("debit_fraud_l3", {"regime": "REG_E", "claim_family_initial": "fraud_cnp"}),
    ("recurring_mid_lifecycle_l3", {"claim_family_initial": "cancelled_recurring", "stage": "pre_arb_decision_due"}),
    ("recurring_trial_l3", {"claim_family_initial": "cancelled_recurring"}),
    ("household_authority_l4", {"regime": "REG_Z", "claim_family_initial": "fraud_cnp", "transaction_count_min": 5, "prior_merchant_purchases_min": 1}),
    ("high_value_cnp_ato_l4", {"regime": "REG_Z", "claim_family_initial": "fraud_cnp", "billing_total_min": 500}),
    ("stale_claim_timeliness_l2", {"claim_family_initial": "not_received", "transaction_age_days_min": 150}),
    ("cnp_fraud_ce3_digital_l3", {"regime": "REG_Z", "claim_family_initial": "fraud_cnp", "transaction_count": 1, "prior_merchant_purchases_min": 1}),
    ("merchant_pattern_not_received_l2", {"claim_family_initial": "not_received", "transaction_count": 1, "merchant_closed_same_family_disputes_min": 3}),
    ("merchant_nonperformance_not_received_l2", {"claim_family_initial": "not_received", "transaction_count": 1, "evidence_has_proof_of_delivery": False}),
    ("single_not_received_graph_check_l2", {"claim_family_initial": "not_received", "transaction_count": 1}),
]
_FALLBACK_ROUTE_ID = "novel_or_ambiguous"

_DEPTHS: dict[str, str] = {
    "descriptor_confusion_l1": "L1",
    "reg_e_not_received_credit_check_l1": "L1",
    "duplicate_processing_l2": "L2",
    "bundled_not_received_l2": "L2",
    "single_not_received_graph_check_l2": "L2",
    "merchant_pattern_not_received_l2": "L2",
    "credit_shortfall_fx_l2": "L2",
    "lodging_cancellation_l2": "L2",
    "not_as_described_l2": "L2",
    "stale_claim_timeliness_l2": "L2",
    "merchant_nonperformance_not_received_l2": "L2",
    "recurring_trial_l3": "L3",
    "debit_fraud_l3": "L3",
    "recurring_mid_lifecycle_l3": "L3",
    "lodging_folio_amount_l3": "L3",
    "cnp_fraud_ce3_digital_l3": "L3",
    "high_value_cnp_ato_l4": "L4",
    "agentic_transaction_novel_l4": "L4",
    "household_authority_l4": "L4",
    "novel_or_ambiguous": "L4",
}

BUDGETS: dict[str, dict[str, float]] = {
    "descriptor_confusion_l1": {"tool_calls": 7, "model_input_tokens": 30000, "model_output_tokens": 4000, "wall_seconds": 60, "replans": 0, "no_progress_iterations": 1, "max_agent_calls": 4},
    "duplicate_processing_l2": {"tool_calls": 10, "model_input_tokens": 50000, "model_output_tokens": 6000, "wall_seconds": 120, "replans": 1, "no_progress_iterations": 2, "max_agent_calls": 6},
    "bundled_not_received_l2": {"tool_calls": 12, "model_input_tokens": 50000, "model_output_tokens": 6000, "wall_seconds": 120, "replans": 1, "no_progress_iterations": 2, "max_agent_calls": 6},
    "recurring_trial_l3": {"tool_calls": 14, "model_input_tokens": 70000, "model_output_tokens": 8000, "wall_seconds": 180, "replans": 2, "no_progress_iterations": 2, "max_agent_calls": 8},
    "debit_fraud_l3": {"tool_calls": 25, "model_input_tokens": 90000, "model_output_tokens": 12000, "wall_seconds": 240, "replans": 2, "no_progress_iterations": 2, "max_agent_calls": 8},
    "high_value_cnp_ato_l4": {"tool_calls": 30, "model_input_tokens": 120000, "model_output_tokens": 16000, "wall_seconds": 300, "replans": 3, "no_progress_iterations": 2, "max_agent_calls": 12},
    "single_not_received_graph_check_l2": {"tool_calls": 35, "model_input_tokens": 140000, "model_output_tokens": 18000, "wall_seconds": 300, "replans": 2, "no_progress_iterations": 2, "max_agent_calls": 6},
    "agentic_transaction_novel_l4": {"tool_calls": 20, "model_input_tokens": 120000, "model_output_tokens": 16000, "wall_seconds": 300, "replans": 1, "no_progress_iterations": 2, "max_agent_calls": 12},
    "recurring_mid_lifecycle_l3": {"tool_calls": 24, "model_input_tokens": 90000, "model_output_tokens": 12000, "wall_seconds": 240, "replans": 1, "no_progress_iterations": 2, "max_agent_calls": 8},
    "household_authority_l4": {"tool_calls": 24, "model_input_tokens": 120000, "model_output_tokens": 16000, "wall_seconds": 300, "replans": 1, "no_progress_iterations": 2, "max_agent_calls": 12},
    "merchant_pattern_not_received_l2": {"tool_calls": 18, "model_input_tokens": 60000, "model_output_tokens": 8000, "wall_seconds": 180, "replans": 1, "no_progress_iterations": 2, "max_agent_calls": 6},
    "reg_e_not_received_credit_check_l1": {"tool_calls": 10, "model_input_tokens": 90000, "model_output_tokens": 12000, "wall_seconds": 240, "replans": 1, "no_progress_iterations": 2, "max_agent_calls": 4},
    "credit_shortfall_fx_l2": {"tool_calls": 10, "model_input_tokens": 90000, "model_output_tokens": 12000, "wall_seconds": 240, "replans": 1, "no_progress_iterations": 2, "max_agent_calls": 6},
    "lodging_folio_amount_l3": {"tool_calls": 24, "model_input_tokens": 90000, "model_output_tokens": 12000, "wall_seconds": 240, "replans": 1, "no_progress_iterations": 2, "max_agent_calls": 8},
    "lodging_cancellation_l2": {"tool_calls": 14, "model_input_tokens": 90000, "model_output_tokens": 12000, "wall_seconds": 240, "replans": 1, "no_progress_iterations": 2, "max_agent_calls": 6},
    "not_as_described_l2": {"tool_calls": 14, "model_input_tokens": 90000, "model_output_tokens": 12000, "wall_seconds": 240, "replans": 1, "no_progress_iterations": 2, "max_agent_calls": 6},
    "stale_claim_timeliness_l2": {"tool_calls": 12, "model_input_tokens": 90000, "model_output_tokens": 12000, "wall_seconds": 240, "replans": 1, "no_progress_iterations": 2, "max_agent_calls": 6},
    "cnp_fraud_ce3_digital_l3": {"tool_calls": 22, "model_input_tokens": 90000, "model_output_tokens": 12000, "wall_seconds": 240, "replans": 1, "no_progress_iterations": 2, "max_agent_calls": 8},
    "merchant_nonperformance_not_received_l2": {"tool_calls": 14, "model_input_tokens": 90000, "model_output_tokens": 12000, "wall_seconds": 240, "replans": 1, "no_progress_iterations": 2, "max_agent_calls": 6},
    "novel_or_ambiguous": {"tool_calls": 24, "model_input_tokens": 120000, "model_output_tokens": 16000, "wall_seconds": 300, "replans": 3, "no_progress_iterations": 2, "max_agent_calls": 12},
}


def classify(features: dict[str, Any]) -> tuple[str, str]:
    for route_id, match in _RULES:
        if _matches(features, match):
            return route_id, _DEPTHS[route_id]
    return _FALLBACK_ROUTE_ID, _DEPTHS[_FALLBACK_ROUTE_ID]


def _matches(features: dict[str, Any], match: dict[str, Any]) -> bool:
    return all(_check(features, expression, expected) for expression, expected in match.items())


def _check(features: dict[str, Any], expression: str, expected: Any) -> bool:
    field, operator = _parse_expression(expression)
    actual = features.get(field)
    if operator == "eq":
        return actual == expected
    if operator == "gte":
        return actual is not None and float(actual) >= float(expected)
    if operator == "lte":
        return actual is not None and float(actual) <= float(expected)
    if operator == "in":
        return actual in expected
    if operator == "contains":
        if isinstance(actual, list):
            return expected in actual
        return str(expected).casefold() in str(actual).casefold()
    raise ValueError(f"unknown route operator {operator}")


def _parse_expression(expression: str) -> tuple[str, str]:
    for suffix, operator in (("_min", "gte"), ("_max", "lte"), ("_in", "in"), ("_contains", "contains")):
        if expression.endswith(suffix):
            return expression.removesuffix(suffix), operator
    return expression, "eq"
