from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request

from api.read_models import connect_readonly
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
