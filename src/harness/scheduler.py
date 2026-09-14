"""External-event scheduler: the only component that moves the virtual clock during a wait."""

from __future__ import annotations

from typing import Any

from domain.events import Actor, ActorKind, EventDraft
from harness.clock import VirtualClock
from harness.evidence import EvidenceSchedulerAccess
from harness.persona import PersonaHarness, parse_time
from observability.emitter import EventEmitter

WAIT_KINDS = frozenset({"merchant_evidence", "provider_record", "cardholder_reply"})


class ExternalEventScheduler:
    """Advances time only to a scheduled arrival or the latest safe decision time."""

    def __init__(
        self,
        emitter: EventEmitter,
        clock: VirtualClock,
        evidence: EvidenceSchedulerAccess,
        persona: PersonaHarness,
    ) -> None:
        self.emitter = emitter
        self.clock = clock
        self.evidence = evidence
        self.persona = persona

    def expected_evidence(self, case_id: str) -> dict[str, Any] | None:
        return self.evidence.next_evidence(case_id)

    def deliver(self, wait: dict[str, Any]) -> dict[str, Any]:
        """Resolve a suspended wait into the resume payload handed to the graph."""

        if wait["kind"] not in WAIT_KINDS:
            raise ValueError(f"suspension is not allowed for {wait['kind']}")
        latest_safe = parse_time(wait["latest_safe_decision_time"])
        expected = parse_time(wait["expected_at"]) if wait.get("expected_at") else None
        arrives = expected is not None and expected <= latest_safe
        before = self.clock.now
        self.clock.advance_to(
            max(before, expected if arrives else latest_safe),
            cause="scheduled_external_event" if arrives else "latest_safe_decision_time",
            refs=[wait["awaited_ref"]],
        )
        if not arrives:
            return {
                "status": "latest_safe_time_reached",
                "wait_id": wait["wait_id"],
                "awaited_ref": wait["awaited_ref"],
                "at": self.clock.now.isoformat(),
            }
        if wait["kind"] == "cardholder_reply":
            reply = self.persona.reply(wait["message"])
            return {"status": "arrived", "wait_id": wait["wait_id"], "reply": reply}
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.HARNESS, name="evidence_scheduler"),
                type="evidence_arrived",
                summary=f"{wait['awaited_ref']} became available",
                payload={
                    "evidence_id": wait["awaited_ref"],
                    "request_id": wait["wait_id"],
                    "available_at": wait["expected_at"],
                    "provider": wait.get("provider"),
                },
                refs=[wait["awaited_ref"]],
            )
        )
        return {"status": "arrived", "wait_id": wait["wait_id"], "packet_id": wait["awaited_ref"]}
