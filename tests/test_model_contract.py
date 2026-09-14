from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from adapters.fake_model import FakeModelGateway
from adapters.openai_responses import strict_function_schema
from domain.events import RuntimeSnapshot
from domain.model import (
    Capability,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    NeutralMessage,
)
from observability.emitter import EventEmitter
from observability.model_gateway import InstrumentedModelGateway


def test_openai_strict_tool_schema_closes_nested_objects_and_keeps_optional_fields() -> None:
    schema = {
        "type": "object",
        "properties": {
            "required_value": {"type": "string"},
            "optional_value": {"type": "integer", "default": 1},
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            },
        },
        "required": ["required_value", "rows"],
    }
    normalized = strict_function_schema(schema)
    assert normalized["additionalProperties"] is False
    assert normalized["required"] == ["required_value", "optional_value", "rows"]
    optional = normalized["properties"]["optional_value"]
    assert {item["type"] for item in optional["anyOf"]} == {"integer", "null"}
    assert normalized["properties"]["rows"]["items"]["additionalProperties"] is False


@pytest.mark.asyncio
async def test_fake_gateway_stream_and_structured_output_contract() -> None:
    gateway = FakeModelGateway({"CASE": json.dumps({"steps": ["one"]})})
    request = ModelRequest(
        call_id="contract-call",
        actor="contract_test",
        rationale="Exercise normalized structured streaming",
        messages=[NeutralMessage(role="user", content="plan")],
        output_schema={
            "type": "object",
            "properties": {"steps": {"type": "array", "items": {"type": "string"}}},
            "required": ["steps"],
            "additionalProperties": False,
        },
        metadata={"case_id": "CASE"},
    )
    events = [event async for event in gateway.stream(request)]
    assert [event.type for event in events] == ["text_delta", "text_delta", "completed"]
    response = events[-1].response
    assert response is not None
    assert response.structured == {"steps": ["one"]}
    assert response.usage.input_tokens > 0
    assert Capability.STRUCTURED_OUTPUT in gateway.capabilities
    assert gateway.requests == [request]


@pytest.mark.asyncio
async def test_instrumented_gateway_retries_pre_stream_timeout(tmp_path: Path) -> None:
    class FlakyGateway:
        calls = 0

        @property
        def capabilities(self) -> frozenset[Capability]:
            return frozenset(Capability)

        async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("temporary timeout")
            yield ModelStreamEvent(
                type="completed",
                response=ModelResponse(text="ok", provider_request_id="request-2"),
            )

    emitter = EventEmitter(
        tmp_path / "events.sqlite",
        run_id="retry-run",
        case_id="CASE",
        runtime=RuntimeSnapshot(
            config_hash="sha256:test",
            agent_runtime="test",
            model_gateway="test",
            provider="fake",
            model="fake",
        ),
        virtual_now=datetime.now(UTC),
    )
    inner = FlakyGateway()
    gateway = InstrumentedModelGateway(
        inner,
        emitter,
        provider="fake",
        model="fake",
        max_attempts=2,
        initial_backoff_ms=0,
    )
    request = ModelRequest(
        call_id="retry-call",
        actor="test",
        rationale="test retry",
        messages=[NeutralMessage(role="user", content="go")],
    )
    events = [event async for event in gateway.stream(request)]
    assert events[-1].response and events[-1].response.text == "ok"
    assert inner.calls == 2
    trajectory = emitter.events()
    assert [event.type for event in trajectory].count("llm_call_started") == 2
    assert [event.type for event in trajectory].count("llm_call_failed") == 1
    assert [event.type for event in trajectory].count("retry") == 1
    assert [event.type for event in trajectory].count("llm_call") == 1
