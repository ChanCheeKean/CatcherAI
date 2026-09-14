from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
import time
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import networkx as nx

from domain.events import Actor, ActorKind, EventDraft
from observability.emitter import EventEmitter


class GraphMemory:
    """Cypher graph boundary with explicit NetworkX fallback and durable hypothesis writes."""

    def __init__(self, graph_root: Path, state_db_path: Path, emitter: EventEmitter) -> None:
        self.graph_root = graph_root
        self.state_db_path = state_db_path
        self.emitter = emitter
        # Reused for this object's lifetime: one `GraphMemory` per run/segment, always driven
        # from that run's own asyncio task on the process's single event-loop thread, so a
        # shared connection cannot be touched concurrently from another thread.
        self._state_connection = sqlite3.connect(state_db_path)
        self._networkx = NetworkXGraphBackend(graph_root)
        self._ladybug: LadybugGraphBackend | None = None
        try:
            backend = LadybugGraphBackend(
                graph_root,
                state_db_path.with_name(f"{state_db_path.stem}_graph.lbug"),
            )
            load = backend.ensure_loaded()
            self._ladybug = backend
            emitter.emit(
                EventDraft(
                    actor=Actor(kind=ActorKind.MEMORY, name="ladybug_graph"),
                    type="memory_write" if load["created"] else "memory_read",
                    summary=(
                        "Bulk-loaded the graph projection into LadybugDB"
                        if load["created"]
                        else "Opened the existing LadybugDB graph projection"
                    ),
                    payload={"store": "ladybug", "target_id": str(backend.db_path), **load},
                )
            )
        except Exception as exc:
            emitter.emit(
                EventDraft(
                    actor=Actor(kind=ActorKind.MEMORY, name="graph_backend_factory"),
                    type="fallback",
                    summary="Fell back from LadybugDB to NetworkX",
                    payload={
                        "component": "graph_store",
                        "from": "ladybug",
                        "to": "networkx",
                        "reason": type(exc).__name__,
                        "sanitized_error": str(exc),
                        "capability_delta": [],
                    },
                )
            )
        self._init_writes()

    @property
    def backend_name(self) -> str:
        return "ladybug" if self._ladybug else "networkx"

    def descriptors_for_merchant(self, merchant_id: str) -> list[dict[str, Any]]:
        cypher = """MATCH (d:Entity)-[r:Link]->(m:Entity)
                    WHERE m.node_id=$merchant_id AND r.rel='DESCRIBES'
                    RETURN d.node_id AS node_id, d.key AS descriptor,
                           m.node_id AS merchant_node_id, r.props_json AS edge_props
                    ORDER BY d.key"""
        rows = self._query(
            "descriptors_for_merchant",
            cypher,
            {"merchant_id": f"Merchant:{merchant_id}"},
            lambda: self._networkx.descriptors_for_merchant(merchant_id),
        )
        for row in rows:
            row.update(json.loads(row.pop("edge_props", "{}") or "{}"))
        return rows

    def common_compromise_points(
        self, *, customer_id: str, fraud_date: date, lookback_days: int = 30
    ) -> list[dict[str, Any]]:
        since = fraud_date - timedelta(days=lookback_days)
        cypher = """MATCH (origin:Entity)-[carry:Link]->(card:Entity),
                           (card)-[made:Link]->(visit:Entity)-[at:Link]->(merchant:Entity),
                           (other_card:Entity)-[made2:Link]->(visit2:Entity)-[at2:Link]->(merchant),
                           (victim:Entity)-[carry2:Link]->(other_card),
                           (victim)-[filed:Link]->(dispute:Entity)-[covers:Link]->(fraud_txn:Entity)
                    WHERE origin.node_id=$customer_id
                      AND carry.rel='CARRIES' AND made.rel='MADE' AND at.rel='AT'
                      AND made2.rel='MADE' AND at2.rel='AT' AND carry2.rel='CARRIES'
                      AND filed.rel='FILED' AND covers.rel='DISPUTES'
                      AND visit.node_date >= $since AND visit.node_date < $fraud_date
                      AND visit2.node_date >= $since AND visit2.node_date < $fraud_date
                      AND dispute.family='fraud_cnp' AND fraud_txn.node_date > visit2.node_date
                      AND victim.node_id <> origin.node_id
                    RETURN merchant.node_id AS merchant_node_id,
                           victim.node_id AS victim_node_id,
                           dispute.node_id AS dispute_node_id,
                           visit2.node_id AS visit_txn_node_id"""
        rows = self._query(
            "common_compromise_points",
            cypher,
            {
                "customer_id": f"Customer:{customer_id}",
                "since": since.isoformat(),
                "fraud_date": fraud_date.isoformat(),
            },
            lambda: self._networkx.common_compromise_rows(customer_id, fraud_date, lookback_days),
        )
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            item = grouped.setdefault(
                row["merchant_node_id"],
                {
                    "merchant_node_id": row["merchant_node_id"],
                    "merchant_id": row["merchant_node_id"].split(":", 1)[1],
                    "victim_node_ids": set(),
                    "dispute_node_ids": set(),
                    "visit_txn_node_ids": set(),
                },
            )
            item["victim_node_ids"].add(row["victim_node_id"])
            item["dispute_node_ids"].add(row["dispute_node_id"])
            item["visit_txn_node_ids"].add(row["visit_txn_node_id"])
        result = []
        for item in grouped.values():
            item["victim_count"] = len(item["victim_node_ids"])
            for key in ("victim_node_ids", "dispute_node_ids", "visit_txn_node_ids"):
                item[key] = sorted(item[key])
            result.append(item)
        return sorted(result, key=lambda row: (-row["victim_count"], row["merchant_id"]))

    def shared_delivery_network(self, case_id: str) -> list[dict[str, Any]]:
        cypher = """MATCH (current:Entity)-[covers:Link]->(txn:Entity)
                           -[ship:Link]->(address:Entity),
                           (other:Entity)-[covers2:Link]->(txn2:Entity)-[ship2:Link]->(address),
                           (customer:Entity)-[filed:Link]->(other)
                    WHERE current.node_id=$case_id AND covers.rel='DISPUTES'
                      AND ship.rel='SHIPPED_TO' AND covers2.rel='DISPUTES'
                      AND ship2.rel='SHIPPED_TO' AND filed.rel='FILED'
                    RETURN address.node_id AS address_node_id,
                           customer.node_id AS customer_node_id,
                           other.node_id AS dispute_node_id, txn2.node_id AS txn_node_id"""
        return self._query(
            "shared_delivery_network",
            cypher,
            {"case_id": f"Dispute:{case_id}"},
            lambda: self._networkx.shared_delivery_network(case_id),
        )

    def shared_identity_component(self, customer_id: str) -> dict[str, Any]:
        cypher = """MATCH (origin:Entity)-[left:Link]->(identifier:Entity)
                           <-[right:Link]-(other:Entity)
                    WHERE origin.node_id=$customer_id
                      AND left.rel IN ['BANKING_LOGIN_FROM', 'HAS_PHONE']
                      AND right.rel=left.rel AND other.label='Customer'
                      AND identifier.label IN ['Device', 'Phone']
                      AND other.node_id <> origin.node_id
                    RETURN other.node_id AS customer_node_id,
                           identifier.node_id AS identifier_node_id,
                           left.rel AS relationship"""
        rows = self._query(
            "shared_identity_component",
            cypher,
            {"customer_id": f"Customer:{customer_id}"},
            lambda: self._networkx.shared_identity_rows(customer_id),
        )
        members = {f"Customer:{customer_id}", *[row["customer_node_id"] for row in rows]}
        for member_node in sorted(members):
            member_id = member_node.split(":", 1)[1]
            if member_id == customer_id:
                continue
            member_rows = self._query(
                "shared_identity_within_component",
                cypher,
                {"customer_id": member_node},
                lambda member_id=member_id: self._networkx.shared_identity_rows(member_id),
            )
            rows.extend(row for row in member_rows if row["customer_node_id"] in members)
        identifiers: dict[str, set[str]] = {}
        for row in rows:
            members.add(row["customer_node_id"])
            identifiers.setdefault(row["relationship"], set()).add(row["identifier_node_id"])
        return {
            "customer_ids": sorted(node.split(":", 1)[1] for node in members),
            "shared_identifiers": {
                relation: sorted(values) for relation, values in identifiers.items()
            },
            "linked": len(members) > 1,
        }

    def device_fingerprint_owners(self, fingerprints: list[str]) -> list[dict[str, Any]]:
        """Which customers' devices carry these fingerprints and log in to banking from them."""

        cypher = """MATCH (device:Entity)-[has:Link]->(fingerprint:Entity),
                           (customer:Entity)-[login:Link]->(device)
                    WHERE fingerprint.node_id IN $fingerprints AND has.rel='HAS_FINGERPRINT'
                      AND login.rel='BANKING_LOGIN_FROM'
                    RETURN fingerprint.node_id AS fingerprint_node_id,
                           device.node_id AS device_node_id,
                           customer.node_id AS customer_node_id,
                           login.props_json AS login_props"""
        nodes = [f"DeviceFingerprint:{value}" for value in fingerprints]
        return self._query(
            "device_fingerprint_owners",
            cypher,
            {"fingerprints": nodes},
            lambda: self._networkx.device_fingerprint_owners(nodes),
        )

    def disputes_for_customers(
        self, customer_ids: list[str], *, family: str, since: date
    ) -> list[dict[str, Any]]:
        cypher = """MATCH (customer:Entity)-[filed:Link]->(dispute:Entity)
                    WHERE customer.node_id=$customer_id AND filed.rel='FILED'
                      AND dispute.family=$family AND dispute.opened >= $since
                    RETURN customer.node_id AS customer_node_id,
                           dispute.node_id AS dispute_node_id,
                           dispute.status AS status, dispute.opened AS opened"""
        rows: list[dict[str, Any]] = []
        for customer_id in customer_ids:
            rows.extend(
                self._query(
                    "disputes_for_customer",
                    cypher,
                    {
                        "customer_id": f"Customer:{customer_id}",
                        "family": family,
                        "since": since.isoformat(),
                    },
                    lambda customer_id=customer_id: self._networkx.disputes_for_customer(
                        customer_id, family, since
                    ),
                )
            )
        return sorted(
            {row["dispute_node_id"]: row for row in rows}.values(),
            key=lambda row: row["dispute_node_id"],
        )

    def write_hypothesis(
        self,
        *,
        hypothesis_id: str,
        kind: str,
        subject_ids: list[str],
        relationship: str,
        evidence_refs: list[str],
        confidence: float,
        properties: dict[str, Any] | None = None,
    ) -> str:
        checks = [
            {
                "check": "allowed_hypothesis_kind",
                "pass": kind
                in {"SuspectedRing", "SuspectedCompromisePoint", "SuspectedDropAddress"},
            },
            {"check": "evidence_refs_present", "pass": bool(evidence_refs)},
            {"check": "subjects_present", "pass": bool(subject_ids)},
            {"check": "confidence_in_range", "pass": 0 <= confidence <= 1},
            {"check": "status_is_bounded_active_hypothesis", "pass": True},
        ]
        if not all(check["pass"] for check in checks):
            self.emitter.emit(
                EventDraft(
                    actor=Actor(kind=ActorKind.MEMORY, name="graph_write_gate"),
                    type="write_rejected",
                    summary=f"Rejected graph hypothesis {hypothesis_id}",
                    payload={"target_id": hypothesis_id, "gate_checks": checks},
                    refs=evidence_refs,
                )
            )
            raise ValueError("graph hypothesis failed write gate")
        after = {
            "node_id": hypothesis_id,
            "kind": kind,
            "status": "active",
            "subject_ids": subject_ids,
            "relationship": relationship,
            "evidence_refs": evidence_refs,
            "confidence": confidence,
            "properties": properties or {},
        }
        with self._state_connection as connection:
            before_row = connection.execute(
                "SELECT payload_json FROM graph_hypotheses WHERE hypothesis_id=?",
                (hypothesis_id,),
            ).fetchone()
            connection.execute(
                """INSERT INTO graph_hypotheses VALUES (?,?,?,?,?,?)
                   ON CONFLICT(hypothesis_id) DO UPDATE SET kind=excluded.kind,
                   status=excluded.status, payload_json=excluded.payload_json,
                   evidence_refs_json=excluded.evidence_refs_json,
                   updated_at=excluded.updated_at""",
                (
                    hypothesis_id,
                    kind,
                    "active",
                    json.dumps(after, sort_keys=True),
                    json.dumps(evidence_refs),
                    self.emitter.virtual_now.isoformat(),
                ),
            )
        if self._ladybug:
            self._ladybug.write_hypothesis(after)
        else:
            self._networkx.write_hypothesis(after)
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.MEMORY, name="graph_write_gate"),
                type="graph_write",
                summary=f"Wrote active {kind} hypothesis",
                payload={
                    "store": self.backend_name,
                    "operation": "upsert_hypothesis_with_evidence_edges",
                    "target_id": hypothesis_id,
                    "before": json.loads(before_row[0]) if before_row else None,
                    "after": after,
                    "source_refs": evidence_refs,
                    "write_gate_checks": checks,
                },
                refs=[hypothesis_id, *subject_ids, *evidence_refs],
            )
        )
        return hypothesis_id

    def skip_hypothesis_write(self, *, candidate: str, reason: str, refs: list[str]) -> None:
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.MEMORY, name="graph_write_gate"),
                type="memory_write_skipped",
                summary=f"Skipped graph write for {candidate}",
                payload={
                    "store": self.backend_name,
                    "candidate": candidate,
                    "reason": reason,
                    "gate_checks": [
                        {"check": "evidence_linkage_present", "pass": False},
                        {"check": "guilt_by_association_guardrail", "pass": True},
                    ],
                },
                refs=refs,
            )
        )

    def _query(
        self,
        template_id: str,
        cypher: str,
        parameters: dict[str, Any],
        fallback: Callable[[], list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        started = time.perf_counter()
        backend = self.backend_name
        try:
            rows = self._ladybug.query(cypher, parameters) if self._ladybug else fallback()
        except Exception as exc:
            backend = "networkx"
            rows = fallback()
            self.emitter.emit(
                EventDraft(
                    actor=Actor(kind=ActorKind.MEMORY, name="graph_query_router"),
                    type="fallback",
                    summary=f"Used NetworkX parity for {template_id}",
                    payload={
                        "component": "graph_query",
                        "from": "ladybug",
                        "to": "networkx",
                        "reason": type(exc).__name__,
                        "sanitized_error": str(exc),
                        "capability_delta": [],
                    },
                )
            )
        node_ids = sorted(
            {
                value
                for row in rows
                for key, value in row.items()
                if key.endswith("_node_id") and isinstance(value, str)
            }
        )
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.MEMORY, name=f"{backend}_graph"),
                type="graph_query",
                summary=f"Executed graph template {template_id}; returned {len(rows)} rows",
                payload={
                    "store": "graph",
                    "backend": backend,
                    "template_id": template_id,
                    "cypher": cypher,
                    "parameters": parameters,
                    "filters": {"status": "active_or_source_fact"},
                    "node_ids": node_ids,
                    "results": rows,
                    "used_ids": node_ids,
                    "discarded": [],
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                },
                refs=node_ids,
            )
        )
        return rows

    def _init_writes(self) -> None:
        with self._state_connection as connection:
            existed = bool(
                connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='graph_hypotheses'"
                ).fetchone()
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS graph_hypotheses(
                   hypothesis_id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
                   payload_json TEXT NOT NULL, evidence_refs_json TEXT NOT NULL,
                   updated_at TEXT NOT NULL)"""
            )
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.MEMORY, name="graph_hypothesis_store"),
                type="memory_read" if existed else "memory_write",
                summary=(
                    "Opened the durable graph-hypothesis store"
                    if existed
                    else "Initialized the durable graph-hypothesis store"
                ),
                payload={
                    "store": "sqlite_system_of_record",
                    "namespace": "graph_hypotheses",
                    "operation": "schema_check" if existed else "schema_create",
                    "result_ids": [],
                    "used_ids": [],
                    "discarded": [],
                },
            )
        )


class LadybugGraphBackend:
    def __init__(self, graph_root: Path, db_path: Path) -> None:
        import ladybug

        self.graph_root = graph_root
        self.db_path = db_path
        self._ladybug = ladybug
        self._connection: Any = None
        self._database: Any = None

    def ensure_loaded(self) -> dict[str, Any]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._database = self._ladybug.Database(self.db_path)
        self._connection = self._ladybug.Connection(self._database)
        try:
            count = self.query("MATCH (n:Entity) RETURN count(n) AS count", {})[0]["count"]
            return {"created": False, "node_count": int(count), "edge_count": None}
        except Exception:
            pass
        self._connection.execute(
            """CREATE NODE TABLE Entity(
               node_id STRING PRIMARY KEY, label STRING, key STRING, props_json STRING,
               node_date STRING, status STRING, family STRING, opened STRING,
               name STRING, node_type STRING)"""
        )
        self._connection.execute(
            """CREATE REL TABLE Link(FROM Entity TO Entity, rel STRING,
               props_json STRING, status STRING, evidence_refs STRING)"""
        )
        with tempfile.TemporaryDirectory(prefix="dispute-graph-load-") as directory:
            node_csv = Path(directory) / "nodes.csv"
            edge_csv = Path(directory) / "edges.csv"
            node_count = self._write_node_csv(node_csv)
            edge_count = self._write_edge_csv(edge_csv)
            self._connection.execute(f"COPY Entity FROM '{_cypher_path(node_csv)}' (header=true)")
            self._connection.execute(f"COPY Link FROM '{_cypher_path(edge_csv)}' (header=true)")
        return {"created": True, "node_count": node_count, "edge_count": edge_count}

    def query(self, cypher: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        if self._connection is None:
            raise RuntimeError("LadybugDB connection is not initialized")
        result = self._connection.execute(cypher, parameters)
        return result.rows_as_dict().get_all()

    def write_hypothesis(self, payload: dict[str, Any]) -> None:
        assert self._connection is not None
        self._connection.execute(
            """MERGE (h:Entity {node_id: $node_id})
               ON CREATE SET h.label='Hypothesis', h.key=$node_id
               SET h.props_json=$props, h.status='active', h.node_type=$kind""",
            {
                "node_id": payload["node_id"],
                "props": json.dumps(payload, sort_keys=True),
                "kind": payload["kind"],
            },
        )
        for subject_id in payload["subject_ids"]:
            self._connection.execute(
                """MATCH (h:Entity {node_id: $node_id}), (s:Entity {node_id: $subject_id})
                   MERGE (h)-[r:Link {rel: $relationship}]->(s)
                   SET r.status='active', r.evidence_refs=$evidence_refs""",
                {
                    "node_id": payload["node_id"],
                    "subject_id": _qualified_subject(subject_id),
                    "relationship": payload["relationship"],
                    "evidence_refs": json.dumps(payload["evidence_refs"]),
                },
            )

    def _write_node_csv(self, path: Path) -> int:
        count = 0
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "node_id",
                    "label",
                    "key",
                    "props_json",
                    "node_date",
                    "status",
                    "family",
                    "opened",
                    "name",
                    "node_type",
                ]
            )
            with (self.graph_root / "nodes.jsonl").open(encoding="utf-8") as source:
                for line in source:
                    row = json.loads(line)
                    props = row.get("props", {})
                    writer.writerow(
                        [
                            row["node_id"],
                            row["label"],
                            row["key"],
                            json.dumps(props, separators=(",", ":")),
                            props.get("date", ""),
                            props.get("status", ""),
                            props.get("family", ""),
                            props.get("opened", ""),
                            props.get("name", ""),
                            props.get("type", ""),
                        ]
                    )
                    count += 1
        return count

    def _write_edge_csv(self, path: Path) -> int:
        count = 0
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["from", "to", "rel", "props_json", "status", "evidence_refs"])
            with (self.graph_root / "edges.jsonl").open(encoding="utf-8") as source:
                for line in source:
                    row = json.loads(line)
                    writer.writerow(
                        [
                            row["src"],
                            row["dst"],
                            row["rel"],
                            json.dumps(row.get("props", {}), separators=(",", ":")),
                            "",
                            "",
                        ]
                    )
                    count += 1
        return count


class NetworkXGraphBackend:
    """Query-parity fallback used when LadybugDB is unavailable or a query fails."""

    def __init__(self, graph_root: Path) -> None:
        self.graph_root = graph_root
        self._graph: nx.MultiDiGraph | None = None

    def descriptors_for_merchant(self, merchant_id: str) -> list[dict[str, Any]]:
        graph = self._load()
        merchant = f"Merchant:{merchant_id}"
        return [
            {
                "node_id": source,
                "descriptor": graph.nodes[source]["key"],
                "merchant_node_id": merchant,
                "edge_props": json.dumps(edge.get("props", {})),
            }
            for source, _, edge in graph.in_edges(merchant, data=True)
            if edge.get("rel") == "DESCRIBES"
        ]

    def common_compromise_rows(
        self, customer_id: str, fraud_date: date, lookback_days: int
    ) -> list[dict[str, Any]]:
        graph = self._load()
        origin = f"Customer:{customer_id}"
        since = fraud_date - timedelta(days=lookback_days)
        cards = _out(graph, origin, "CARRIES")
        merchants = {
            merchant
            for card in cards
            for txn in _out(graph, card, "MADE")
            if (txn_date := _node_date(graph, txn)) and since <= txn_date < fraud_date
            for merchant in _out(graph, txn, "AT")
        }
        rows = []
        for merchant in merchants:
            for visit in _incoming(graph, merchant, "AT"):
                visit_date = _node_date(graph, visit)
                if not visit_date or not since <= visit_date < fraud_date:
                    continue
                for card in _incoming(graph, visit, "MADE"):
                    for victim in _incoming(graph, card, "CARRIES"):
                        if victim == origin:
                            continue
                        for dispute in _out(graph, victim, "FILED"):
                            if graph.nodes[dispute]["props"].get("family") != "fraud_cnp":
                                continue
                            if any(
                                (fraud_txn_date := _node_date(graph, txn))
                                and fraud_txn_date > visit_date
                                for txn in _out(graph, dispute, "DISPUTES")
                            ):
                                rows.append(
                                    {
                                        "merchant_node_id": merchant,
                                        "victim_node_id": victim,
                                        "dispute_node_id": dispute,
                                        "visit_txn_node_id": visit,
                                    }
                                )
        return rows

    def shared_delivery_network(self, case_id: str) -> list[dict[str, Any]]:
        graph = self._load()
        dispute = f"Dispute:{case_id}"
        addresses = {
            address
            for txn in _out(graph, dispute, "DISPUTES")
            for address in _out(graph, txn, "SHIPPED_TO")
        }
        return [
            {
                "address_node_id": address,
                "customer_node_id": customer,
                "dispute_node_id": other_dispute,
                "txn_node_id": txn,
            }
            for address in addresses
            for txn in _incoming(graph, address, "SHIPPED_TO")
            for other_dispute in _incoming(graph, txn, "DISPUTES")
            for customer in _incoming(graph, other_dispute, "FILED")
        ]

    def shared_identity_rows(self, customer_id: str) -> list[dict[str, Any]]:
        graph = self._load()
        origin = f"Customer:{customer_id}"
        return [
            {
                "customer_node_id": other,
                "identifier_node_id": identifier,
                "relationship": relation,
            }
            for relation in ("BANKING_LOGIN_FROM", "HAS_PHONE")
            for identifier in _out(graph, origin, relation)
            if graph.nodes[identifier].get("label") in {"Device", "Phone"}
            for other in _incoming(graph, identifier, relation)
            if other.startswith("Customer:") and other != origin
        ]

    def device_fingerprint_owners(self, fingerprint_nodes: list[str]) -> list[dict[str, Any]]:
        graph = self._load()
        rows = []
        for fingerprint in fingerprint_nodes:
            if fingerprint not in graph:
                continue
            for device in _incoming(graph, fingerprint, "HAS_FINGERPRINT"):
                for customer, _, edge in graph.in_edges(device, data=True):
                    if edge.get("rel") == "BANKING_LOGIN_FROM":
                        rows.append(
                            {
                                "fingerprint_node_id": fingerprint,
                                "device_node_id": device,
                                "customer_node_id": customer,
                                "login_props": json.dumps(
                                    edge.get("props", {}), separators=(",", ":")
                                ),
                            }
                        )
        return rows

    def disputes_for_customer(
        self, customer_id: str, family: str, since: date
    ) -> list[dict[str, Any]]:
        graph = self._load()
        customer = f"Customer:{customer_id}"
        return [
            {
                "customer_node_id": customer,
                "dispute_node_id": dispute,
                "status": props.get("status", ""),
                "opened": props.get("opened", ""),
            }
            for dispute in _out(graph, customer, "FILED")
            if (props := graph.nodes[dispute]["props"]).get("family") == family
            and props.get("opened", "") >= since.isoformat()
        ]

    def write_hypothesis(self, payload: dict[str, Any]) -> None:
        graph = self._load()
        graph.add_node(
            payload["node_id"], label="Hypothesis", key=payload["node_id"], props=payload
        )
        for subject_id in payload["subject_ids"]:
            graph.add_edge(
                payload["node_id"],
                _qualified_subject(subject_id),
                rel=payload["relationship"],
                props={"status": "active", "evidence_refs": payload["evidence_refs"]},
            )

    def _load(self) -> nx.MultiDiGraph:
        if self._graph is not None:
            return self._graph
        graph = nx.MultiDiGraph()
        with (self.graph_root / "nodes.jsonl").open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                graph.add_node(
                    row["node_id"],
                    label=row["label"],
                    key=row["key"],
                    props=row["props"],
                )
        with (self.graph_root / "edges.jsonl").open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                graph.add_edge(row["src"], row["dst"], rel=row["rel"], props=row["props"])
        self._graph = graph
        return graph


def _out(graph: nx.MultiDiGraph, node: str, relationship: str) -> list[str]:
    return [
        target
        for _, target, edge in graph.out_edges(node, data=True)
        if edge.get("rel") == relationship
    ]


def _incoming(graph: nx.MultiDiGraph, node: str, relationship: str) -> list[str]:
    return [
        source
        for source, _, edge in graph.in_edges(node, data=True)
        if edge.get("rel") == relationship
    ]


def _node_date(graph: nx.MultiDiGraph, node_id: str) -> date | None:
    raw = graph.nodes[node_id].get("props", {}).get("date")
    return date.fromisoformat(raw) if raw else None


def _qualified_subject(subject_id: str) -> str:
    if ":" in subject_id:
        return subject_id
    prefixes = {
        "CUS-": "Customer",
        "MER-": "Merchant",
        "ADR-": "Address",
        "DSP-": "Dispute",
        "TXN-": "Transaction",
        "DEV-": "Device",
    }
    label = next((value for key, value in prefixes.items() if subject_id.startswith(key)), "Entity")
    return f"{label}:{subject_id}"


def _cypher_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")
