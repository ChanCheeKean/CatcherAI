from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Literal

from adapters.fake_model import FakeModelGateway
from adapters.openai_responses import OpenAIResponsesGateway
from config import (
    ModelsConfig,
    RoutesConfig,
    ScenarioConfig,
    load_models_config,
    load_routes_config,
    load_scenario,
)
from runtime.langgraph_runtime import LangGraphRuntime


def build_runtime(
    root: Path,
    *,
    adapter: Literal["fake", "openai"] = "fake",
    sqlite_path: Path | None = None,
) -> LangGraphRuntime:
    models = load_models_config(root / "config/models.yaml")
    routes = load_routes_config(root / "config/routes.yaml")
    scenario = load_scenario(root / "config/scenarios/hero.yaml", root)
    return build_runtime_from_config(
        root,
        models=models,
        routes=routes,
        scenario=scenario,
        adapter=adapter,
        sqlite_path=sqlite_path,
    )


def build_runtime_from_config(
    root: Path,
    *,
    models: ModelsConfig,
    routes: RoutesConfig,
    scenario: ScenarioConfig,
    adapter: Literal["fake", "openai"] = "fake",
    sqlite_path: Path | None = None,
) -> LangGraphRuntime:
    """Build a runtime from configs the caller already loaded (avoids re-parsing every YAML
    file on every UI-started run — `RunManager` loads all three once and reuses them)."""

    if sqlite_path is not None:
        scenario = scenario.model_copy(update={"sqlite_path": sqlite_path.resolve()})
    if adapter == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for the OpenAI adapter")
        gateway = OpenAIResponsesGateway(models)
    else:
        gateway = FakeModelGateway()
    return LangGraphRuntime(
        root=root,
        models=models,
        routes=routes,
        scenario=scenario,
        gateway=gateway,
    )


def isolated_workspace(root: Path, directory: Path, name: str) -> Path:
    """Copy the pristine scenario store so a run's memory and case writes stay isolated."""

    scenario = load_scenario(root / "config/scenarios/hero.yaml", root)
    return copy_scenario_store(scenario, directory, name)


def copy_scenario_store(scenario: ScenarioConfig, directory: Path, name: str) -> Path:
    """Copy an already-loaded scenario's pristine store so a run's writes stay isolated."""

    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{name}.sqlite"
    shutil.copy2(scenario.sqlite_path, target)
    graph = scenario.sqlite_path.with_name(f"{scenario.sqlite_path.stem}_graph.lbug")
    if graph.exists():
        shutil.copy2(graph, directory / f"{name}_graph.lbug")
    return target
