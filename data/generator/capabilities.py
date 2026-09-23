"""Architecture capability coverage for the graph-discovery case set."""

from __future__ import annotations

CAPABILITIES = {
    "agents": {
        "label": "Agents",
        "definition": (
            "Goal-directed investigators revise hypotheses and choose what evidence to pursue."
        ),
        "trajectory_signals": ["triage", "supervisor_turn", "plan_updated"],
    },
    "router_triage": {
        "label": "Router / triage",
        "definition": (
            "Structured LLM classification and an initial evidence plan, including novel cases."
        ),
        "trajectory_signals": ["triage {case_type, hypotheses, plan}"],
    },
    "loop_termination": {
        "label": "Loop termination",
        "definition": (
            "Explicit decided, max-turn and no-progress endings with a closed-plan precondition."
        ),
        "trajectory_signals": ["termination {reason}", "edge_taken"],
    },
    "agent_graph": {
        "label": "Agent graph",
        "definition": (
            "LangGraph control flow with supervisor revisits, parallel workers and adjudication."
        ),
        "trajectory_signals": ["node_entered", "node_exited", "edge_taken"],
    },
    "subagents": {
        "label": "Subagents",
        "definition": ("Specialist Deep Agents receive scoped tasks and may run in parallel."),
        "trajectory_signals": ["delegation_started", "delegation_finished"],
    },
    "tool_calling": {
        "label": "Tool calling",
        "definition": "Typed graph, knowledge, memory and computation tools used by workers.",
        "trajectory_signals": ["tool_call {tool, args}", "tool_result {node_ids, edge_ids}"],
    },
    "harness": {
        "label": "Harness",
        "definition": (
            "Deterministic scenario loading, trajectory capture and ground-truth evaluation."
        ),
        "trajectory_signals": ["run_started", "termination", "eval result"],
    },
    "skills": {
        "label": "Skills",
        "definition": "Generic investigation and policy knowledge loaded for a delegated task.",
        "trajectory_signals": ["skill_loaded {skill}"],
    },
    "memory_persistent": {
        "label": "Memory — persistent",
        "definition": (
            "Durable checkpoints, trajectories and reports preserve exact run state for replay."
        ),
        "trajectory_signals": ["checkpoint persisted", "event replay", "decision persisted"],
    },
    "memory_graph": {
        "label": "Memory — graph",
        "definition": (
            "Temporal multi-hop evidence retrieval and provenance-bearing inferred graph writes."
        ),
        "trajectory_signals": ["graph_query", "graph_write"],
    },
    "memory_semantic": {
        "label": "Memory — semantic",
        "definition": "Hybrid retrieval over policy clauses, precedents and Memory Notes.",
        "trajectory_signals": ["tool_call {tool: search_knowledge}"],
    },
    "sandbox": {
        "label": "Sandbox / Python",
        "definition": "Bounded Python execution for reconciliation, dates and aggregation.",
        "trajectory_signals": ["tool_call {tool: python}"],
    },
    "read_paths": {
        "label": "Agent read paths",
        "definition": (
            "Selective graph and knowledge reads that verify temporal scope and stale notes."
        ),
        "trajectory_signals": ["tool_result {node_ids, edge_ids}", "search_knowledge"],
    },
    "write_paths": {
        "label": "Agent write paths",
        "definition": (
            "Provenance-backed findings and memory write, supersede, retract or merge operations."
        ),
        "trajectory_signals": ["graph_write", "memory_write"],
    },
}

P, S = "primary", "supporting"

CASE_NEEDS = {}


def required_capabilities(code: str) -> list[dict]:
    """Return evaluator requirements for one case code."""
    return [
        {
            "capability": capability,
            "label": CAPABILITIES[capability]["label"],
            "necessity": necessity,
            "why": why,
            "trajectory_signals": CAPABILITIES[capability]["trajectory_signals"],
        }
        for capability, necessity, why in CASE_NEEDS[code]
    ]


def coverage() -> dict[str, dict]:
    """Return capability-first coverage used by evaluation and documentation."""
    result = {}
    for capability, metadata in CAPABILITIES.items():
        uses = [
            (code, necessity, why)
            for code, needs in CASE_NEEDS.items()
            for name, necessity, why in needs
            if name == capability
        ]
        result[capability] = {
            **metadata,
            "primary_cases": [code for code, necessity, _ in uses if necessity == P],
            "supporting_cases": [code for code, necessity, _ in uses if necessity == S],
            "why": {code: why for code, _, why in uses},
        }
    return result
