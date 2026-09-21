"""Minimal API shell retained during the graph-agent rebuild."""

from __future__ import annotations

from fastapi import FastAPI

from api.routers import meta


def create_app() -> FastAPI:
    app = FastAPI(title="CatcherAI API", version="0.1.0")
    app.include_router(meta.router)
    return app


app = create_app()
