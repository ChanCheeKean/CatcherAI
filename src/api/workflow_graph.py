"""Static workflow node/edge description for the React Flow workflow canvas.

This mirrors the graph actually wired in `runtime.langgraph_runtime.LangGraphRuntime._build_graph`.
It is hand-maintained rather than introspected because the node functions there are closures built
per-run; if that wiring changes, update this module in the same change.
"""

from __future__ import annotations

from api.models import WorkflowEdge, WorkflowGraph, WorkflowNode

_NODE_KINDS: dict[str, str] = {
    "run_start": "deterministic",
    "load_case": "deterministic",
    "route": "deterministic",
    "compute_clocks": "deterministic",
    "investigate": "agent",
    "assess_progress": "deterministic",
    "gather_evidence": "tool",
    "ask_cardholder": "agent",
    "await_external_event": "harness",
    "apply_external_event": "deterministic",
    "run_specialists": "subagent",
    "analyze_track": "subagent",
    "merge_tracks": "deterministic",
    "verify": "agent",
    "replan": "agent",
    "propose_decision": "agent",
    "governance_gate": "deterministic",
    "review_panel": "subagent",
    "record_decision": "deterministic",
    "execute_actions": "deterministic",
    "memory_maintenance": "memory",
    "terminate": "deterministic",
}

_FIXED_EDGES: list[tuple[str, str, bool]] = [
    ("__start__", "run_start", False),
    ("run_start", "load_case", False),
    ("load_case", "route", False),
    ("route", "compute_clocks", False),
    ("compute_clocks", "investigate", False),
    ("investigate", "assess_progress", False),
    ("ask_cardholder", "await_external_event", False),
    ("await_external_event", "apply_external_event", False),
    ("apply_external_event", "assess_progress", True),
    ("run_specialists", "assess_progress", True),
    ("analyze_track", "merge_tracks", False),
    ("merge_tracks", "assess_progress", True),
    ("replan", "assess_progress", True),
    ("propose_decision", "governance_gate", False),
    ("review_panel", "record_decision", False),
    ("record_decision", "execute_actions", False),
    ("execute_actions", "memory_maintenance", False),
    ("memory_maintenance", "terminate", False),
    ("terminate", "__end__", False),
]

_CONDITIONAL_EDGES: list[tuple[str, str, str]] = [
    ("assess_progress", "gather_evidence", "next planned step: gather_evidence"),
    ("assess_progress", "ask_cardholder", "next planned step: ask_cardholder"),
    ("assess_progress", "run_specialists", "next planned step: run_specialists"),
    ("assess_progress", "verify", "no remaining steps or forced stop"),
    ("gather_evidence", "await_external_event", "evidence not yet available"),
    ("gather_evidence", "assess_progress", "evidence already available"),
    ("verify", "replan", "verifier failed and replans remain"),
    ("verify", "propose_decision", "verifier passed or replans exhausted"),
    ("governance_gate", "review_panel", "SOP-DSP-003 panel required"),
    ("governance_gate", "record_decision", "panel not required"),
]

_FAN_OUT_EDGES: list[tuple[str, str, str]] = [
    ("assess_progress", "analyze_track", "fan out independent case tracks (Send)"),
]


def build_workflow_graph() -> WorkflowGraph:
    nodes = [
        WorkflowNode(id=node_id, label=node_id, kind=kind) for node_id, kind in _NODE_KINDS.items()
    ]
    edges = [
        WorkflowEdge(source=source, target=target, kind="fixed")
        for source, target, _back_edge in _FIXED_EDGES
    ]
    edges.extend(
        WorkflowEdge(source=source, target=target, kind="conditional", label=label)
        for source, target, label in _CONDITIONAL_EDGES
    )
    edges.extend(
        WorkflowEdge(source=source, target=target, kind="fan_out", label=label)
        for source, target, label in _FAN_OUT_EDGES
    )
    return WorkflowGraph(nodes=nodes, edges=edges)
