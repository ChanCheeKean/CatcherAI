"""FastAPI presentation adapter over the card-dispute agent's SQLite trajectory store.

Stage 2 adds a `RunManager`: isolated UI run workspaces, a durable run registry, start/cancel/
rerun/queue endpoints, and a reconnectable SSE stream. It still never writes to the pristine
`data/generated/catcher.sqlite` scenario store itself — only to per-run copies under
`data/generated/ui/`.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from api.constants import API_PREFIX
from api.dependencies import load_config_state
from api.errors import ApiError, api_error_handler
from api.routers import cases, graph, memory, meta, queue, runs, sources
from api.run_manager import RunManager


def create_app(root: Path, db_path: Path | None = None, ui_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Dispute Observatory API", version="0.1.0")
    app.state.root = root
    app.state.db_path = (db_path or root / "data/generated/catcher.sqlite").resolve()
    models, routes, scenario = load_config_state(root)
    app.state.models = models
    app.state.routes = routes
    app.state.scenario = scenario
    app.state.run_manager = RunManager(
        root=root,
        models=models,
        routes=routes,
        scenario=scenario,
        fallback_db_path=app.state.db_path,
        ui_dir=ui_dir,
    )

    app.add_exception_handler(ApiError, api_error_handler)

    app.include_router(meta.router, prefix=API_PREFIX)
    app.include_router(cases.router, prefix=API_PREFIX)
    app.include_router(runs.router, prefix=API_PREFIX)
    app.include_router(queue.router, prefix=API_PREFIX)
    app.include_router(memory.router, prefix=API_PREFIX)
    app.include_router(graph.router, prefix=API_PREFIX)
    app.include_router(sources.router, prefix=API_PREFIX)
    return app


def _default_root() -> Path:
    return Path(__file__).resolve().parents[2]


app = create_app(_default_root())
