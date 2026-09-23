"""Structured contracts shared by the agent graph and its workers."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    WithJsonSchema,
    model_validator,
)

# Strict structured output rejects pydantic's Decimal regex, so advertise a plain number.
Money = Annotated[Decimal, Field(ge=0), WithJsonSchema({"type": "number", "minimum": 0})]


class SchemaModel(BaseModel):
    """Base class used to keep provider-generated objects closed and predictable."""

    model_config = ConfigDict(extra="forbid")


class Hypothesis(SchemaModel):
    label: str
    status: str
    support: list[str]
    against: list[str]


class Fact(SchemaModel):
    statement: str
    node_ids: list[str] = Field(validation_alias=AliasChoices("node_ids", "source_node_ids"))
    edge_ids: list[str] = Field(validation_alias=AliasChoices("edge_ids", "source_edge_ids"))


class PlanStatus(StrEnum):
    OPEN = "open"
    DONE = "done"
    WAIVED = "waived"


class PlanItem(SchemaModel):
    id: str
    question: str
    status: PlanStatus
    evidence_refs: list[str]
    waiver_reason: str | None


class PlanEdit(SchemaModel):
    operation: Literal["add", "drop", "mark_done", "done", "waive"] = Field(
        validation_alias=AliasChoices("operation", "action", "op")
    )
    plan_item_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("plan_item_id", "item_id", "plan_id"),
    )
    item: PlanItem | None = None
    question: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    waiver_reason: str | None = None


class Triage(SchemaModel):
    case_type: str
    hypotheses: list[Hypothesis]
    plan: list[PlanItem]
    rationale: str


class InvestigationSummary(SchemaModel):
    hypotheses: list[Hypothesis]
    key_facts: list[Fact]
    open_questions: list[str]
    contradictions: list[str]


_CATALOG_ROLES = frozenset(
    {
        "graph_analyst",
        "payments_analyst",
        "evidence_analyst",
        "policy_analyst",
        "memory_keeper",
        "critic",
        "adjudicator",
    }
)


class Task(SchemaModel):
    role: str
    instructions: str | None
    objective: str
    skills: list[str]
    plan_item_ids: list[str]

    @model_validator(mode="after")
    def ad_hoc_role_has_instructions(self) -> Task:
        if self.role not in _CATALOG_ROLES and not self.instructions:
            raise ValueError("ad-hoc tasks require instructions")
        return self


class Delegate(SchemaModel):
    tasks: list[Task]


class Decide(SchemaModel):
    reason: str | None = None


class SupervisorTurn(SchemaModel):
    reasoning: str
    plan_edits: list[PlanEdit]
    summary: InvestigationSummary
    action: Delegate | Decide


class Findings(SchemaModel):
    facts: list[Fact]
    hypothesis_updates: list[Hypothesis]
    suggested_next: list[str]
    node_ids: list[str]
    edge_ids: list[str]


class Verdict(StrEnum):
    ACCEPTED = "accepted"
    PARTIALLY_ACCEPTED = "partially_accepted"
    REJECTED = "rejected"
    GOODWILL_CREDIT = "goodwill_credit"
    NOT_A_DISPUTE = "not_a_dispute"
    FRAUD_REFERRAL = "fraud_referral"


class DisputeCategory(StrEnum):
    NKN = "NKN"
    RET = "RET"
    CNC = "CNC"
    CNR = "CNR"
    DMG = "DMG"
    DSS = "DSS"
    DUP = "DUP"
    NRC = "NRC"
    OVR = "OVR"
    PDD = "PDD"


_NO_CREDIT = {Verdict.REJECTED, Verdict.NOT_A_DISPUTE, Verdict.FRAUD_REFERRAL}
_CREDIT = {Verdict.ACCEPTED, Verdict.PARTIALLY_ACCEPTED, Verdict.GOODWILL_CREDIT}


class EvidenceLink(SchemaModel):
    claim: str
    node_ids: list[str]
    edge_ids: list[str]
    source_excerpt: str | None


class ChargeDecision(SchemaModel):
    charge_id: str
    verdict: Verdict
    category: DisputeCategory
    disputed_amount: Money
    credit_amount: Money
    card_member_liability: Money
    rationale: str
    evidence: list[EvidenceLink]


class HypothesisAssessment(SchemaModel):
    hypothesis: str
    status: Literal["accepted", "rejected"]
    why: str
    evidence: list[EvidenceLink]


class Citation(SchemaModel):
    document_id: str
    why: str


class SystemImprovement(SchemaModel):
    target: Literal["amex_policy", "merchant_policy", "process", "product", "data"]
    issue: str
    suggestion: str
    evidence: list[EvidenceLink]


class CaseReport(SchemaModel):
    case_id: str
    verdict: Verdict
    category: DisputeCategory
    headline: str
    executive_summary: str
    detailed_reasoning: str
    charges: list[ChargeDecision]
    hypotheses: list[HypothesisAssessment]
    decoys_ruled_out: list[str]
    policy_basis: list[Citation]
    system_improvements: list[SystemImprovement]
    confidence: float = Field(ge=0, le=1)
    flip_fact: str
    card_member_letter: str

    @model_validator(mode="after")
    def validate_evidence_and_amounts(self) -> CaseReport:
        for charge in self.charges:
            if not charge.evidence:
                raise ValueError(f"charge {charge.charge_id} requires evidence")
            if charge.credit_amount + charge.card_member_liability != charge.disputed_amount:
                raise ValueError(
                    f"charge {charge.charge_id}: credit_amount + card_member_liability must "
                    "equal disputed_amount"
                )
            if charge.verdict in _NO_CREDIT and charge.credit_amount:
                raise ValueError(f"charge {charge.charge_id}: {charge.verdict} gives no credit")
            if charge.verdict in _CREDIT and not charge.credit_amount:
                raise ValueError(f"charge {charge.charge_id}: {charge.verdict} needs a credit")
        for item in (*self.hypotheses, *self.system_improvements):
            if not item.evidence:
                raise ValueError(f"{type(item).__name__} requires evidence")
        return self
