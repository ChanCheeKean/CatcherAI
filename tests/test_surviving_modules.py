from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from config import load_models_config
from domain.events import Actor, ActorKind, EventDraft, RuntimeSnapshot
from observability.emitter import EventEmitter


def _runtime() -> RuntimeSnapshot:
    return RuntimeSnapshot(
        config_hash="test",
        agent_runtime="test",
        provider="test",
        model="test-model",
    )


def test_models_config_loads_without_legacy_domain_model() -> None:
    config = load_models_config(Path("config/models.yaml"))

    assert config.default.model
    assert "structured_output" in config.default.required_capabilities


def test_event_log_is_append_only_without_hash_chain(tmp_path: Path) -> None:
    db_path = tmp_path / "trajectory.sqlite"
    emitter = EventEmitter(db_path, run_id="run-1", case_id="DSP-1", runtime=_runtime())
    emitter.emit(
        EventDraft(
            actor=Actor(kind=ActorKind.AGENT, name="triage"),
            type="node_entered",
            summary="entered",
        )
    )

    assert [event.seq for event in emitter.events()] == [1]
    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(run_events)")}
    assert "event_hash" not in columns
    assert "redactions_json" not in columns


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    assert client.get("/health").json() == {"status": "ok"}
