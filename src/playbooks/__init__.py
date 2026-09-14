"""Route playbooks: one plain module per route id in `config/routes.yaml`.

Adding a route means adding a route entry and a module named after its id. The graph calls
these module-level hooks; only `investigate` and `decide` are required.

    STEPS                               initial ordered steps: gather_evidence, ask_cardholder,
                                        run_specialists, analyze_tracks
    investigate(ctx, state)             initial retrieval, memory leads, findings -> state update
    evidence_request(ctx, state)        request details when evidence is not yet available
    on_evidence(ctx, state, packets)    interpret available evidence -> state update
    cardholder_question(ctx, state)     {"question", "rationale", "channel"}
    on_reply(ctx, state, reply)         interpret a cardholder reply -> state update
    on_timeout(ctx, state, wait)        awaited event absent at the latest safe time
    specialists(ctx, state)             (state update, Deep Agents task delegations)
    tracks(ctx, state) / analyze_track  independent parallel branches (LangGraph Send)
    verify(ctx, state)                  verifier checks (runtime.context.check)
    replan(ctx, state)                  back-edge after a remediable verifier failure
    decide(ctx, state)                  proposed DecisionRecord (governance may amend it)
    hypotheses(ctx, state)              competing-hypotheses board for the review panel
    curate(ctx, state)                  in-case memory maintenance -> state update

Every hook must reach data through `ctx` (tools, stores, sandbox) so that each step emits
its canonical trajectory event.
"""

from __future__ import annotations

import importlib
from types import ModuleType


def load_playbook(route_id: str) -> ModuleType:
    return importlib.import_module(f"{__name__}.{route_id}")
