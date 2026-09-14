from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from domain.events import Actor, ActorKind, EventDraft
from observability.emitter import EventEmitter


class AccessDenied(PermissionError):
    pass


class PathGuard:
    def __init__(
        self, root: Path, denied_parts: tuple[str, ...] = ("ground_truth", "simulation")
    ) -> None:
        self.root = root.resolve()
        self.denied_parts = frozenset(denied_parts)

    def resolve(self, relative: str) -> Path:
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or self.denied_parts.intersection(pure.parts):
            raise AccessDenied(f"agent data path denied: {relative}")
        resolved = (self.root / Path(*pure.parts)).resolve()
        if self.root not in resolved.parents and resolved != self.root:
            raise AccessDenied(f"agent data path escapes root: {relative}")
        if self.denied_parts.intersection(resolved.parts):
            raise AccessDenied(f"agent data path denied: {relative}")
        return resolved


class CaseDataAccess:
    """Read-only operational queries with virtual-time gating and mandatory events."""

    def __init__(self, db_path: Path, emitter: EventEmitter) -> None:
        self.db_path = db_path
        self.emitter = emitter
        self._connection: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        """One connection reused for this access object's lifetime.

        Safe because `CaseDataAccess` is constructed once per run/segment and only ever driven
        from that run's own asyncio task on the process's single event-loop thread (see
        `LangGraphRuntime._drive`); it is never shared across runs or accessed from another
        thread. Each `sqlite3` call here is synchronous with no `await` in between, so
        interleaving with other coroutines on the same loop cannot corrupt a query in flight.
        """

        if self._connection is None:
            self._connection = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def _query(
        self,
        query_id: str,
        sql: str,
        params: tuple[Any, ...],
        *,
        refs_column: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self._connect().execute(sql, params).fetchall()]
        refs = [str(row[refs_column]) for row in rows] if refs_column else []
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.MEMORY, name="sqlite_system_of_record"),
                type="sql_query",
                summary=f"Executed {query_id} and returned {len(rows)} rows",
                payload={
                    "store": "sqlite",
                    "query_id": query_id,
                    "sql": sql,
                    "parameters": list(params),
                    "filters": {"available_at_lte": self.emitter.virtual_now.isoformat()},
                    "result_ids": refs,
                    "used_ids": refs,
                    "discarded": [],
                },
                refs=refs,
            )
        )
        return rows

    def get_case(self, case_id: str) -> dict[str, Any]:
        rows = self._query(
            "case_by_id",
            "SELECT * FROM disputes WHERE case_id=? AND opened_at<=?",
            (case_id, self.emitter.virtual_now.isoformat().replace("+00:00", "Z")),
            refs_column="case_id",
        )
        if not rows:
            raise KeyError(f"unknown or unavailable case {case_id}")
        return rows[0]

    def get_case_transactions(self, case_id: str) -> list[dict[str, Any]]:
        return self._query(
            "transactions_for_case",
            """SELECT t.*, m.dba_name AS merchant_name FROM transactions t
               JOIN dispute_transactions dt ON dt.txn_id=t.txn_id
               LEFT JOIN merchants m ON m.merchant_id=t.merchant_id
               WHERE dt.case_id=? AND t.available_at<=? ORDER BY t.processing_date, t.txn_id""",
            (case_id, self.emitter.virtual_now.isoformat().replace("+00:00", "Z")),
            refs_column="txn_id",
        )

    def descriptor_history(self, customer_id: str, merchant_id: str) -> list[dict[str, Any]]:
        return self._query(
            "descriptor_history",
            """SELECT txn_id, descriptor, billing_amount, processing_date, available_at
               FROM transactions WHERE customer_id=? AND merchant_id=? AND available_at<=?
               ORDER BY processing_date""",
            (customer_id, merchant_id, self.emitter.virtual_now.isoformat().replace("+00:00", "Z")),
            refs_column="txn_id",
        )

    def descriptor_variants(self, merchant_id: str) -> list[dict[str, Any]]:
        return self._query(
            "descriptor_variants",
            "SELECT * FROM merchant_descriptors WHERE merchant_id=? ORDER BY first_seen",
            (merchant_id,),
        )

    def clearing_group(self, auth_id: str) -> list[dict[str, Any]]:
        return self._query(
            "clearing_group",
            """SELECT txn_id, auth_id, auth_amount, billing_amount, clearing_seq,
                      clearing_count, posting_date, available_at
               FROM transactions WHERE auth_id=? AND available_at<=? ORDER BY clearing_seq""",
            (auth_id, self.emitter.virtual_now.isoformat().replace("+00:00", "Z")),
            refs_column="txn_id",
        )

    def research_for_merchant(self, merchant_id: str) -> list[dict[str, Any]]:
        return self._query(
            "research_by_merchant",
            """SELECT doc_id, title, valid_from, body, meta_json FROM documents
               WHERE kind='research' AND meta_json LIKE ? AND valid_from<=?
               ORDER BY valid_from DESC""",
            (
                f'%"related_merchant_id": "{merchant_id}"%',
                self.emitter.virtual_now.date().isoformat(),
            ),
            refs_column="doc_id",
        )

    def evidence_packets(self, case_id: str) -> list[dict[str, Any]]:
        return self._query(
            "available_evidence_packets",
            """SELECT packet_id, case_id, txn_id, available_at, json
               FROM evidence_packet_documents WHERE case_id=? AND available_at<=?
               ORDER BY available_at""",
            (case_id, self.emitter.virtual_now.isoformat().replace("+00:00", "Z")),
            refs_column="packet_id",
        )

    def case_communications(self, case_id: str) -> list[dict[str, Any]]:
        return self._query(
            "communications_for_case",
            """SELECT comm_id, case_id, timestamp_utc, subject, body, attachments
               FROM communications WHERE case_id=? AND available_at<=?
               ORDER BY timestamp_utc""",
            (case_id, self.emitter.virtual_now.isoformat().replace("+00:00", "Z")),
            refs_column="comm_id",
        )

    def account(self, account_id: str) -> dict[str, Any]:
        rows = self._query(
            "account_by_id",
            "SELECT * FROM accounts WHERE account_id=?",
            (account_id,),
            refs_column="account_id",
        )
        if not rows:
            raise KeyError(f"unknown account {account_id}")
        return rows[0]

    def prior_disputes(
        self, customer_id: str, current_case_id: str, since: str
    ) -> list[dict[str, Any]]:
        return self._query(
            "prior_disputes_for_customer",
            """SELECT case_id, opened_at, status, claim_family_initial
               FROM disputes WHERE customer_id=? AND case_id<>? AND opened_at>=?
               AND opened_at<=? ORDER BY opened_at""",
            (
                customer_id,
                current_case_id,
                since,
                self.emitter.virtual_now.isoformat().replace("+00:00", "Z"),
            ),
            refs_column="case_id",
        )

    def account_events(self, account_id: str, *, since: str, until: str) -> list[dict[str, Any]]:
        return self._query(
            "account_events_in_window",
            """SELECT event_id, customer_id, account_id, event_type, timestamp_utc,
                      channel, device_id, ip, detail
               FROM account_events WHERE account_id=? AND timestamp_utc>=?
               AND timestamp_utc<=? AND available_at<=? ORDER BY timestamp_utc""",
            (
                account_id,
                since,
                until,
                self.emitter.virtual_now.isoformat().replace("+00:00", "Z"),
            ),
            refs_column="event_id",
        )

    def bank_holidays(self, *, since: str, until: str) -> list[dict[str, Any]]:
        return self._query(
            "bank_holidays_in_window",
            "SELECT date, holiday FROM ref_bank_holidays_2026 WHERE date>=? AND date<=?",
            (since, until),
            refs_column="date",
        )

    def customer_with_address(self, customer_id: str) -> dict[str, Any]:
        rows = self._query(
            "customer_with_home_address",
            """SELECT c.customer_id, c.phone, c.alt_phone, c.home_address_id,
                      a.line1, a.line2, a.city, a.state, a.postal_code
               FROM customers c JOIN addresses a ON a.address_id=c.home_address_id
               WHERE c.customer_id=?""",
            (customer_id,),
            refs_column="customer_id",
        )
        if not rows:
            raise KeyError(f"unknown customer {customer_id}")
        return rows[0]

    def disputes_by_ids(self, case_ids: list[str]) -> list[dict[str, Any]]:
        if not case_ids:
            return []
        placeholders = ",".join("?" for _ in case_ids)
        return self._query(
            "disputes_by_ids",
            f"""SELECT case_id, customer_id, account_id, status, stage, opened_at,
                       claim_family_initial, network_condition, dispute_amount,
                       cardholder_outcome, network_outcome
                FROM disputes WHERE case_id IN ({placeholders}) AND opened_at<=?
                ORDER BY case_id""",
            (
                *case_ids,
                self.emitter.virtual_now.isoformat().replace("+00:00", "Z"),
            ),
            refs_column="case_id",
        )

    def transactions_for_cases(self, case_ids: list[str]) -> list[dict[str, Any]]:
        if not case_ids:
            return []
        placeholders = ",".join("?" for _ in case_ids)
        return self._query(
            "transactions_for_cases",
            f"""SELECT dt.case_id, t.* FROM dispute_transactions dt
                 JOIN transactions t ON t.txn_id=dt.txn_id
                 WHERE dt.case_id IN ({placeholders}) AND t.available_at<=?
                 ORDER BY dt.case_id, t.txn_id""",
            (
                *case_ids,
                self.emitter.virtual_now.isoformat().replace("+00:00", "Z"),
            ),
            refs_column="txn_id",
        )

    def transactions_by_ids(self, txn_ids: list[str]) -> list[dict[str, Any]]:
        if not txn_ids:
            return []
        placeholders = ",".join("?" for _ in txn_ids)
        return self._query(
            "transactions_by_ids",
            f"""SELECT * FROM transactions WHERE txn_id IN ({placeholders})
                 AND available_at<=? ORDER BY processing_date, txn_id""",
            (*txn_ids, self.emitter.virtual_now.isoformat().replace("+00:00", "Z")),
            refs_column="txn_id",
        )

    def route_features(
        self, case: dict[str, Any], transactions: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Data-derived routing features; routes in config decide what they mean."""

        merchant_ids = sorted({row["merchant_id"] for row in transactions})
        channels = sorted({row["channel"] for row in transactions})
        placeholders = ",".join("?" for _ in merchant_ids) or "''"
        history = self._query(
            "route_features_merchant_dispute_history",
            f"""SELECT d.case_id FROM disputes d
                JOIN dispute_transactions dt ON dt.case_id=d.case_id
                JOIN transactions t ON t.txn_id=dt.txn_id
                WHERE t.merchant_id IN ({placeholders}) AND d.status='closed'
                  AND d.claim_family_initial=? AND d.opened_at<=?
                GROUP BY d.case_id""",
            (
                *merchant_ids,
                case["claim_family_initial"],
                self.emitter.virtual_now.isoformat().replace("+00:00", "Z"),
            ),
            refs_column="case_id",
        )
        packets = self.evidence_packets(case["case_id"])
        now = self.emitter.virtual_now.date()
        return {
            "transaction_channels": channels,
            "merchant_closed_same_family_disputes": len(history),
            "evidence_has_proof_of_delivery": any(
                "proof_of_delivery" in row["json"] for row in packets
            ),
            "transaction_age_days": max(
                (now - date.fromisoformat(row["processing_date"])).days for row in transactions
            )
            if transactions
            else 0,
        }

    def dispute_events(self, case_ids: list[str]) -> list[dict[str, Any]]:
        placeholders = ",".join("?" for _ in case_ids)
        return self._query(
            "dispute_events_for_cases",
            f"""SELECT * FROM dispute_events WHERE case_id IN ({placeholders})
                AND timestamp_utc<=? ORDER BY timestamp_utc""",
            (*case_ids, self.emitter.virtual_now.isoformat().replace("+00:00", "Z")),
            refs_column="event_id",
        )

    def dispute_conditions(self) -> list[dict[str, Any]]:
        return self._query(
            "visa_dispute_conditions",
            "SELECT * FROM ref_visa_dispute_conditions ORDER BY condition",
            (),
            refs_column="condition",
        )

    def related_merchants(self, merchant_id: str) -> list[dict[str, Any]]:
        """Near-duplicate merchant entities: same acquirer and MCC, name sharing a leading token."""

        return self._query(
            "near_duplicate_merchants",
            """SELECT other.merchant_id, other.dba_name, other.status, other.acquirer_id, other.mcc
               FROM merchants base JOIN merchants other
                 ON other.acquirer_id=base.acquirer_id AND other.mcc=base.mcc
                AND other.merchant_id<>base.merchant_id
                AND lower(substr(other.dba_name, 1, instr(other.dba_name || ' ', ' ') - 1))
                  = lower(substr(base.dba_name, 1, instr(base.dba_name || ' ', ' ') - 1))
               WHERE base.merchant_id=? ORDER BY other.merchant_id""",
            (merchant_id,),
            refs_column="merchant_id",
        )

    def merchant_activity(self, merchant_ids: list[str], *, since: str) -> dict[str, Any]:
        placeholders = ",".join("?" for _ in merchant_ids)
        now = self.emitter.virtual_now.isoformat().replace("+00:00", "Z")
        orders = self._query(
            "merchant_orders_since",
            f"""SELECT txn_id, merchant_id, processing_date FROM transactions
                WHERE merchant_id IN ({placeholders}) AND processing_date>=? AND available_at<=?
                ORDER BY processing_date""",
            (*merchant_ids, since, now),
            refs_column="txn_id",
        )
        disputes = self._query(
            "merchant_disputes_by_opened",
            f"""SELECT d.case_id, d.opened_at, d.status, d.claim_family_initial, t.merchant_id,
                       t.processing_date
                FROM disputes d JOIN dispute_transactions dt ON dt.case_id=d.case_id
                JOIN transactions t ON t.txn_id=dt.txn_id
                WHERE t.merchant_id IN ({placeholders}) AND d.opened_at<=?
                ORDER BY t.processing_date""",
            (*merchant_ids, now),
            refs_column="case_id",
        )
        return {"orders_since": orders, "disputes": disputes}

    def current_policy_version(self, family: str, as_of: date) -> str | None:
        rows = self._query(
            "current_policy_version",
            """SELECT doc_id, valid_from, valid_to FROM documents
               WHERE kind='policy' AND doc_id LIKE ? AND valid_from<=?
                 AND (valid_to IS NULL OR valid_to IN ('', 'null') OR valid_to>?)
               ORDER BY valid_from DESC LIMIT 1""",
            (f"{family}@%", as_of.isoformat(), as_of.isoformat()),
            refs_column="doc_id",
        )
        return str(rows[0]["doc_id"]) if rows else None

    def statements(self, account_id: str) -> list[dict[str, Any]]:
        return self._query(
            "statements_for_account",
            """SELECT * FROM statements WHERE account_id=? AND transmitted_at<=?
               ORDER BY cycle_end""",
            (account_id, self.emitter.virtual_now.isoformat().replace("+00:00", "Z")),
            refs_column="statement_id",
        )

    def account_transactions(
        self, account_id: str, *, since: str, until: str
    ) -> list[dict[str, Any]]:
        return self._query(
            "account_transactions_in_window",
            """SELECT t.txn_id, t.txn_type, t.channel, t.merchant_id, m.dba_name AS merchant_name,
                      m.acquirer_id, t.descriptor, t.billing_amount, t.txn_amount, t.txn_currency,
                      t.fx_rate, t.related_txn_id, t.txn_local_datetime, t.processing_date,
                      t.posting_date, t.available_at
               FROM transactions t LEFT JOIN merchants m ON m.merchant_id=t.merchant_id
               WHERE t.account_id=? AND t.processing_date>=? AND t.processing_date<=?
                 AND t.available_at<=? ORDER BY t.processing_date, t.txn_id""",
            (account_id, since, until, self.emitter.virtual_now.isoformat().replace("+00:00", "Z")),
            refs_column="txn_id",
        )

    def related_transactions(self, txn_ids: list[str]) -> list[dict[str, Any]]:
        placeholders = ",".join("?" for _ in txn_ids)
        return self._query(
            "linked_transactions",
            f"""SELECT * FROM transactions
                WHERE (txn_id IN ({placeholders}) OR related_txn_id IN ({placeholders}))
                  AND available_at<=? ORDER BY processing_date, txn_id""",
            (*txn_ids, *txn_ids, self.emitter.virtual_now.isoformat().replace("+00:00", "Z")),
            refs_column="txn_id",
        )

    def fx_rates(self, dates: list[str]) -> list[dict[str, Any]]:
        placeholders = ",".join("?" for _ in dates)
        return self._query(
            "reference_fx_rates",
            f"SELECT date, eur_usd FROM ref_fx_rates_eur_usd WHERE date IN ({placeholders})",
            tuple(dates),
            refs_column="date",
        )

    def merchant(self, merchant_id: str) -> dict[str, Any]:
        rows = self._query(
            "merchant_by_id",
            """SELECT merchant_id, dba_name, mcc, city, state, country, timezone, phone,
                      acquirer_id, parent_merchant_id, status FROM merchants WHERE merchant_id=?""",
            (merchant_id,),
            refs_column="merchant_id",
        )
        if not rows:
            raise KeyError(f"unknown merchant {merchant_id}")
        return rows[0]

    def city_timezone(self, city: str) -> str | None:
        rows = self._query(
            "city_timezone", "SELECT city, timezone FROM ref_cities WHERE city=?", (city,)
        )
        return str(rows[0]["timezone"]) if rows else None

    def open_portfolio(self) -> dict[str, list[dict[str, Any]]]:
        """Everything the portfolio router needs about open cases, in a few audited queries."""

        now = self.emitter.virtual_now.isoformat().replace("+00:00", "Z")
        cases = self._query(
            "open_cases_with_accounts",
            """SELECT d.case_id, d.regime, d.stage, d.opened_at, d.dispute_amount,
                      d.provisional_credit_at, d.dispute_processing_date,
                      d.response_processing_date,
                      a.statement_cycle_day, a.first_deposit_date
               FROM disputes d JOIN accounts a ON a.account_id=d.account_id
               WHERE d.status='open' AND d.opened_at<=? ORDER BY d.case_id""",
            (now,),
            refs_column="case_id",
        )
        transactions = self._query(
            "open_case_transactions",
            """SELECT dt.case_id, t.txn_id, t.merchant_id, t.channel, t.txn_local_datetime,
                      t.processing_date
               FROM dispute_transactions dt JOIN transactions t ON t.txn_id=dt.txn_id
               JOIN disputes d ON d.case_id=dt.case_id
               WHERE d.status='open' AND t.available_at<=? ORDER BY dt.case_id, t.txn_id""",
            (now,),
            refs_column="txn_id",
        )
        # Acknowledgment letters are the issuer's own outbound queue, so a letter already scheduled
        # satisfies the acknowledgment clock even if its send time is later today or tomorrow.
        acknowledged = self._query(
            "acknowledgment_letters_sent_or_queued",
            """SELECT DISTINCT case_id FROM dispute_events WHERE event_type='ack_letter_sent'""",
            (),
            refs_column="case_id",
        )
        research = self._query(
            "research_with_merchant_links",
            """SELECT doc_id, body, meta_json FROM documents
               WHERE kind='research'
                 AND meta_json LIKE '%related_merchant_id": "MER-%'
                 AND valid_from<=?""",
            (self.emitter.virtual_now.date().isoformat(),),
            refs_column="doc_id",
        )
        requested_records = self._query(
            "outstanding_written_record_requests",
            """SELECT packet_id, case_id, source, requested_at, available_at FROM evidence_packets
               WHERE source LIKE '%written_request%' AND available_at>?""",
            (now,),
            refs_column="packet_id",
        )
        return {
            "cases": cases,
            "transactions": transactions,
            "acknowledged": acknowledged,
            "research": research,
            "requested_records": requested_records,
        }
