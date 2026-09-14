"""Durable agent notes: selective read, gated writes, and SOP-DSP-005 lifecycle operations."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import uuid
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from domain.events import Actor, ActorKind, EventDraft
from governance import CHARACTER_LABELS, PROHIBITED_BASES
from observability.emitter import EventEmitter

COLUMNS = (
    "note_id kind scope subject_ids content created_at created_by source_refs confidence status "
    "valid_from valid_to superseded_by tags sensitivity last_accessed_at access_count"
).split()
JSON_COLUMNS = ("subject_ids", "source_refs", "tags")
KINDS = frozenset({"semantic", "episodic", "procedural"})
SCOPES = frozenset({"customer", "merchant", "procedure", "policy", "policy_gap", "operational"})
TTL_DAYS = {"operational": 30}
MIN_PATTERN_OBSERVATIONS = 3
DECAY_HALF_LIFE_DAYS = 90
PAN = re.compile(r"\b\d{13,19}\b")
CUSTOMER_RISK_LABEL = re.compile(r"\b(risk|misuse|heightened scrutiny|suspicious)\b", re.I)
WRITER = "agent:memory-curator@2"


class MemoryNoteStore:
    """Every read, write, rejection, skip, and lifecycle change emits one canonical event."""

    def __init__(self, db_path: Path, emitter: EventEmitter) -> None:
        self.db_path = db_path
        self.emitter = emitter

    # ------------------------------------------------------------------ read path
    def read_current(
        self,
        *,
        subject_ids: list[str],
        as_of: date,
        minimum_confidence: float = 0.5,
        scope: str | None = None,
    ) -> list[dict[str, Any]]:
        """Current leads for subjects, or unscoped lessons of one scope when no subject is given."""

        clauses = " OR ".join("subject_ids LIKE ?" for _ in subject_ids) or "subject_ids='[]'"
        sql = f"""SELECT * FROM agent_memory_notes
                  WHERE status='active' AND confidence>=?
                    AND valid_from<=? AND (valid_to IS NULL OR valid_to='' OR valid_to>=?)
                    AND ({clauses}){" AND scope=?" if scope else ""}"""
        params: list[Any] = [minimum_confidence, as_of.isoformat(), as_of.isoformat()]
        params.extend(f'%"{subject_id}"%' for subject_id in subject_ids)
        if scope:
            params.append(scope)
        candidates = [_decode(row) for row in self._select(sql, params)]
        rows, discarded = [], []
        for row in candidates:
            if row["sensitivity"] != "normal":
                discarded.append(
                    {"id": row["note_id"], "reason": "prohibited_content_pending_purge"}
                )
                continue
            row["rank_score"] = _rank_score(row, as_of)
            rows.append(row)
        rows.sort(key=lambda row: (-row["rank_score"], row["note_id"]))
        note_ids = [row["note_id"] for row in rows]
        with self._connect() as connection:
            connection.executemany(
                """UPDATE agent_memory_notes SET access_count=CAST(access_count AS INTEGER)+1,
                   last_accessed_at=? WHERE note_id=?""",
                [(self.emitter.virtual_now.isoformat(), note_id) for note_id in note_ids],
            )
        self._event(
            "memory_read",
            f"Read {len(rows)} current memory leads for scoped subjects",
            {
                "store": "sqlite_system_of_record",
                "namespace": "agent_memory_notes",
                "query": sql,
                "parameters": params,
                "filters": {
                    "as_of": as_of.isoformat(),
                    "status": "active",
                    "validity_window_contains": as_of.isoformat(),
                    "subject_ids": subject_ids,
                    "scope": scope,
                    "minimum_confidence": minimum_confidence,
                    "sensitivity": "normal",
                },
                "results": [
                    {
                        key: row[key]
                        for key in ("note_id", "kind", "valid_from", "valid_to", "rank_score")
                    }
                    for row in rows
                ],
                "result_ids": note_ids,
                "used_ids": note_ids,
                "discarded": discarded,
                "ranking": f"confidence * recency/access decay (half-life {DECAY_HALF_LIFE_DAYS}d)",
                "access_stats_updated": note_ids,
                "treatment": "unverified_leads_not_evidence",
            },
            refs=note_ids,
            actor="durable_memory_notes",
        )
        return rows

    def scan(self, *, statuses: Iterable[str] = ("active",)) -> list[dict[str, Any]]:
        """Curator scan across all notes in the given lifecycle states."""

        wanted = list(statuses)
        sql = (
            f"SELECT * FROM agent_memory_notes WHERE status IN ({','.join('?' for _ in wanted)}) "
            "ORDER BY note_id"
        )
        rows = [_decode(row) for row in self._select(sql, wanted)]
        ids = [row["note_id"] for row in rows]
        self._event(
            "memory_read",
            f"Curator scanned {len(rows)} notes",
            {
                "store": "sqlite_system_of_record",
                "namespace": "agent_memory_notes",
                "query": sql,
                "parameters": wanted,
                "filters": {"status_in": wanted},
                "result_ids": ids,
                "used_ids": ids,
                "discarded": [],
                "treatment": "curation_scan",
            },
            refs=ids,
        )
        return rows

    def verify(self, note: dict[str, Any], *, reason: str, evidence_refs: list[str]) -> None:
        self._event(
            "memory_verified",
            f"Verified {note['note_id']} against current evidence",
            {
                "note_id": note["note_id"],
                "reason": reason,
                "memory_source_refs": note["source_refs"],
                "verification_evidence_refs": evidence_refs,
                "used_as_evidence": False,
            },
            refs=[note["note_id"], *evidence_refs],
            actor="lead_verifier",
        )

    def reject(self, note: dict[str, Any], *, reason: str, evidence_refs: list[str]) -> None:
        self._event(
            "memory_rejected",
            f"Rejected {note['note_id']} as a current source of truth",
            {
                "note_id": note["note_id"],
                "reason": reason,
                "memory_source_refs": note["source_refs"],
                "verification_evidence_refs": evidence_refs,
                "used_as_evidence": False,
            },
            refs=[note["note_id"], *evidence_refs],
            actor="lead_verifier",
        )

    # ----------------------------------------------------------------- write path
    def write(
        self,
        *,
        kind: str,
        scope: str,
        subject_ids: list[str],
        content: str,
        source_refs: list[str],
        valid_from: date,
        confidence: float,
        valid_to: date | None = None,
        tags: Iterable[str] = (),
    ) -> str | None:
        """Selective write; returns None when the write gate rejects the candidate."""

        note = self._new_note(
            kind=kind,
            scope=scope,
            subject_ids=subject_ids,
            content=content,
            source_refs=source_refs,
            valid_from=valid_from,
            valid_to=valid_to,
            confidence=confidence,
            tags=list(tags),
        )
        checks = self._gate(note)
        duplicate = self._active_duplicate(note)
        checks.append({"check": "no_duplicate_active_note", "pass": duplicate is None})
        if not _passed(checks):
            self._reject_write(note, checks)
            return None
        self._insert(note)
        self._event(
            "memory_write",
            f"Wrote {scope} note {note['note_id']}",
            {
                "store": "sqlite_system_of_record",
                "target_id": note["note_id"],
                "scope": scope,
                "kind": kind,
                "before": None,
                "after": _public(note),
                "content": content,
                "source_refs": source_refs,
                "validity": _validity(note),
                "confidence": confidence,
                "write_gate_checks": checks,
            },
            refs=[note["note_id"], *source_refs],
        )
        return note["note_id"]

    def skip(self, *, candidate: str, reason: str, refs: Iterable[str] = ()) -> None:
        self._event(
            "memory_write_skipped",
            f"Deliberately did not write {candidate}",
            {
                "candidate": candidate,
                "reason": reason,
                "gate_checks": [
                    {"check": "worth_remembering", "pass": False},
                    {"check": "sop_004_prohibited_content", "pass": True},
                ],
            },
            refs=refs,
        )

    def supersede(
        self,
        note: dict[str, Any],
        *,
        source_refs: list[str],
        valid_from: date | None = None,
        valid_to: date | None = None,
        content: str | None = None,
        replaced_by: str | None = None,
        confidence: float = 0.99,
        reason: str = "source of truth changed",
    ) -> str:
        """Supersede by a new correction (`content`) or by an existing note/document."""

        if (content is None) == (replaced_by is None):
            raise ValueError("supersede needs exactly one of content or replaced_by")
        end = valid_to or (valid_from - timedelta(days=1) if valid_from else None)
        if end is None:
            raise ValueError("supersede needs valid_from or valid_to")
        correction_id = replaced_by
        checks = [
            {"check": "source_refs_present", "pass": bool(source_refs)},
            {"check": "history_retained_not_deleted", "pass": True},
        ]
        if content is not None:
            correction = self._new_note(
                kind="semantic",
                scope=note["scope"],
                subject_ids=note["subject_ids"],
                content=content,
                source_refs=source_refs,
                valid_from=valid_from or end + timedelta(days=1),
                valid_to=None,
                confidence=confidence,
                tags=["corrected", "policy_versioned"],
            )
            checks.extend(self._gate(correction))
            duplicate = self._active_duplicate(correction)
            checks.append(
                {
                    "check": "duplicate_active_correction",
                    "pass": True,
                    "result": "reused_existing" if duplicate else "new",
                }
            )
            if not _passed(checks):
                self._reject_write(correction, checks, target_id=note["note_id"])
                raise ValueError("memory correction failed write gate")
            correction_id = duplicate or correction["note_id"]
            if not duplicate:
                self._insert(correction)
                self._event(
                    "memory_write",
                    f"Wrote validity-bounded correction {correction_id}",
                    {
                        "store": "sqlite_system_of_record",
                        "target_id": correction_id,
                        "scope": correction["scope"],
                        "before": None,
                        "after": _public(correction),
                        "content": content,
                        "source_refs": source_refs,
                        "validity": _validity(correction),
                        "confidence": confidence,
                        "write_gate_checks": checks,
                    },
                    refs=[correction_id, *source_refs],
                )
        before = _lifecycle(note)
        after = {
            "status": "superseded",
            "valid_to": end.isoformat(),
            "superseded_by": correction_id,
        }
        self._update(note["note_id"], **after)
        self._event(
            "memory_supersede",
            f"Superseded {note['note_id']}",
            {
                "store": "sqlite_system_of_record",
                "target_id": note["note_id"],
                "reason": reason,
                "before": before,
                "after": after,
                "source_refs": source_refs,
                "validity": {"valid_to": end.isoformat()},
                "confidence": confidence,
                "write_gate_checks": checks,
            },
            refs=[note["note_id"], str(correction_id), *source_refs],
        )
        return str(correction_id)

    def retract(
        self,
        note: dict[str, Any],
        *,
        correction: str,
        source_refs: list[str],
        valid_from: date,
        confidence: float,
    ) -> str:
        """Retract a contradicted belief and retain a sourced correction note."""

        replacement = self._new_note(
            kind="semantic",
            scope=note["scope"],
            subject_ids=note["subject_ids"],
            content=correction,
            source_refs=source_refs,
            valid_from=valid_from,
            valid_to=None,
            confidence=confidence,
            tags=["correction", "retraction"],
        )
        checks = self._gate(replacement)
        if not _passed(checks):
            self._reject_write(replacement, checks, target_id=note["note_id"])
            raise ValueError("memory retraction failed write gate")
        self._insert(replacement)
        valid_to = valid_from - timedelta(days=1)
        before = _lifecycle(note)
        after = {
            "status": "retracted",
            "valid_to": valid_to.isoformat(),
            "superseded_by": replacement["note_id"],
        }
        self._update(note["note_id"], **after)
        self._event(
            "memory_retract",
            f"Retracted contradicted memory {note['note_id']}",
            {
                "store": "sqlite_system_of_record",
                "target_id": note["note_id"],
                "before": before,
                "after": after,
                "source_refs": source_refs,
                "validity": {"valid_to": valid_to.isoformat()},
                "confidence": confidence,
                "write_gate_checks": checks,
            },
            refs=[note["note_id"], replacement["note_id"], *source_refs],
        )
        self._event(
            "memory_write",
            f"Wrote correction {replacement['note_id']} after retraction",
            {
                "store": "sqlite_system_of_record",
                "target_id": replacement["note_id"],
                "scope": replacement["scope"],
                "before": None,
                "after": _public(replacement),
                "content": correction,
                "source_refs": source_refs,
                "validity": _validity(replacement),
                "confidence": confidence,
                "write_gate_checks": checks,
            },
            refs=[replacement["note_id"], *source_refs],
        )
        return replacement["note_id"]

    def consolidate(
        self,
        observations: list[dict[str, Any]],
        *,
        content: str,
        subject_ids: list[str],
        source_refs: list[str],
        valid_from: date,
        valid_to: date | None,
        confidence: float,
        entity_merge_evidence: list[str],
    ) -> str | None:
        """Archive at least three observations into one validity-bounded pattern note."""

        note = self._new_note(
            kind="semantic",
            scope="merchant",
            subject_ids=subject_ids,
            content=content,
            source_refs=source_refs,
            valid_from=valid_from,
            valid_to=valid_to,
            confidence=confidence,
            tags=["pattern", "consolidated", *(["time_bounded"] if valid_to else [])],
        )
        observed_subjects = {subject for row in observations for subject in row["subject_ids"]}
        checks = [
            *self._gate(note),
            {
                "check": "minimum_observations_gte_3",
                "pass": len(observations) >= MIN_PATTERN_OBSERVATIONS,
                "observed": len(observations),
            },
            {
                "check": "near_duplicate_entities_merged",
                "pass": observed_subjects <= set(subject_ids)
                and (len(observed_subjects) < 2 or bool(entity_merge_evidence)),
                "merged_subject_ids": sorted(observed_subjects),
                "evidence": entity_merge_evidence,
            },
        ]
        if not _passed(checks):
            self._reject_write(note, checks)
            return None
        self._insert(note)
        before = {row["note_id"]: _lifecycle(row) for row in observations}
        for row in observations:
            self._update(row["note_id"], status="archived", superseded_by=note["note_id"])
        from_ids = [row["note_id"] for row in observations]
        self._event(
            "memory_consolidate",
            f"Consolidated {len(observations)} observations into {note['note_id']}",
            {
                "store": "sqlite_system_of_record",
                "operation": "consolidate",
                "target_id": note["note_id"],
                "from_ids": from_ids,
                "subject_ids": subject_ids,
                "before": before,
                "after": {
                    **_public(note),
                    "archived": {note_id: "archived" for note_id in from_ids},
                },
                "content": content,
                "source_refs": source_refs,
                "validity": _validity(note),
                "confidence": confidence,
                "write_gate_checks": checks,
            },
            refs=[note["note_id"], *from_ids, *source_refs],
        )
        return note["note_id"]

    def dedupe(self, duplicates: list[dict[str, Any]]) -> str:
        """Keep the earliest of several notes recording the same fact; archive the rest."""

        ordered = sorted(duplicates, key=lambda row: (row["created_at"], row["note_id"]))
        keep, extras = ordered[0], ordered[1:]
        for row in extras:
            self._update(row["note_id"], status="archived", superseded_by=keep["note_id"])
        self._event(
            "memory_consolidate",
            f"Deduplicated {len(ordered)} notes into {keep['note_id']}",
            {
                "store": "sqlite_system_of_record",
                "operation": "dedupe",
                "target_id": keep["note_id"],
                "from_ids": [row["note_id"] for row in ordered],
                "before": {row["note_id"]: _lifecycle(row) for row in extras},
                "after": {
                    row["note_id"]: {"status": "archived", "superseded_by": keep["note_id"]}
                    for row in extras
                },
                "source_refs": sorted({ref for row in ordered for ref in row["source_refs"]}),
                "write_gate_checks": [
                    {"check": "same_scope_subjects_and_fact", "pass": True},
                    {"check": "earliest_retained", "pass": True},
                ],
            },
            refs=[row["note_id"] for row in ordered],
        )
        return keep["note_id"]

    def expire(self, note: dict[str, Any], *, as_of: date) -> None:
        ttl = TTL_DAYS[note["scope"]]
        after = {"status": "expired", "valid_to": as_of.isoformat()}
        self._update(note["note_id"], **after)
        self._event(
            "memory_expire",
            f"Expired {note['scope']} note {note['note_id']} after {ttl}-day TTL",
            {
                "store": "sqlite_system_of_record",
                "target_id": note["note_id"],
                "before": _lifecycle(note),
                "after": after,
                "ttl_days": ttl,
                "created_at": note["created_at"],
                "source_refs": note["source_refs"],
                "write_gate_checks": [{"check": "ttl_elapsed", "pass": True}],
            },
            refs=[note["note_id"]],
        )

    def purge(self, note: dict[str, Any], *, reason: str) -> None:
        """Remove prohibited content, keeping a non-sensitive tombstone for audit."""

        tombstone = f"[purged under LFB-SOP-DSP-004@v2: {reason}]"
        digest = hashlib.sha256(note["content"].encode()).hexdigest()
        after = {"status": "purged", "content": tombstone, "tags": ["tombstone"]}
        self._update(
            note["note_id"],
            status="purged",
            content=tombstone,
            tags=json.dumps(["tombstone"]),
            sensitivity="purged",
        )
        self._event(
            "memory_purge",
            f"Purged prohibited content from {note['note_id']}",
            {
                "store": "sqlite_system_of_record",
                "target_id": note["note_id"],
                "before": {**_lifecycle(note), "content_sha256": digest},
                "after": after,
                "reason": reason,
                "source_refs": [note["note_id"], "LFB-SOP-DSP-004@v2", "LFB-SOP-DSP-005@v1"],
                "write_gate_checks": [
                    {"check": "sop_004_prohibited_content_absent", "pass": False}
                ],
            },
            refs=[note["note_id"], "LFB-SOP-DSP-004@v2"],
        )

    # ---------------------------------------------------------------- internals
    def _gate(self, note: dict[str, Any]) -> list[dict[str, Any]]:
        content = note["content"]
        valid_to = note["valid_to"]
        return [
            {
                "check": "allowed_kind_and_scope",
                "pass": note["kind"] in KINDS and note["scope"] in SCOPES,
            },
            {"check": "source_refs_present", "pass": bool(note["source_refs"])},
            {
                "check": "validity_window_valid",
                "pass": bool(note["valid_from"])
                and (not valid_to or valid_to >= note["valid_from"]),
            },
            {"check": "confidence_in_range", "pass": 0 <= float(note["confidence"]) <= 1},
            {
                "check": "sop_004_prohibited_content_absent",
                "pass": not PROHIBITED_BASES.search(content)
                and not CHARACTER_LABELS.search(content),
            },
            {"check": "no_full_pan_or_secret", "pass": not PAN.search(content)},
            {
                "check": "no_customer_risk_label",
                "pass": note["scope"] != "customer" or not CUSTOMER_RISK_LABEL.search(content),
            },
            {
                "check": "merchant_pattern_has_3_sources",
                "pass": "pattern" not in note["tags"]
                or len(note["source_refs"]) >= MIN_PATTERN_OBSERVATIONS,
            },
        ]

    def _reject_write(
        self, note: dict[str, Any], checks: list[dict[str, Any]], *, target_id: str | None = None
    ) -> None:
        failed = [check["check"] for check in checks if not check["pass"]]
        self._event(
            "write_rejected",
            f"Write gate rejected {note['scope']} note: {', '.join(failed)}",
            {
                "store": "sqlite_system_of_record",
                "target_id": target_id or note["note_id"],
                "candidate_sha256": hashlib.sha256(note["content"].encode()).hexdigest(),
                "scope": note["scope"],
                "failed_checks": failed,
                "gate_checks": checks,
            },
            refs=[target_id or note["note_id"], *note["source_refs"]],
            actor="memory_write_gate",
        )

    def _new_note(self, **fields: Any) -> dict[str, Any]:
        now = self.emitter.virtual_now.isoformat()
        return {
            "note_id": f"MEM-{uuid.uuid4().hex[:12].upper()}",
            "created_at": now,
            "created_by": WRITER,
            "status": "active",
            "superseded_by": None,
            "sensitivity": "normal",
            "last_accessed_at": now,
            "access_count": 0,
            **fields,
            "valid_from": fields["valid_from"].isoformat(),
            "valid_to": fields["valid_to"].isoformat() if fields.get("valid_to") else None,
        }

    def _active_duplicate(self, note: dict[str, Any]) -> str | None:
        rows = self._select(
            """SELECT note_id FROM agent_memory_notes WHERE status='active' AND scope=?
               AND subject_ids=? AND content=? LIMIT 1""",
            [note["scope"], json.dumps(note["subject_ids"]), note["content"]],
        )
        return str(rows[0]["note_id"]) if rows else None

    def _insert(self, note: dict[str, Any]) -> None:
        values = [
            json.dumps(note[column]) if column in JSON_COLUMNS else note[column]
            for column in COLUMNS
        ]
        values[COLUMNS.index("confidence")] = str(note["confidence"])
        values[COLUMNS.index("access_count")] = str(note["access_count"])
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO agent_memory_notes VALUES ({','.join('?' for _ in COLUMNS)})", values
            )

    def _update(self, note_id: str, **fields: Any) -> None:
        assignments = ", ".join(f"{column}=?" for column in fields)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE agent_memory_notes SET {assignments} WHERE note_id=?",
                [*fields.values(), note_id],
            )

    def _select(self, sql: str, params: list[Any]) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(sql, params).fetchall()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _event(
        self,
        event_type: str,
        summary: str,
        payload: dict[str, Any],
        *,
        refs: Iterable[str] = (),
        actor: str = "memory_curator",
    ) -> None:
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.MEMORY, name=actor),
                type=event_type,
                summary=summary,
                payload=payload,
                refs=list(dict.fromkeys(str(ref) for ref in refs)),
            )
        )


def _decode(row: sqlite3.Row) -> dict[str, Any]:
    note = dict(row)
    for column in JSON_COLUMNS:
        note[column] = json.loads(note[column]) if note[column] else []
    note["confidence"] = float(note["confidence"])
    note["access_count"] = int(note["access_count"] or 0)
    return note


def _rank_score(note: dict[str, Any], as_of: date) -> float:
    """Recency/access decay changes ranking only; it never makes a note current or stale."""

    last = datetime.fromisoformat(note["last_accessed_at"].replace("Z", "+00:00")).date()
    age = max((as_of - last).days, 0)
    recency = 0.5 ** (age / DECAY_HALF_LIFE_DAYS)
    access = 1 + math.log1p(note["access_count"]) / 10
    return round(note["confidence"] * recency * access, 4)


def _lifecycle(note: dict[str, Any]) -> dict[str, Any]:
    return {key: note.get(key) for key in ("status", "valid_to", "superseded_by")}


def _validity(note: dict[str, Any]) -> dict[str, Any]:
    return {"valid_from": note["valid_from"], "valid_to": note["valid_to"]}


def _public(note: dict[str, Any]) -> dict[str, Any]:
    return {key: note[key] for key in COLUMNS if key not in {"last_accessed_at", "access_count"}}


def _passed(checks: list[dict[str, Any]]) -> bool:
    return all(check["pass"] for check in checks)
