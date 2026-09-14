"""FastAPI presentation adapter over the card-dispute agent's SQLite trajectory store.

Read-only in Stage 1: no execution manager, no SSE stream, no writes to any scenario store.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from api.dependencies import load_config_state
from api.errors import ApiError, api_error_handler
from api.routers import cases, meta, runs

API_PREFIX = "/api/v1"


def create_app(root: Path, db_path: Path | None = None) -> FastAPI:
    app = FastAPI(title="Dispute Observatory API", version="0.1.0")
    app.state.root = root
    app.state.db_path = (db_path or root / "data/generated/catcher.sqlite").resolve()
    models, routes, scenario = load_config_state(root)
    app.state.models = models
    app.state.routes = routes
    app.state.scenario = scenario

    app.add_exception_handler(ApiError, api_error_handler)

    app.include_router(meta.router, prefix=API_PREFIX)
    app.include_router(cases.router, prefix=API_PREFIX)
    app.include_router(runs.router, prefix=API_PREFIX)
    return app


def _default_root() -> Path:
    return Path(__file__).resolve().parents[2]


app = create_app(_default_root())
