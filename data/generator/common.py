"""Shared primitives for the synthetic card-dispute data generator.

Everything is deterministic given SEED. Standard library only (Python 3.9+).
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import random
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

SEED = 20261021
UTC = dt.timezone.utc
ET = ZoneInfo("America/New_York")

# Simulation clock: Wednesday 2026-10-21 09:00 America/New_York.
AS_OF = dt.datetime(2026, 10, 21, 13, 0, tzinfo=UTC)
HISTORY_START = dt.date(2025, 10, 1)

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated")


# ---------------------------------------------------------------- money / time
def money(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def m(x) -> str:
    return str(money(x))


def d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def local_dt(date_s: str, time_s: str, tz: str) -> dt.datetime:
    naive = dt.datetime.fromisoformat(f"{date_s}T{time_s}")
    return naive.replace(tzinfo=ZoneInfo(tz))


def iso_utc(x: dt.datetime) -> str:
    return x.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc(date_s: str, time_s: str = "12:00:00", tz: str = "America/New_York") -> str:
    """Local wall time in `tz` -> ISO UTC string."""
    return iso_utc(local_dt(date_s, time_s, tz))


def add_days(date_s: str, n: int) -> str:
    return (d(date_s) + dt.timedelta(days=n)).isoformat()


def stable_hex(*parts, n: int = 40) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:n]


# ---------------------------------------------------------------- schemas
# Column order for every CSV table. The data dictionary documents each column.
SCHEMAS = {
    "customers": ["customer_id", "full_name", "preferred_name", "birth_year", "email", "phone", "alt_phone",
                  "home_address_id", "employer_name", "work_address_id", "customer_since", "segment",
                  "preferred_contact", "is_hero"],
    "addresses": ["address_id", "line1", "line2", "city", "state", "postal_code", "country", "lat", "lon",
                  "address_type"],
    "accounts": ["account_id", "primary_customer_id", "product", "regime", "opened_at", "status", "credit_limit",
                 "apr", "statement_cycle_day", "payment_behavior", "autopay", "first_deposit_date", "is_hero"],
    "account_holders": ["account_id", "customer_id", "role", "added_at", "removed_at"],
    "cards": ["card_id", "account_id", "customer_id", "role", "network", "bin", "pan_masked", "last4", "expiry",
              "status", "issued_at", "closed_at", "replaced_card_id"],
    "tokens": ["token_id", "card_id", "token_requestor_type", "token_requestor_name", "provisioned_at",
               "device_id", "status"],
    "merchants": ["merchant_id", "legal_name", "dba_name", "mcc", "mcc_description", "country", "city", "state",
                  "timezone", "channel", "website", "phone", "acquirer_id", "acquirer_name", "card_acceptor_id",
                  "is_marketplace", "parent_merchant_id", "onboarded_at", "status", "is_hero"],
    "merchant_descriptors": ["merchant_id", "descriptor", "first_seen", "last_seen", "note"],
    "devices": ["device_id", "device_type", "os", "hardware_id", "device_fingerprint", "first_seen",
                "observed_primary_customer_id"],
    "transactions": ["txn_id", "account_id", "card_id", "token_id", "customer_id", "merchant_id", "descriptor",
                     "mcc", "txn_type", "billing_amount", "billing_currency", "txn_amount", "txn_currency",
                     "fx_rate", "auth_amount", "auth_id", "auth_code", "auth_response_code", "auth_timestamp_utc",
                     "txn_local_datetime", "merchant_timezone", "processing_date", "posting_date",
                     "pos_entry_mode", "card_present", "channel", "cof_type", "eci", "cavv_present",
                     "three_ds_status", "three_ds_browser_ip", "avs_result", "cvv2_presence", "cvv2_result",
                     "clearing_seq", "clearing_count", "arn", "related_txn_id", "fraud_reported_at",
                     "available_at", "is_hero"],
    "statements": ["statement_id", "account_id", "cycle_start", "cycle_end", "transmitted_at", "due_date",
                   "previous_balance", "purchases", "credits", "payments", "fees", "closing_balance",
                   "minimum_due"],
    "account_events": ["event_id", "customer_id", "account_id", "event_type", "timestamp_utc", "channel",
                       "device_id", "ip", "detail", "available_at", "is_hero"],
    "disputes": ["case_id", "account_id", "customer_id", "card_id", "regime", "status", "stage", "opened_at",
                 "intake_channel", "intake_authenticated_via", "claim_summary", "claim_family_initial",
                 "network", "network_condition", "dispute_amount", "provisional_credit_amount",
                 "provisional_credit_at", "network_case_ref", "dispute_processing_date",
                 "response_processing_date", "pre_arb_processing_date", "cardholder_outcome",
                 "network_outcome", "closed_at", "assigned_queue", "related_case_ids", "is_hero"],
    "dispute_transactions": ["case_id", "txn_id", "disputed_amount"],
    "dispute_events": ["event_id", "case_id", "timestamp_utc", "event_type", "actor", "summary", "detail",
                       "available_at"],
    "communications": ["comm_id", "case_id", "customer_id", "merchant_id", "direction", "channel", "party",
                       "timestamp_utc", "available_at", "subject", "body", "attachments"],
    "evidence_packets": ["packet_id", "case_id", "txn_id", "merchant_id", "source", "requested_at",
                         "available_at", "path"],
    "ip_intel": ["ip", "ip_type", "isp", "city", "state", "country", "note"],
}


class Ctx:
    """In-memory store of all generated records."""

    def __init__(self, seed: int = SEED):
        self.rng = random.Random(seed)
        self.t = defaultdict(list)
        self.index = defaultdict(dict)  # table -> id -> row
        self.counters = defaultdict(int)
        self.packets = {}        # packet_id -> dict (written as JSON files)
        self.ground_truth = {}   # case_id -> dict
        self.personas = {}       # case_id -> dict
        self.precedents = {}     # precedent_id -> markdown
        self.memory_notes = []
        self.run_traces = {}     # trace_id -> list[dict]
        self.home_ip = {}        # customer_id -> residential IP
        self.people = []
        self.pools = {}
        self.bg_labels = []
        self.research = {}      # doc_id -> dict (written as markdown)

    # ids
    def next_id(self, prefix: str, width: int = 6) -> str:
        self.counters[prefix] += 1
        return f"{prefix}-{self.counters[prefix]:0{width}d}"

    def add(self, table: str, row: dict) -> dict:
        cols = SCHEMAS[table]
        unknown = set(row) - set(cols)
        if unknown:
            raise KeyError(f"{table}: unknown columns {unknown}")
        full = {c: row.get(c, "") for c in cols}
        self.t[table].append(full)
        key = cols[0]
        if key.endswith("_id") or key in ("ip", "case_id"):
            self.index[table][full[key]] = full
        return full

    def get(self, table: str, key: str) -> dict:
        return self.index[table][key]


# ---------------------------------------------------------------- writers
def _cell(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (dict, list)):
        return json.dumps(v, separators=(",", ":"), ensure_ascii=False)
    if v is None:
        return ""
    return v


def write_csv(path: str, table: str, rows: list):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SCHEMAS[table])
        w.writeheader()
        for r in rows:
            w.writerow({k: _cell(v) for k, v in r.items()})


def write_jsonl(path: str, rows: list):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_json(path: str, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_text(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
