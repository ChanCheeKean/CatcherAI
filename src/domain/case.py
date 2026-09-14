from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class RouteBudget(BaseModel):
    tool_calls: int
    model_input_tokens: int
    model_output_tokens: int
    wall_seconds: float
    replans: int
    no_progress_iterations: int


class RouteDecision(BaseModel):
    route_id: str
    method: Literal["rule", "llm", "fallback"]
    candidates: list[str]
    confidence: float
    depth: Literal["L1", "L2", "L3", "L4"]
    graph_path: str
    budget: RouteBudget
    agents: list[str]
    skills: list[str]
    rationale: str


class NetworkAction(BaseModel):
    txn_id: str
    case_id: str
    action: str
    reason: str | None = None
    condition: str | None = None
    amount: Decimal
    certification: list[str] = Field(default_factory=list)
    earliest_filing_date: str | None = None


class CardholderResolution(BaseModel):
    outcome: str
    credit_amount: Decimal
    reversal_amount: Decimal
    liability_amount: Decimal
    credit_type: str | None = None
    reversal_of_txn_id: str | None = None
    redirect: dict[str, str] | None = None


class Adjudication(BaseModel):
    review_panel_used: bool
    positions: list[dict[str, str]] = Field(default_factory=list)
    confidence: float
    threshold: float = 0.75
    conservative_default_applied: bool = False
    flip_fact: str


class DecisionRecord(BaseModel):
    case_id: str
    regime: str
    is_dispute: bool
    claim_family: str
    split_case_required: bool = False
    network_actions: list[NetworkAction]
    cardholder_resolution: CardholderResolution
    case_resolutions: list[dict[str, Any]] = Field(default_factory=list)
    deadlines: dict[str, Any] = Field(default_factory=dict)
    adjudication: Adjudication
    automated_actions: list[dict[str, Any]] = Field(default_factory=list)
    follow_ups: list[dict[str, Any]] = Field(default_factory=list)
    wait: dict[str, Any] | None = None
    cardholder_guidance: dict[str, Any] = Field(default_factory=dict)
    conditions_considered: list[dict[str, str]] = Field(default_factory=list)
    memory_ops: list[dict[str, Any]] = Field(default_factory=list)
    account_actions: list[str] = Field(default_factory=list)
    letters: list[str] = Field(default_factory=list)
    citations: list[dict[str, str]] = Field(default_factory=list)
    hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    ring_members: list[str] = Field(default_factory=list)
    ring_linkage: bool | None = None
    visa_rule_notes: list[str] = Field(default_factory=list)
    ce3_assessment: dict[str, Any] = Field(default_factory=dict)
    ce3_analysis: dict[str, Any] = Field(default_factory=dict)
    fallback: dict[str, str] = Field(default_factory=dict)
    confidence: float
    explanation_for_cardholder: str
