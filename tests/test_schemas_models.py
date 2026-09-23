from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from langchain.agents.structured_output import StructuredOutputValidationError
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from config import load_agents_config, load_models_config
from domain.events import RuntimeSnapshot
from models import ModelCallCallbackHandler, chat_model, invoke_structured
from observability.emitter import EventEmitter
from schemas import (
    CaseReport,
    ChargeDecision,
    Citation,
    DisputeCategory,
    EvidenceLink,
    HypothesisAssessment,
    SystemImprovement,
    Task,
    Triage,
    Verdict,
)


def _evidence(claim: str = "source") -> EvidenceLink:
    return EvidenceLink(
        claim=claim,
        node_ids=["CHG-1"],
        edge_ids=["E-1"],
        source_excerpt=None,
    )


def _report(**overrides: object) -> CaseReport:
    values: dict[str, object] = {
        "case_id": "DSP-1",
        "verdict": Verdict.ACCEPTED,
        "category": DisputeCategory.OVR,
        "headline": "The claim is accepted.",
        "executive_summary": "The graph supports the claim.",
        "detailed_reasoning": "The charge and its evidence were checked.",
        "charges": [
            ChargeDecision(
                charge_id="CHG-1",
                verdict=Verdict.ACCEPTED,
                category=DisputeCategory.OVR,
                disputed_amount=Decimal("10.00"),
                credit_amount=Decimal("10.00"),
                card_member_liability=Decimal("0"),
                rationale="The evidence supports the claim.",
                evidence=[_evidence()],
            )
        ],
        "hypotheses": [
            HypothesisAssessment(
                hypothesis="The charge amount was wrong.",
                status="accepted",
                why="The graph evidence supports it.",
                evidence=[_evidence("authorization")],
            )
        ],
        "decoys_ruled_out": [],
        "policy_basis": [Citation(document_id="CLS-1", why="It applies to the Dispute.")],
        "system_improvements": [],
        "confidence": 0.9,
        "flip_fact": "A different agreed amount.",
        "card_member_letter": "We accepted your Dispute.",
    }
    values.update(overrides)
    return CaseReport.model_validate(values)


def test_schema_validators_cover_ad_hoc_tasks_and_case_reports() -> None:
    with pytest.raises(ValidationError):
        Task(role="fresh_specialist", objective="Investigate")

    report = _report()
    assert report.policy_basis[0].document_id == "CLS-1"
    assert report.system_improvements == []

    with pytest.raises(ValidationError, match="must equal disputed_amount"):
        _report(
            charges=[
                ChargeDecision(
                    charge_id="CHG-1",
                    verdict=Verdict.ACCEPTED,
                    category=DisputeCategory.OVR,
                    disputed_amount=Decimal("10.00"),
                    credit_amount=Decimal("9.00"),
                    card_member_liability=Decimal("0"),
                    rationale="The evidence supports the claim.",
                    evidence=[_evidence()],
                )
            ]
        )

    with pytest.raises(ValidationError, match="requires evidence"):
        _report(
            charges=[
                ChargeDecision(
                    charge_id="CHG-1",
                    verdict=Verdict.ACCEPTED,
                    category=DisputeCategory.OVR,
                    disputed_amount=Decimal("10.00"),
                    credit_amount=Decimal("10.00"),
                    card_member_liability=Decimal("0"),
                    rationale="The evidence supports the claim.",
                    evidence=[],
                )
            ]
        )

    for verdict, credit in ((Verdict.REJECTED, "10"), (Verdict.GOODWILL_CREDIT, "0")):
        with pytest.raises(ValidationError):
            _report(
                charges=[
                    ChargeDecision(
                        charge_id="CHG-1",
                        verdict=verdict,
                        category=DisputeCategory.OVR,
                        disputed_amount=Decimal("10"),
                        credit_amount=Decimal(credit),
                        card_member_liability=Decimal("10") - Decimal(credit),
                        rationale="Checked",
                        evidence=[_evidence()],
                    )
                ]
            )

    with pytest.raises(ValidationError, match="requires evidence"):
        _report(
            system_improvements=[
                SystemImprovement(target="process", issue="Gap", suggestion="Clarify", evidence=[])
            ]
        )


def test_agents_config_loads() -> None:
    config = load_agents_config(Path("config/agents.yaml"))

    assert {role.id for role in config.roles} == {
        "graph_analyst",
        "payments_analyst",
        "evidence_analyst",
        "policy_analyst",
        "memory_keeper",
        "critic",
        "adjudicator",
    }
    assert "graph-investigation" in config.role_map["graph_analyst"].default_skills
    assert config.runtime.max_parallel_tasks == 4


def test_models_config_loads() -> None:
    config = load_models_config(Path("config/models.yaml"))

    assert config.default.model
    assert "structured_output" in config.default.required_capabilities


def test_chat_model_builds_without_network() -> None:
    config = load_models_config(Path("config/models.yaml"))
    model = chat_model(config)

    assert model.model == config.default.model


class _StructuredStub:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls = 0

    def with_structured_output(self, schema: type[object], *, strict: bool) -> _StructuredStub:
        assert strict is True
        return self

    def invoke(self, messages: list[object]) -> object:
        self.calls += 1
        return self.responses.pop(0)


def test_invoke_structured_retries_once_on_validation_error() -> None:
    model = _StructuredStub(
        [
            {"case_type": "known"},
            {
                "case_type": "known",
                "hypotheses": [],
                "plan": [],
                "rationale": "The intake is clear.",
            },
        ]
    )

    result = invoke_structured(model, Triage, ["inspect the case"])

    assert result.case_type == "known"
    assert model.calls == 2


class _WrappedFailureStub(_StructuredStub):
    """Like a Deep Agent, whose structured-output middleware wraps the validation error."""

    def invoke(self, messages: list[object]) -> object:
        response = super().invoke(messages)
        if isinstance(response, Exception):
            raise StructuredOutputValidationError("Triage", response, AIMessage(content=""))
        return response


def test_invoke_structured_retries_wrapped_validation_error() -> None:
    valid = {"case_type": "known", "hypotheses": [], "plan": [], "rationale": "Clear."}
    model = _WrappedFailureStub([ValueError("credit mismatch"), valid])

    assert invoke_structured(model, Triage, ["inspect the case"]).case_type == "known"
    assert model.calls == 2


def test_invoke_structured_raises_after_one_retry() -> None:
    model = _StructuredStub([{"case_type": "known"}, {"case_type": "known"}])

    with pytest.raises(ValidationError):
        invoke_structured(model, Triage, ["inspect the case"])
    assert model.calls == 2


class _AgentStub:
    def __init__(self, response: object) -> None:
        self.response = response

    def invoke(self, messages: list[object]) -> object:
        return self.response


def test_invoke_structured_reads_deep_agent_structured_response() -> None:
    result = invoke_structured(
        _AgentStub(
            {
                "structured_response": {
                    "case_type": "known",
                    "hypotheses": [],
                    "plan": [],
                    "rationale": "The intake is clear.",
                }
            }
        ),
        Triage,
        ["inspect the case"],
    )

    assert result.case_type == "known"


def test_model_callback_emits_usage_and_latency(tmp_path: Path) -> None:
    emitter = EventEmitter(
        tmp_path / "events.sqlite",
        run_id="run-1",
        case_id="DSP-1",
        runtime=RuntimeSnapshot(
            config_hash="test",
            agent_runtime="test",
            provider="test",
            model="test",
        ),
    )
    callback = ModelCallCallbackHandler(emitter, actor="triage")
    callback.on_chat_model_start(
        {"kwargs": {"model": "test-model"}},
        [[]],
        run_id="model-1",
        metadata={"schema_name": "Triage"},
    )
    callback.on_llm_end(
        type(
            "Response",
            (),
            {
                "llm_output": {"token_usage": {"prompt_tokens": 3, "completion_tokens": 5}},
                "generations": [],
            },
        )(),
        run_id="model-1",
    )

    event = emitter.events()[0]
    assert event.type == "model_call"
    assert event.payload["schema"] == "Triage"
    assert event.usage.input_tokens == 3
    assert event.usage.output_tokens == 5
