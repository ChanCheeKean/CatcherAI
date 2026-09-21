# CatcherAI — agentic graph-discovery revamp: handoff

Last updated: 2026-09-21
Current phase: **S1 — Graph foundation complete**
Next stage: **S2 — Background world generator**

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

- Python env: `uv sync --extra dev --extra graph --extra api` (LadybugDB comes from the `graph`
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
  `docs/superpowers/plans/2026-09-16-*`, `docs/technical.md` (rewritten in S14)
- Every test in `tests/` whose subject was deleted. Keep tests only for surviving modules.

Keep: `src/domain/events.py`, `src/observability/emitter.py`, `src/replay.py`, `src/storage.py`,
`src/memory/retrieval.py`, `src/config.py` (drop its `domain.model` dependency; keep
`ModelsConfig` loading only), `src/cli.py` (reduce to commands that still work, or to an empty
Typer app), `src/api/app.py`, `src/api/errors.py`, `src/api/routers/meta.py`, `data/corpus/`
(except `skills/`), `skills/` (rewritten in S5), `config/models.yaml`, `frontend/` (untouched until
S11), `README.md` (rewritten in S14; add one line at the top saying it is being rewritten).

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

### S2 — Background world generator  ☐
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

### S3 — Case kit, validation, and cases 1–5  ☐
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

### S4 — Cases 6–10, missing evidence, capability map  ☐
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

### S5 — Knowledge store and skills  ☐
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

### S6 — Schemas, config and model setup  ☐
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

### S7 — Agent tools  ☐
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

### S8 — Agent runtime (LangGraph)  ☐
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

### S9 — Real-LLM evaluation and tuning  ☐
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

### S10 — API  ☐
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

### S11 — Frontend part 1: shell, cases page, run page layout, conclusion  ☐
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

### S12 — Frontend part 2: agent-flow graph + inspector  ☐
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

### S13 — Frontend part 3: evidence graph, highlighting, E2E  ☐
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

### S14 — Documentation and final cleanup  ☐
**Complexity: Medium**

Goal: docs a new developer and a demo audience can follow; zero leftovers.

Do: rewrite `README.md` (what it is, a 5-minute quickstart, the demo script per case with
screenshots of the run page, architecture diagram) and `docs/technical.md` (runtime, graph
ontology, tools, schemas, events, frontend data flow, eval, "add a role / skill / case type /
case"). Remove the spec's "pending review" status. Final repo-wide `code-simplifier` pass; `rg`
for leftovers of removed concepts (`playbook`, `governance`, `virtual_clock`, `persona`,
`scheduler`, `route_id`, `hash_chain`, `redact`, `queue`) and remove them. Full verification:
pytest, ruff, frontend checks, E2E, and one full `inspect eval` recorded in §8.

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
