from __future__ import annotations

import os
from pathlib import Path

import pytest

from adapters.openai_responses import OpenAIResponsesGateway
from config import load_models_config
from domain.model import ModelRequest, NeutralMessage


@pytest.mark.skipif(
    os.environ.get("DISPUTE_AGENT_RUN_OPENAI_SMOKE") != "1",
    reason="set DISPUTE_AGENT_RUN_OPENAI_SMOKE=1 for the opt-in real API contract test",
)
@pytest.mark.asyncio
async def test_openai_responses_adapter_contract(project_root: Path) -> None:
    config = load_models_config(project_root / "config/models.yaml")
    gateway = OpenAIResponsesGateway(config)
    request = ModelRequest(
        call_id="openai-contract-smoke",
        actor="contract_test",
        rationale="Verify Responses structured streaming contract",
        messages=[NeutralMessage(role="user", content='Return {"ok": true}.')],
        output_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
        reasoning_effort="low",
        max_output_tokens=128,
        metadata={"case_id": "SMOKE"},
    )
    events = [event async for event in gateway.stream(request)]
    response = events[-1].response
    assert response is not None
    assert response.structured == {"ok": True}
    assert response.provider_request_id
    assert response.usage.input_tokens > 0
