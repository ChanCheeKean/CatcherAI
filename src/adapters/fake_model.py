from __future__ import annotations

import json
from collections.abc import AsyncIterator

from adapters import fake_routing
from domain.model import (
    Capability,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    NeutralToolCall,
    Usage,
)


def _last_user_message(request: ModelRequest) -> str:
    return next(
        (message.content for message in reversed(request.messages) if message.role == "user"),
        "{}",
    )


class FakeModelGateway:
    """Deterministic model for contracts and recorded scenario runs."""

    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.responses = responses or {}
        self.requests: list[ModelRequest] = []

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset(Capability)

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        self.requests.append(request)
        case_id = request.metadata.get("case_id", "default")
        text, tool_calls = self._response(request, case_id)
        midpoint = max(1, len(text) // 2)
        if text:
            yield ModelStreamEvent(type="text_delta", delta=text[:midpoint])
            yield ModelStreamEvent(type="text_delta", delta=text[midpoint:])
        for call in tool_calls:
            yield ModelStreamEvent(type="tool_call", payload=call.model_dump(mode="json"))
        response = ModelResponse(
            text=text,
            tool_calls=tool_calls,
            structured=json.loads(text) if request.output_schema else None,
            usage=Usage(input_tokens=120, output_tokens=48, cached_tokens=20),
            provider_request_id=f"fake-{request.call_id}",
            provider_metadata={"adapter": "fake"},
        )
        yield ModelStreamEvent(type="completed", response=response)

    def _response(self, request: ModelRequest, case_id: str) -> tuple[str, list[NeutralToolCall]]:
        if case_id in self.responses:
            return self.responses[case_id], []
        if request.actor == "case_router":
            payload = json.loads(_last_user_message(request))
            route_id, depth = fake_routing.classify(payload["case"])
            return (
                json.dumps(
                    {
                        "route_id": route_id,
                        "depth": depth,
                        "confidence": 1.0,
                        "agents": [],
                        "skills": [],
                        "budget": fake_routing.BUDGETS[route_id],
                        "rationale": "fake-deterministic route classification",
                    }
                ),
                [],
            )
        if request.actor == "assess_progress":
            payload = json.loads(_last_user_message(request))
            steps = payload.get("available_actions", [])
            next_step = steps[0] if steps else "verify"
            return json.dumps({"next_step": next_step, "rationale": "fake-deterministic"}), []
        if request.actor == "specialist_supervisor":
            if any(message.role == "tool" for message in request.messages):
                return json.dumps({"status": "complete", "specialists_synthesized": True}), []
            payload = json.loads(_last_user_message(request))
            calls = [
                NeutralToolCall(
                    id=f"{request.call_id}-task-{index}",
                    name="task",
                    arguments={
                        "subagent_type": delegation["subagent_type"],
                        "description": delegation["description"],
                    },
                )
                for index, delegation in enumerate(payload.get("delegations", []), start=1)
            ]
            return "", calls
        if request.actor != "lead_investigator":
            return (
                json.dumps(
                    {
                        "status": "complete",
                        "specialist": request.actor,
                        "assessment": (
                            "The supplied source-linked facts were independently checked."
                        ),
                    }
                ),
                [],
            )
        return (
            json.dumps(
                {
                    "steps": [
                        "Confirm the claimed transaction and account regime",
                        "Test the route-specific alternative explanation",
                        "Verify evidence and stop when the outcome cannot change",
                    ]
                }
            ),
            [],
        )
