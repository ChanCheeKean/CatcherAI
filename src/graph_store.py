"""LadybugDB evidence store: bulk load, read-only Cypher, temporal neighbours, agent findings."""

from __future__ import annotations

import csv
import json
import re
import shutil
import tempfile
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

import ladybug as lb

_WRITE_KEYWORDS = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DROP|COPY|LOAD|INSTALL|ATTACH|ALTER|DETACH)\b", re.I
)
_LITERALS = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`[^`]*`|//[^\n]*|/\*.*?\*/", re.S)
_ID = re.compile(r"^(?:[A-Z]{2,3}|E)-\S+$")


def _ontology_path(db_path: Path) -> Path:
    return Path(str(db_path) + ".ontology.json")


def load(jsonl_dir: Path, db_path: Path) -> GraphStore:
    """Create `db_path` from `nodes.jsonl`, `edges.jsonl` and `ontology.json` in `jsonl_dir`."""
    jsonl_dir, db_path = Path(jsonl_dir), Path(db_path)
    ontology = json.loads((jsonl_dir / "ontology.json").read_text())
    for stale in (db_path, Path(str(db_path) + ".wal")):
        stale.unlink(missing_ok=True)
    _ontology_path(db_path).write_text(json.dumps(ontology))
    store = GraphStore(db_path)
    nodes, edges = ontology["nodes"], ontology["edges"]
    for label, spec in nodes.items():
        cols = "".join(f", {k} {t}" for k, t in spec["props"].items())
        store.conn.execute(f"CREATE NODE TABLE {label}(id STRING PRIMARY KEY{cols})")
    for etype, spec in edges.items():
        pairs = ", ".join(f"FROM {s} TO {d}" for s, d in spec["pairs"])
        cols = "".join(f", {k} {t}" for k, t in spec["props"].items())
        store.conn.execute(f"CREATE REL TABLE {etype}({pairs}, id STRING{cols})")

    # One CSV per node table and per (edge type, src label, dst label) table pair.
    csv_rows: dict[tuple, list[list]] = defaultdict(list)
    for row in _jsonl(jsonl_dir / "nodes.jsonl"):
        props = nodes[row["label"]]["props"]
        csv_rows[(row["label"],)].append([row["id"], *(row["props"].get(c, "") for c in props)])
    for row in _jsonl(jsonl_dir / "edges.jsonl"):
        props = edges[row["type"]]["props"]
        src, dst = (store.label_of(row[k]) for k in ("src", "dst"))
        csv_rows[(row["type"], src, dst)].append(
            [row["src"], row["dst"], row["id"], *(row["props"].get(c, "") for c in props)]
        )
    with tempfile.TemporaryDirectory() as tmp:
        for i, (key, rows) in enumerate(csv_rows.items()):
            path = Path(tmp) / f"{i}.csv"
            with path.open("w", newline="") as f:
                csv.writer(f).writerows(rows)
            opts = "header=false, parallel=false"
            if len(key) == 3:
                opts += f", from='{key[1]}', to='{key[2]}'"
            store.conn.execute(f"COPY {key[0]} FROM '{path}' ({opts})")
    return store


def copy_store(src: Path, dst: Path) -> GraphStore:
    """Copy a store for per-run isolation (the source must not be open for writing)."""
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    for a, b in ((src, dst), (_ontology_path(src), _ontology_path(dst))):
        shutil.copy2(a, b)
    return GraphStore(dst)


def _jsonl(path: Path):
    with path.open() as f:
        for line in f:
            yield json.loads(line)


class GraphStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.conn = lb.Connection(lb.Database(str(self.db_path)))
        onto = _ontology_path(self.db_path)
        self.ontology = (
            json.loads(onto.read_text()) if onto.exists() else {"nodes": {}, "edges": {}}
        )
        self._label_of = {s["prefix"]: label for label, s in self.ontology["nodes"].items()}

    def label_of(self, node_id: str) -> str:
        label = self._label_of.get(node_id.split("-")[0])
        if label is None:
            raise ValueError(f"unknown node id {node_id!r}")
        return label

    def schema(self) -> dict:
        """Labels, edge types, their properties and counts."""
        nodes = {
            label: {"props": {"id": "STRING", **s["props"]}, "count": self._count(f"(n:{label})")}
            for label, s in self.ontology["nodes"].items()
        }
        edges = {
            etype: {
                "pairs": s["pairs"],
                "props": {"id": "STRING", **s["props"]},
                "count": self._count(f"()-[n:{etype}]->()"),
            }
            for etype, s in self.ontology["edges"].items()
        }
        return {"nodes": nodes, "edges": edges}

    def _count(self, pattern: str) -> int:
        return self.conn.execute(f"MATCH {pattern} RETURN count(n)").get_next()[0]

    def query(self, cypher: str, params: dict | None = None, row_cap: int = 50) -> dict:
        """Run read-only Cypher; returns rows plus the node/edge ids that appear in them."""
        bad = _WRITE_KEYWORDS.search(_LITERALS.sub("''", cypher))
        if bad:
            raise ValueError(f"read-only store: {bad.group(0).upper()} is not allowed")
        result = self.conn.execute(cypher, params or {})
        seen = _new_seen()
        rows: list[list] = []
        truncated = False
        while result.has_next():
            if len(rows) == row_cap:
                truncated = True
                break
            rows.append([_clean(v, seen) for v in result.get_next()])
        return {
            "columns": result.get_column_names(),
            "rows": rows,
            "truncated": truncated,
            "node_ids": sorted(seen["node_ids"]),
            "edge_ids": sorted(seen["edge_ids"]),
        }

    def neighbors(
        self,
        node_id: str,
        rel_types: list[str] | None = None,
        direction: str = "both",
        since: str = "",
        until: str = "",
        limit: int = 50,
    ) -> dict:
        """Edges around a node, active within [since, until] when the edge is temporal."""
        label = self.label_of(node_id)
        found: list[dict] = []
        seen = _new_seen()
        for etype, spec in self.ontology["edges"].items():
            if rel_types and etype not in rel_types:
                continue
            for way in ("out", "in") if direction == "both" else (direction,):
                if not any(p[0 if way == "out" else 1] == label for p in spec["pairs"]):
                    continue
                arrow = f"-[r:{etype}]->" if way == "out" else f"<-[r:{etype}]-"
                when, params = _active_between(spec["props"], since, until)
                cypher = (
                    f"MATCH (a:{label} {{id: $id}}){arrow}(b) WHERE true{when} "
                    f"RETURN r, b LIMIT {limit + 1}"
                )
                result = self.conn.execute(cypher, {"id": node_id, **params})
                while result.has_next():
                    edge, node = result.get_next()
                    found.append(
                        {
                            "type": etype,
                            "direction": way,
                            "edge": _clean(edge, seen),
                            "node": _clean(node, seen),
                        }
                    )
        truncated = len(found) > limit
        found = found[:limit]
        return {
            "neighbors": found,
            "truncated": truncated,
            "node_ids": sorted({f["node"]["id"] for f in found} | {node_id}),
            "edge_ids": sorted(f["edge"]["id"] for f in found),
        }

    def write_finding(
        self,
        text: str,
        run_id: str,
        confidence: float,
        evidence_path: str = "",
        kind: str = "",
        edges: list[dict] | None = None,
    ) -> dict:
        """Create a Finding plus inferred edges `{type, src, dst}`; agents may only add edges whose
        ontology type carries provenance (`run_id`, `confidence`, `evidence_path`)."""
        edges = edges or []
        finding_id = f"FND-{uuid.uuid4().hex[:10]}"
        for e in edges:
            spec = self.ontology["edges"].get(e["type"])
            if spec is None or "run_id" not in spec["props"]:
                raise ValueError(f"agents may not write edge type {e['type']!r}")
            labels = [self.label_of(e.get("src", finding_id)), self.label_of(e["dst"])]
            if labels not in [list(p) for p in spec["pairs"]]:
                raise ValueError(f"{e['type']} cannot connect {labels[0]} -> {labels[1]}")
        self.conn.execute(
            "CREATE (:Finding {id: $id, text: $text, kind: $kind, run_id: $run_id, "
            "confidence: $confidence, evidence_path: $path})",
            {
                "id": finding_id,
                "text": text,
                "kind": kind,
                "run_id": run_id,
                "confidence": confidence,
                "path": evidence_path,
            },
        )
        edge_ids = []
        for e in edges:
            src, dst = e.get("src", finding_id), e["dst"]
            s_label, d_label = self.label_of(src), self.label_of(dst)
            edge_id = f"E-{uuid.uuid4().hex[:10]}"
            self.conn.execute(
                f"MATCH (a:{s_label} {{id: $src}}), (b:{d_label} {{id: $dst}}) "
                f"CREATE (a)-[:{e['type']} {{id: $id, run_id: $run_id, confidence: $confidence, "
                "evidence_path: $path}]->(b)",
                {
                    "src": src,
                    "dst": dst,
                    "id": edge_id,
                    "run_id": run_id,
                    "confidence": confidence,
                    "path": evidence_path,
                },
            )
            edge_ids.append(edge_id)
        return {"finding_id": finding_id, "edge_ids": edge_ids}

    def close(self) -> None:
        self.conn.close()


def _active_between(props: dict, since: str, until: str) -> tuple[str, dict]:
    """Cypher conditions (and params) keeping edges whose validity overlaps [since, until]."""
    when, params = "", {}
    if "valid_from" in props:
        if until:
            when += " AND (r.valid_from IS NULL OR r.valid_from = '' OR r.valid_from <= $until)"
            params["until"] = until
        if since:
            when += " AND (r.valid_to IS NULL OR r.valid_to = '' OR r.valid_to >= $since)"
            params["since"] = since
    elif "ts" in props:
        for op, key, bound in ((">=", "since", since), ("<=", "until", until)):
            if bound:
                when += f" AND r.ts {op} ${key}"
                params[key] = bound
    return when, params


def _new_seen() -> dict[str, set[str]]:
    return {"node_ids": set(), "edge_ids": set()}


def _clean(value: Any, seen: dict[str, set[str]]) -> Any:
    """Strip Ladybug internals from a result value and collect the node/edge ids it contains."""
    if isinstance(value, dict):
        if "_SRC" in value:
            seen["edge_ids"].add(value["id"])
            return {"_type": value["_LABEL"], **_props(value)}
        if "_LABEL" in value:
            seen["node_ids"].add(value["id"])
            return {"_label": value["_LABEL"], **_props(value)}
        return {k: _clean(v, seen) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v, seen) for v in value]
    if isinstance(value, str) and _ID.match(value):
        seen["edge_ids" if value.startswith("E-") else "node_ids"].add(value)
    return value


def _props(value: dict) -> dict:
    return {k: v for k, v in value.items() if not k.startswith("_")}
