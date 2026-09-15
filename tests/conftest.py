from __future__ import annotations

import shutil
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from adapters.fake_model import FakeModelGateway
from config import load_models_config, load_routes_config, load_scenario
from runtime.langgraph_runtime import LangGraphRuntime


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).parents[1]


@pytest.fixture
def scenario_db(project_root: Path, tmp_path: Path) -> Path:
    source_db = project_root / "data/generated/disputes.sqlite"
    assert source_db.exists(), "run: uv run python data/generator/load_sqlite.py"
    db_path = tmp_path / "disputes.sqlite"
    shutil.copy2(source_db, db_path)
    return db_path


@pytest.fixture
def make_runtime(project_root: Path, scenario_db: Path):  # type: ignore[no-untyped-def]
    """Build independent runtime instances over one store, as separate processes would."""

    def build() -> LangGraphRuntime:
        scenario = load_scenario(project_root / "config/scenarios/hero.yaml", project_root)
        return LangGraphRuntime(
            root=project_root,
            models=load_models_config(project_root / "config/models.yaml"),
            routes=load_routes_config(project_root / "config/routes.yaml"),
            scenario=scenario.model_copy(update={"sqlite_path": scenario_db}),
            gateway=FakeModelGateway(),
        )

    return build


@pytest.fixture
async def runtime(make_runtime) -> AsyncIterator[LangGraphRuntime]:  # type: ignore[no-untyped-def]
    yield make_runtime()
