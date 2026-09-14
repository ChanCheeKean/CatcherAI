from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

from fastapi import Request

from api.read_models import connect_readonly
from api.run_manager import RunManager
from config import (
    ModelsConfig,
    RoutesConfig,
    ScenarioConfig,
    load_models_config,
    load_routes_config,
    load_scenario,
)


def get_root(request: Request) -> Path:
    return request.app.state.root  # type: ignore[no-any-return]


def get_db_path(request: Request) -> Path:
    return request.app.state.db_path  # type: ignore[no-any-return]


def get_connection(request: Request) -> Iterator[sqlite3.Connection]:
    connection = connect_readonly(request.app.state.db_path)
    try:
        yield connection
    finally:
        connection.close()


def get_run_manager(request: Request) -> RunManager:
    return request.app.state.run_manager  # type: ignore[no-any-return]


async def get_run_connection(run_id: str, request: Request) -> AsyncIterator[sqlite3.Connection]:
    """The store holding one specific run, resolved through the UI run registry (falling back to
    the app's single configured store for runs the registry doesn't know about, e.g. a Stage-1
    style run created directly against `--db`).

    Async, not a plain generator: every Stage 2 run-lifecycle endpoint is `async def` (they await
    `RunManager`), and FastAPI runs a sync generator dependency in a worker thread pool distinct
    from the event loop thread the async endpoint body runs on — `sqlite3` connections may only be
    used from the thread that created them, so this must open (and be used) on the same thread."""

    manager: RunManager = request.app.state.run_manager
    connection = connect_readonly(manager.resolve_store(run_id))
    try:
        yield connection
    finally:
        connection.close()


async def get_all_connections(request: Request) -> AsyncIterator[list[sqlite3.Connection]]:
    """Every store the API currently knows about, for endpoints (like `GET /runs`) that must
    merge across isolated UI-run workspaces rather than resolve a single run. Async for the same
    thread-affinity reason as `get_run_connection`."""

    manager: RunManager = request.app.state.run_manager
    connections = [connect_readonly(path) for path in manager.all_store_paths() if path.exists()]
    try:
        yield connections
    finally:
        for connection in connections:
            connection.close()


def get_models_config(request: Request) -> ModelsConfig:
    return request.app.state.models  # type: ignore[no-any-return]


def get_routes_config(request: Request) -> RoutesConfig:
    return request.app.state.routes  # type: ignore[no-any-return]


def get_scenario_config(request: Request) -> ScenarioConfig:
    return request.app.state.scenario  # type: ignore[no-any-return]


def load_config_state(root: Path) -> tuple[ModelsConfig, RoutesConfig, ScenarioConfig]:
    return (
        load_models_config(root / "config/models.yaml"),
        load_routes_config(root / "config/routes.yaml"),
        load_scenario(root / "config/scenarios/hero.yaml", root),
    )
