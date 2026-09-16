"""Required architecture capabilities and the cases that need them.

Single source of truth for:
  - ground_truth/cases/*.json  -> `required_capabilities`
  - ground_truth/capability_coverage.json
  - the capability table in docs/design/02-case-catalog.md

necessity: "primary"    = the case cannot be solved correctly without this capability
           "supporting" = used in the expected solution but not decisive on its own
"""
from __future__ import annotations

CAPABILITIES = {
    "agents": dict(
        label="Agents",
        definition="Goal-directed investigators that choose what evidence to pursue next and revise hypotheses.",
        trajectory_signals=["plan_created", "plan_updated (agent-initiated)", "hypothesis_updated"]),
    "router": dict(
        label="Router",
        definition="LLM classification over a described menu of routes (not-a-dispute, regime, claim family, depth, case split, novel type, portfolio priority), with a confidence-gated conservative fallback.",
        trajectory_signals=["route_decision {route_id, method: llm|fallback, confidence}"]),
    "loop_termination": dict(
        label="Loop engineering (real termination conditions)",
        definition="Explicit stop reasons: decision complete + verified, early stop, suspend/resume on external events, budget, no-progress, max re-plans, conservative default.",
        trajectory_signals=["termination {reason}", "wait_suspended {until, latest_safe_decision}", "wait_resumed"]),
    "agent_graph": dict(
        label="Agent graph engineering",
        definition="LangGraph nodes/edges with back-edges (verify → re-plan), conditional routing, parallel branches and the review-panel node.",
        trajectory_signals=["node_entered / node_exited", "edge_taken {from, to} incl. back-edges"]),
    "subagents": dict(
        label="Subagents",
        definition="Specialist subagents with isolated context, incl. parallel fan-out and the advocate/adjudicator review panel.",
        trajectory_signals=["subagent_started {name, parent_span_id}", "subagent_finished {result_summary}", "panel_position / adjudication"]),
    "tool_calling": dict(
        label="Tool / function calling",
        definition="Typed tools over data, evidence requests, research, messaging, case actions, memory and sandbox.",
        trajectory_signals=["tool_call {tool, args}", "tool_result {status, source_ids}"]),
    "harness": dict(
        label="Harness",
        definition="Virtual clock and available_at gating, simulated cardholder personas, scenario loading, budgets, trajectory capture, evaluation.",
        trajectory_signals=["clock_advanced", "evidence_arrived {packet_id}", "persona_reply", "eval_scored"]),
    "skills": dict(
        label="Skills",
        definition="Route-selected playbooks loaded on demand (Deep Agents SKILL.md).",
        trajectory_signals=["skill_loaded {skill}"]),
    "memory_persistent": dict(
        label="Memory — persistent (SQLite system of record)",
        definition="Exact queries over transactions, statements, events, case state and memory-note lifecycle.",
        trajectory_signals=["tool_call sql_query / get_* with row ids in tool_result"]),
    "memory_graph": dict(
        label="Memory — graph",
        definition="Multi-hop traversal over customers, cards, devices, IPs, phones, addresses, merchants and disputes; graph writes of findings.",
        trajectory_signals=["graph_query {cypher|pattern, node_ids}", "graph_write {node|edge, status}"]),
    "memory_semantic": dict(
        label="Memory — semantic / vector",
        definition="Similarity + keyword retrieval over policies, precedents, communications, research and notes, filtered by effective date/validity.",
        trajectory_signals=["retrieval {query, filters: as_of/status/validity, doc_ids}"]),
    "sandbox": dict(
        label="Sandbox / REPL",
        definition="Code execution for dates, business days, billing cycles, pro-rata, FX, time zones, grouping and analytics.",
        trajectory_signals=["computation {code, inputs, output}"]),
    "read_paths": dict(
        label="Agent read paths (selective read)",
        definition="Scoped retrieval by case/entity/as-of/validity/status/confidence; memory treated as a lead and verified or rejected.",
        trajectory_signals=["memory_read {filters}", "memory_verified / memory_rejected {note_id, reason}"]),
    "write_paths": dict(
        label="Agent write paths (selective write, consolidation, forgetting)",
        definition="Agent decides whether to write; write gate validates; supersede/retract/consolidate/time-bound/purge; case actions; must-not-write rules.",
        trajectory_signals=["memory_write / memory_supersede / memory_retract / memory_consolidate / memory_purge", "write_rejected {reason}", "automated_action"]),
}

P, S = "primary", "supporting"

CASE_NEEDS = {
    "C01": [("tool_calling", P, "research tool finds the bankruptcy that waives the 13.1 waiting period; cluster query finds 4 other disputes"),
            ("memory_semantic", P, "retrieve the 13.1 waiver clause ('merchant is insolvent or bankrupt')"),
            ("memory_persistent", P, "statement transmitted 2026-08-26 anchors the Reg Z 60-day notice window"),
            ("skills", P, "pb-not-received checklist"),
            ("loop_termination", P, "stop without waiting 15 days or re-requesting evidence from a defunct merchant"),
            ("sandbox", S, "Reg Z deadline 2026-10-25"), ("write_paths", S, "optional merchant insolvency note"),
            ("router", S, "non-fraud → not_received"), ("agents", S, "decides research is worth one call")],
    "C02": [("router", P, "recognize a non-dispute (descriptor confusion) instead of a fraud workflow"),
            ("memory_graph", P, "descriptor history → merchant → 16 prior visits by the same card"),
            ("harness", P, "simulated cardholder reply arrives after ~4h on the virtual clock"),
            ("loop_termination", P, "terminate on withdrawal within ≤6 tool calls"),
            ("tool_calling", P, "clarification message + descriptor directory lookup"),
            ("write_paths", P, "selective write: no fraud report, no card reissue, no customer risk note")],
    "C03": [("router", P, "split one intake case into per-transaction decisions"),
            ("read_paths", P, "MEM-0150 ($25) conflicts with SOP v4 ($15) as of intake date — memory rejected"),
            ("write_paths", P, "supersede MEM-0150; write-off one transaction, dispute the other"),
            ("loop_termination", P, "write-off path stops immediately; $19.99 path waits for the packet due 11:00 ET"),
            ("harness", P, "available_at gating of MEP-90003-OI after AS_OF"),
            ("memory_semantic", S, "SOP-DSP-002 v3 vs v4 retrieval"), ("sandbox", S, "12-month lookback"),
            ("skills", S, "pb-eligibility-check")],
    "C04": [("sandbox", P, "group clearings by auth code; 2 × round(60.55 × 1.06) = 128.36"),
            ("memory_persistent", P, "clearing_seq/clearing_count/auth_amount on transactions"),
            ("harness", P, "packet at 12:00 ET and persona disclosure of the second delivery"),
            ("agents", S, "chooses to contact the cardholder after seeing quantity 2"),
            ("tool_calling", S, "evidence request + messaging"), ("loop_termination", S, "stop once cardholder confirms")],
    "C05": [("subagents", P, "parallel line-item analysis of the folio (destination fee / upgrade / parking)"),
            ("memory_semantic", P, "retrieve 12.5 and 13.3 exclusions phrased differently from the claim; find PRE-0007 to distinguish"),
            ("sandbox", P, "parking + tax = 105.60; denied portion 328.46; occupancy tax check"),
            ("agents", P, "weigh cardholder testimony against the initialed registration card"),
            ("memory_persistent", P, "rideshare transactions on arrival/departure corroborate 'no car'"),
            ("skills", P, "pb-lodging-te"), ("agent_graph", S, "verifier before partial decision"),
            ("read_paths", S, "precedent used as lead, not copied")],
    "C06": [("agent_graph", P, "verifier invalidates 13.2 → back-edge to re-plan → 13.5"),
            ("memory_semantic", P, "retrieve 13.2 as of the dispute date and the trial-notice duty ('not clearly advised')"),
            ("read_paths", P, "PRE-0012 and MEM-0160 filtered/flagged as decided under the superseded rule"),
            ("write_paths", P, "supersede MEM-0160"),
            ("sandbox", P, "unused portion 119.88 × 360/365 = 118.24"),
            ("skills", P, "pb-recurring-trial"), ("agents", S, "re-plans after verifier failure")],
    "C07": [("sandbox", P, "FX arithmetic shows EUR refund was complete; shortfall is rate movement"),
            ("router", P, "route to issuer fee SOP instead of a network dispute"),
            ("memory_semantic", P, "SOP-DSP-007 and cardholder agreement §9"),
            ("memory_persistent", S, "fx_rates reference + linked credit/fee transactions"), ("tool_calling", S, "reference lookups")],
    "C08": [("router", P, "debit → Reg E regime and clocks"),
            ("sandbox", P, "20 business days with bank holidays → 2026-11-10"),
            ("memory_graph", P, "common point of compromise across 9 other victims"),
            ("subagents", P, "graph analyst and Reg E clock specialist in parallel"),
            ("read_paths", P, "reject MEM-0152 / superseded CB-2025-03 (calendar days)"),
            ("write_paths", P, "graph edge SUSPECTED_COMPROMISE_POINT, watchlist, supersede MEM-0152"),
            ("skills", P, "pb-reg-e-clocks, pb-fraud-cnp"), ("memory_persistent", S, "deposits, alerts, first deposit date"),
            ("tool_calling", S, "evidence + research")],
    "C09": [("memory_semantic", P, "select the CE 3.0 version by projected dispute processing date"),
            ("read_paths", P, "as-of filter: VISA-10.4@2026-10-24 vs @2026-04-18"),
            ("harness", P, "persona only admits purchase after specific evidence (reply after ~25h virtual)"),
            ("agent_graph", P, "claim family changes fraud → quality complaint → re-route"),
            ("write_paths", P, "factual note only; must not write labels"),
            ("sandbox", P, "prior-transaction ages 220/164/46 days"),
            ("loop_termination", S, "suspend for cardholder reply"), ("skills", S, "pb-fraud-cnp")],
    "C10": [("subagents", P, "cardholder advocate + issuer advocate + adjudicator review panel"),
            ("agent_graph", P, "review-panel node gates the authority determination"),
            ("memory_graph", P, "card-added fingerprint = primary cardholder's phone; tablet shared with banking logins"),
            ("harness", P, "persona discloses February card entry only when asked specifically"),
            ("skills", P, "pb-automated-adjudication"),
            ("memory_semantic", S, "Reg Z comment 12(b)(1)(ii)-3; PRE-0010 distinction"),
            ("write_paths", S, "scheduled follow-up; notice of revoked authority recorded")],
    "C11": [("subagents", P, "security-events analyst, merchant-evidence analyst, graph analyst; panel for reopening"),
            ("memory_graph", P, "drop address → 4 disputed transactions → prior denied case"),
            ("read_paths", P, "MEM-0142 read as a lead and rejected after verification"),
            ("write_paths", P, "retract MEM-0142 + correction; reopen DSP-2026-04471; watchlist; account security actions"),
            ("agents", P, "overturns the initial first-party-misuse hypothesis"),
            ("agent_graph", P, "review-panel node for reopening"),
            ("memory_persistent", P, "security event sequence (phone change → VPN logins → reset)"),
            ("loop_termination", S, "long investigation within budget"), ("skills", S, "pb-fraud-cnp")],
    "C12": [("memory_graph", P, "ring component: shared banking devices + alternate phone across 4 customers"),
            ("subagents", P, "fan-out over 10 linked cases"),
            ("write_paths", P, "SuspectedRing graph write + bounded controls; must not touch CUS-90017"),
            ("agent_graph", P, "review-panel node for cross-customer finding"),
            ("loop_termination", P, "budgeted fan-out across linked cases"),
            ("skills", S, "pb-not-received"), ("memory_persistent", S, "dispute history per customer")],
    "C12b": [("memory_graph", P, "negative traversal result: no shared identifiers with the ring"),
             ("write_paths", P, "must not write ring linkage"),
             ("memory_semantic", S, "13.1 full-address requirement"), ("tool_calling", S, "evidence packet")],
    "C13": [("loop_termination", P, "suspend until the instruction record (2026-10-23T15:00Z) then resume; latest safe decision 2026-12-30"),
            ("harness", P, "virtual clock releases MEP-90015-APP only after its available_at"),
            ("router", P, "novel agentic-transaction route"),
            ("memory_semantic", P, "retrieve §4.1.24 and confirm no applicable dispute condition or precedent"),
            ("subagents", P, "review panel for a no-applicable-rule decision"),
            ("write_paths", P, "policy_gap_record"),
            ("tool_calling", P, "request_record to the agentic provider"),
            ("agent_graph", S, "wait → resume edge")],
    "C14": [("sandbox", P, "14:41 America/Los_Angeles = 17:41 America/New_York; one night + tax = 304.09"),
            ("memory_semantic", P, "find PRE-0019 and 13.7 no-show rules"),
            ("skills", P, "pb-lodging-te"), ("read_paths", S, "MEM-0221 lesson"), ("tool_calling", S, "evidence request")],
    "C15": [("agent_graph", P, "two charges on different lifecycle stages handled as parallel tracks"),
            ("memory_persistent", P, "case lifecycle state, response processing date, billing cycle day"),
            ("harness", P, "late Dispute Response event + persona certification reply"),
            ("sandbox", P, "pre-arb deadline 2026-11-15; Reg Z deadlines 2026-12-05 and 2027-01-05"),
            ("agents", P, "re-plans after late merchant evidence"),
            ("subagents", S, "per-charge track"), ("loop_termination", S, "wait for cardholder reply")],
    "C16": [("memory_semantic", P, "retrieve the listing snapshot captured on the purchase date"),
            ("read_paths", P, "select by captured_at, reject the current page"),
            ("tool_calling", P, "research tool over dated snapshots"),
            ("skills", S, "pb-eligibility-check (13.3 vs 13.7)")],
    "C17": [("loop_termination", P, "value-of-information stop: every formal remedy closed"),
            ("sandbox", P, "13.1 limit 2026-08-23; Reg Z notice deadline 2026-04-22; outstanding balance 0.00"),
            ("memory_persistent", P, "statements and payments prove pay-in-full"),
            ("router", P, "expired / redirect route"),
            ("memory_semantic", S, "§1026.12(c) and PRE-0017 distinction")],
    "C18": [("memory_persistent", P, "out-of-order credit with no original-transaction link"),
            ("sandbox", P, "reconcile double recovery; 5 business days honoring → 2026-10-28"),
            ("router", P, "Reg E + no network dispute"),
            ("loop_termination", P, "early stop once credit matched"),
            ("harness", S, "forwarded email and credit become visible on 2026-10-20"), ("tool_calling", S, "transactions lookup")],
    "C19": [("write_paths", P, "consolidate MEM-0201..0208 across two merchant IDs, time-bound, supersede MEM-0209"),
            ("read_paths", P, "validity-window filter exposes MEM-0209 as stale"),
            ("harness", P, "persona confirms delivery"),
            ("memory_graph", S, "merge near-duplicate merchants"), ("tool_calling", S, "research"), ("loop_termination", S, "withdrawal")],
    "Q01": [("router", P, "portfolio-level prioritization by earliest hard deadline"),
            ("subagents", P, "per-case clock computation fan-out"),
            ("sandbox", P, "Reg Z cycles, Reg E business days, pre-arb deadlines for 95 open cases"),
            ("memory_persistent", P, "open case state across the portfolio"),
            ("agent_graph", S, "batch map-reduce"), ("harness", S, "batch scenario run")],
}

MUST_NOT_WRITE = {
    "C02": ["fraud report", "card reissue", "customer risk or fraud note"],
    "C09": ["labels such as fraudster, abuser, liar"],
    "C12b": ["SuspectedRing membership or linkage for CUS-90017"],
    "C12": ["account closure or restriction for any ring member"],
}


def required_capabilities(code: str) -> list:
    return [dict(capability=c, label=CAPABILITIES[c]["label"], necessity=n, why=w,
                 trajectory_signals=CAPABILITIES[c]["trajectory_signals"]) for c, n, w in CASE_NEEDS.get(code, [])]


def coverage() -> dict:
    out = {}
    for cap, meta in CAPABILITIES.items():
        rows = [(code, n, w) for code, needs in CASE_NEEDS.items() for c, n, w in needs if c == cap]
        out[cap] = dict(label=meta["label"], definition=meta["definition"], trajectory_signals=meta["trajectory_signals"],
                        primary_cases=[r[0] for r in rows if r[1] == P], supporting_cases=[r[0] for r in rows if r[1] == S],
                        why={r[0]: r[2] for r in rows})
    return out


def markdown_table() -> str:
    lines = ["| Required capability | Cases that **cannot be solved** without it (primary) | Also used in | Proof in the trajectory |",
             "|---|---|---|---|"]
    for cap, row in coverage().items():
        lines.append(f"| **{row['label']}** | {', '.join(row['primary_cases'])} | {', '.join(row['supporting_cases']) or '—'} | "
                     f"{'; '.join(row['trajectory_signals'])} |")
    return "\n".join(lines)
