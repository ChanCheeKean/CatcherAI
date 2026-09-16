from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from config import RoutesConfig
from domain.events import RuntimeSnapshot
from domain.model import Capability, ModelRequest, ModelResponse, ModelStreamEvent, Usage
from observability.emitter import EventEmitter
from routing import route_case
from runtime.gateway_chat_model import GatewayChatModel

ROUTES = RoutesConfig.model_validate(
    {
        "schema_version": 1,
        "route_confidence_threshold": 0.80,
        "routes": [
            {
                "id": "debit_fraud_l3",
                "depth": "L3",
                "description": "Reg E CNP fraud.",
                "required_skills": ["reg-e-clocks", "fraud-cnp"],
            },
            {
                "id": "novel_or_ambiguous",
                "depth": "L4",
                "description": "Fallback.",
                "required_skills": ["eligibility-check"],
            },
        ],
        "depth_bounds": {
            "L3": {
                "tool_calls": [8, 30],
                "model_input_tokens": [50000, 100000],
                "model_output_tokens": [6000, 14000],
                "wall_seconds": [90, 260],
                "replans": [1, 3],
                "no_progress_iterations": [1, 3],
                "max_agent_calls": [6, 10],
            },
            "L4": {
                "tool_calls": [15, 35],
                "model_input_tokens": [100000, 140000],
                "model_output_tokens": [12000, 20000],
                "wall_seconds": [200, 320],
                "replans": [1, 4],
                "no_progress_iterations": [1, 3],
                "max_agent_calls": [8, 16],
            },
        },
    }
)


class StubGateway:
    """Returns a fixed JSON body for every model call, for isolated routing.py tests."""

    def __init__(self, body: dict[str, object]) -> None:
        self.body = body

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset(Capability)

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        text = self.body if isinstance(self.body, str) else json.dumps(self.body)
        yield ModelStreamEvent(
            type="completed",
            response=ModelResponse(
                text=text,
                tool_calls=[],
                usage=Usage(input_tokens=10, output_tokens=10, cached_tokens=0),
                provider_request_id="stub",
                provider_metadata={},
            ),
        )


def _chat_model(body: dict[str, object] | str) -> GatewayChatModel:
    return GatewayChatModel(gateway=StubGateway(body), model_name="stub")


def _emitter(db_path: Path) -> EventEmitter:
    """Match the constructor every other test file uses; the brief's bare `EventEmitter()`
    does not match the (unchanged, out of scope) EventEmitter constructor, which requires
    db_path/run_id/case_id/runtime/virtual_now."""

    return EventEmitter(
        db_path,
        run_id="run-unit",
        case_id="DSP-TEST",
        runtime=RuntimeSnapshot(
            config_hash="sha256:unit",
            agent_runtime="unit",
            model_gateway="fake",
            provider="fake",
            model="fake",
        ),
        virtual_now=datetime(2026, 10, 21, 13, tzinfo=UTC),
    )


CASE = {"case_id": "DSP-TEST", "dispute_amount": "600"}
FEATURES = {"claim_family_initial": "fraud_cnp", "regime": "REG_E"}


async def test_route_case_accepts_confident_llm_classification(tmp_path: Path) -> None:
    body = {
        "route_id": "debit_fraud_l3",
        "depth": "L3",
        "agents": ["reg_e_clock_analyst"],
        "skills": ["fraud-cnp"],
        "budget": {
            "tool_calls": 20,
            "model_input_tokens": 80000,
            "model_output_tokens": 10000,
            "wall_seconds": 200,
            "replans": 2,
            "no_progress_iterations": 2,
            "max_agent_calls": 7,
        },
        "confidence": 0.92,
        "rationale": "Reg E CNP fraud pattern.",
    }
    decision = await route_case(
        CASE, FEATURES, ROUTES, _chat_model(body), _emitter(tmp_path / "events.sqlite")
    )
    assert decision.route_id == "debit_fraud_l3"
    assert decision.method == "llm"
    assert decision.confidence == 0.92
    assert set(decision.skills) == {"fraud-cnp", "reg-e-clocks"}
    assert decision.budget.tool_calls == 20
    assert decision.budget.max_agent_calls == 7


async def test_route_case_clamps_out_of_range_budget(tmp_path: Path) -> None:
    body = {
        "route_id": "debit_fraud_l3",
        "depth": "L3",
        "agents": [],
        "skills": [],
        "budget": {
            "tool_calls": 999,
            "model_input_tokens": 1,
            "model_output_tokens": 1,
            "wall_seconds": 1,
            "replans": 99,
            "no_progress_iterations": 99,
            "max_agent_calls": 999,
        },
        "confidence": 0.9,
        "rationale": "x",
    }
    decision = await route_case(
        CASE, FEATURES, ROUTES, _chat_model(body), _emitter(tmp_path / "events.sqlite")
    )
    assert decision.budget.tool_calls == 30
    assert decision.budget.model_input_tokens == 50000
    assert decision.budget.max_agent_calls == 10


async def test_route_case_falls_back_on_low_confidence(tmp_path: Path) -> None:
    body = {
        "route_id": "debit_fraud_l3",
        "depth": "L3",
        "agents": [],
        "skills": [],
        "budget": {},
        "confidence": 0.4,
        "rationale": "unsure",
    }
    decision = await route_case(
        CASE, FEATURES, ROUTES, _chat_model(body), _emitter(tmp_path / "events.sqlite")
    )
    assert decision.route_id == "novel_or_ambiguous"
    assert decision.method == "fallback"
    assert decision.skills == ["eligibility-check"]


async def test_route_case_falls_back_on_unknown_route_id(tmp_path: Path) -> None:
    body = {"route_id": "not_a_real_route", "confidence": 0.99, "rationale": "x"}
    decision = await route_case(
        CASE, FEATURES, ROUTES, _chat_model(body), _emitter(tmp_path / "events.sqlite")
    )
    assert decision.route_id == "novel_or_ambiguous"
    assert decision.method == "fallback"
    assert decision.confidence == 0.0


async def test_route_case_falls_back_on_malformed_field_types(tmp_path: Path) -> None:
    """Case content is untrusted: valid JSON with the wrong shape (budget as a scalar,
    depth as a list) must fall back cleanly rather than crash with a TypeError from an
    `in`/membership check or from iterating a non-dict budget."""

    body = {
        "route_id": "debit_fraud_l3",
        "depth": ["L3"],
        "agents": [],
        "skills": [],
        "budget": 5000,
        "confidence": 0.95,
        "rationale": "x",
    }
    decision = await route_case(
        CASE, FEATURES, ROUTES, _chat_model(body), _emitter(tmp_path / "events.sqlite")
    )
    assert decision.route_id == "novel_or_ambiguous"
    assert decision.method == "fallback"
    assert decision.confidence == 0.0


async def test_route_case_falls_back_on_unparseable_output(tmp_path: Path) -> None:
    decision = await route_case(
        CASE,
        FEATURES,
        ROUTES,
        _chat_model("not json at all"),
        _emitter(tmp_path / "events.sqlite"),
    )
    assert decision.route_id == "novel_or_ambiguous"
    assert decision.method == "fallback"
    assert decision.confidence == 0.0
