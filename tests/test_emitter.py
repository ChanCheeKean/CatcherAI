from __future__ import annotations

from pathlib import Path

from domain.events import Actor, ActorKind, EventDraft, RuntimeSnapshot
from observability.emitter import EventEmitter


def test_event_log_is_append_only(tmp_path: Path) -> None:
    emitter = EventEmitter(
        tmp_path / "trajectory.sqlite",
        run_id="run-1",
        case_id="DSP-1",
        runtime=RuntimeSnapshot(
            config_hash="test",
            agent_runtime="test",
            provider="test",
            model="test-model",
        ),
    )
    for summary in ("entered", "exited"):
        emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.AGENT, name="triage"),
                type="node_entered",
                summary=summary,
            )
        )

    assert [event.seq for event in emitter.events()] == [1, 2]
    assert [event.summary for event in emitter.events()] == ["entered", "exited"]
