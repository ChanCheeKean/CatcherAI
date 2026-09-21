"""Per-app configuration and the in-process registry of background runs."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

from deepagents import create_deep_agent
from fastapi import Depends, Request

from runtime import RuntimePaths, run_case


@dataclass
class Run:
    case_id: str
    thread: threading.Thread | None = None
    error: str | None = None


@dataclass
class ApiContext:
    paths: RuntimePaths = field(default_factory=RuntimePaths)
    catalog: Path = Path("data/generated/case_catalog.json")
    ground_truth_dir: Path = Path("data/generated/ground_truth/cases")
    eval_dir: Path = Path("data/generated/eval")
    model: Any | None = None
    agent_builder: Any = create_deep_agent
    runs: dict[str, Run] = field(default_factory=dict)

    def start_run(self, run_id: str, case_id: str) -> None:
        run = Run(case_id)

        def work() -> None:
            try:
                run_case(
                    case_id,
                    paths=self.paths,
                    run_id=run_id,
                    model=self.model,
                    agent_builder=self.agent_builder,
                )
            except Exception as error:  # the failure is reported through the run status
                run.error = f"{type(error).__name__}: {error}"

        run.thread = threading.Thread(target=work, name=run_id, daemon=True)
        self.runs[run_id] = run
        run.thread.start()

    def is_active(self, run_id: str) -> bool:
        run = self.runs.get(run_id)
        return bool(run and run.thread and run.thread.is_alive())


def context(request: Request) -> ApiContext:
    return request.app.state.context


Ctx = Annotated[ApiContext, Depends(context)]
