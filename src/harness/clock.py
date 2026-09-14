from __future__ import annotations

from datetime import datetime

from domain.events import Actor, ActorKind, EventDraft
from observability.emitter import EventEmitter


class VirtualClock:
    def __init__(self, now: datetime, emitter: EventEmitter) -> None:
        self.now = now
        self.emitter = emitter

    def advance_to(self, value: datetime, *, cause: str, refs: list[str] | None = None) -> None:
        if value < self.now:
            raise ValueError("virtual clock cannot move backward")
        before = self.now
        self.now = value
        self.emitter.set_virtual_now(value)
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.HARNESS, name="virtual_clock"),
                type="clock_advanced",
                summary=f"Advanced virtual clock for {cause}",
                payload={"before": before.isoformat(), "after": value.isoformat(), "cause": cause},
                refs=refs or [],
            )
        )
