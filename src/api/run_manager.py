"""Isolated UI run workspaces, a durable run registry, and background runtime tasks.

Every UI-started run gets its own copy of the pristine scenario store under
`data/generated/ui/` (never `data/generated/disputes.sqlite` itself) and its own
`LangGraphRuntime`, because `LangGraphRuntime` and its `ScenarioConfig` are bound to one
SQLite path. The registry is a tiny SQLite table mapping `run_id -> store path` so run
history and store routing survive an API process reload; the live `LangGraphRuntime`
instances (needed to `cancel()` an active run, or to know whether its task is still
running for `api/sse.py`) exist only in this process's memory, same as the harness's
own `_tasks`/`_emitters` dicts they wrap.
"""

from __future__ import annotations

import asyncio
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from api.errors import ApiError
from api.models import Adapter, RunStatus
from bootstrap import build_runtime_from_config, copy_scenario_store
from config import ModelsConfig, RoutesConfig, ScenarioConfig
from domain.events import Actor, ActorKind, EventDraft
from runtime.langgraph_runtime import LangGraphRuntime
from runtime.portfolio import rank_portfolio
from storage import connect_readonly

_REGISTRY_SCHEMA = """CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    case_id TEXT,
    kind TEXT NOT NULL,
    store_path TEXT NOT NULL,
    adapter TEXT NOT NULL,
    auto_resume INTEGER NOT NULL,
    created_at TEXT NOT NULL
)"""


@dataclass(frozen=True)
class RunHandle:
    run_id: str
    case_id: str | None
    status: RunStatus
    store_path: Path


class RunManager:
    def __init__(
        self,
        *,
        root: Path,
        models: ModelsConfig,
        routes: RoutesConfig,
        scenario: ScenarioConfig,
        fallback_db_path: Path,
        ui_dir: Path | None = None,
    ) -> None:
        self.root = root
        self.models = models
        self.routes = routes
        self.scenario = scenario
        self.fallback_db_path = fallback_db_path
        self.ui_dir = ui_dir or root / "data/generated/ui"
        self.registry_path = self.ui_dir / "registry.sqlite"
        self._registry_ready = False
        self._runtimes: dict[str, LangGraphRuntime] = {}
        self._queue_tasks: dict[str, asyncio.Task[None]] = {}
        self._queue_rankings: dict[str, list[dict[str, object]]] = {}
        self._registry_cache: dict[str, sqlite3.Row] = {}
        self._write_lock = asyncio.Lock()

    def _forget_finished_runs(self) -> None:
        """Drop this process's in-memory `LangGraphRuntime`/task objects for runs that finished.

        Registry rows, the run's own persisted events and `_queue_rankings` are left alone: a
        finished run stays inspectable/rerunnable (via the durable registry), and
        `GET /queue/runs/{run_id}` keeps serving its ranking for the rest of this process's
        lifetime exactly as before (`queue_ranking` has no fallback to the persisted
        `portfolio_ranked` event, so evicting it here — rather than only on process restart, its
        documented limitation — would be a regression, not a cleanup). Only the heavier
        `LangGraphRuntime`/task objects (each holding a gateway, agent configs and a chat model
        wrapper) are swept, which is where the actual per-process memory growth was.
        """

        for run_id in [rid for rid, task in self._queue_tasks.items() if task.done()]:
            del self._queue_tasks[run_id]
        for run_id in [rid for rid, runtime in self._runtimes.items() if runtime.is_done(rid)]:
            del self._runtimes[run_id]

    # ------------------------------------------------------------------ case runs
    async def start_run(self, *, case_id: str, adapter: Adapter, auto_resume: bool) -> RunHandle:
        self._forget_finished_runs()
        store = copy_scenario_store(self.scenario, self.ui_dir, f"run-{uuid.uuid4().hex}")
        runtime = build_runtime_from_config(
            self.root,
            models=self.models,
            routes=self.routes,
            scenario=self.scenario,
            adapter=adapter,
            sqlite_path=store,
        )
        run_id = await runtime.start(case_id, auto_resume=auto_resume)
        self._runtimes[run_id] = runtime
        await self._register(
            run_id,
            case_id=case_id,
            kind="case",
            store=store,
            adapter=adapter,
            auto_resume=auto_resume,
        )
        return RunHandle(run_id=run_id, case_id=case_id, status="running", store_path=store)

    async def rerun(self, run_id: str) -> RunHandle:
        row = self._registry_row(run_id)
        if row is None or row["kind"] != "case":
            raise ApiError(
                "run_not_rerunnable",
                f"run {run_id} was not started by this API and cannot be rerun",
                status_code=400,
                details={"run_id": run_id},
            )
        return await self.start_run(
            case_id=row["case_id"], adapter=row["adapter"], auto_resume=bool(row["auto_resume"])
        )

    async def cancel(self, run_id: str) -> None:
        runtime = self._runtimes.get(run_id)
        if runtime is None:
            raise ApiError(
                "run_not_active",
                f"run {run_id} is not an active run in this API process",
                status_code=409,
                details={"run_id": run_id},
            )
        await runtime.cancel(run_id)

    def is_task_done(self, run_id: str) -> bool | None:
        """True/False for a run this process is driving; `None` if unmanaged here (a historical
        run, or one owned by a different API process) — the caller must fall back to the
        persisted terminal-status heuristic, which is safe precisely because nothing more will
        ever be written to an unmanaged store from this process.

        A case run's task lives inside `LangGraphRuntime` itself (`start`/`cancel`/`resume` own
        it); a queue run's task is driven directly by `_drive_queue` below, so it is tracked here
        instead."""

        if run_id in self._queue_tasks:
            return self._queue_tasks[run_id].done()
        runtime = self._runtimes.get(run_id)
        return None if runtime is None else runtime.is_done(run_id)

    # ----------------------------------------------------------------------- queue
    async def start_queue_run(self, *, adapter: Adapter) -> RunHandle:
        self._forget_finished_runs()
        store = copy_scenario_store(self.scenario, self.ui_dir, f"queue-{uuid.uuid4().hex}")
        runtime = build_runtime_from_config(
            self.root,
            models=self.models,
            routes=self.routes,
            scenario=self.scenario,
            adapter=adapter,
            sqlite_path=store,
        )
        run_id = f"queue-{uuid.uuid4().hex}"
        self._runtimes[run_id] = runtime
        await self._register(
            run_id, case_id=None, kind="queue", store=store, adapter=adapter, auto_resume=True
        )
        self._queue_tasks[run_id] = asyncio.create_task(self._drive_queue(runtime, run_id))
        return RunHandle(run_id=run_id, case_id=None, status="running", store_path=store)

    async def _drive_queue(self, runtime: LangGraphRuntime, run_id: str) -> None:
        try:
            _, ranking = await rank_portfolio(runtime, run_id=run_id)
            self._queue_rankings[run_id] = ranking
        except Exception as exc:  # noqa: BLE001 - recorded as a canonical event, then re-raised state ends
            emitter = runtime.emitter(run_id)
            emitter.emit(
                EventDraft(
                    actor=Actor(kind=ActorKind.HARNESS, name="runtime"),
                    type="error",
                    summary="Portfolio ranking failed",
                    payload={"category": type(exc).__name__, "sanitized_error": str(exc)},
                )
            )
            emitter.close_stream()

    def queue_ranking(self, run_id: str) -> list[dict[str, object]] | None:
        return self._queue_rankings.get(run_id)

    # -------------------------------------------------------------------- storage
    def resolve_store(self, run_id: str) -> Path:
        row = self._registry_row(run_id)
        return Path(row["store_path"]) if row is not None else self.fallback_db_path

    def all_store_paths(self) -> list[Path]:
        self._ensure_registry()
        with connect_readonly(self.registry_path) as connection:
            rows = connection.execute("SELECT DISTINCT store_path FROM runs").fetchall()
        paths = [Path(row[0]) for row in rows]
        if self.fallback_db_path not in paths:
            paths.append(self.fallback_db_path)
        return paths

    def _registry_row(self, run_id: str) -> sqlite3.Row | None:
        """Registry rows are immutable once written (`_register` only ever inserts), so a
        lazily-populated process-local cache needs no invalidation."""

        if run_id in self._registry_cache:
            return self._registry_cache[run_id]
        self._ensure_registry()
        with connect_readonly(self.registry_path) as connection:
            row = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is not None:
            self._registry_cache[run_id] = row
        return row

    async def _register(
        self,
        run_id: str,
        *,
        case_id: str | None,
        kind: str,
        store: Path,
        adapter: str,
        auto_resume: bool,
    ) -> None:
        self._ensure_registry()
        async with self._write_lock:
            with sqlite3.connect(self.registry_path) as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?)",
                    (
                        run_id,
                        case_id,
                        kind,
                        str(store),
                        adapter,
                        int(auto_resume),
                        datetime.now(UTC).isoformat(),
                    ),
                )

    def _ensure_registry(self) -> None:
        if self._registry_ready:
            return
        self.ui_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.registry_path) as connection:
            connection.execute(_REGISTRY_SCHEMA)
        self._registry_ready = True
