"""Investigation tools. Each call emits `tool_call`/`tool_result` events that carry
the graph ids it touched; errors go back to the agent as text, never as exceptions."""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

import notebook
from domain.events import Actor, ActorKind, EventDraft
from graph_store import GraphStore
from memory import retrieval
from observability.emitter import EventEmitter

MAX_TEXT = 1200
READ_ONLY_TOOLS = frozenset(
    {
        "graph_schema",
        "graph_query",
        "graph_neighbors",
        "graph_find",
        "search_knowledge",
        "notebook_read",
    }
)
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
    notebook_db: Path
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
    id: str = Field(description="Node id from the evidence graph.")
    rel_types: list[str] | None = Field(default=None, description="Only these edge types.")
    direction: Literal["out", "in", "both"] = "both"


class FindArgs(BaseModel):
    text: str
    labels: list[str] | None = None


class KnowledgeArgs(BaseModel):
    query: str
    kinds: list[Literal["policy", "precedent", "memory_note"]] = Field(
        default=["policy", "precedent", "memory_note"]
    )


class NotebookWriteArgs(BaseModel):
    kind: Literal[*notebook.KINDS]
    text: str
    node_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)


class NotebookReadArgs(BaseModel):
    kinds: list[Literal[*notebook.KINDS]] | None = None
    author: str | None = None


class MemoryArgs(BaseModel):
    op: Literal["write", "supersede", "retract", "merge"]
    text: str = Field(default="", description="Note text (write, supersede, merge).")
    sources: list[str] = Field(
        description="Graph or knowledge document ids supporting the Memory Note."
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

    def graph_neighbors(id: str, rel_types: list[str] | None, direction: str) -> dict:
        return run.store.neighbors(id, rel_types, direction)

    def graph_find(text: str, labels: list[str] | None) -> dict:
        return run.store.find(text, labels)

    def search_knowledge(query: str, kinds: list[str]) -> dict:
        docs = retrieval.search(run.knowledge_db, query, kinds=tuple(kinds)) if kinds else []
        graph_ids = []
        for doc in docs:
            try:
                run.store.node(doc["doc_id"])
            except ValueError:
                continue
            graph_ids.append(doc["doc_id"])
        return {
            "results": [_clip(d) for d in docs],
            "node_ids": graph_ids,
            "edge_ids": [],
        }

    def notebook_write(kind: str, text: str, node_ids: list[str], edge_ids: list[str]) -> dict:
        for node_id in node_ids:
            run.store.node(node_id)
        if edge_ids:
            found = run.store.query(
                "MATCH ()-[r]->() WHERE r.id IN $ids RETURN r.id",
                {"ids": edge_ids},
                row_cap=len(edge_ids),
            )
            missing = set(edge_ids) - {row[0] for row in found["rows"]}
            if missing:
                raise ValueError(f"unknown edge ids: {', '.join(sorted(missing))}")
        out = notebook.write_entry(
            run.notebook_db, run.run_id, run.actor, kind, text, node_ids, edge_ids
        )
        _emit(run, "notebook_write", "notebook_write", {"kind": kind, "text": text}, out)
        return out

    def notebook_read(kinds: list[str] | None, author: str | None) -> dict:
        entries = notebook.read_entries(run.notebook_db, run.run_id, kinds, author)
        return {
            "entries": entries,
            "node_ids": sorted({i for e in entries for i in e["node_ids"]}),
            "edge_ids": sorted({i for e in entries for i in e["edge_ids"]}),
        }

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
                retrieval.set_status(run.knowledge_db, note_id, "retracted")
            out = {"retracted": replaces, "node_ids": [], "edge_ids": []}
        else:
            status = "merged" if op == "merge" else "superseded"
            note_id = retrieval.add_note(run.knowledge_db, text, sources, run.run_id, confidence)
            for old_id in replaces:
                retrieval.set_status(run.knowledge_db, old_id, status)
            out = {"note_id": note_id, "replaced": replaces, "node_ids": [], "edge_ids": []}
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
            "node/edge ids they contain. Quote labels with backticks when they are Cypher "
            "keywords. Long results are truncated.",
            QueryArgs,
            graph_query,
        ),
        _tool(
            run,
            "graph_neighbors",
            "Expand the edges around a node, optionally limited to edge types and a direction.",
            NeighborsArgs,
            graph_neighbors,
        ),
        _tool(
            run,
            "graph_find",
            "Find nodes by a case-insensitive substring in their string properties.",
            FindArgs,
            graph_find,
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
            "notebook_write",
            "Record a cited finding in this run's Case Notebook.",
            NotebookWriteArgs,
            notebook_write,
        ),
        _tool(
            run,
            "notebook_read",
            "Read this run's Case Notebook entries.",
            NotebookReadArgs,
            notebook_read,
        ),
        _tool(
            run,
            "memory_write",
            "Write, supersede, retract or merge a Memory Note with source ids.",
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
                **({"entry": result} if type_ == "notebook_write" else {}),
                "node_ids": node_ids,
                "edge_ids": edge_ids,
            },
            refs=[*node_ids, *edge_ids],
        )
    )


def _clip(value: Any) -> Any:
    """Shorten long strings so one result can't flood the agent's context."""
    if isinstance(value, str):
        return value if len(value) <= MAX_TEXT else value[:MAX_TEXT] + "…[truncated]"
    if isinstance(value, dict):
        return {k: _clip(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clip(v) for v in value]
    return value
