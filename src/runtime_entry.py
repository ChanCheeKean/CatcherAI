"""Public entrypoint and filesystem paths for an investigation run."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent

from domain.events import Actor, ActorKind, EventDraft, RuntimeSnapshot
from graph_store import copy_store
from models import chat_model
from observability.emitter import EventEmitter
from schemas import CaseReport


@dataclass(frozen=True)
class RuntimePaths:
    source_graph: Path = Path("data/generated/evidence.lbug")
    knowledge_db: Path = Path("data/generated/knowledge.sqlite")
    run_dir: Path = Path("data/generated/runs")
    trajectory_db: Path = Path("trajectory.sqlite")
    checkpoint_db: Path = Path("checkpoints.sqlite")
    agents_config: Path = Path("config/agents.yaml")
    models_config: Path = Path("config/models.yaml")
    skills_dir: Path = Path("skills")


def run_case(
    case_id: str,
    *,
    paths: RuntimePaths | None = None,
    run_id: str | None = None,
    model: Any | None = None,
    agent_builder=create_deep_agent,
    agents_config=None,
) -> CaseReport:
    """Run a case to a final report, with an isolated graph and SQLite checkpoints."""

    from langgraph.checkpoint.sqlite import SqliteSaver

    from config import load_agents_config, load_models_config
    from runtime import _Runtime

    paths = paths or RuntimePaths()
    run_id = run_id or f"run-{uuid.uuid4().hex}"
    paths.run_dir.mkdir(parents=True, exist_ok=True)
    paths.trajectory_db.parent.mkdir(parents=True, exist_ok=True)
    paths.checkpoint_db.parent.mkdir(parents=True, exist_ok=True)
    store = copy_store(paths.source_graph, paths.run_dir / f"{run_id}.lbug")
    config = agents_config or load_agents_config(paths.agents_config)
    models = load_models_config(paths.models_config)
    emitter = EventEmitter(
        paths.trajectory_db,
        run_id=run_id,
        case_id=case_id,
        runtime=RuntimeSnapshot(
            config_hash=models.snapshot_hash,
            agent_runtime="langgraph",
            provider=models.provider,
            model=models.default.model,
            adapter_versions={"deepagents": "0.5.9"},
        ),
    )
    runtime = _Runtime(
        store=store,
        emitter=emitter,
        run_id=run_id,
        knowledge_db=paths.knowledge_db,
        skills_dir=paths.skills_dir.resolve(),
        config=config,
        model=model or chat_model(models, emitter=emitter),
        agent_builder=agent_builder,
    )
    emitter.emit(
        EventDraft(
            actor=Actor(kind=ActorKind.GRAPH_NODE, name="runtime"),
            type="run_started",
            summary=f"investigation started for {case_id}",
            payload={"case_id": case_id},
            refs=[case_id],
        )
    )
    checkpoint_connection = sqlite3.connect(paths.checkpoint_db, check_same_thread=False)
    try:
        graph = runtime.build(SqliteSaver(checkpoint_connection))
        result = graph.invoke(
            {"case": runtime.case_context(case_id), "findings": [], "turn": 0},
            config={"configurable": {"thread_id": run_id}},
        )
        return CaseReport.model_validate(result["report"])
    except Exception as error:
        emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.GRAPH_NODE, name="runtime"),
                type="error",
                summary=f"investigation failed: {type(error).__name__}",
                payload={"error": f"{type(error).__name__}: {error}"},
            )
        )
        emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.GRAPH_NODE, name="runtime"),
                type="termination",
                summary="investigation terminated with an error",
                payload={"reason": "error"},
            )
        )
        raise
    finally:
        checkpoint_connection.close()
        store.close()
        emitter.close_stream()
