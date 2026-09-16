from __future__ import annotations

from runtime.langgraph_runtime import LangGraphRuntime


async def test_route_node_produces_an_llm_or_fallback_decision(make_runtime) -> None:  # noqa: ANN001
    runtime: LangGraphRuntime = make_runtime()
    decision = await runtime.run("DSP-2026-90001")
    events = runtime.emitter(runtime.last_run_id).events()
    route_event = next(event for event in events if event.type == "route_decision")
    assert route_event.payload["method"] in {"llm", "fallback"}
    assert decision is not None
