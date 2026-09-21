"""The seven tools every worker shares. Each call emits `tool_call`/`tool_result` events that carry
the graph ids it touched; errors go back to the agent as text, never as exceptions."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from domain.events import Actor, ActorKind, EventDraft
from graph_store import GraphStore
from memory import retrieval
from observability.emitter import EventEmitter

MAX_TEXT = 1200
PYTHON_TIMEOUT_SECONDS = 10
PYTHON_MODULES = ("datetime", "decimal", "math", "statistics", "collections", "json", "zoneinfo")
_PYTHON_RUNNER = f"""
import builtins, sys
for _m in {PYTHON_MODULES!r}:
    __import__(_m)
_import = builtins.__import__
def _guarded(name, globals=None, locals=None, fromlist=(), level=0):
    caller = (globals or {{}}).get("__name__")
    if caller == "__main__" and name.split(".")[0] not in {PYTHON_MODULES!r}:
        raise ImportError(f"only {{', '.join({PYTHON_MODULES!r})}} may be imported")
    return _import(name, globals, locals, fromlist, level)
builtins.__import__ = _guarded
exec(compile(sys.stdin.read(), "<python tool>", "exec"), {{"__name__": "__main__"}})
"""


@dataclass
class Run:
    """Everything the tools need for one run; `actor` names the agent making the calls."""

    store: GraphStore
    emitter: EventEmitter
    run_id: str
    knowledge_db: Path
    as_of: date
    actor: str = "worker"
    visit: int = 1
    turn: int = 0
    parent_id: str | None = None


class SchemaArgs(BaseModel):
    pass


class QueryArgs(BaseModel):
    cypher: str = Field(description="Read-only Cypher. Use $name parameters for values.")
    params: dict[str, Any] = Field(default_factory=dict, description="Values for $parameters.")


class NeighborsArgs(BaseModel):
    id: str = Field(description="Node id such as CUS-… or TXN-…")
    rel_types: list[str] | None = Field(default=None, description="Only these edge types.")
    direction: Literal["out", "in", "both"] = "both"
    since: str = Field(default="", description="ISO date: keep edges still valid on/after it.")
    until: str = Field(default="", description="ISO date: keep edges already valid by it.")


class EdgeSpec(BaseModel):
    type: str = Field(description="Inferred edge type, e.g. SUPPORTS, SAME_ACTOR, COMPROMISED_AT.")
    src: str | None = Field(default=None, description="Source node id; defaults to the finding.")
    dst: str = Field(description="Destination node id.")


class FindingArgs(BaseModel):
    text: str = Field(description="What was established, in one or two sentences.")
    kind: str = Field(default="", description="Short label, e.g. 'shared_device'.")
    confidence: float = Field(ge=0, le=1)
    evidence_path: str = Field(default="", description="Ids or a path that prove the finding.")
    edges: list[EdgeSpec] = Field(default_factory=list)


class KnowledgeArgs(BaseModel):
    query: str
    kinds: list[Literal["policy", "precedent", "memory_note"]] = Field(
        default=["policy", "precedent", "memory_note"]
    )
    as_of: str = Field(
        default="", description="ISO date the policy must be in force; default: run."
    )


class MemoryArgs(BaseModel):
    op: Literal["write", "supersede", "retract", "merge"]
    text: str = Field(default="", description="Note text (write, supersede, merge).")
    sources: list[str] = Field(
        description="Node ids the note is about; every note must cite at least one."
    )
    replaces: list[str] = Field(
        default_factory=list,
        description="MEM- ids: the note to supersede or retract, or the notes to merge.",
    )
    confidence: float = Field(default=0.8, ge=0, le=1)


class PythonArgs(BaseModel):
    code: str = Field(description=f"Python using only {', '.join(PYTHON_MODULES)}; print results.")


def make_tools(run: Run) -> list[BaseTool]:
    def graph_schema() -> dict:
        return run.store.schema()

    def graph_query(cypher: str, params: dict) -> dict:
        return run.store.query(cypher, params)

    def graph_neighbors(
        id: str, rel_types: list[str] | None, direction: str, since: str, until: str
    ) -> dict:
        return run.store.neighbors(id, rel_types, direction, since, until)

    def graph_write_finding(
        text: str, kind: str, confidence: float, evidence_path: str, edges: list[EdgeSpec]
    ) -> dict:
        args = {
            "text": text,
            "kind": kind,
            "confidence": confidence,
            "evidence_path": evidence_path,
        }
        out = run.store.write_finding(
            run_id=run.run_id, edges=[e.model_dump(exclude_none=True) for e in edges], **args
        )
        _emit(run, "graph_write", "graph_write_finding", args, out)
        return {**out, "node_ids": [out["finding_id"]], "edge_ids": out["edge_ids"]}

    def search_knowledge(query: str, kinds: list[str], as_of: str) -> dict:
        when = date.fromisoformat(as_of) if as_of else run.as_of
        docs = retrieval.search(
            run.knowledge_db,
            query,
            as_of=when,
            kinds=tuple(k for k in kinds if k != "memory_note"),
        )
        hits = [
            {k: _clip(d[k]) for k in ("doc_id", "kind", "title", "body", "valid_from", "valid_to")}
            for d in docs
        ]
        notes = _search_notes(run.store, query) if "memory_note" in kinds else []
        return {"results": hits + notes, "node_ids": [n["id"] for n in notes], "edge_ids": []}

    def memory_write(
        op: str, text: str, sources: list[str], replaces: list[str], confidence: float
    ) -> dict:
        if op in ("supersede", "retract", "merge") and not replaces:
            raise ValueError(f"{op} needs `replaces` (the MEM- ids)")
        if op in ("write", "supersede", "merge") and not text:
            raise ValueError(f"{op} needs `text`")
        if op == "merge" and len(replaces) < 2:
            raise ValueError("merge needs at least two notes in `replaces`")
        if not sources:
            raise ValueError("a memory note must cite at least one source node id")
        if op == "retract":
            for note_id in replaces:
                run.store.set_note_status(note_id, "retracted")
            out = {"retracted": replaces, "node_ids": replaces, "edge_ids": []}
        else:
            status = "merged" if op == "merge" else "superseded"
            out = run.store.write_note(text, run.run_id, confidence, sources, replaces, status)
            out = {**out, "node_ids": [out["note_id"], *replaces], "replaced": replaces}
        _emit(run, "memory_write", "memory_write", {"op": op, "sources": sources}, out)
        return out

    def python(code: str) -> dict:
        try:
            done = subprocess.run(
                [sys.executable, "-I", "-c", _PYTHON_RUNNER],
                input=code,
                capture_output=True,
                text=True,
                timeout=PYTHON_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            raise ValueError(f"python timed out after {PYTHON_TIMEOUT_SECONDS}s") from None
        if done.returncode:
            raise ValueError(done.stderr.strip().splitlines()[-1] if done.stderr else "failed")
        return {"stdout": done.stdout[:4000], "node_ids": [], "edge_ids": []}

    return [
        _tool(
            run,
            "graph_schema",
            "Node labels, edge types, their properties and row counts of the evidence graph.",
            SchemaArgs,
            graph_schema,
        ),
        _tool(
            run,
            "graph_query",
            "Run read-only Cypher (paths allowed) on the evidence graph; returns rows and the "
            "node/edge ids they contain. Long results are truncated.",
            QueryArgs,
            graph_query,
        ),
        _tool(
            run,
            "graph_neighbors",
            "Expand the edges around a node, optionally limited to edge types, a direction and a "
            "since/until window on the edges' valid_from/valid_to.",
            NeighborsArgs,
            graph_neighbors,
        ),
        _tool(
            run,
            "graph_write_finding",
            "Record an inferred Finding in the graph with confidence, the evidence path and "
            "inferred edges (SUPPORTS, CONTRADICTS, SAME_ACTOR, ABOUT, COMPROMISED_AT).",
            FindingArgs,
            graph_write_finding,
        ),
        _tool(
            run,
            "search_knowledge",
            "Hybrid keyword + vector search over policies, precedents and active memory notes.",
            KnowledgeArgs,
            search_knowledge,
        ),
        _tool(
            run,
            "memory_write",
            "Write, supersede, retract or merge a MemoryNote. Notes must cite source node ids.",
            MemoryArgs,
            memory_write,
        ),
        _tool(
            run,
            "python",
            "Run Python for arithmetic, dates, currency and aggregation. No files or network.",
            PythonArgs,
            python,
        ),
    ]


def _tool(
    run: Run, name: str, description: str, schema: type[BaseModel], fn: Callable[..., dict]
) -> BaseTool:
    def call(**kwargs: Any) -> str:
        args = schema(**kwargs)
        call_id = uuid.uuid4().hex[:8]
        arguments = args.model_dump()
        _emit(run, "tool_call", name, arguments, call_id=call_id)
        try:
            result = fn(**{k: getattr(args, k) for k in schema.model_fields})
        except Exception as error:  # noqa: BLE001 - every failure is returned to the agent
            result = {"error": f"{type(error).__name__}: {error}"}
        result = _clip(result)
        _emit(run, "tool_result", name, arguments, result, call_id=call_id)
        return json.dumps(result, default=str)

    return StructuredTool.from_function(
        func=call, name=name, description=description, args_schema=schema
    )


def _emit(
    run: Run,
    type_: str,
    tool: str,
    arguments: dict,
    result: dict | None = None,
    *,
    call_id: str = "",
) -> None:
    result = result or {}
    node_ids, edge_ids = result.get("node_ids", []), result.get("edge_ids", [])
    error = result.get("error")
    run.emitter.emit(
        EventDraft(
            actor=Actor(kind=ActorKind.TOOL, name=tool),
            visit=run.visit,
            turn=run.turn,
            parent_id=run.parent_id,
            type=type_,
            summary=f"{run.actor} {type_.replace('_', ' ')}: {tool}"
            + (f" failed: {error}" if error else ""),
            payload={
                "caller": run.actor,
                "tool": tool,
                "call_id": call_id,
                "args": arguments,
                **({"result": result} if type_ == "tool_result" else {}),
                "node_ids": node_ids,
                "edge_ids": edge_ids,
            },
            refs=[*node_ids, *edge_ids],
        )
    )


def _search_notes(store: GraphStore, query: str, limit: int = 5) -> list[dict]:
    """Rank active MemoryNotes by how many query words they contain."""
    words = {w for w in retrieval.TOKEN_RE.findall(query.casefold()) if len(w) > 2}
    rows = store.query(
        "MATCH (m:MemoryNote) WHERE m.status = 'active' RETURN m.id, m.text",
        row_cap=1000,
    )["rows"]
    scored = [
        (
            sum(w in text.casefold() for w in words),
            {"id": note_id, "kind": "memory_note", "text": text},
        )
        for note_id, text in rows
    ]
    return [n for score, n in sorted(scored, key=lambda s: -s[0])[:limit] if score]


def _clip(value: Any) -> Any:
    """Shorten long strings so one result can't flood the agent's context."""
    if isinstance(value, str):
        return value if len(value) <= MAX_TEXT else value[:MAX_TEXT] + "…[truncated]"
    if isinstance(value, dict):
        return {k: _clip(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clip(v) for v in value]
    return value
