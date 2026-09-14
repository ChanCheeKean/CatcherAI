"""Simulated cardholder driven by private, harness-only persona fixtures."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from domain.events import Actor, ActorKind, EventDraft
from observability.emitter import EventEmitter

_WORD = re.compile(r"[a-z0-9]+")
_IGNORED = frozenset(
    "a an and are as at be by did do does for from has have if in is it of on or our "
    "the that this to was were with you your agent asks explains shares suggests".split()
)
MATCH_THRESHOLD = 0.5


class PersonaHarness:
    """Chooses scripted replies by question relevance, like a τ-bench user simulator.

    Personas live under `simulation/`, which only the harness may read. The investigator
    sees the question it sent and the reply it receives, never the script or its triggers.
    """

    def __init__(self, simulation_root: Path, emitter: EventEmitter) -> None:
        self.path = simulation_root / "cardholder_personas.json"
        self.emitter = emitter
        self._personas: dict[str, Any] | None = None

    def send(self, case_id: str, question: str, *, channel: str) -> dict[str, Any]:
        """Deliver a question and return when the simulated reply is expected, if ever."""

        match = self._best_reply(case_id, question)
        sent_at = self.emitter.virtual_now
        message = {
            "message_id": f"persona-message-{case_id}-{sent_at:%Y%m%dT%H%M}",
            "case_id": case_id,
            "question": question,
            "channel": channel,
            "sent_at": sent_at.isoformat(),
            "expected_at": (sent_at + timedelta(minutes=match["delay_minutes"])).isoformat()
            if match
            else None,
        }
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.HARNESS, name="persona"),
                type="persona_message",
                summary=f"Sent a clarification to the simulated cardholder by {channel}",
                payload={
                    **{key: value for key, value in message.items() if key != "question"},
                    "text_blob": self.emitter.put_blob(question, media_type="text/plain"),
                    "reply_scheduled": match is not None,
                    "redacted": True,
                },
                refs=[message["message_id"]],
            )
        )
        return message

    def reply(self, message: dict[str, Any]) -> dict[str, Any]:
        match = self._best_reply(message["case_id"], message["question"])
        if match is None:
            raise LookupError(f"no scheduled reply for {message['message_id']}")
        reply = {
            "reply_id": message["message_id"].replace("message", "reply"),
            "message_id": message["message_id"],
            "text": match["reply"],
            "available_at": self.emitter.virtual_now.isoformat(),
        }
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.HARNESS, name="persona"),
                type="persona_reply",
                summary="Simulated cardholder replied",
                payload={
                    "message_id": reply["message_id"],
                    "reply_id": reply["reply_id"],
                    "text_blob": self.emitter.put_blob(reply["text"], media_type="text/plain"),
                    "available_at": reply["available_at"],
                    "match_score": match["score"],
                    "redacted": True,
                },
                refs=[reply["reply_id"]],
            )
        )
        return reply

    def _best_reply(self, case_id: str, question: str) -> dict[str, Any] | None:
        persona = self._load().get(case_id)
        if not persona:
            return None
        asked = _terms(question)
        scored = []
        for scripted in persona["scripted_replies"]:
            wanted = _terms(scripted["trigger"])
            score = len(wanted & asked) / len(wanted) if wanted else 0.0
            scored.append({**scripted, "score": round(score, 3)})
        best = max(scored, key=lambda row: row["score"], default=None)
        return best if best and best["score"] >= MATCH_THRESHOLD else None

    def _load(self) -> dict[str, Any]:
        if self._personas is None:
            self._personas = json.loads(self.path.read_text(encoding="utf-8"))
        return self._personas


def _terms(text: str) -> set[str]:
    """Order-free word stems (five-character prefixes) without filler words."""

    return {
        word[:5]
        for word in _WORD.findall(text.casefold().replace("/", " "))
        if word not in _IGNORED
    }


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
