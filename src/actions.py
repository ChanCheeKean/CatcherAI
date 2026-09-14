from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from domain.case import DecisionRecord
from domain.events import Actor, ActorKind, EventDraft
from observability.emitter import EventEmitter

ALLOWED_ACTIONS = frozenset(
    {
        "close_inquiry",
        "close_case_no_dispute",
        "file_dispute",
        "write_off_no_chargeback",
        "finalize_cardholder_credit",
        "reverse_provisional_credit",
        "send_explanation",
        "fraud_report_tc40",
        "card_reissue",
        "revert_phone_change_and_secure_online_banking",
        "lock_digital_banking_pending_step_up",
        "revert_unverified_phone_change",
        "reopen_case",
        "credit_reopened_case",
        "watchlist_add",
        "enhanced_monitoring",
        "claims_control_evidence_first",
        "enqueue_automated_rereview",
        "graph_write",
        "accept_dispute_response",
        "request_record",
        "policy_gap_record",
        "record_authority_revocation_notice",
        "schedule_follow_up",
        "issuer_absorbs_loss",
        "reverse_foreign_transaction_fee",
    }
)
NETWORK_EXECUTED = frozenset({"file_dispute", "write_off_no_chargeback", "accept_dispute_response"})


class ActionRepository:
    """Execute bounded case actions through one audited write boundary."""

    def __init__(self, db_path: Path, emitter: EventEmitter) -> None:
        self.db_path = db_path
        self.emitter = emitter
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS case_actions (
                    action_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL,
                    action TEXT NOT NULL, status TEXT NOT NULL, details_json TEXT NOT NULL
                )"""
            )

    def execute(self, decision: DecisionRecord) -> list[str]:
        actions: list[tuple[str, dict[str, Any]]] = []
        if decision.cardholder_resolution.outcome == "withdrawn_after_clarification":
            actions.append(("close_inquiry", {"outcome": "withdrawn_after_clarification"}))
        elif not decision.is_dispute:
            actions.append(
                (
                    "close_case_no_dispute",
                    {"outcome": decision.cardholder_resolution.outcome},
                )
            )
        for network_action in decision.network_actions:
            if network_action.action in NETWORK_EXECUTED:
                actions.append(
                    (
                        network_action.action,
                        network_action.model_dump(mode="json"),
                    )
                )
        if decision.cardholder_resolution.credit_amount:
            actions.append(
                (
                    "finalize_cardholder_credit",
                    {"amount": str(decision.cardholder_resolution.credit_amount)},
                )
            )
        if decision.cardholder_resolution.reversal_amount:
            actions.append(
                (
                    "reverse_provisional_credit",
                    {"amount": str(decision.cardholder_resolution.reversal_amount)},
                )
            )
        actions.extend(
            (action, {"source": "account_actions"}) for action in decision.account_actions
        )
        for automated in decision.automated_actions:
            action = str(automated["action"])
            actions.append((action, automated))
        actions.append(
            (
                "send_explanation",
                {"text": decision.explanation_for_cardholder, "channel": "secure_message"},
            )
        )

        action_ids: list[str] = []
        for action, details in actions:
            allowed = action in ALLOWED_ACTIONS
            self.emitter.emit(
                EventDraft(
                    actor=Actor(kind=ActorKind.GRAPH_NODE, name="action_guard"),
                    type="guardrail_check",
                    summary=f"Action allow-list check for {action}: "
                    f"{'pass' if allowed else 'fail'}",
                    payload={
                        "check": "bounded_action_allow_list",
                        "action": action,
                        "allowed_actions": sorted(ALLOWED_ACTIONS),
                        "pass": allowed,
                    },
                    refs=[decision.case_id],
                )
            )
            if not allowed:
                raise ValueError(f"forbidden automated action: {action}")
            action_id = f"action-{uuid.uuid4().hex}"
            with sqlite3.connect(self.db_path) as connection:
                connection.row_factory = sqlite3.Row
                before: dict[str, Any] | None = None
                target_case_id = details.get("case_id")
                if target_case_id:
                    row = connection.execute(
                        """SELECT case_id, status, stage, cardholder_outcome
                           FROM disputes WHERE case_id=?""",
                        (target_case_id,),
                    ).fetchone()
                    before = dict(row) if row else None
                if action in {"reopen_case", "credit_reopened_case"} and target_case_id:
                    if before is None:
                        raise ValueError(f"unknown case action target: {target_case_id}")
                    if action == "reopen_case":
                        connection.execute(
                            """UPDATE disputes SET status='open', stage='reopened_automated'
                               WHERE case_id=?""",
                            (target_case_id,),
                        )
                    else:
                        connection.execute(
                            """UPDATE disputes SET status='open', stage='reopened_automated',
                               cardholder_outcome='credited' WHERE case_id=?""",
                            (target_case_id,),
                        )
                connection.execute(
                    "INSERT INTO case_actions VALUES (?,?,?,?,?,?)",
                    (
                        action_id,
                        self.emitter.run_id,
                        decision.case_id,
                        action,
                        "executed",
                        json.dumps(details),
                    ),
                )
                if target_case_id:
                    row = connection.execute(
                        """SELECT case_id, status, stage, cardholder_outcome
                           FROM disputes WHERE case_id=?""",
                        (target_case_id,),
                    ).fetchone()
                    after = dict(row) if row else details
                else:
                    after = {
                        "action_id": action_id,
                        "status": "executed",
                        "details": details,
                    }
            self.emitter.emit(
                EventDraft(
                    actor=Actor(kind=ActorKind.TOOL, name="case_action_writer"),
                    type="automated_action",
                    summary=f"Executed bounded action {action}",
                    payload={
                        "action_id": action_id,
                        "action": action,
                        "status": "executed",
                        "details": details,
                        "allowed_action_check": "pass",
                        "store": "sqlite_system_of_record",
                        "target_id": target_case_id or action_id,
                        "before": before,
                        "after": after,
                        "source_refs": [decision.case_id],
                        "write_gate_checks": [{"check": "bounded_action_allow_list", "pass": True}],
                    },
                    refs=[decision.case_id, action_id],
                )
            )
            action_ids.append(action_id)
        return action_ids
