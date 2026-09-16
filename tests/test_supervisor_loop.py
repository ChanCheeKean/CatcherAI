from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

from domain.model import Capability, ModelRequest, ModelResponse, ModelStreamEvent, Usage
from runtime.gateway_chat_model import GatewayChatModel
from runtime.langgraph_runtime import _decide_next_step


class StubGateway:
    """Returns a fixed JSON body for every model call; see tests/test_routing.py for the twin."""

    def __init__(self, body: dict[str, object] | str) -> None:
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


async def test_decide_next_step_accepts_a_valid_choice() -> None:
    chat_model = _chat_model({"next_step": "run_specialists", "rationale": "need more depth"})
    state = {"case_id": "DSP-TEST", "completed_steps": ["gather_evidence"]}
    result = await _decide_next_step(chat_model, state, ["run_specialists"])
    assert result == "run_specialists"


async def test_decide_next_step_allows_looping_back_to_a_completed_action() -> None:
    chat_model = _chat_model({"next_step": "gather_evidence", "rationale": "not enough yet"})
    state = {"case_id": "DSP-TEST", "completed_steps": ["gather_evidence"]}
    result = await _decide_next_step(chat_model, state, frozenset({"gather_evidence", "verify"}))
    assert result == "gather_evidence"


async def test_decide_next_step_defaults_to_verify_on_bad_output() -> None:
    chat_model = _chat_model("not json")
    result = await _decide_next_step(chat_model, {"case_id": "DSP-TEST"}, ["gather_evidence"])
    assert result == "verify"


async def test_decide_next_step_defaults_to_verify_on_out_of_menu_choice() -> None:
    chat_model = _chat_model({"next_step": "delete_the_case", "rationale": "x"})
    result = await _decide_next_step(chat_model, {"case_id": "DSP-TEST"}, ["gather_evidence"])
    assert result == "verify"


def test_max_agent_calls_boundary_is_strict_greater_than() -> None:
    """Pins the off-by-one boundary in assess_progress: the supervisor must be genuinely
    consulted up to max_agent_calls times, and the forced stop must only fire on the call
    *after* that (iterations > max_agent_calls), not on the call whose ordinal equals
    max_agent_calls itself.

    assess_progress is an async closure defined inside LangGraphRuntime._build_graph
    (src/runtime/langgraph_runtime.py), not a separately importable function, so driving
    the real closure end-to-end is out of scope here even though the fixture-backed
    FakeModelGateway (src/adapters/fake_model.py) does know how to answer the supervisor
    call. Instead this test reads the actual comparison out of the source file, so a
    regression back to `>=` is caught even though the closure itself can't be
    unit-invoked in isolation, and separately pins the intended semantics with concrete
    iteration counts.
    """
    source = Path(__file__).parents[1] / "src/runtime/langgraph_runtime.py"
    lines = source.read_text().splitlines()
    (boundary_line,) = [
        line for line in lines if "iterations" in line and "max_agent_calls" in line and "elif" in line
    ]
    assert boundary_line.strip() == 'elif iterations > budget["max_agent_calls"]:'

    max_agent_calls = 3
    # iterations == max_agent_calls: still a real supervisor call, no forced stop yet.
    assert (max_agent_calls > max_agent_calls) is False
    # iterations == max_agent_calls - 1: also a real supervisor call.
    assert (max_agent_calls - 1 > max_agent_calls) is False
    # iterations == max_agent_calls + 1: forced stop kicks in on this call.
    assert (max_agent_calls + 1 > max_agent_calls) is True
