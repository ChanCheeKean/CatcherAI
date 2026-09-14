from __future__ import annotations

import shutil
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from domain.events import RuntimeSnapshot
from memory.retrieval import HybridKnowledgeStore
from observability.emitter import EventEmitter
from sandbox import reg_e_deadlines, unused_portion, write_off_eligibility


def _emitter(db_path: Path) -> EventEmitter:
    return EventEmitter(
        db_path,
        run_id="run-unit",
        case_id="DSP-UNIT",
        runtime=RuntimeSnapshot(
            config_hash="sha256:unit",
            agent_runtime="unit",
            model_gateway="fake",
            provider="fake",
            model="fake",
        ),
        virtual_now=datetime(2026, 10, 21, 13, tzinfo=UTC),
    )


def test_hybrid_retrieval_respects_historical_validity_intervals(
    project_root: Path, tmp_path: Path
) -> None:
    db_path = tmp_path / "knowledge.sqlite"
    shutil.copy2(project_root / "data/generated/catcher.sqlite", db_path)
    store = HybridKnowledgeStore(db_path, _emitter(db_path))

    old = store.search(
        "goodwill write-off threshold",
        as_of=date(2026, 6, 30),
        kinds=("policy",),
        limit=12,
    )
    current = store.search(
        "goodwill write-off threshold",
        as_of=date(2026, 10, 20),
        kinds=("policy",),
        limit=12,
    )

    assert "LFB-SOP-DSP-002@v3" in {row["doc_id"] for row in old}
    assert "LFB-SOP-DSP-002@v4" not in {row["doc_id"] for row in old}
    assert "LFB-SOP-DSP-002@v4" in {row["doc_id"] for row in current}
    assert "LFB-SOP-DSP-002@v3" not in {row["doc_id"] for row in current}


def test_write_off_and_unused_portion_helpers_emit_replayable_computations(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "sandbox.sqlite"
    emitter = _emitter(db_path)

    eligible = write_off_eligibility(
        txn_id="TXN-LOW",
        amount=Decimal("12.49"),
        threshold=Decimal("15.00"),
        prior_dispute_count=0,
        delinquency_days=0,
        merchant_cluster_open=False,
        emitter=emitter,
    )
    unused = unused_portion(
        amount=Decimal("119.88"),
        service_start=date(2026, 9, 29),
        service_end=date(2027, 9, 28),
        used_through=date(2026, 10, 3),
        emitter=emitter,
    )

    assert eligible.eligible is True
    assert unused.days_in_period == 365
    assert unused.days_used == 5
    assert unused.days_unused == 360
    assert unused.unused_portion == Decimal("118.24")
    computations = [event for event in emitter.events() if event.type == "computation"]
    assert [event.payload["helper"] for event in computations] == [
        "write_off_eligibility",
        "unused_portion",
    ]


def test_reg_e_new_account_business_day_deadlines_are_calendar_grounded(
    tmp_path: Path,
) -> None:
    emitter = _emitter(tmp_path / "reg-e.sqlite")
    result = reg_e_deadlines(
        notice_date=date(2026, 10, 13),
        first_deposit_date=date(2026, 9, 28),
        transaction_dates=[date(2026, 10, 9)],
        holidays=[date(2026, 11, 11), date(2026, 11, 26)],
        card_lost_or_stolen=False,
        emitter=emitter,
    )

    assert result.new_account is True
    assert result.provisional_credit_business_days == 20
    assert result.provisional_credit_deadline == date(2026, 11, 10)
    assert result.written_confirmation_due_if_bank_requires == date(2026, 10, 27)
    assert result.investigation_deadline == date(2027, 1, 11)
    assert result.liability_amount == Decimal("0")
    event = emitter.events()[-1]
    assert event.type == "computation"
    assert event.payload["helper"] == "reg_e_deadlines"
