"""Structured contracts shared by the agent graph and its workers."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


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
    case_type_description: str | None
    suggested_skills: list[str]
    suggested_roles: list[str]
    hypotheses: list[Hypothesis]
    plan: list[PlanItem]
    rationale: str

    @model_validator(mode="after")
    def novel_case_type_has_description(self) -> Triage:
        if self.case_type == "novel" and not self.case_type_description:
            raise ValueError("case_type_description is required when case_type is 'novel'")
        return self


class InvestigationSummary(SchemaModel):
    hypotheses: list[Hypothesis]
    key_facts: list[Fact]
    open_questions: list[str]
    contradictions: list[str]


_CATALOG_ROLES = frozenset(
    {
        "graph_analyst",
        "transaction_analyst",
        "evidence_analyst",
        "policy_researcher",
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
    NOT_A_DISPUTE = "not_a_dispute"


class EvidenceLink(SchemaModel):
    claim: str
    node_ids: list[str]
    edge_ids: list[str]
    source_excerpt: str | None


class TransactionDecision(SchemaModel):
    txn_id: str
    verdict: Verdict
    disputed_amount: Decimal = Field(ge=0)
    credit_amount: Decimal = Field(ge=0)
    cardholder_liability: Decimal = Field(ge=0)
    network_action: Literal["file_dispute", "no_dispute", "pre_arbitration", "none"]
    reason_code: str | None = None
    rationale: str
    evidence: list[EvidenceLink]


class HypothesisAssessment(SchemaModel):
    hypothesis: str
    status: Literal["accepted", "rejected"]
    why: str
    evidence: list[EvidenceLink]


class Citation(SchemaModel):
    document_id: str = Field(validation_alias=AliasChoices("document_id", "doc_id"))
    why: str

    @property
    def doc_id(self) -> str:
        return self.document_id


class AccountAction(SchemaModel):
    action: str
    target_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("target_id", "account_id", "card_id"),
    )
    reason: str = Field(validation_alias=AliasChoices("reason", "rationale"))

    @property
    def rationale(self) -> str:
        return self.reason


class CaseReport(SchemaModel):
    case_id: str
    verdict: Verdict
    claim_family: str
    headline: str
    executive_summary: str
    detailed_reasoning: str
    transactions: list[TransactionDecision]
    hypotheses: list[HypothesisAssessment]
    decoys_ruled_out: list[str]
    missing_evidence: list[str]
    policy_basis: list[Citation]
    account_actions: list[AccountAction]
    confidence: float = Field(ge=0, le=1)
    flip_fact: str
    cardholder_letter: str

    @model_validator(mode="after")
    def validate_evidence_and_amounts(self) -> CaseReport:
        for transaction in self.transactions:
            if not transaction.evidence:
                raise ValueError(f"transaction {transaction.txn_id} requires evidence")
            if (
                transaction.credit_amount + transaction.cardholder_liability
                != transaction.disputed_amount
            ):
                raise ValueError(
                    f"transaction {transaction.txn_id} amounts do not reconcile: "
                    "credit_amount + cardholder_liability must equal disputed_amount"
                )
        for hypothesis in self.hypotheses:
            if not hypothesis.evidence:
                raise ValueError(f"hypothesis {hypothesis.hypothesis!r} requires evidence")
        return self
