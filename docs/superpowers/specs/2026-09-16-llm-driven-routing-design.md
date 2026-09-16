# LLM-driven routing and supervisor loop

## Why

Two problems in the current runtime:

1. `src/config.py`'s `ConcurrencyConfig.model_calls` is dead config — only `concurrency.per_run`
   is ever read (it feeds `InstrumentedModelGateway`'s semaphore in
   `src/runtime/langgraph_runtime.py::_context`).
2. `src/routing.py::route_case` picks a case's operating profile by deterministic field
   matching against `config/routes.yaml` (`claim_family_initial == "fraud_cnp"`,
   `billing_total_min: 500`, etc.), and `assess_progress` in
   `src/runtime/langgraph_runtime.py` walks a pre-baked, fixed-order `steps` list instead of
   deciding anything at runtime. Neither decision point uses the model. The domain schema
   already anticipated fixing this: `RouteDecision.method` is typed
   `Literal["rule", "llm", "fallback"]` and the `router` capability's documented trajectory
   signal is `route_decision {route_id, method: rule|llm, confidence}` — LLM-based routing
   was designed in from day one and never wired up.

This changes both decision points to real model calls, while keeping the parts of the
system that are genuine domain/legal logic (not routing artifacts) exactly as they are.

## Non-goals

- Rewriting the 20 playbook modules (`src/playbooks/*.py`) into generic, fully dynamic
  agent-driven tool-calling. Confirmed by diffing `debit_fraud_l3.py` against
  `high_value_cnp_ato_l4.py`: even within one `claim_family`, the tool sequence, actors, and
  regulatory citations genuinely differ per scenario. That is real business logic, not
  "case matching," and rewriting it is a much larger project than this one.
- Making `RouteDecision.agents` load-bearing. It is decorative today — playbooks hardcode
  which specialists they delegate to (verified: `route["agents"]` is only ever read for
  logging, in `routing.py` and two playbook files). It stays decorative; the LLM still
  free-composes it (informational, and useful for capability-coverage trajectory checks),
  but nothing downstream branches on it.

## 1. Route decision becomes a real, free-composed LLM call

`route_case` in `src/routing.py` drops `_parse_expression`/`_compare`/the matching loop
entirely. It becomes:

1. Build the same feature dict as today (`claim_family_initial`, `regime`,
   `transaction_count`, `billing_total`, etc.).
2. Build a menu from `config/routes.yaml`: for each of the 20 entries, `id`, `description`
   (new field, replaces `match`), `depth`, and `required_skills` (new field, replaces the
   old fixed `skills` list — see §2).
3. Call the model (same `create_deep_agent` + JSON-parse pattern already used in
   `investigate()`) with the case features and the menu, asking for: `route_id`, `depth`,
   `agents` (free list), `skills` (free list), `budget` (free numeric object, same shape as
   `RouteBudget` plus a new `max_agent_calls` field — see §3), `confidence` (0–1),
   `rationale`.
4. If `route_id` isn't one of the known ids, or confidence is below
   `route_confidence_threshold` (0.80, unchanged), or the output fails to parse: fall back
   to the existing `novel_or_ambiguous` entry with `method="fallback"`. Otherwise
   `method="llm"`.
5. Union the LLM's `skills` with that route's `required_skills` (see §2) before returning.
6. Clamp every `budget` field into that route's depth-tier bounds (see §2) before returning.

`RouteDecision` and its emitted `route_decision` event payload shape don't change. `"rule"`
stays a valid `RouteDecision.method` value in the type (harmless) but is never produced.

## 2. `config/routes.yaml` restructuring + safety clamps

Each route entry's `match:` block is replaced with:

```yaml
- id: debit_fraud_l3
  depth: L3
  description: >
    Reg E card-not-present fraud with a cross-customer compromise point suspected.
  required_skills: [eligibility-check, reg-e-clocks, fraud-cnp]
```

(`description` is written from each playbook's module docstring / the old `match` intent —
this is the only place a human needs to hand-author text; everything else is mechanical.)
`output.graph_path`, `output.agents`, `output.budget` are dropped from the schema — they were
either dead (`graph_path` is unused for dispatch; `agents` is decorative) or superseded by
the LLM's free-composed budget.

A new top-level `depth_bounds` block gives the clamp range per depth, covering every
`RouteBudget` field including the new `max_agent_calls`:

```yaml
depth_bounds:
  L1: {tool_calls: [3, 10], model_input_tokens: [10000, 40000], model_output_tokens: [2000, 6000], wall_seconds: [30, 90], replans: [0, 1], no_progress_iterations: [1, 2], max_agent_calls: [3, 6]}
  L2: {...}
  L3: {...}
  L4: {tool_calls: [15, 35], model_input_tokens: [60000, 140000], model_output_tokens: [8000, 20000], wall_seconds: [120, 300], replans: [1, 3], no_progress_iterations: [2, 3], max_agent_calls: [8, 16]}
```

`RouteConfig` in `src/config.py` drops `match`/`RouteOutputConfig` in favor of `description`,
`depth`, `required_skills`; `RoutesConfig` gains `depth_bounds: dict[str, dict[str, tuple[int, int] | tuple[float, float]]]`.
`priority` is dropped (nothing left to order — selection is no longer first-match-wins), and
`RoutesConfig.unique_ordered_routes` is rewritten to just check id-uniqueness (drop the
priority sort).

Playbook dispatch (`load_playbook(route_id)`) is unchanged: `route_id` still names the
Python module, just chosen by the LLM instead of matched.

## 3. Supervisor loop replaces the fixed `steps` walk

`assess_progress` in `src/runtime/langgraph_runtime.py` currently does `next_step = steps[0]
if steps else "verify"` — a deterministic pop off a list built once from
`playbook.STEPS` in `investigate()`. It becomes a model call:

1. Build a compact state summary: case claim, `completed_steps`, current `findings` keys,
   evidence/specialist-result counts, iteration/stall counters, remaining tool-call budget.
2. Ask the model to pick one of the five actions the graph already supports as edges out of
   `assess_progress`: `gather_evidence`, `ask_cardholder`, `run_specialists`,
   `analyze_tracks`, `verify` — with a one-line rationale. The model may pick an action
   already in `completed_steps` (loop back) if it judges the current result insufficient;
   nothing here forces monotonic progress through a list anymore.
3. A new `agent_calls` counter in `WorkflowState` increments every time this call happens.
   Existing forced-stop checks (`budget_exhausted`, `no_progress`) run first and still take
   priority; a new check `agent_calls >= route["budget"]["max_agent_calls"]` is added right
   alongside them, setting `forced_stop="max_agent_calls_reached"` (added to the
   `FORCED_STOPS` tuple) and `next_step="verify"` — same mechanism the other forced stops
   already use, so it flows straight into the existing
   `verify → propose_decision → governance_gate → record_decision → terminate` pipeline.
4. On parse failure or an out-of-menu answer, default to `"verify"` (conservative,
   cardholder-favorable — consistent with the existing fallback philosophy elsewhere in the
   runtime) rather than raising or retrying indefinitely.

`playbook.STEPS` stops being consumed as an ordered plan; `investigate()` still calls it (or
a renamed equivalent, e.g. a docstring-level "supported actions" hint) only to seed
`completed_steps`/logging context, not to gate `assess_progress`. `_complete_step` and
`_progress_marker` are unchanged — they're already just bookkeeping, not decision logic.

## 4. Cleanup

- Delete `ConcurrencyConfig.model_calls` from `src/config.py` and `concurrency.model_calls`
  from `config/models.yaml`.
- Update the `router` capability's `definition` in `data/generator/capabilities.py` from
  "Config-driven routing: ..." to describe LLM classification over a described menu with a
  confidence-gated conservative fallback, so the dataset's own description of what it's
  testing stays accurate.
- After the above lands, run the `code-simplifier` agent over every file this touches to
  remove anything left unused (e.g. `RouteOutputConfig`, `priority` sort logic in
  `RoutesConfig.unique_ordered_routes`, any now-dead imports) and keep the result elegant
  and human-friendly — no legacy baggage.

## Testing impact

- `tests/test_route_perturbations.py` asserts `decision_semantics()` (final decision fields,
  not `route_id`/`method`) is stable across renamed-entity variants of the same case. It
  doesn't need to change, but it's now exercising an LLM classification call instead of a
  pure function, so it inherits whatever the project's existing LLM-in-tests approach is
  (already true for `investigate()` today).
- `capability_coverage` scoring checks trajectory *event shape* (`route_decision
  {route_id, method, confidence}`), not a specific `route_id`/`method` value against ground
  truth, so switching `method` from `rule` to `llm` doesn't break existing scoring.
- No other test currently asserts on `RouteConfig.match`, `RouteOutputConfig`, or
  `priority`.
