"""SOP-DSP-005 memory curation rules, shared by in-case maintenance and the offline job.

The rules only decide *what* to do; every change goes through `MemoryNoteStore`, so the offline
job and in-case curation use the same write gate and emit the same canonical events.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime, timedelta
from itertools import groupby
from pathlib import Path
from typing import Any

from data.access import CaseDataAccess
from domain.events import Actor, ActorKind, EventDraft, RuntimeSnapshot
from governance import CHARACTER_LABELS, PROHIBITED_BASES
from memory.notes import MIN_PATTERN_OBSERVATIONS, TTL_DAYS, MemoryNoteStore
from observability.emitter import EventEmitter

VERSIONED_REF = re.compile(r"^(?P<family>[A-Z0-9][A-Z0-9.\-]+)@(?P<version>[^\s]+)$")
PATTERN_REVALIDATE_DAYS = 90


def duplicate_groups(notes: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Active notes recording the same fact: same scope, subjects, tags and a shared source.

    Distinct episodic observations of one merchant are not duplicates; they are consolidation input.
    """

    def key(note: dict[str, Any]) -> tuple[str, str, str]:
        return note["scope"], ",".join(sorted(note["subject_ids"])), ",".join(sorted(note["tags"]))

    candidates = sorted(
        (
            note
            for note in notes
            if note["status"] == "active"
            and note["kind"] != "episodic"
            and note["subject_ids"]
            and note["tags"]
        ),
        key=key,
    )
    groups = []
    for _, rows in groupby(candidates, key=key):
        group = list(rows)
        shared = set.intersection(*(set(note["source_refs"]) for note in group))
        if len(group) > 1 and shared:
            groups.append(group)
    return groups


def expired(notes: list[dict[str, Any]], as_of: date) -> list[dict[str, Any]]:
    return [
        note
        for note in notes
        if note["scope"] in TTL_DAYS
        and date.fromisoformat(note["created_at"][:10]) + timedelta(days=TTL_DAYS[note["scope"]])
        <= as_of
    ]


def prohibited(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        note
        for note in notes
        if note["sensitivity"] not in {"normal", "purged"}
        or PROHIBITED_BASES.search(note["content"])
        or CHARACTER_LABELS.search(note["content"])
    ]


def stale_policy_citations(
    notes: list[dict[str, Any]], data: CaseDataAccess, as_of: date
) -> list[tuple[dict[str, Any], str]]:
    """Notes whose cited policy version is no longer the version in force as of `as_of`."""

    stale = []
    for note in notes:
        if note["scope"] not in {"policy", "procedure"}:
            continue
        for ref in note["source_refs"]:
            match = VERSIONED_REF.match(ref)
            if not match:
                continue
            current = data.current_policy_version(match.group("family"), as_of)
            if current and current != ref:
                stale.append((note, current))
                break
    return stale


def unconsolidated_patterns(notes: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Merchants with at least three raw observations, and whether a pattern note covers them."""

    raw = [note for note in notes if note["kind"] == "episodic" and note["scope"] == "merchant"]
    by_subject: dict[str, list[dict[str, Any]]] = {}
    for note in raw:
        for subject in note["subject_ids"]:
            by_subject.setdefault(subject, []).append(note)
    return [
        (subject, rows)
        for subject, rows in sorted(by_subject.items())
        if len(rows) >= MIN_PATTERN_OBSERVATIONS
    ]


def curate_offline(db_path: Path, *, as_of: date) -> dict[str, Any]:
    """Run the portfolio memory curator as its own replayable, fully evented run."""

    run_id = f"curation-{uuid.uuid4().hex}"
    emitter = EventEmitter(
        db_path,
        run_id=run_id,
        case_id=None,
        runtime=RuntimeSnapshot(
            config_hash="offline-curator",
            agent_runtime="memory-curator@2",
            model_gateway="none",
            provider="none",
            model="none",
        ),
        virtual_now=datetime.combine(as_of, datetime.min.time(), tzinfo=UTC),
    )
    _event(
        emitter,
        "run_started",
        "Started offline memory curation",
        {"as_of": as_of.isoformat(), "policy": "LFB-SOP-DSP-005@v1"},
    )
    store = MemoryNoteStore(db_path, emitter)
    data = CaseDataAccess(db_path, emitter)
    summary: dict[str, list[str]] = {
        "purged": [],
        "expired": [],
        "deduplicated": [],
        "superseded": [],
        "skipped": [],
    }
    active = store.scan(statuses=["active"])

    for note in prohibited(active):
        store.purge(note, reason="prohibited basis or character judgment")
        summary["purged"].append(note["note_id"])
    for note in expired(active, as_of):
        store.expire(note, as_of=as_of)
        summary["expired"].append(note["note_id"])
    handled = set(summary["purged"]) | set(summary["expired"])
    remaining = [note for note in active if note["note_id"] not in handled]

    for group in duplicate_groups(remaining):
        keep = store.dedupe(group)
        summary["deduplicated"].extend(note["note_id"] for note in group if note["note_id"] != keep)
    for note, current in stale_policy_citations(remaining, data, as_of):
        store.supersede(
            note,
            replaced_by=current,
            valid_to=as_of - timedelta(days=1),
            source_refs=[current],
            reason=f"cited policy version replaced by {current}",
        )
        summary["superseded"].append(note["note_id"])

    patterns = [note for note in remaining if "pattern" in note["tags"]]
    for subject, observations in unconsolidated_patterns(remaining):
        covering = [note for note in patterns if subject in note["subject_ids"]]
        if covering:
            reason = (
                f"{len(observations)} observations are already summarized by "
                f"{', '.join(note['note_id'] for note in covering)}; revalidate against current "
                f"evidence within {PATTERN_REVALIDATE_DAYS} days before consolidating"
            )
        else:
            reason = (
                "consolidation needs a case-verified validity window; queued for the next "
                "investigation that touches this merchant"
            )
        store.skip(
            candidate=f"merchant pattern for {subject}",
            reason=reason,
            refs=[subject, *[note["note_id"] for note in observations]],
        )
        summary["skipped"].append(subject)

    _event(emitter, "run_completed", "Completed offline memory curation", {"summary": summary})
    emitter.close_stream()
    return {"run_id": run_id, **summary}


def _event(emitter: EventEmitter, event_type: str, summary: str, payload: dict[str, Any]) -> None:
    emitter.emit(
        EventDraft(
            actor=Actor(kind=ActorKind.HARNESS, name="memory_curator_job"),
            type=event_type,
            summary=summary,
            payload=payload,
        )
    )
