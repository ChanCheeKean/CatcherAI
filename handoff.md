# DisputeAI — agentic graph-discovery revamp: handoff

Last updated: 2026-09-21
Current phase: **S14 final cleanup complete; S9 pass@1 verified on all 10 cases (pass@3 not run)**
Next stage: none scheduled; S9 pass@3 and decoy-naming tuning (see the last S9 entry in §8) are the remaining open work

This file is the single entry point for any agent continuing this work. The previous handoff (the
Dispute Observatory build history) is in git history: `git show 56d9380:handoff.md`.

---

## 1. Read first (in order)

1. This file, completely.
2. `docs/superpowers/specs/2026-09-21-agentic-graph-revamp-design.md`, the approved design.
   It is the source of truth for architecture, schemas, ontology, cases and tools. If this handoff
   and the spec disagree, the spec wins; record the conflict in §7.
3. Only the files listed under your stage's **Read** line. Do not read the whole repo.

## 2. What we are building (one paragraph)

A card-dispute investigation POC that shows off **agents + graph**. Every case's evidence lives in a
rich temporal property graph (LadybugDB/Cypher). An LLM `triage` node classifies and plans; an LLM
`supervisor` loop sees the plan and a structured investigation summary and delegates tasks to
parallel Deep Agents `worker`s (catalog roles or ad-hoc roles it invents); workers query the
graph, search policies, run Python and write findings; a final `adjudicator` agent writes a
detailed, evidence-cited `CaseReport` (Pydantic); `consolidate_memory` maintains memory notes.
No playbooks, no rule-based governance, no simulation or time advancement, no human in the loop.

## 3. Non-negotiable rules for every stage

- **Leave decisions to the LLM.** No per-case or per-route Python logic, no hard-coded outcomes or
  confidences, no rule-based gates. Config (`config/agents.yaml`) is a starting menu, never a
  whitelist. Only loop termination (max turns, no-progress, plan-closed precondition) is hard-coded.
- **Every LLM output is a Pydantic model** passed via `response_format` / structured output. Never
  parse JSON out of free text. This is enforced, not just intended:
  - All LLM calls go through one helper, `invoke_structured(agent_or_model, schema, messages) ->
    BaseModel` (in `src/models.py`, S6). No other code calls `.invoke`/`.ainvoke` on a model or agent.
  - Use provider-native strict structured output (LangChain `ProviderStrategy`, OpenAI strict JSON
    schema) so the output is guaranteed to match the schema. On a Pydantic validator error, feed the
    error back and retry once, then fail the run with a clear `error` event (never fall back to text).
  - Every tool has a Pydantic `args_schema`, so tool calls are typed too.
  - The only unstructured model text allowed is a worker's intermediate reasoning between tool
    calls inside its own loop. It is never read by other nodes.
  - A test (S8) fails if any LLM call is made without a schema, and if `rg` finds `json.loads` on
    model output anywhere in `src/`.
- **Robust but not over-engineered.** Plain functions and data, few files, no class hierarchies or
  wrappers unless unavoidable. Add a node/tool/field/config file only when a case or the demo needs
  it. If something is unused, delete it. Never leave stubs, shims, `TODO`s or commented-out code.
- **Graph is the core.** Every case must be solvable only by connecting graph nodes; the surface
  story may mislead. Case evidence lives only in the graph (no parallel SQL tables).
- **Missing evidence is data**, e.g. `(:Dispute)-[:REQUESTED]->(:EvidenceRequest{status:'no_response'})`.
  The agent must discover it and apply the cardholder-favourable default taught by a skill.
- **Out of scope:** security hardening, governance, fairness gates, redaction, hash chains, prompt-
  injection filters, real-time or simulated waits, portfolio queue.
- **Observability:** every step emits a trajectory event; every tool result carries the graph
  `node_ids`/`edge_ids` it touched (the frontend draws the evidence subgraph from these).
- **Verify library APIs** against live docs (context7) before coding: `deepagents` 0.5.9 is
  installed (`create_deep_agent(..., response_format=..., skills=[...], subagents=...)`),
  `ladybug` 0.20.4 (Cypher, variable-length paths confirmed), LangGraph `Send` for fan-out.
- Ground truth under `data/generated/ground_truth/` is **evaluator-only**. Never load it into the
  graph, knowledge store, prompts or tools.

## 4. Environment and commands

- Python env: `uv sync --extra dev --extra api` (LadybugDB comes from the `graph`
  extra; S1 makes it a required dependency).
- Tests: `uv run pytest`; lint: `uv run ruff check src tests data/generator`; format:
  `uv run ruff format src tests data/generator`.
- Frontend (S11+): `cd frontend && npm ci && npx tsc -b && npx vitest run && npm run build`;
  E2E `npm run e2e`.
- Real LLM: `.env` holds `OPENAI_API_KEY`; model in `config/models.yaml` (`gpt-5.6-luna`,
  OpenAI Responses API). Real-LLM tests are marked `@pytest.mark.llm` and skipped by default.
- Launcher: `./dev.sh` (backend :8000 + frontend :5173). Broken between S0 and S10 by design.

## 5. Stage protocol (every stage, no exceptions)

1. Read §1–§4, your stage's section and its **Read** list.
2. Implement only your stage's scope. If you discover the stage is bigger than described, stop at
   a coherent point, document the remainder as a new stage in §6, and finish the protocol.
3. Tests first where behaviour is testable; `uv run pytest` and ruff must pass at the end.
4. Run the `code-simplifier` agent over the files changed in this stage. Remove dead code,
   unused config and leftovers from the old design.
5. Update this handoff: header (`Last updated`, `Current phase`, `Next stage`), tick the stage in
   §6, and append an entry to §8 (what was built, files, commands + results, deviations, open
   issues). Update the spec only if a design decision changed (say so in §8).
6. Commit everything with a descriptive message, ending with the co-author line used in this
   repo's recent commits, then `git push`.
7. **Stop.** Report a short summary to the user. Do not start the next stage.

Complexity guide (for picking the model): **Simple** = mechanical, clear instructions, a small
model is fine. **Medium** = some design judgement within a clear contract, Sonnet-class.
**Complex** = open-ended design, data realism, or LLM behaviour tuning, Opus-class.

---

## 6. Stages

Order matters: each stage lists what it consumes. The app is intentionally not runnable end to end
from S0 until S8, and the frontend until S11 (graphs complete in S13).

### S0 — Teardown of the old design  ☑
**Complexity: Simple**

Goal: delete everything the new design replaces, so later stages build forward without legacy code.

Read: spec §9; this list.

Delete:
- `src/playbooks/`, `src/governance.py`, `src/actions.py`, `src/decisions.py`, `src/routing.py`,
  `src/sandbox.py`, `src/harness/`, `src/data/`, `src/tools/`, `src/evaluation/`,
  `src/memory/graph.py`, `src/memory/notes.py`, `src/memory/curator.py`
- `src/runtime/` (all), `src/bootstrap.py`
- Model plumbing: `src/ports.py`, `src/domain/model.py`, `src/adapters/`,
  `src/observability/model_gateway.py`, `src/observability/redaction.py`
- API layers that read the old data: `src/api/read_models.py`, `graph_read_models.py`,
  `evaluation_read_models.py`, `workflow_graph.py`, `models.py`, `run_manager.py`, `sse.py`,
  `dependencies.py`, `constants.py`, and all `src/api/routers/*` except `meta.py`
  (reduce `meta.py` to a `/health` endpoint; `app.py` mounts only that).
- `config/routes.yaml`, `config/agents/`, `config/scenarios/`
- `data/generator/` (all), `data/generated/` (all), `data/corpus/skills/` (duplicate of `skills/`),
  `schemas/openapi.json`
- `docs/design/`, `docs/prompts/`, `docs/superpowers/specs/2026-09-16-*`,
  `docs/superpowers/plans/2026-09-16-*`, `docs/technical.md`
- Every test in `tests/` whose subject was deleted. Keep tests only for surviving modules.

Keep: `src/domain/events.py`, `src/observability/emitter.py`, `src/replay.py`, `src/storage.py`,
`src/memory/retrieval.py`, `src/config.py` (drop its `domain.model` dependency; keep
`ModelsConfig` loading only), `src/cli.py` (reduce to commands that still work, or to an empty
Typer app), `src/api/app.py`, `src/api/errors.py`, `src/api/routers/meta.py`, `data/corpus/`
(except `skills/`), `skills/` (rewritten in S5), `config/models.yaml`, `frontend/` (untouched until
S11), `README.md`.

In `events.py`/`emitter.py`, remove the hash chain, its verification and redaction calls; keep an
append-only SQLite event log with blobs. Remove event types listed as removed in spec §6.

If a kept module imports a deleted one, delete that code path. Do not stub it.

Done when: `uv run pytest` passes (the surviving tests only), ruff is clean, `rg` finds no imports
of deleted modules, and the repo contains no playbook, governance, harness or routing code.

### S1 — Graph foundation: ontology, builder, LadybugDB store  ☑
**Complexity: Medium**

Goal: one small, typed way to build and query the evidence graph. Later stages just add data.

Read: spec §4.1–4.2, §5; `ladybug` docs (context7).

Build:
- `data/generator/ontology.py`: a plain dict of node labels → properties (with types) and edge
  types → `(src_label, dst_label, properties)`, exactly the ontology in spec §4.2. Every node has
  `id STRING PRIMARY KEY` with a readable prefix (`CUS-`, `ACC-`, `CRD-`, `DEV-`, `IP-`, `PHN-`,
  `EML-`, `ADR-`, `MER-`, `TRM-`, `DSC-`, `AUT-`, `TXN-`, `ORD-`, `SHP-`, `TOK-`, `AGP-`, `MDT-`,
  `DSP-`, `EVI-`, `ERQ-`, `COM-`, `AEV-`, `MEM-`, `FND-`, `MAC-`). Every edge has `id` (`E-…`);
  temporal edges have `valid_from`/`valid_to` (ISO strings, empty = open).
- `data/generator/graph_builder.py`: `Graph` with `node(label, id, **props)` and
  `edge(type, src_id, dst_id, **props)` that validate against the ontology (unknown label/type/
  property or dangling endpoint raises), plus `write(out_dir)` producing `nodes.jsonl`,
  `edges.jsonl`.
- `src/graph_store.py`: `load(jsonl_dir, db_path)` bulk-loads into LadybugDB (one node table per
  label, one rel table per edge type); `schema()` returns labels, edge types, properties and
  counts; `query(cypher, params, row_cap)` rejects write clauses (`CREATE|MERGE|SET|DELETE|
  REMOVE|DROP|COPY|LOAD|INSTALL|ATTACH`, case-insensitive, outside string literals) and returns
  rows plus the `node_ids`/`edge_ids` found in them; `neighbors(id, rel_types, direction, since,
  until, limit)`; `write_finding(...)` (creates `Finding` + inferred edges with `run_id`,
  `confidence`, `evidence_path`); `copy_store(src, dst)` for per-run isolation.
- Make `ladybug` a required dependency in `pyproject.toml`; remove `networkx` if unused.

Tests (`tests/test_graph_store.py`): builder rejects unknown label/edge/prop and dangling edges;
a tiny fixture graph loads; `schema()` counts; `query` returns IDs and rejects each write keyword
(but allows the word inside a string literal); `neighbors` respects `since/until` on
`valid_from/valid_to`; `write_finding` persists and is visible to a new connection.

Done when the tests pass and the whole API of `graph_store.py` fits comfortably on a screen or two.

### S2 — Background world generator  ☑
**Complexity: Medium**

Goal: a realistic, deterministic world that hides the cases in noise.

Read: spec §4.3; `data/generator/ontology.py`, `graph_builder.py`.

Build `data/generator/world.py` (seeded, deterministic) and `data/generator/gen.py` (entry point:
`uv run python data/generator/gen.py` → `data/generated/graph/*.jsonl` → `data/generated/evidence.lbug`):
- About 2,500 customers, accounts (credit and debit, some with authorized users via `HOLDS{role}`),
  cards, tokens, devices, IPs, phones, emails, addresses; about 250 merchants with terminals,
  descriptors and some `SUB_MERCHANT_OF` marketplaces; about 50,000 transactions over about 6 months
  with authorizations, orders and shipments for e-commerce.
- Benign sharing that looks suspicious but isn't: households (shared address, device, authorized
  user), roommates (same street, different unit), office IP ranges, CGNAT IP blocks, recycled phone
  numbers (`HAS_PHONE` with non-overlapping `valid_from/valid_to`), shared family tablets.
- A background of about 300 ordinary disputes (all claim types, mostly benign resolutions) with
  evidence items and a few `EvidenceRequest` nodes in varied states.
- A `stats()` printout: counts per label and edge type.

Tests (`tests/test_generator_world.py`): determinism (same seed gives byte-identical jsonl);
every ontology label and edge type used; no dangling edges; temporal edges have
`valid_from <= valid_to`.

### S3 — Case kit, validation, and cases 1–5  ☑
**Complexity: Complex**

Goal: the first five showcase cases, each provably solvable by graph traversal and not by the
surface story.

Read: spec §4.3–4.5; old case ideas via `git show 56d9380:data/generator/heroes/cases_a.py` (and
`cases_b/c/d.py`) for narrative inspiration only; do not port code.

Build:
- `data/generator/cases/__init__.py`: the case contract. Each case module exposes
  `build(g: Graph, rng) -> dict` that adds its nodes/edges into the world graph and returns ground
  truth:
  ```python
  {
    "case_id": "DSP-2026-9xxxx", "code": "C02", "title": str,
    "intake": str,                      # what the cardholder said (goes on the Dispute node)
    "misleading_surface": str,          # why the obvious reading is wrong
    "expected": {"verdict": ..., "claim_family": ..., "transactions": [
        {"txn_id", "verdict", "credit_amount", "cardholder_liability", "network_action",
         "reason_code"}], "account_actions": [...]},
    "solution_node_ids": [...],         # 5–25 IDs
    "proof_patterns": [{"name", "cypher", "min_rows": 1}],
    "decoy_patterns": [{"name", "cypher", "why_irrelevant"}],
    "missing_evidence": bool,
  }
  ```
- `data/generator/validate.py`: after load, runs every proof pattern (must return ≥ `min_rows`)
  and every decoy pattern (must return rows, proving the decoy exists), checks all
  `solution_node_ids` exist, and fails the build otherwise. `gen.py` calls it and writes
  `data/generated/ground_truth/cases/<case_id>.json`, plus the UI-only
  `data/generated/case_catalog.json` (`case_id`, `title`, `claim_type`, `amount`, `summary`); the
  summary is a neutral one-liner of what the cardholder says and must not reveal the answer.
- Cases 1–5 from spec §4.4: C02 descriptor confusion, C04 split-not-double, C08 Pump Six
  compromise point, C10 family tablet, C11 ATO drop-address ring (about 40 accounts).
- For each case, write a short "human effort" note in the ground truth: the number of hops and
  entities a human would have to trace. This is useful in the demo.

Tests (`tests/test_cases.py`): validation passes for all built cases; ground-truth files contain no
field that leaks into the graph (e.g. `expected` text is not on any node); each case has at least
one decoy.

### S4 — Cases 6–10, missing evidence, capability map  ☑
**Complexity: Complex**

Goal: complete the case set and the capability coverage mapping.

Read: S3 outputs; spec §4.4; `git show 56d9380:data/generator/capabilities.py`.

Build: cases C12 porch ring, C12b wrong house (control, with `EvidenceRequest{no_response}`),
C13 agent booked it (Token, AgentProvider, Mandate), C18 refund crossed (unlinked credit matched
through `Order`, `no_response` on the remainder), C19 yesterday's reputation (merchant pattern +
a `MemoryNote` that newer graph facts contradict). Rewrite `data/generator/capabilities.py` for
the new components (agents, router/triage, loop termination, agent graph, subagents, tool calling,
harness = scenario loading + trajectory + eval, skills, persistent/graph/semantic memory, sandbox,
read/write paths) and write `ground_truth/capability_coverage.json`; each case's ground truth
gets `required_capabilities`.

Tests: extend `tests/test_cases.py`: 10 cases validate; at least 2 cases have
`missing_evidence: true`; at least 6 cases have a non-empty `misleading_surface`; every capability is
primary for at least one case.

### S5 — Knowledge store and skills  ☑
**Complexity: Medium**

Goal: searchable policies/precedents/memory-note text, and skills rewritten as generic knowledge.

Read: `src/memory/retrieval.py`, `data/corpus/`, `skills/`, spec §3.5 and §5.

Build:
- `data/generator/knowledge.py`: loads `data/corpus/policies/**` and generates about 30 precedents
  (short resolved-case write-ups consistent with the new cases' patterns, without giving away
  answers) into `data/generated/knowledge.sqlite` using `memory/retrieval.py` (FTS5 +
  sqlite-vec). Trim `retrieval.py` to what `search_knowledge` needs.
- Rewrite `skills/*/SKILL.md` (Deep Agents skill format, with frontmatter `name`/`description`) as
  generic domain knowledge: `graph-investigation` (new: how to explore, pivot on shared
  identifiers, use temporal edges, rule out decoys), `fraud-and-ato-signals`,
  `household-authority`, `missing-evidence-default`, `reg-e-and-reg-z`, `network-reason-codes`,
  `agentic-transactions`, `memory-hygiene`, `not-received-and-refunds`. Delete skills that don't
  fit. No case IDs or case-specific answers in skills.

Tests: search returns relevant policy for a few queries; `as_of` filter works; every skill parses
(frontmatter present) and contains no `DSP-`/`TXN-` IDs.

### S6 — Schemas, config and model setup  ☑
**Complexity: Simple**

Goal: every contract later stages rely on, in two small files.

Read: spec §3 (all schema blocks), §9 "Model stack".

Build:
- `src/schemas.py`: `Hypothesis`, `Fact`, `PlanItem`, `PlanEdit`, `Triage`,
  `InvestigationSummary`, `Task`, `Delegate`, `Decide`, `SupervisorTurn`, `Findings`, `Verdict`,
  `EvidenceLink`, `TransactionDecision`, `HypothesisAssessment`, `Citation`, `AccountAction`,
  `CaseReport`, exactly as in the spec. Validators: ad-hoc `Task` requires `instructions`;
  `Triage` with `case_type == "novel"` requires a description; `CaseReport` requires at least one
  `EvidenceLink` per transaction and per hypothesis, and per-transaction
  `credit_amount + cardholder_liability == disputed_amount`.
- `config/agents.yaml`: `case_types` (id, description, suggested skills/roles) and `roles` (id,
  description, prompt, default skills) for `graph_analyst`, `transaction_analyst`,
  `evidence_analyst`, `policy_researcher`, `memory_keeper`, `critic`, `adjudicator`, and a
  `supervisor`/`triage` prompt. Loader in `src/config.py`, plus `runtime` limits: `max_turns`,
  `no_progress_turns`, `max_parallel_tasks`.
- `src/models.py`: `chat_model(config)` via `langchain.chat_models.init_chat_model` from
  `config/models.yaml`; `invoke_structured(agent_or_model, schema, messages)` (the only way the
  codebase calls an LLM: plain models via `with_structured_output(schema, strict=True)`, Deep
  Agents via `response_format=ProviderStrategy(schema)` reading `structured_response`; validates,
  retries once with the validation error, returns the model instance); and a LangChain
  `BaseCallbackHandler` that emits `model_call` events (model, schema name, tokens, latency)
  through the emitter.

Tests: schema validators accept good and reject bad examples; config loads; `chat_model` builds
without network; `invoke_structured` retries once on a validation error, then raises.

### S7 — Agent tools  ☑
**Complexity: Medium**

Goal: the seven tools every worker gets, each emitting `tool_call`/`tool_result` events with
graph IDs.

Read: spec §5; `src/graph_store.py`; `src/memory/retrieval.py`; `src/observability/emitter.py`.

Build `src/tools.py` (every tool with a Pydantic `args_schema`): `make_tools(run) -> list[BaseTool]` returning `graph_schema`, `graph_query`,
`graph_neighbors`, `graph_write_finding`, `search_knowledge`, `memory_write`, `python`. Tool
errors (bad Cypher, timeouts) are returned to the agent as text, never raised. Results are
compact: IDs plus key properties, capped rows, with a "truncated" note. `memory_write(op, note)`
supports `write|supersede|retract|merge` on `MemoryNote` nodes with `ABOUT` edges and requires
source node IDs. `python` runs code in a subprocess with a timeout and a small allow-listed stdlib
(`datetime`, `decimal`, `math`, `statistics`, `collections`, `json`, `zoneinfo`), returning
stdout.

Tests (`tests/test_tools.py`) against a fixture graph: each tool's happy path; the read-only guard;
error-as-text; the event payload includes `node_ids`/`edge_ids`; the python timeout.

### S8 — Agent runtime (LangGraph)  ☑
**Complexity: Complex**

Goal: the five-node agent graph, end to end, with a replayable trajectory.

Read: spec §3 and §6; `src/schemas.py`, `src/tools.py`, `src/models.py`, `config/agents.yaml`;
LangGraph `Send` and Deep Agents docs (context7).

Build `src/runtime.py` (split into at most two or three files if it grows past about 500 lines):
- State: case, triage, plan, summary, findings (reducer), turn counters, report.
- Nodes: `triage` (reads Dispute intake + 1-hop neighbourhood + schema; `Triage`), `supervisor`
  (`SupervisorTurn`; applies plan edits; rejects `Decide` while plan items are open by feeding
  the rejection back), `worker` (Deep Agent from role prompt or ad-hoc instructions + skills +
  tools, `response_format=Findings`), `adjudicator` (Deep Agent with read-only tools,
  `response_format=CaseReport`; a validator error is fed back for a retry), `consolidate_memory`
  (`memory_keeper` worker).
- Fan-out with `Send` per `Task` (cap `max_parallel_tasks`); termination: `decided`, `max_turns`,
  `no_progress` (the last two force the adjudicator with a note).
- Events per spec §6, including `node_entered`/`node_exited`/`edge_taken`, `triage`,
  `plan_updated`, `supervisor_turn`, `delegation_started/finished`, `skill_loaded`, `decision`,
  `termination`. Every event carries `actor` (node or role), `visit` (1-based per actor),
  `turn` (supervisor turn) and `parent_id` (spawning delegation); `node_exited` carries the node's
  structured output; `delegation_started` carries the `Task`, `delegation_finished` the `Findings`
  (the frontend builds both graphs from these alone; see spec §7.5). The run result is the
  `CaseReport`, persisted with the run.
- Per-run graph isolation via `graph_store.copy_store`. LangGraph SQLite checkpointer.
- CLI (`src/cli.py`): `inspect run <case_id>`, `inspect replay <run_id>`.

Tests: `tests/test_runtime.py` with a stub chat model that returns fixed Pydantic objects
(plumbing only): triage → supervisor delegates two tasks in parallel → findings merge →
premature `Decide` is rejected → plan closed → adjudicator → consolidate → `decided`; plus
`max_turns` and `no_progress` terminations; the event order is replayable. Structured-output
enforcement test: the stub model records every call and the test asserts each one carried a
schema; a second test scans `src/` and fails on `json.loads` applied to model output or any LLM
call outside `invoke_structured`. One `@pytest.mark.llm`
smoke run on C04.

### S9 — Real-LLM evaluation and tuning  ◐ (tooling done; 10/10 pass@1, pass@3 not run)
**Complexity: Complex**

Goal: prove the agent solves the cases, and tune prompts and skills (never case code) until it does.

Read: spec §8; ground-truth format from S3.

Build `src/evaluation.py` + `inspect eval [--cases ...] [--k N]`: per case, verdict and amounts
match; account actions overlap; solution-subgraph coverage (share of `solution_node_ids` in the
trajectory's `node_ids`); report grounding (every cited ID exists; cites solution nodes; names
the decoys); missing-evidence cases apply the cardholder-favourable default; required-capability
signals present in the trajectory; pass@k. Output a JSON + Markdown summary to
`data/generated/eval/<timestamp>/` (git-ignored).

Then run all 10 cases with the real model, iterate on role prompts, skills and tool ergonomics,
and record the results table in §8. Target: at least 8/10 correct verdicts at pass@1, all 10 at
pass@3, and average subgraph coverage of at least 0.7. If a case is unsolvable because the data is
ambiguous, fix the data (and its proof patterns), not the agent.

### S10 — API  ☑
**Complexity: Medium**

Goal: exactly the endpoints the two-page frontend needs (spec §6, §7.5).

Read: spec §6–7; `src/api/app.py`; `git show 56d9380:src/api/run_manager.py` and
`git show 56d9380:src/api/sse.py` for the run-registry and SSE patterns (reuse ideas, not code).

Build: `GET /cases` (from `case_catalog.json`), `POST /runs {case_id}` (starts a background run
with an isolated graph store, returns `run_id`), `GET /runs/{id}` (status + `CaseReport` when
done), `GET /runs/{id}/events` (SSE; replays stored events then streams live; reconnect with
`Last-Event-ID`), `GET /graph/nodes?ids=` (properties of nodes/edges, batch),
`GET /graph/neighbors/{id}`, `GET /eval/latest` (solution/decoy IDs for the overlay; only
after an eval run). Regenerate `schemas/openapi.json` and `schemas/trajectory-event.schema.json`.

Tests: `tests/test_api.py` with the stub model (FastAPI TestClient): list cases; start a run;
stream events to completion; every event has `actor`/`visit`/`turn`; fetch report; batch node
lookup; neighbours.

### S11 — Frontend part 1: shell, cases page, run page layout, conclusion  ☑
**Complexity: Medium**

Goal: the simple two-page app with the final layout, without the graphs yet.

Read: spec §7 (all); `frontend/package.json`, `frontend/src/api/*`, `frontend/src/app/*`.

Do:
- Delete everything not in the new design: `features/mission-control`, `features/evaluation`,
  `features/memory`, `features/graph`, all of `features/run-observatory` except code you
  deliberately reuse, `CommandPalette`, `NavigationRail`, `Inspector*`, queue code, and their
  tests. Remove unused dependencies.
- `api/types.ts` + `client.ts` for the S10 endpoints; `useRunEvents(runId)` hook (SSE with
  reconnect) feeding one small store: events, derived plan, per-actor visits, touched node/edge
  IDs, report.
- Page 1 `/`: case cards (title, claim type, amount, summary); click → `POST /runs` → navigate.
- Page 2 `/cases/:caseId/runs/:runId`: header (back, title, status, "Run again"); left canvas
  with `Agent flow | Evidence graph` tabs (placeholders in this stage); right inspector panel
  (selection-driven; shows raw event data for now); bottom **conclusion panel** fully built from
  `CaseReport`: verdict badge, headline, executive summary, detailed reasoning (collapsible),
  per-transaction table, hypotheses accepted/rejected, decoys ruled out, missing evidence, policy
  basis, cardholder letter; live status (turn, open plan items) until the decision arrives.
  Evidence chips set a shared `highlight` selection (used by S13).

Checks: `npx tsc -b`, `npx vitest run` (tests for event → store derivation and the conclusion
panel with a fixture `CaseReport`), `npm run build`.

### S12 — Frontend part 2: agent-flow graph + inspector  ☑
**Complexity: Complex**

Goal: the region-segmented agent map where every node can be opened to see what it did.

Read: spec §7.3, §7.5; S11 output; React Flow docs (context7); the `frontend-design` skill.

Do (React Flow):
- Four fixed background regions left to right: **Planning** (triage, supervisor),
  **Investigation** (one node per role that ran, ad-hoc roles tagged), **Tools & Memory** (one
  node per tool), **Decision** (adjudicator, consolidate_memory). Deterministic positions:
  region column + stacking order; nodes appear as actors first run; nothing reflows.
- Edges with counts: triage → supervisor, supervisor → worker (labelled "decided by
  supervisor"), worker → supervisor (dashed curved **loop** arc), worker → tool, supervisor →
  supervisor on rejected `Decide` (self-loop), supervisor → adjudicator (labelled "Decide" or
  "forced: max_turns/no_progress"), adjudicator → consolidate_memory.
- Visit badges `×N`; active node pulses; last-taken edge animates.
- Inspector for an agent node: list of visits (1…N), each with input, structured output rendered
  as readable fields (raw JSON toggle), tool calls (args + compact result), duration, tokens.
  Supervisor visits also show the plan checklist after that turn. Tool nodes list their calls.
- Selecting an agent node publishes the node IDs it touched (used by S13 to dim the evidence
  graph).

Checks: tsc, vitest (layout is deterministic for a fixture event stream; visit counts;
loop-edge rendering), build.

### S13 — Frontend part 3: evidence graph, highlighting, E2E  ☑
**Complexity: Complex**

Goal: the data graph that shows how everything links together.

Read: spec §7.4; S11–S12 output; `d3-force` docs.

Do:
- Evidence graph from touched `node_ids`/`edge_ids` (properties via `GET /graph/nodes?ids=`),
  growing live; three regions (**Identity**, **Commerce**, **Case & knowledge**) with d3-force
  pulling nodes toward their region centre; colour + icon per label; edge type labels;
  agent-written edges dashed accent; new nodes flash.
- Click node → inspector: properties, edges with `valid_from/valid_to`, "found by <agent> via
  <tool> at turn N". Double-click → expand 1-hop neighbours (dimmed context).
- Highlighting: `CaseReport` evidence emphasised after decision; conclusion evidence chips
  highlight exact nodes/edges and switch to this tab; agent-node selection from S12 dims to that
  agent's nodes; eval overlay toggle (solution/decoy outlines) when `/eval/latest` has the case.
- Playwright E2E: open cases page → click a case → agent-flow nodes appear → evidence graph grows →
  conclusion shows a verdict → clicking an evidence chip highlights nodes. Keep `./dev.sh`
  working.

Checks: tsc, vitest, build, `npm run e2e`.

### S14 — Documentation and final cleanup  ☑
**Complexity: Medium**

Goal: zero leftovers and a fully verified repo.

Do: remove the spec's "pending review" status. Final repo-wide `code-simplifier` pass; `rg`
for leftovers of removed concepts (`playbook`, `governance`, `virtual_clock`, `persona`,
`scheduler`, `route_id`, `hash_chain`, `redact`, `queue`) and remove them. Full verification:
pytest, ruff, frontend checks and E2E.

---

## 7. Open questions and conflicts

- The handoff calls the design approved, while the spec header still says “pending written-spec
  review.” No architecture conflict was found; this stage follows the handoff's approved-design
  status.
- Ontology deviations (S1): Cypher reserves `Order` and `LIMIT`, so the label is `PurchaseOrder`
  (id prefix still `ORD-`) and `Account.limit` is `credit_limit`. The spec's `REQUESTED{status,
  deadline,responded_at}` edge properties live on the `EvidenceRequest` node (as in §4.2's missing-
  evidence example); the edge only carries `requested_at`. Several edge types connect more than one
  label pair (`pairs` list in `ontology.py`). Update the spec if these stick.
- The spec removal list includes `handoff.md`, while the stage protocol requires updating and
  committing this file after every stage. The handoff is retained as the active execution record.

## 8. Stage history

### 2026-09-21 — Design approved
- Brainstormed and approved the revamp; spec at
  `docs/superpowers/specs/2026-09-21-agentic-graph-revamp-design.md`.
- Key decisions: approach 1 (explicit LangGraph supervisor loop over Deep Agents workers); test
  strategy A (deterministic plumbing tests + real-LLM eval); frontend option A (adapt + live
  evidence subgraph); 10 graph-first cases; drop portfolio queue; final `adjudicator` agent
  produces a Pydantic `CaseReport`; router and planner merged into `triage`; supervisor actions
  limited to `Delegate`/`Decide`; seven tools; replace the custom model gateway with
  `init_chat_model`; drop hash chain and redaction.
- Frontend redesigned as two pages (cases → run page). The run page has the graph on the left
  (tabs: region-segmented agent flow, and the evidence graph), the inspector on the right, and the
  conclusion (`CaseReport`) at the bottom. Split into S11–S13; docs moved to S14.
- Baseline before teardown: HEAD `56d9380` plus the spec commits.

### 2026-09-21 — S0 teardown complete

- Removed the legacy playbooks, routing, governance, action/decision, simulation harness, old
  runtime, adapters, operational data access, graph/memory helpers, old API projections/run
  manager/SSE layers, route and agent config, old generator/generated artifacts, duplicate skills,
  stale design/plan/technical docs, and tests tied to those modules. Removed the obsolete
  `domain.case` records as part of the replaced model layer.
- Reduced the surviving API to `GET /health`, the CLI to replay/schema export, and config loading to
  `ModelsConfig` only. Added a small smoke suite for the surviving modules.
- Simplified trajectory persistence to an append-only SQLite event/blob log: removed hash-chain
  columns and verification, payload redaction, virtual time, and legacy event plumbing. Removed
  `networkx` from project dependencies and kept the frontend untouched for S11.
- Files changed directly: `src/domain/events.py`, `src/observability/emitter.py`, `src/replay.py`,
  `src/config.py`, `src/cli.py`, `src/api/app.py`, `src/api/routers/meta.py`, `pyproject.toml`,
  `uv.lock`, `README.md`, and `tests/test_surviving_modules.py`; deletion scope is recorded by git.
- Verification: `uv run ruff check src tests data/generator` — clean; `uv run pytest` — **3 passed**
  with one upstream Starlette deprecation warning. The required code-simplifier pass reviewed the
  S0 files, removed stale actor/API/CLI leftovers, and confirmed the same checks.
- Deviations/open issues: `data/generated/` was removed including ignored local artifacts; the app
  is intentionally non-runnable beyond health until S10, and the existing README remains legacy
  content with the required rewrite notice at its top. No design decision was changed.

### 2026-09-21 — S1 graph foundation complete

- Built `data/generator/ontology.py` (26 labels, 38 edge types, plain dicts; `pairs` per edge type;
  provenance props `run_id/confidence/evidence_path` on agent-writable edges), `graph_builder.py`
  (`Graph.node/edge/write`, validates labels, props, id prefixes, endpoints and label pairs; writes
  `nodes.jsonl`, `edges.jsonl`, `ontology.json`) and `src/graph_store.py` (`load`, `copy_store`,
  `GraphStore.schema/query/neighbors/write_finding/close`). The store is generic: it reads the
  ontology from `ontology.json`, kept beside the DB as `<db>.ontology.json`, so `src/` does not import
  the generator. Bulk load uses CSV `COPY`; the write guard strips string literals/comments first.
- `ladybug` is now a required dependency; `pytest` gets `pythonpath = ["data/generator"]`.
- Tests: `tests/test_graph_store.py` (19 cases). `uv run ruff check src tests data/generator` clean;
  `uv run pytest` 22 passed. Code-simplifier pass done (removed dead helpers, validate-before-write in
  `write_finding`).
- Notes for S2: Ladybug returns empty strings as NULL, so temporal filters treat NULL as open;
  `query` ids include id-shaped string values (e.g. `RETURN a.id`); edges from `neighbors` are
  compact dicts. Deviations listed in §7.

### 2026-09-21 — S2 background world generator complete

- Built `data/generator/world.py`: deterministic seeded identity, commerce and dispute background
  data with production defaults of 2,500 customers, 250 merchants, 50,000 transactions over about
  six months, and 300 ordinary disputes. The world includes credit/debit accounts, authorized
  users, tokens, orders/shipments, merchant accounts, terminals/descriptors, evidence requests,
  communications, account events and historical memory/findings.
- Added benign graph ambiguity: shared household addresses and family devices, same-street
  different-unit addresses, office and CGNAT IPs, a recycled phone with non-overlapping ownership,
  marketplace sub-merchants, refunds and agent-provider mandates. Every one of the 26 node labels
  and 38 edge types is present in the background graph.
- Built `data/generator/gen.py`: `uv run python data/generator/gen.py` writes deterministic JSONL,
  loads `data/generated/evidence.lbug`, and prints sorted node/edge counts. Generated artifacts are
  now wholly ignored through `.gitignore` rather than partially ignored by file extension.
- Added `tests/test_generator_world.py` for byte determinism, full ontology coverage, referential
  integrity, valid temporal intervals and stats output. The code-simplifier pass removed unused
  generator parameters/accumulators and tightened minimum custom counts without changing output.
- Verification: `uv run ruff check src tests data/generator` clean; `uv run ruff format --check src
  tests data/generator` clean; `uv run pytest` **26 passed** with one upstream Starlette warning.
  The production generator completed in about five seconds, produced a 154 MB ignored artifact set,
  loaded successfully into LadybugDB, and reported 2,500 customers / 50,000 transactions / 300
  disputes. A variable-length Cypher query against the resulting store returned connected IDs.
- No design decisions changed and no spec update was required.

### 2026-09-21 — S3 case kit, validation, and cases 1–5 complete

- Added the typed case contract and deterministic builder in `data/generator/cases/`, plus five
  graph-first showcases: C02 descriptor confusion, C04 split clearing, C08 common compromise point,
  C10 authorized family-tablet use, and C11 a forty-account takeover/drop-address cluster. Each
  case includes executable proof paths, matching but irrelevant decoys, a 5–25 node solution set,
  evaluator outcomes, and a quantified human-effort note.
- Added `data/generator/validate.py`: it verifies every solution node, minimum proof-row count and
  decoy match after LadybugDB load, then writes evaluator-only case JSON and an answer-free UI case
  catalog. Catalog claim types and amounts come from the intake Dispute nodes rather than hidden
  expected outcomes.
- Updated `data/generator/gen.py` to compose cases into the background world, validate the loaded
  graph before emitting artifacts, and write `data/generated/ground_truth/cases/` plus
  `data/generated/case_catalog.json`. Added `tests/test_cases.py` for all contracts, validation
  failure modes, ground-truth separation, decoy coverage and neutral catalog fields.
- Verification: `uv run ruff check src tests data/generator` clean; `uv run ruff format --check src
  tests data/generator` clean; `uv run pytest` **29 passed** with one upstream Starlette warning.
  The production generator completed successfully with 2,552 customers, 50,060 transactions and
  349 disputes, and all case proof/decoy queries passed. A simplification review removed a direct
  graph-property mutation and made catalog display data derive from graph intake facts.
- No design decisions changed and no spec update was required. Generated graph, ground truth,
  catalog and LadybugDB files remain ignored build artifacts.

### 2026-09-21 — S4 cases 6–10, missing evidence, and capability map complete

- Added the remaining five graph-first showcases: C12 coordinated porch-claim ring, C12b wrong-
  house control, C13 agent-provider mandate overrun, C18 unlinked partial refund, and C19 stale
  merchant reputation. Each has executable proof paths, at least one matched decoy, a bounded
  solution subgraph, evaluator outcomes, and a human-effort note.
- C12b uses non-overlapping recycled-phone ownership plus a delivery-address mismatch; C18 matches
  an otherwise unlinked credit through its order. Both model missing merchant evidence as
  `EvidenceRequest{status:'no_response', deadline_passed:true}` and expect the remaining uncertainty
  to resolve in the cardholder's favour.
- Rewrote `data/generator/capabilities.py` around the new architecture: agents, router/triage,
  termination, agent graph, subagents, typed tools, harness, skills, persistent/graph/semantic
  memory, sandbox, and selective read/write paths. Every capability is primary for at least one
  case. Case ground truth now includes `required_capabilities`, and generation writes evaluator-only
  `ground_truth/capability_coverage.json`.
- Extended `tests/test_cases.py` for all ten cases, missing-evidence and misleading-surface minima,
  required-capability validity, and primary coverage. The required code-simplifier pass removed an
  unused C13 device/edge and found no other safe reductions or contract violations.
- Verification: `uv run pytest` — **30 passed** with one upstream Starlette warning;
  `uv run ruff check src tests data/generator` clean; `uv run ruff format --check src tests
  data/generator` clean. The production generator completed in about six seconds with 2,568
  customers, 50,079 transactions, and 364 disputes; all ten cases' proof and decoy patterns passed.
- No design decisions changed and no spec update was required. Generated graph, ground truth,
  capability coverage, catalog, and LadybugDB files remain ignored build artifacts.

### 2026-09-21 — S5 knowledge store and skills complete

- `src/memory/retrieval.py` is now two functions: `build(db_path, docs)` (documents table, FTS5 and
  sqlite-vec indexes) and `search(db_path, query, as_of=, kinds=, limit=)` (reciprocal-rank fusion of
  vector and keyword hits, filtered by `valid_from <= as_of <= valid_to`, open bounds allowed). The
  emitter dependency and event emission were removed; S7's `search_knowledge` tool emits the event.
  Embeddings remain the offline hashed bag-of-words vectors (no network needed).
- `data/generator/knowledge.py` loads the 35 policy documents from `data/corpus/policies/**` plus 30
  precedents from `data/corpus/precedents.yaml` (analogous patterns only, no showcase-case IDs or
  answers) into `data/generated/knowledge.sqlite` (kind `policy` or `precedent`). `gen.py` builds it
  after the graph. `author_policies.py` no longer authors skills.
- Replaced the old skills with nine generic ones in `skills/*/SKILL.md` (frontmatter `name` and
  `description`): graph-investigation, fraud-and-ato-signals, household-authority,
  missing-evidence-default, reg-e-and-reg-z, network-reason-codes, agentic-transactions,
  memory-hygiene, not-received-and-refunds. Removed dispute-lifecycle, eligibility-check, lodging-te,
  recurring-trial, automated-adjudication, fraud-cnp, not-received and reg-e-clocks.
- Tests: `tests/test_knowledge.py` (relevant policy search, kind filter, `as_of` validity for the
  scheduled Visa 10.4 version, skills parse and contain no `DSP-`/`TXN-`/`CUS-`/`ACC-` IDs).
- Verification: `uv run ruff check` clean; `uv run pytest` 34 passed; `gen.py` builds 65 knowledge
  documents. Memory notes are not in `knowledge.sqlite`; they are `MemoryNote` graph nodes, so S7's
  `search_knowledge` decides whether to add them (spec §5 lists them as searchable).
- No design decisions changed.

### 2026-09-21 — S6 schemas, config and model setup complete

- Added `src/schemas.py` with the agent contracts from spec §3: triage/planning, investigation
  summaries, delegation, findings, verdicts, evidence links, transaction decisions, citations,
  account actions, and the evidence-grounded `CaseReport`. Pydantic validators enforce novel-case
  descriptions, instructions for ad-hoc roles, transaction amount reconciliation, and evidence
  links for every transaction and hypothesis.
- Added `config/agents.yaml` with ten starting case types, the seven catalog roles, triage and
  supervisor prompts, and runtime limits. Added typed loading and lookup helpers in `src/config.py`.
- Added `src/models.py`: `chat_model` builds LangChain's configured OpenAI Responses model,
  `provider_strategy` supplies strict native output for Deep Agents, `invoke_structured` is the
  single model/agent invocation boundary with one validation-error retry, and the callback handler
  emits `model_call` trajectory events with schema, token, model, and latency data.
- Added `tests/test_schemas_models.py` covering validators, config loading, no-network model
  construction, plain-model and Deep-Agent structured responses, retry/failure behavior, and model
  telemetry. A missing OpenAI key uses a construction-only sentinel; actual calls still require the
  configured key.
- Verification: `uv run ruff check src tests data/generator` clean; `uv run ruff format --check
  src tests data/generator` clean; `uv run pytest` — **41 passed** with one upstream Starlette
  deprecation warning. The required code-simplifier review found no safe reductions; the
  provider-strategy helper is intentionally retained for S8's Deep Agent construction. No design
  decisions changed and no spec update was required.

### 2026-09-21 — S7 agent tools complete

- Added `src/tools.py`: `Run` (store, emitter, run_id, knowledge_db, as_of, `actor`) and `make_tools(run)`
  returning the seven tools (`graph_schema`, `graph_query`, `graph_neighbors`, `graph_write_finding`,
  `search_knowledge`, `memory_write`, `python`), each with a Pydantic `args_schema`. Every call emits
  `tool_call` then `tool_result` (actor kind `tool`; payload has `caller`, `tool`, `call_id`, `args`,
  `result`, `node_ids`, `edge_ids`; ids also in `refs`); writes additionally emit `graph_write` /
  `memory_write`. Errors are returned as `{"error": ...}` JSON text. Strings are clipped to 1,200 chars;
  Cypher rows are capped by the store. S8 should use `dataclasses.replace(run, actor=role)` per worker
  and add `visit`/`turn`/`parent_id` (the emitter draft has no such fields yet; put them in the payload
  or extend `EventDraft`).
- `python` runs in an isolated subprocess (10 s timeout) with imports restricted to `datetime, decimal,
  math, statistics, collections, json, zoneinfo` (a convenience guard, not a security boundary).
- `search_knowledge` combines `retrieval.search` (policy/precedent, `as_of` defaults to the run's date)
  with keyword-ranked active `MemoryNote` graph nodes (kind `memory_note`).
- `graph_store.py`: `write_finding` refactored onto shared `_check_edges`/`_create_edge`, now rejects
  dangling endpoints; added `write_note` (MemoryNote + `ABOUT` edges, marks replaced notes
  `superseded`/`merged`) and `set_note_status` (retract). No SUPERSEDES edge exists in the ontology, so
  the supersede link is recorded only in the `memory_write` event payload.
- Deleted stale empty `src/{adapters,data,evaluation,harness,playbooks,runtime,tools}` dirs (only
  `__pycache__`; `src/tools/` would have shadowed `tools.py`).
- Tests: `tests/test_tools.py` (10). `uv run ruff check src tests data/generator` clean; `uv run pytest`
  **51 passed**. Code-simplifier pass done. No design decisions changed.

### 2026-09-21 — S8 agent runtime complete

- Built the five-node LangGraph runtime in `src/runtime.py`, with small entry/state helpers in
  `src/runtime_entry.py` and `src/runtime_support.py`: triage, supervisor, parallel worker fan-out
  through `Send`, adjudicator, and memory consolidation. The supervisor applies plan edits,
  rejects premature `Decide` actions while items remain open, caps parallel delegation, and forces
  adjudication on `max_turns` or `no_progress` without encoding case outcomes.
- Workers and the adjudicator are Deep Agents using provider-native Pydantic response formats.
  Requested role/task skills are attached directly to their prompts while the native `/skills`
  source remains available for ad-hoc discovery. Workers use independent LadybugDB connections for
  parallel tool calls; the adjudicator receives only the four read-only domain tools.
- Added per-run graph copying, persistent SQLite LangGraph checkpoints, the `inspect run <case_id>`
  command, and structured error termination. The final `CaseReport` is returned and durably stored
  in the trajectory's `decision` event.
- Extended the trajectory contract and SQLite migration with top-level `visit`, `turn`, and
  `parent_id`. Runtime events now cover every node/edge, task and finding payloads, skill loading,
  forced termination, and the final consolidation-to-end edge. Tool/model events inherit the same
  execution context; legacy trajectory databases receive the new columns automatically.
- Added `tests/test_runtime.py`: deterministic triage → two-worker fan-out → merged findings →
  rejected premature decision → closed plan → adjudication → consolidation; forced max-turn and
  no-progress paths; replay sequence and frontend payload contracts; read-only adjudicator tools;
  and an AST guard preventing model invocation outside `invoke_structured`. Added a C04 real-model
  smoke test marked `llm` and excluded from default runs.
- Verified installed `deepagents` 0.5.9 signatures, LangGraph `Send`, Deep Agents skills/backends,
  and SQLite checkpoint usage against installed source and live LangChain documentation. The
  required code-simplifier review was completed; its skill-event, final-edge, test-contract and
  file-size findings were incorporated.
- Verification: `uv run ruff check src tests data/generator` clean; `uv run ruff format --check src
  tests data/generator` clean; `uv run pytest` — **55 passed, 1 deselected** (the real-LLM smoke
  test), with one upstream Starlette deprecation warning; `uv run inspect --help` works. The
  real-LLM smoke was not run in S8 and remains S9 work.
- No design decision changed and no spec update was required.

### 2026-09-21 — S10 API complete (built while S9 tuning is in progress)

- Added the seven endpoints from the S10 spec as `create_app(context: ApiContext | None)` in `src/api/`
  (`app.py`, `context.py`, `models.py`, `routers/runs.py`, `routers/graph.py`): `GET /cases`,
  `POST /runs` (202, background thread through `run_case`, isolated graph copy), `GET /runs/{id}`
  (`running|completed|failed`, `CaseReport` from the `decision` event), `GET /runs/{id}/events` (SSE with
  replay, live follow and `Last-Event-ID`), `GET /graph/nodes?ids=`, `GET /graph/neighbors/{id}`,
  `GET /eval/latest` (solution and decoy ids from ground truth for the newest eval batch, empty when none).
- Deviations: `/graph/*` take an optional `run_id` to read that run's graph copy (the only place agent-
  written `FND-`/`MEM-`/`E-` items live); `GraphStore` gained `read_only`; `load_events` gained
  `after_seq`; `/eval/latest` returns an empty body rather than 404. `schemas/openapi.json` and
  `schemas/trajectory-event.schema.json` regenerated.
- Open issues: the run registry is per process (a run still in flight when the API restarts shows as
  `failed`); `/graph/*` has no CORS, so S11 needs the Vite proxy; several parallel runs in one process
  are untested against the LadybugDB mmap limit (see S9 notes once recorded).
- Verification: `uv run pytest` 66 passed, ruff clean. Tests use the stub model (`tests/test_api.py`, 8).
- S9 changes that touch shared code (`graph_store` now shares one `Database` per file, `schemas.Money`)
  must keep S10 and later stages passing.

### 2026-09-21 — S9 partial: eval tooling shipped, 3/10 cases verified (to be revisited)

- Built `src/evaluation.py` and `inspect eval [--cases C02 --cases C04 ...] [--k N] [--parallel N]`.
  Per attempt it scores verdict and per-transaction verdict/credit, account-action overlap, solution-node
  coverage of the trajectory, report grounding (cited ids exist, solution ids cited, decoy ids named),
  the missing-evidence default, and required-capability signals. Each attempt runs in its own process with
  a 900 s alarm so a hang becomes a scored failure with a traceback. Output: `summary.json` and
  `summary.md` under `data/generated/eval/<timestamp>/` (git-ignored). `tests/test_evaluation.py` covers
  scoring with a stub store. The CLI loads `.env` (`python-dotenv` is now a declared dependency).
- Fixes found by real runs: `schemas.Money` (Decimal advertised as a plain JSON number, because OpenAI
  strict schemas reject the regex pydantic emits for Decimal); `graph_store` shares one LadybugDB
  `Database` per file per process (each reserves ~8 TB of address space, so per-worker databases hit
  "Mmap ... failed" after about 15); new generic skill `unrecognized-charges`; `missing-evidence-default`
  now applies only when an unanswered `EvidenceRequest` exists (the agent had used it for data that was
  merely absent from the graph); the skill is a default for `graph_analyst` and `adjudicator`.
- Results with the real model (`gpt-5.6-luna`, one attempt each; verdict and amounts correct, solution
  coverage 1.00 in all three): **C02** not_a_dispute (~7 min), **C04** rejected as expected (~4 min),
  **C08** accepted, 642.90 credit, both decoys named, but it ended by `max_turns` (9 supervisor turns).
- **Queue (not yet run with the real model):** C10, C11, C12, C13, C18, C19, C12b. Then the targets: at
  least 8/10 at pass@1, 10/10 at pass@3, mean coverage at least 0.7. Nothing here should block S11+.
- Known issues to revisit: (1) one C02 run hung after the last `memory_write` in `consolidate_memory`
  (no events for 6 minutes, cause not found; the mmap fix may or may not explain it, the eval alarm
  will now expose it); (2) runs take 4-10 minutes, mostly sequential supervisor and worker calls, and
  C08 used up its turn limit, so consider lower worker reasoning effort or fewer supervisor turns;
  (3) the scorer reports some agent-written edge ids (`E-<hash>`) as "missing" (seen in C02 and C08),
  likely a mapping gap for edges written by `graph_write_finding`; (4) parallel `--parallel N>1` was
  crashy before the mmap fix and has not been retried.
- If S9 tuning changes shared contracts (`CaseReport`, event payloads, `graph_store`), the S10 API and the
  S11+ frontend must be kept working in the same change.
- Verification: `uv run pytest` and ruff pass (see the commit).


### 2026-09-21 — S11 frontend part 1 complete

- Deleted the old console (mission control, evaluation, memory, graph lab, run observatory, command
  palette, navigation rail, inspector context, projections, old API client/types/SSE hook, old e2e
  spec) and the unused `@vitest/ui` dependency. The simplifier also removed the unused `@xyflow/react`, `@playwright/test`, `playwright.config.ts` and the `e2e` script: S12 re-adds `@xyflow/react`, S13 adds `d3-force`, Playwright, its config (webServer `../scripts/dev.sh`) and the e2e script.
- New app (`frontend/src/`): `App.tsx` (router + query client), `api/{types,client}.ts` for the S10
  endpoints, `run/store.ts` (pure `reduceEvent` folding trajectory events into one `RunView`: plan,
  supervisor turn, visits per actor, touched node/edge ids with "found by actor via tool at turn",
  report, termination, status; duplicate `seq` ignored so SSE reconnects are safe),
  `run/useRunEvents.ts` (EventSource; the browser reconnects with `Last-Event-ID`, the hook closes the
  stream after the final event or when `GET /runs/{id}` says the run is no longer active),
  `run/RunContext.tsx` (shared selection, highlight, canvas tab), `pages/CasesPage.tsx`,
  `pages/RunPage.tsx`, `run/Canvas.tsx` (tabs with stand-ins), `run/Inspector.tsx` (raw events of the
  selected actor or graph item), `run/Conclusion.tsx` (live status with open plan items, then the
  full `CaseReport`: verdict ruling, summary, collapsible reasoning, transaction table, hypotheses,
  decoys, missing evidence, policy basis, account actions, cardholder letter; evidence chips call
  `showEvidence`, which sets the shared highlight and switches to the Evidence graph tab).
- Design: cool slate "case file" palette with fixed verdict colours (accepted/partial/rejected/
  informational), Schibsted Grotesk UI, Newsreader for the ruling and cardholder letter, IBM Plex
  Mono for ids; the verdict band is the one deliberate visual moment.
- Integration notes for S12/S13: the API has no `/api/v1` prefix, so the Vite dev proxy strips
  `/api`; `scripts/dev.sh` health checks now use `/health`. Money fields arrive as strings (Pydantic
  Decimal) and are read with `Number()`. Node events use actor kind `graph_node` for every role
  (including ad-hoc roles such as `fraud-pattern-investigator` and `memory_keeper`); `run_started`
  and `error` events are excluded from actor visits. Tool events have actor = tool name and the calling
  role in `payload.caller`. The Agent flow and Evidence graph tabs are stand-ins (actor buttons with
  `×N`, and id chips) that S12/S13 replace; the shared `selection`/`highlight`/`tab` state is the
  contract they plug into.
- Vite binds IPv6 `localhost` only; browser checks must use `localhost`, not `127.0.0.1`.
  `scripts/dev.sh` still probes `127.0.0.1:5173`, so `./dev.sh` and `npm run e2e` need the frontend host
  fixed (`--host 127.0.0.1` is passed there, so it should work; verify in S13).
- Verified in a browser against stored real runs (C08 replay): case grid, live/decided status, actor
  inspector, and evidence-chip highlight into the graph tab.
- Verification: `npx tsc -b`, `npx vitest run` (9 tests: store derivation, conclusion panel), `npm run
  build`, `npm run lint`. No design decision changed and no spec update was required.

### 2026-09-21 — S12 frontend part 2 complete

- Added `@xyflow/react`. `run/flow.ts` derives the whole agent map from trajectory events alone (`deriveFlow`): nodes by region (Planning, Investigation, Tools and memory, Decision) in order of first appearance, per-actor visits (input, output, duration, tokens, skills, tool calls, plan after each supervisor turn, exit reasons), aggregated edges (`forward`, `return`, `self`, `tool`, `decision`) with counts, active visits and last edge. `layout()` gives deterministic positions. `run/AgentFlow.tsx` renders it: dashed return arcs, a self-loop for rejected `Decide` (also a "↻ N rejected" chip), an underpass edge labelled `Decide` or `forced: ...`, `×N` visit badges, pulsing active node, animated last edge while running, ad-hoc roles dashed and tagged, selection dims unrelated edges, refit on new nodes or pane resize. `run/ActorPanel.tsx` + `run/Fields.tsx` are the inspector: every visit as a collapsible block with readable fields for input/output (generic renderer, raw JSON toggle), plan checklist, skills, tool calls; tool nodes list all their calls.
- Deviations: (1) Investigation wraps into another column after 6 roles (real runs invented up to 22 ad-hoc roles), so regions right of it shift one slot when that happens; nothing else moves. (2) Crowded maps (more than 16 edges) draw edges at half opacity and hide count labels until a node is selected. (3) The "selected agent publishes touched node ids" hook was removed by the simplifier as unused; S13 should derive it from `Flow.visits[name].tools` / `Flow.toolCalls[tool]` (each call has `nodeIds`/`edgeIds`) and add it to `RunPanels`. (4) Ad hoc = the supervisor gave the task `instructions`; tool calls by `memory_keeper` without a delegation parent are filed under `consolidate_memory`.
- Verified in a browser against stored real runs (C04 and C08 replays; C08 has 22 roles). Playwright is not yet a project dependency (S13 adds it).
- Verification: `npx tsc -b`, `npx vitest run` (20 tests: flow derivation, layout stability and wrapping, inspector), `npm run lint`, `npm run build`; `uv run pytest` passes. No design decision changed.

### 2026-09-21 — S13 frontend part 3 complete

- Added `d3-force` and `@playwright/test`. New files in `frontend/src/run/`: `graphModel.ts` (region, colour and icon name per label; caption; agent-written test; neighbour-to-node/edge mapping), `GraphIcon.tsx` (26 line icons), `evidenceLayout.ts` (`layoutGraph`: d3-force run synchronously to settle, links plus a pull toward each node's region column, collision, clamp inside the loop; new nodes start beside a placed neighbour so growth does not reshuffle; column widths scale with the node count in steps), `evidence.ts` (`touchedBy(flow, actor|tool)`, `citedBy(report)`), `useEvidenceGraph.ts` (fetches `GET /graph/nodes?ids=&run_id=` in batches as touched ids grow, then missing edge endpoints; `expand(id)` uses `/graph/neighbors`), `EvidenceGraph.tsx` (React Flow, three region bands Identity / Commerce / Case and knowledge, nodes coloured with icon and caption, edge type labels, parallel edges bent apart, agent-written nodes and edges dashed in `--color-agent`, new nodes ring-flash while the run is live, double-click expands one hop as faded context), `GraphItemPanel.tsx` (inspector for a node or edge: properties, dated connections that can be clicked, "found by <agent> with <tool> in turn N", raw events).
- Highlighting: evidence chips from the conclusion focus exactly those nodes and edges (banner with "Show everything"); selecting an agent or tool on the flow tab dims the graph to what it touched (`touchedBy`); cited evidence gets a yellow ring after the decision; an Evaluation overlay toggle (solution ring green, decoy ring red dashed, "n of m solution nodes found") appears when `/eval/latest` has the case.
- Deviation: real runs touch hundreds of nodes (survey queries return many isolated rows), which was unreadable. The graph has a scope switch: **Connected** (default: nodes with a drawn edge, agent-written nodes and cited nodes), **Everything touched**, **Cited only**.
- Deviation: icons are 26 hand-drawn SVG line icons rather than an icon library (no new UI dependency). Labels shown under nodes are the first readable property (`name`, `text`, `street`, ...) or the id.
- `RunPage` is keyed by run id, so "Run again" resets selection, highlight and graph state. `RunPanels` gained `graph`, `cited`, `clearHighlight`.
- E2E: hermetic, no LLM. `tests/e2e_server.py` serves a tiny graph with scripted agents that call the real tools (so events carry graph ids); `frontend/playwright.config.ts` starts it on :8100 and Vite on :5273 (`API_URL` env overrides the proxy target in `vite.config.ts`). `frontend/e2e/run-page.spec.ts`: cases page, click case, agent map nodes, "Decided", evidence graph nodes, verdict, node inspector "Found by", chip focus, agent-selection dimming. Deviation: the plan said use `scripts/dev.sh`; the hermetic stack was chosen so the test needs no API key or generated data. `./dev.sh` still works (verified by hand against stored real runs C04 and C08).
- Verification: `npx tsc -b`, `npx vitest run` (28 tests), `npm run lint`, `npm run build`, `npm run e2e` (1 passed), `uv run pytest` (66 passed, 1 deselected), ruff check and format clean. Code-simplifier pass done. No design decision changed.
- Open: the Playwright browser must be installed once (`npx playwright install chromium`); the frontend bundle is over 500 kB (warning only).

### 2026-09-21 — S13b inspector capsules and saved results
- Inspector: every section is now a colour-coded collapsible capsule (`run/Capsule.tsx`; tone tokens `--color-model/reason/next/plan/hypo/facts/tools/input` in `index.css`, `@theme static` so Tailwind keeps them). A visit shows metadata pills (turn, time, tokens, skills), then a solid-header **Model output** capsule (`run/ModelOutput.tsx`) with cards for Reasoning, Next step (delegate tasks or decide), Plan / plan edits, Hypotheses, Facts, Investigation summary, then Other fields, Graph items cited and Raw JSON; then Tool calls (arguments and result), Plan after this turn, Input. The schema name comes from `model_call` (`Visit.schema`). Graph item panel uses capsules for Properties, Connections and Events. Inspector column widened to `minmax(26rem, 32%)`.
- Saved results: `GET /cases` now returns `latest_run_id` and `latest_verdict` (newest inactive run with a `decision` event and its graph copy in `data/generated/runs`; failed runs never count). Clicking a case opens that run without running; "Run again" (card footer and run page header) starts a fresh run. Cases without one show "Not run yet". `schemas/openapi.json` regenerated.
- Verification: `npx tsc -b`, vitest (29), lint, build, `npm run e2e` (1 passed), `uv run pytest` (67 passed), ruff clean; checked in a browser on stored runs C04 and C08. Code-simplifier pass done. No design decision changed.

### 2026-09-21 — S13c resizable report panel
- The conclusion panel (`run/Conclusion.tsx`) has a drag handle on its top edge (`role="separator"`): drag or ArrowUp/ArrowDown (40 px steps) to resize up to 75% of the window; below 48 px it collapses to the verdict strip; double-click cycles strip, 34% and 66% of the window. The height is kept in `localStorage` (`disputeai.report-height`, wrapped in try/catch). "Hide details"/"Show details" toggles between the strip and the last open height.
- A section row (Summary, Transactions, Hypotheses, Decoys and policy, Letter) scrolls inside the panel to that section. Clicking an evidence chip calls `showEvidence` and collapses the panel to the strip so the graph is visible; "Show details" restores it.
- Verification: `npx tsc -b`, vitest (30, incl. chip collapse and keyboard resize), lint, `npm run e2e`; dragged in a browser on the stored C04 run (340 to 596 px, persisted over a reload). Code-simplifier pass run. No design decision changed.

### 2026-09-21 — S14 final cleanup complete
- Spec status is now "approved". Repo-wide code-simplifier pass: deleted `src/storage.py` (no callers), `put_blob`/`run_blobs` and `last_event` in the emitter, unused `ConcurrencyConfig`/`RetryConfig`/`max_attempts` (and their keys in `config/models.yaml`), `RunView.termination` in the frontend store; named the eval SIGALRM handler; renamed `OBS_*` vars in `scripts/dev.sh`; replaced `tests/test_surviving_modules.py` with `tests/test_emitter.py` (health and models-config checks moved to `test_api.py` / `test_schemas_models.py`).
- Leftover grep (`playbook`, `governance`, `virtual_clock`, `persona`, `scheduler`, `route_id`, `hash_chain`, `redact`, `queue`): only legitimate hits remain (`asyncio.Queue` in the emitter, domain policy text in `data/corpus`, and the "no hash chain" wording in tests).
- Left for the owner: `pyproject.toml` still names the project `card-dispute-agent`.
- Verification: `uv run pytest` 67 passed, 1 deselected; ruff check and format clean; frontend `tsc -b`, vitest (30), lint, build, `npm run e2e` (1 passed). Docs rewrite and full `inspect eval` were dropped from S14 by decision.

### 2026-09-21 — S9 continued: remaining 7 cases verified with the real model
- Ran `inspect eval` for C10, C11, C12, C12b, C13, C18, C19 (k=1, parallel 4, no prompt or code changes; no run hung, each was watched for stalled event streams every 120 s). All 7 passed: verdict and per-transaction amounts correct, missing-evidence default applied, solution coverage 1.00 each. With C02, C04 and C08 from the earlier entry, pass@1 is **10/10** and mean coverage 1.00, meeting the pass@1 and coverage targets. Runs took about 8-14 minutes each.
- Weak spots (not failures under the current scorer): decoys named in the report were 0/2 (C10, C12, C18), 0/1 (C13, C19), while C11 (1/1) and C12b (4/4) named them; cited-solution share was 0.50 for C19, 0.88-0.92 for C10, C12 and C18. Candidate tuning: have the adjudicator prompt/skill require ruling out matched decoys explicitly.
- Not done: pass@3 across the 10 cases; the earlier known issues (consolidate_memory hang, scorer missing `E-<hash>` edge ids) did not reappear in these runs.

### 2026-09-21 — Committed showcase (stored results in a fresh clone)
- `src/showcase.py`: `export()` (CLI `inspect showcase-export`) snapshots into `data/showcase/` (about 12 MB, committed): the base evidence graph as gzipped JSONL, case catalog, ground truth, a merged eval summary (newest result per case), the knowledge store, and for the latest completed run of each case its trajectory events (`runs/<run_id>.events.jsonl.gz`) plus what the agents added to that run's graph (`<run_id>.graph.json`: Finding/MemoryNote nodes, provenance edges, retired note statuses). `install()` runs when the API starts with its default context: it rebuilds whatever is missing under `data/generated/` (graph load takes seconds), inserts the events into `trajectory.sqlite` and recreates each run's graph copy, so `GET /cases` reports `latest_run_id` and the UI opens the stored run. Only "Run again" calls the model (needs `OPENAI_API_KEY`). Installed eval summary is batch `0-showcase`, so a newer real eval batch takes over in `/eval/latest`.
- Re-export after new runs: `uv run inspect showcase-export`, then commit `data/showcase/`.
- Removed the dead column migration from `emitter.init_event_db` (extracted so `install` can create the table).
- Verification: `uv run pytest` (68 passed, incl. `tests/test_showcase.py` round trip), ruff clean, code-simplifier pass done.

### 2026-09-21 — Verdict definitions in the adjudicator prompt; C02 and C04 scored for the showcase
- A fresh C04 run reasoned correctly but labelled the verdict `not_a_dispute` where the ground truth says `rejected`; no prompt or schema defined the difference. `config/agents.yaml` (adjudicator prompt) now defines the verdicts generically: `accepted`/`partially_accepted` when credit is due, `rejected` when the cardholder asserts a specific wrong and the evidence shows it did not happen, `not_a_dispute` only when the cardholder merely did not recognise a genuine charge. No case-specific wording.
- `inspect eval --cases C02 --cases C04`: 2/2 pass (C04 now `rejected`, decoys 2/2; C02 still `not_a_dispute`). The other 8 cases were last scored before this prompt change and were not re-run (decision: their earlier scored runs stand, so their pass status reflects the previous prompt).
- Showcase re-exported: the stored C02 and C04 runs are the scored eval runs, so the overlay and the stored run agree for all ten cases.
