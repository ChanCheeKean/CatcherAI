from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from domain.model import Capability, ModelRequest, ModelStreamEvent


class ModelGateway(Protocol):
    @property
    def capabilities(self) -> frozenset[Capability]: ...

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]: ...
