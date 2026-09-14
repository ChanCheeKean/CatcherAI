"""Deterministic presentation perturbations for route-generalization checks."""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any


def create_perturbed_store(source: Path, target: Path, *, seed: int) -> dict[str, str]:
    """Copy a scenario store and rename non-semantic entities and intake wording."""

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    source_graph = source.with_name(f"{source.stem}_graph.lbug")
    if source_graph.exists():
        shutil.copy2(source_graph, target.with_name(f"{target.stem}_graph.lbug"))

    renamed: dict[str, str] = {}
    with sqlite3.connect(target) as connection:
        merchants = connection.execute(
            "SELECT merchant_id, dba_name FROM merchants ORDER BY merchant_id"
        ).fetchall()
        for index, (merchant_id, old_name) in enumerate(merchants, start=1):
            new_name = f"Variant {seed} Merchant {index:03d}"
            renamed[str(old_name)] = new_name
            connection.execute(
                "UPDATE merchants SET dba_name=?, legal_name=? WHERE merchant_id=?",
                (new_name, f"{new_name} LLC", merchant_id),
            )
        connection.execute(
            "UPDATE customers SET full_name='Variant ' || ? || ' ' || customer_id, "
            "preferred_name='Variant' || ?",
            (seed, seed),
        )
        connection.execute(
            "UPDATE disputes SET claim_summary='Variant wording ' || ? || ': ' || claim_summary",
            (seed,),
        )
        _rename_agentic_provider(connection, seed)
    return renamed


def decision_semantics(record: dict[str, Any]) -> dict[str, Any]:
    """Return the decision fields that presentation-only variants must preserve."""

    return {
        "is_dispute": record["is_dispute"],
        "claim_family": record["claim_family"],
        "network_actions": [
            {
                "action": row["action"],
                "condition": row.get("condition"),
                "amount": row["amount"],
            }
            for row in record["network_actions"]
        ],
        "cardholder_outcome": record["cardholder_resolution"]["outcome"],
        "credit_amount": record["cardholder_resolution"]["credit_amount"],
        "liability_amount": record["cardholder_resolution"]["liability_amount"],
        "ring_linkage": record.get("ring_linkage"),
        "conditions_considered": record.get("conditions_considered", []),
    }


def _rename_agentic_provider(connection: sqlite3.Connection, seed: int) -> None:
    provider = f"Variant {seed} Travel Assistant"
    rows = connection.execute(
        "SELECT event_id, detail FROM account_events WHERE event_type='token_provisioned'"
    ).fetchall()
    for event_id, raw in rows:
        detail = json.loads(raw)
        if detail.get("requestor_type") != "agentic_payment_provider":
            continue
        old = detail.get("requestor")
        detail["requestor"] = provider
        connection.execute(
            "UPDATE account_events SET detail=? WHERE event_id=?",
            (json.dumps(detail, sort_keys=True), event_id),
        )
        if old:
            connection.execute(
                "UPDATE communications SET subject=replace(subject, ?, ?), "
                "body=replace(body, ?, ?) WHERE subject LIKE ? OR body LIKE ?",
                (old, provider, old, provider, f"%{old}%", f"%{old}%"),
            )
    packets = connection.execute("SELECT packet_id, json FROM evidence_packet_documents").fetchall()
    for packet_id, raw in packets:
        packet = json.loads(raw)
        if packet.get("provider", {}).get("role") != "Agentic Payment Provider":
            continue
        packet["provider"]["name"] = provider
        connection.execute(
            "UPDATE evidence_packet_documents SET json=? WHERE packet_id=?",
            (json.dumps(packet, sort_keys=True), packet_id),
        )
