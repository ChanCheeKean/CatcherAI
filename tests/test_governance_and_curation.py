from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

import governance
from domain.case import Adjudication, CardholderResolution, DecisionRecord, NetworkAction
from domain.events import RuntimeSnapshot
from harness.clock import VirtualClock
from harness.scheduler import ExternalEventScheduler
from memory.curator import curate_offline
from memory.notes import MemoryNoteStore
from observability.emitter import EventEmitter


def _record(
    outcome: str = "denied_with_explanation", credit: str = "0", actions=()
) -> DecisionRecord:  # type: ignore[no-untyped-def]
    return DecisionRecord(
        case_id="DSP-TEST",
        regime="REG_Z",
        is_dispute=True,
        claim_family="fraud_cnp",
        network_actions=[
            NetworkAction(
                txn_id="TXN-1",
                case_id="DSP-TEST",
                action="file_dispute",
                condition="10.4",
                amount=Decimal("600.00"),
            )
        ],
        cardholder_resolution=CardholderResolution(
            outcome=outcome,
            credit_amount=Decimal(credit),
            reversal_amount=Decimal("0"),
            liability_amount=Decimal("0"),
        ),
        adjudication=Adjudication(review_panel_used=False, confidence=0.9, flip_fact="x"),
        automated_actions=list(actions),
        confidence=0.9,
        explanation_for_cardholder="We reviewed the evidence.",
    )


def _board(for_weight: float, against_weight: float) -> list[dict]:  # type: ignore[type-arg]
    return [
        {
            "id": "H1",
            "label": "authorized",
            "favors": "issuer",
            "outcome": "deny",
            "flip_fact": "f1",
            "evidence_for": [{"fact": "a", "refs": ["S1"], "weight": for_weight}],
            "evidence_against": [{"fact": "b", "refs": ["S2"], "weight": against_weight}],
        },
        {
            "id": "H2",
            "label": "unauthorized",
            "favors": "cardholder",
            "outcome": "credit",
            "flip_fact": "f2",
            "evidence_for": [{"fact": "b", "refs": ["S2"], "weight": against_weight}],
            "evidence_against": [{"fact": "a", "refs": ["S1"], "weight": for_weight}],
        },
    ]


def test_panel_triggers_are_deterministic_and_cannot_be_skipped() -> None:
    case = {"claim_family_initial": "fraud_cnp", "dispute_amount": "600.00"}
    assert governance.panel_triggers(case, _record(), {}) == ["unauthorized_use_denial_500_or_more"]
    assert governance.panel_triggers({**case, "dispute_amount": "100"}, _record(), {}) == []
    assert governance.panel_triggers(case, _record("credited", "600"), {}) == []
    reopen = _record("credited", "600", [{"action": "reopen_case", "case_id": "DSP-OLD"}])
    assert "reopen_or_amend_closed_case" in governance.panel_triggers(case, reopen, {})
    facts = {
        "authority_determination": True,
        "novel_transaction_type": True,
        "cross_customer_finding": True,
    }
    assert governance.panel_triggers(
        {"claim_family_initial": "not_received"}, _record("credited", "1"), facts
    ) == [
        "authority_household_determination",
        "no_applicable_rule_or_novel_type",
        "cross_customer_abuse_finding",
    ]


def test_adjudication_threshold_and_conservative_default() -> None:
    confident = governance.adjudicate(_board(9, 1))
    assert confident["hypothesis"] == "H1" and confident["confidence"] == 0.9
    uncertain = governance.adjudicate(_board(3, 2))
    assert uncertain["confidence"] == 0.6 < governance.THRESHOLD
    positions = [
        governance.advocate_position(_board(3, 2), side) for side in ("cardholder", "issuer")
    ]
    assert [position["hypothesis"] for position in positions] == ["H2", "H1"]

    defaulted = governance.apply_conservative_default(
        _record(), disputed_amount=Decimal("600.00"), reason="panel_confidence_threshold"
    )
    assert defaulted.cardholder_resolution.credit_amount == Decimal("600.00")
    assert defaulted.cardholder_resolution.liability_amount == 0
    assert [action.action for action in defaulted.network_actions] == ["no_dispute"]
    assert defaulted.adjudication.conservative_default_applied is True
    assert defaulted.automated_actions[-1]["action"] == "issuer_absorbs_loss"


def test_fairness_scan_blocks_prohibited_bases_and_labels() -> None:
    record = _record().model_copy(
        update={"explanation_for_cardholder": "Given the customer's age, a fraudster."}
    )
    assert governance.fairness_violations(record) == ["age", "fraudster"]
    assert governance.fairness_violations(_record()) == []


@pytest.fixture
def store(project_root: Path, tmp_path: Path) -> MemoryNoteStore:
    db_path = tmp_path / "memory.sqlite"
    shutil.copy2(project_root / "data/generated/catcher.sqlite", db_path)
    emitter = EventEmitter(
        db_path,
        run_id="run-memory",
        case_id=None,
        runtime=RuntimeSnapshot(
            config_hash="t", agent_runtime="t", model_gateway="t", provider="t", model="t"
        ),
        virtual_now=datetime(2026, 10, 21, 13, tzinfo=UTC),
    )
    return MemoryNoteStore(db_path, emitter)


def _status(store: MemoryNoteStore, note_id: str) -> str:
    with sqlite3.connect(store.db_path) as connection:
        return connection.execute(
            "SELECT status FROM agent_memory_notes WHERE note_id=?", (note_id,)
        ).fetchone()[0]


def test_write_gate_rejects_unsourced_prohibited_and_label_writes(store: MemoryNoteStore) -> None:
    base = dict(
        kind="semantic", subject_ids=["CUS-90010"], valid_from=date(2026, 10, 21), confidence=0.8
    )
    assert (
        store.write(
            scope="customer",
            content="Customer sounds elderly and confused.",
            source_refs=["DSP-2026-90011"],
            **base,
        )
        is None
    )
    assert (
        store.write(
            scope="customer",
            content="Heightened scrutiny for this customer's claims.",
            source_refs=["DSP-2026-90011"],
            **base,
        )
        is None
    )
    assert store.write(scope="merchant", content="Ships slowly.", source_refs=[], **base) is None
    written = store.write(
        scope="merchant",
        content="Refund portal open until 2026-12-31.",
        source_refs=["WEB-04100"],
        **base,
    )
    assert (
        written
        and store.write(
            scope="merchant",
            content="Refund portal open until 2026-12-31.",
            source_refs=["WEB-04100"],
            **base,
        )
        is None
    )
    events = store.emitter.events()
    rejected = [event for event in events if event.type == "write_rejected"]
    assert [event.payload["failed_checks"] for event in rejected] == [
        ["sop_004_prohibited_content_absent"],
        ["no_customer_risk_label"],
        ["source_refs_present"],
        ["no_duplicate_active_note"],
    ]
    assert all("content" not in event.payload for event in rejected)


def test_consolidation_requires_three_observations_and_hides_archived_notes(
    store: MemoryNoteStore,
) -> None:
    raw = store.read_current(subject_ids=["MER-90023", "MER-90024"], as_of=date(2026, 10, 21))
    observations = [note for note in raw if note["kind"] == "episodic"]
    assert (
        store.consolidate(
            observations[:2],
            content="pattern",
            subject_ids=["MER-90023", "MER-90024"],
            source_refs=["a", "b", "c"],
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 8, 12),
            confidence=0.9,
            entity_merge_evidence=["m"],
        )
        is None
    )
    note_id = store.consolidate(
        observations,
        content="Stuck parcels Jan-Aug 2026.",
        subject_ids=["MER-90023", "MER-90024"],
        source_refs=[note["note_id"] for note in observations],
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 8, 12),
        confidence=0.9,
        entity_merge_evidence=["same acquirer and MCC"],
    )
    assert note_id and all(_status(store, note["note_id"]) == "archived" for note in observations)
    current = store.read_current(subject_ids=["MER-90023", "MER-90024"], as_of=date(2026, 10, 21))
    assert not {note["note_id"] for note in observations} & {note["note_id"] for note in current}
    historical = store.read_current(subject_ids=["MER-90024"], as_of=date(2026, 6, 1))
    assert note_id in {note["note_id"] for note in historical}


def test_offline_curator_expires_purges_dedupes_and_supersedes(
    project_root: Path, tmp_path: Path
) -> None:
    db_path = tmp_path / "curate.sqlite"
    shutil.copy2(project_root / "data/generated/catcher.sqlite", db_path)
    summary = curate_offline(db_path, as_of=date(2026, 10, 21))
    assert summary["purged"] == ["MEM-0196"]
    assert summary["expired"] == ["MEM-0185"]
    assert summary["deduplicated"] == ["MEM-0181"]
    assert set(summary["superseded"]) == {"MEM-0150", "MEM-0151"}
    with sqlite3.connect(db_path) as connection:
        purged = connection.execute(
            "SELECT content, status FROM agent_memory_notes WHERE note_id='MEM-0196'"
        ).fetchone()
        types = [
            row[0]
            for row in connection.execute(
                "SELECT type FROM run_events WHERE run_id=? ORDER BY seq", (summary["run_id"],)
            )
        ]
    assert purged[1] == "purged" and "elderly" not in purged[0]
    assert {
        "memory_purge",
        "memory_expire",
        "memory_consolidate",
        "memory_supersede",
        "memory_write_skipped",
    } <= set(types)


def test_scheduler_only_advances_to_arrival_or_latest_safe_time(tmp_path: Path) -> None:
    db_path = tmp_path / "events.sqlite"
    emitter = EventEmitter(
        db_path,
        run_id="run-scheduler",
        case_id=None,
        runtime=RuntimeSnapshot(
            config_hash="t", agent_runtime="t", model_gateway="t", provider="t", model="t"
        ),
        virtual_now=datetime(2026, 10, 21, 13, tzinfo=UTC),
    )
    clock = VirtualClock(emitter.virtual_now, emitter)
    scheduler = ExternalEventScheduler(emitter, clock, evidence=None, persona=None)  # type: ignore[arg-type]
    wait = {
        "wait_id": "w1",
        "kind": "merchant_evidence",
        "awaited_ref": "MEP-1",
        "expected_at": "2027-03-01T00:00:00Z",
        "latest_safe_decision_time": "2026-12-30T00:00:00+00:00",
    }
    assert scheduler.deliver(wait)["status"] == "latest_safe_time_reached"
    assert clock.now == datetime(2026, 12, 30, tzinfo=UTC)
    with pytest.raises(ValueError):
        scheduler.deliver({**wait, "kind": "human_approval"})
