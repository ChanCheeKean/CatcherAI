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
        "definition": ("As-of hybrid retrieval over policies, precedents and memory-note text."),
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

CASE_NEEDS = {
    "C02": [
        ("router_triage", P, "Recognize descriptor confusion rather than assume fraud."),
        ("memory_graph", P, "Join the new descriptor to the merchant and prior card history."),
        ("memory_persistent", P, "Persist the non-dispute report and its evidence trajectory."),
        ("agents", S, "Test the unfamiliar-merchant hypothesis against graph history."),
    ],
    "C04": [
        ("sandbox", P, "Reconcile two equal clearings to one authorization and order total."),
        ("harness", P, "Validate the complete proof path and capture it in the trajectory."),
        ("memory_graph", P, "Connect both clearings to the order and separate shipments."),
    ],
    "C08": [
        ("subagents", P, "Compare victim histories and the terminal window in parallel."),
        ("memory_graph", P, "Find the common terminal across later fraud disputes."),
        ("sandbox", S, "Aggregate transactions inside the compromise window."),
    ],
    "C10": [
        ("skills", P, "Apply generic household-authority guidance."),
        ("memory_graph", P, "Reach the authorized user through device and account edges."),
        ("agent_graph", S, "Return specialist findings to the supervisor for closure."),
    ],
    "C11": [
        ("agents", P, "Revise the friendly-fraud hypothesis after finding takeover facts."),
        ("agent_graph", P, "Loop from contradictory findings through a revised plan."),
        ("write_paths", P, "Retract the stale note and record the supported cluster finding."),
        ("read_paths", S, "Treat the historical note as a lead and verify it."),
    ],
    "C12": [
        ("subagents", P, "Fan out over linked claimants and merge component findings."),
        ("memory_graph", P, "Traverse shared phone, device and address components."),
        ("write_paths", P, "Record a bounded, evidence-backed ring finding."),
    ],
    "C12b": [
        ("tool_calling", P, "Query temporal ownership, delivery and evidence-request facts."),
        ("skills", P, "Apply the cardholder-favourable missing-evidence default."),
        ("read_paths", P, "Use phone validity windows instead of a timeless shared-ID match."),
    ],
    "C13": [
        ("router_triage", P, "Classify an agentic transaction as a novel investigation."),
        ("memory_semantic", P, "Retrieve mandate and agentic-transaction guidance."),
        ("sandbox", P, "Calculate the amount outside the mandate ceiling."),
        ("tool_calling", S, "Inspect token, provider, mandate and order facts."),
    ],
    "C18": [
        ("loop_termination", P, "Stop after matching the credit and resolving the remainder."),
        ("sandbox", P, "Reconcile prior credit against the disputed purchase without duplication."),
        ("memory_graph", S, "Match an unlinked credit through the shared order."),
    ],
    "C19": [
        ("memory_semantic", P, "Retrieve the older merchant reputation note as a lead."),
        ("read_paths", P, "Prefer newer graph facts that contradict the stale note."),
        ("agents", P, "Reverse the initial reputation-based hypothesis."),
        ("write_paths", S, "Supersede the contradicted merchant memory."),
    ],
}


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
