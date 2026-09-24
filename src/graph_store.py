"""LadybugDB evidence store: bulk load and read-only Cypher."""

from __future__ import annotations

import csv
import json
import re
import tempfile
import threading
import weakref
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
    store = GraphStore(db_path, read_only=False)
    nodes, edges = ontology["nodes"], ontology["edges"]
    for label, spec in nodes.items():
        cols = "".join(f", {k} {p['type']}" for k, p in spec["props"].items())
        store.conn.execute(f"CREATE NODE TABLE `{label}`(id STRING PRIMARY KEY{cols})")
    for etype, spec in edges.items():
        pairs = ", ".join(f"FROM `{s}` TO `{d}`" for s, d in spec["pairs"])
        cols = "".join(f", {k} {p['type']}" for k, p in spec["props"].items())
        store.conn.execute(f"CREATE REL TABLE `{etype}`({pairs}, id STRING{cols})")

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
            # csv.writer's dialect, stated so Ladybug never guesses it from a sample of rows.
            opts = "header=false, parallel=false, auto_detect=false, "
            opts += "delim=',', quote='\"', escape='\"'"
            if len(key) == 3:
                opts += f", from='{key[1]}', to='{key[2]}'"
            store.conn.execute(f"COPY `{key[0]}` FROM '{path}' ({opts})")
    return store


def _jsonl(path: Path):
    with path.open() as f:
        for line in f:
            yield json.loads(line)


_DATABASES: weakref.WeakValueDictionary[tuple[str, bool], lb.Database] = (
    weakref.WeakValueDictionary()
)
_DATABASES_LOCK = threading.Lock()


def _database(path: Path, read_only: bool) -> lb.Database:
    """One Database per file and process.

    Each Database reserves a huge address range, so parallel workers share one and
    take their own Connection.
    """

    key = (str(path.resolve()), read_only)
    with _DATABASES_LOCK:
        database = _DATABASES.get(key)
        if database is None:
            database = _DATABASES[key] = lb.Database(str(path), read_only=read_only)
        return database


class GraphStore:
    def __init__(self, db_path: Path, read_only: bool = True) -> None:
        self.db_path = Path(db_path)
        self.conn = lb.Connection(_database(self.db_path, read_only))
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
        """Ontology descriptions, groups, properties and graph counts."""
        nodes = {
            label: {
                "group": spec["group"],
                "description": spec["description"],
                "props": spec["props"],
                "count": self._count(f"(n:`{label}`)"),
            }
            for label, spec in self.ontology["nodes"].items()
        }
        edges = {
            etype: {**spec, "count": self._count(f"()-[n:`{etype}`]->()")}
            for etype, spec in self.ontology["edges"].items()
        }
        return {"groups": self.ontology["groups"], "nodes": nodes, "edges": edges}

    def size(self) -> dict[str, int]:
        """How many nodes and edges the whole graph holds."""
        return {"nodes": self._count("(n)"), "edges": self._count("()-[n]->()")}

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
        limit: int = 50,
    ) -> dict:
        """Return one-hop edges around a node."""
        label = self.label_of(node_id)
        found: list[dict] = []
        seen = _new_seen()
        for etype, spec in self.ontology["edges"].items():
            if rel_types and etype not in rel_types:
                continue
            for way in ("out", "in") if direction == "both" else (direction,):
                if not any(p[0 if way == "out" else 1] == label for p in spec["pairs"]):
                    continue
                arrow = f"-[r:`{etype}`]->" if way == "out" else f"<-[r:`{etype}`]-"
                result = self.conn.execute(
                    f"MATCH (a:`{label}` {{id: $id}}){arrow}(b) RETURN r, b LIMIT {limit + 1}",
                    {"id": node_id},
                )
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

    def node(self, node_id: str) -> dict:
        label = self.label_of(node_id)
        rows = self.query(f"MATCH (n:`{label}` {{id: $id}}) RETURN n", {"id": node_id}, 1)["rows"]
        if not rows:
            raise ValueError(f"no such node {node_id}")
        return rows[0][0]

    def find(self, text: str, labels: list[str] | None = None, limit: int = 25) -> dict:
        """Find nodes by case-insensitive substring in any string property."""
        matches: list[dict] = []
        seen = _new_seen()
        for label, spec in self.ontology["nodes"].items():
            if labels is not None and label not in labels:
                continue
            fields = ["id", *(k for k, p in spec["props"].items() if p["type"] == "STRING")]
            where = " OR ".join(f"lower(n.{field}) CONTAINS lower($text)" for field in fields)
            result = self.conn.execute(
                f"MATCH (n:`{label}`) WHERE {where} RETURN n LIMIT {limit}", {"text": text}
            )
            while result.has_next() and len(matches) < limit:
                matches.append(_clean(result.get_next()[0], seen))
            if len(matches) == limit:
                break
        return {"matches": matches, "node_ids": sorted(seen["node_ids"]), "edge_ids": []}

    def close(self) -> None:
        self.conn.close()


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
