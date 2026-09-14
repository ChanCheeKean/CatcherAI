from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from domain.case import DecisionRecord
from domain.events import EventEnvelope
from domain.model import Capability, ModelRequest, ModelStreamEvent


class ModelGateway(Protocol):
    @property
    def capabilities(self) -> frozenset[Capability]: ...

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]: ...


class AgentRuntime(Protocol):
    """Start, observe, resume and cancel investigations without exposing the agent framework.

    `result` raises a runtime-specific suspension error when a run was started with
    `auto_resume=False` and is waiting for an external event; `resume` continues it from the
    durable checkpoint, possibly in another process. Only the harness delivers external events.
    """

    async def start(
        self, case_id: str, scenario_id: str = "hero", *, auto_resume: bool = True
    ) -> str: ...

    async def run(self, case_id: str, scenario_id: str = "hero") -> DecisionRecord: ...

    async def result(self, run_id: str) -> DecisionRecord: ...

    async def events(self, run_id: str) -> AsyncIterator[EventEnvelope]: ...

    async def resume(
        self, run_id: str, external_event: dict[str, object] | None = None
    ) -> DecisionRecord: ...

    async def cancel(self, run_id: str) -> None: ...
