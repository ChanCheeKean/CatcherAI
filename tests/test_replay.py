from __future__ import annotations

from replay import load_events, render_timeline, verify_hash_chain
from runtime.langgraph_runtime import LangGraphRuntime


async def test_replay_to_sequence_and_hash_chain(runtime: LangGraphRuntime) -> None:
    await runtime.run("DSP-2026-90002")
    assert runtime.last_run_id
    db_path = runtime.scenario.sqlite_path
    events = load_events(db_path, runtime.last_run_id)
    partial = load_events(db_path, runtime.last_run_id, to_seq=12)
    assert len(partial) == 12
    assert partial[-1].seq == 12
    assert verify_hash_chain(db_path, runtime.last_run_id)
    timeline = render_timeline(events)
    assert "[route_decision]" in timeline
    assert "[decision_recorded]" in timeline


async def test_runtime_start_stream_and_result_contract(runtime: LangGraphRuntime) -> None:
    run_id = await runtime.start("DSP-2026-90002")
    streamed = [event async for event in runtime.events(run_id)]
    decision = await runtime.result(run_id)
    assert decision.cardholder_resolution.outcome == "withdrawn_after_clarification"
    assert streamed
    assert [event.seq for event in streamed] == list(range(1, len(streamed) + 1))
    assert streamed[-1].type == "checkpoint_saved"
