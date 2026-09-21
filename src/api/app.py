"""FastAPI app factory: everything the two-page frontend needs, nothing more."""

from __future__ import annotations

from fastapi import FastAPI

from api.context import ApiContext
from api.errors import ApiError, api_error_handler
from api.routers import graph, meta, runs


def create_app(context: ApiContext | None = None) -> FastAPI:
    """Build the app; tests inject an `ApiContext` with tmp paths and a stub model."""

    app = FastAPI(title="DisputeAI API", version="0.1.0")
    app.state.context = context or ApiContext()
    app.add_exception_handler(ApiError, api_error_handler)
    for router in (meta.router, runs.router, graph.router):
        app.include_router(router)
    return app


app = create_app()
