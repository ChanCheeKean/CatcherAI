# Dispute Observatory implementation handoff

Last updated: 2026-09-15  
Repository: `/Users/kean/Dev/CatcherAI`  
Branch / starting commit: `main` / `63e521b`  
Current phase: Stage 4 (advanced observability) COMPLETE
Next stage: Stage 5 — evaluation and interaction polish

## Current objective

Build **Dispute Observatory**, a polished dark-mode frontend for running and inspecting the
card-dispute agent in real time. It must expose routes, workflow nodes and edges, subagents, tools,
skills, memory reads/writes, graph traversals, computations, waits and virtual time, verifier checks,
governance-panel positions, decisions and field-level provenance. It also needs a backend API, live
event streaming and a shell script that starts backend and frontend together.

The design is complete. Implementation must proceed one stage at a time, and this handoff must be
updated after every stage.

## Start here next session

Read these files completely, in order, before editing:

1. `docs/prompts/03-observability-console-kickoff.md` — implementation rules for the new initiative.
2. `docs/design/07-observability-console.md` — authoritative UX, API/SSE contract, architecture,
   source layout, six stages and acceptance gates (Stage 1 and Stage 2's entries now reflect what
   was actually built).
3. `README.md` — current working commands, including the "Dispute Observatory API" section
   (execution endpoints table added in Stage 2).
4. `docs/design/05-agent-architecture.md` — runtime boundaries and automation constraints.
5. `docs/design/03-data-dictionary.md` — data stores, joins and private-data boundaries.
6. `schemas/trajectory-event.schema.json` and `src/domain/events.py` — canonical frontend event.
7. `src/observability/emitter.py`, `src/replay.py`, `src/decisions.py` — event persistence, replay,
   blobs, hash chains and decision provenance.
8. `src/runtime/langgraph_runtime.py`, `src/bootstrap.py`, `src/cli.py` — lifecycle methods
   `src/api/run_manager.py` wraps rather than duplicates (`start`/`result`/`resume`/`cancel`/
   `events`, plus the new `is_done`).
9. `src/api/run_manager.py`, `src/api/sse.py`, `src/api/dependencies.py`, `src/api/read_models.py`
   — the Stage 2 execution/streaming layer Stage 3's frontend will call against. Read this before
   adding any memory/graph/source router or touching run lifecycle: the isolated-store registry has
   already replaced Stage 1's single-`db_path` shortcut; extend it rather than re-adding a shortcut.
10. For historical implementation context, `docs/prompts/02-implementation-kickoff.md`,
    `docs/design/06-eval-results.md` and the remaining design/research documents.

Stage 4's acceptance gate is met; see its stage-history entry for exact evidence. Stage 5 adds
evaluation/capability navigation, replay controls, deep links, queue visualization and performance
polish. Continue extending the existing `frontend/src/` feature structure and deterministic
`RunProjection`; do not move replay or evaluation semantics into React components.

## Product and UX decision

The planned console has five core areas:

- **Mission Control:** case browser, Q01 queue, run launcher and recent run status.
- **Live Run Observatory:** workflow graph, live/replay timeline, actor swimlanes, filters, playback
  and usage/budget/clock metrics.
- **Decision & Provenance:** separate cardholder/network outcomes, conditions, confidence, panel,
  actions, deadlines and clickable field-to-event/source provenance.
- **Memory Explorer:** persistent notes, semantic retrieval and graph hypotheses with as-of/status/
  scope filters and lifecycle history.
- **Graph Lab:** runtime graph plus bounded operational entity graph with query/write overlays.

“Thought” is intentionally rendered as **Reasoning Artifacts**: recorded plans, tool rationales,
hypotheses, contradictions, verifier checks, panel positions and explanations. Do not expose, request
or fabricate private chain-of-thought.

The visual direction is a near-black navy investigation workbench with cyan active execution, violet
model/subagent work, amber waits/deadlines, emerald verification and rose contradiction/failure.
Desktop uses a resizable three-pane layout. Animations correspond only to committed events.

## Architecture decision

Use a presentation adapter, not a second application core:

```text
frontend/ React + TypeScript + Vite
  REST + EventSource → disposable deterministic event projections
                         │
src/api/ FastAPI
  typed read models + RunManager + reconnectable SSE + source resolver
                         │
existing runtime/replay/decision/memory/graph boundaries
                         │
isolated SQLite/checkpoint/Ladybug stores
```

Chosen implementation stack:

- FastAPI + Uvicorn + Pydantic DTOs.
- Native FastAPI SSE (`EventSourceResponse`) rather than WebSockets.
- React + TypeScript + Vite.
- TanStack Query for REST server state and a custom SSE hook for append-only events.
- React Flow for both workflow and bounded entity graphs.
- Tailwind CSS theme tokens; accessible headless primitives where needed.
- Vitest + React Testing Library; Playwright in the integrated stage.

The backend API namespace is `/api/v1`. Vite proxies `/api` to port 8000; frontend runs on 5173.
The final launcher is `scripts/dev.sh`, optionally with root `dev.sh` as a convenience shim.

### Critical API decisions

- `POST /api/v1/runs` creates an isolated store, starts `LangGraphRuntime.start()` in a background
  task and immediately returns `202` with the run ID and stream URL. **Built in Stage 2.**
- `GET /api/v1/runs/{run_id}/events/stream` sends complete canonical events, SSE `id=seq`, honors
  `Last-Event-ID`, emits heartbeats and closes after the terminal suffix is committed. **Built in
  Stage 2** (`src/api/sse.py`); see that stage's handoff entry below for the one non-obvious
  correctness problem it had to solve (a run can emit more than one `termination` event).
- A small durable UI registry (`data/generated/ui/registry.sqlite`) maps run IDs to isolated store
  paths/status so history survives API reloads. **Built in Stage 2** (`src/api/run_manager.py`).
- SSE tails committed SQLite rows rather than subscribing to the in-process `EventEmitter`, exactly
  as planned — it works for live, replay and reloaded API processes uniformly. **Built in Stage 2.**
- Memory, graph and source endpoints are explicit read models/resolvers. Never accept arbitrary SQL
  or filesystem paths. **Not yet built** — planned for Stage 4.
- The browser never receives `OPENAI_API_KEY`; it only sees whether the OpenAI adapter is available.
  Verified again in Stage 2 (the same `test_meta_never_returns_the_openai_key` test from Stage 1).

Full endpoint tables and response behavior are in `docs/design/07-observability-console.md` §5.

## Non-negotiable constraints

- The product remains fully automated. No human approval, review queue or adjudication control.
- UI controls may launch, cancel, rerun, filter, pause/seek playback and inspect. Pausing playback
  never pauses the actual agent.
- Every visualization comes from canonical events or persisted operational records. If an event is
  unknown, show a generic raw-event card; never discard it or crash.
- Never expose `data/generated/ground_truth/**` or `data/generated/simulation/**` through the API.
- Never expose arbitrary SQL, arbitrary paths, secrets or unredacted blob content.
- UI-started runs default to fake and always use copied stores under `data/generated/ui/`; they must
  not mutate `data/generated/catcher.sqlite`.
- Domain policy, routing, governance, actions and memory-write decisions stay outside `src/api/` and
  `frontend/`.
- Keep Python flat under `src/`; do not recreate a product-named package wrapper.
- Commit and push at the end of every completed stage (standing authorization; see "Mandatory
  handoff maintenance" below). Never use destructive git operations (reset, force-push, history
  rewrite) unless the user explicitly asks for those specifically.
- Production security/infrastructure is out of scope, but basic boundary correctness—especially no
  secret/private-fixture exposure—is required for a functional UI.

## Stage plan

### Stage 0 — Design and handoff: COMPLETE

Delivered:

- `docs/design/07-observability-console.md`: full product, visual, API, streaming, projection,
  testing, launcher and staged implementation design.
- `docs/prompts/03-observability-console-kickoff.md`: next-session implementation prompt.
- README and base architecture links/extension notes.
- This rewritten handoff.

No runtime, dependency or frontend source changes were made in Stage 0.

### Stage 1 — Read-only API foundation: COMPLETE

Delivered exactly the planned scope, nothing more:

- `src/api/app.py` — FastAPI app factory (`create_app(root, db_path=None)`); module-level `app`
  for `uvicorn api.app:app --app-dir src`.
- `src/api/dependencies.py` — request-scoped dependencies for the root path, the configured
  `db_path`, a read-only sqlite connection, and cached `ModelsConfig`/`RoutesConfig`/
  `ScenarioConfig` loaded once at app-creation time.
- `src/api/errors.py` — one `ApiError` exception mapped to the one error envelope
  (`{"error": {"code", "message", "details"}}`) via a FastAPI exception handler.
- `src/api/models.py` — stable response DTOs. Reuses the existing canonical `EventEnvelope`
  (`domain.events`) and raw `DecisionRecord` JSON rather than re-deriving frontend-facing shapes
  for those two, per the design's "never expose sqlite rows ad hoc" rule.
- `src/api/read_models.py` — all SQL. Every query opens `sqlite3.connect(..., mode=ro)`; queries
  are plain, parameterized, and never touch `ground_truth/**` or `simulation/**` (those tables
  aren't even loaded into `catcher.sqlite` — see `data/generator/load_sqlite.py`). Run status is
  *derived*, not stored: see the note below.
- `src/api/workflow_graph.py` — a small hand-maintained static description of the LangGraph node/
  edge wiring in `runtime.langgraph_runtime.LangGraphRuntime._build_graph`, for `/meta/workflow`.
  It is not introspected from the graph object because the node functions there are per-run
  closures; if that wiring changes, this file needs a matching edit (called out in its docstring).
- `src/api/routers/{meta,cases,runs}.py` — the endpoints below.
- `schemas/openapi.json` — generated OpenAPI document (regenerate command in `README.md`).
- `tests/test_api.py` — 8 new tests using the existing `project_root`/`scenario_db`/`runtime`/
  `make_runtime` fixtures from `tests/conftest.py`, so every API test runs against a
  `tmp_path`-copied store, never the pristine `data/generated/catcher.sqlite`.

Endpoints (all under `/api/v1`, all read-only, all returning the one error envelope on failure):

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | store reachability, `scenario_db_path` |
| GET | `/meta` | adapter availability (never the key value), model, virtual clock, feature flags |
| GET | `/meta/routes` | `config/routes.yaml`, sorted by priority |
| GET | `/meta/agents` | `config/agents/*.yaml` |
| GET | `/meta/skills` | `skills/*/SKILL.md` front matter (the repo-root `skills/` dir the runtime actually loads from — not `data/corpus/skills`) |
| GET | `/meta/workflow` | static `{nodes, edges}` for the React Flow canvas |
| GET | `/schema/events` | `domain.events.event_json_schema()` |
| GET | `/cases` | filters `regime`/`status`/`stage`/`claim_family`/`q`; `limit`+`cursor` paging |
| GET | `/cases/{case_id}` | case + disputed transactions + communications summary + `latest_runs` |
| GET | `/runs` | filters `case_id`/`status`; `limit`+`cursor` paging |
| GET | `/runs/{run_id}` | derived status, event/wait/decision-availability summary |
| GET | `/runs/{run_id}/events` | filters `after_seq`/`type`/`actor`/`ref`; returns `{items, next_after_seq, limit}` |
| GET | `/runs/{run_id}/decision` | full `DecisionRecord` JSON + field-level `event_seqs`/`source_ids` provenance |

Deliberate Stage-1-only decision, to be revisited in Stage 2: `create_app` takes one `db_path` for
the whole process (defaulting to `data/generated/catcher.sqlite`), not a run registry mapping many
run IDs to many isolated stores. That is enough to satisfy the Stage 1 acceptance gate ("inspect a
historical run") because nothing writes new runs through the API yet; Stage 2's `RunManager`
supersedes this with the planned `run_id -> isolated db path` registry so the UI can hold many
concurrent/historical runs across many copied stores at once.

Non-obvious implementation note for whoever builds Stage 2: a run's `status` is derived by finding
the **latest `error` or `termination` event**, not simply by reading the highest-`seq` row. The
`terminate` graph node emits `termination` (with `payload.final_status`) and then a trailing
`run_completed` event, and `_drive()`'s checkpointer wrapper commits one more `checkpoint_saved`
event after the graph finishes — so the literal last row for a decided run is `checkpoint_saved`,
not `termination`. `read_models._derive_status` accounts for this; keep that in mind if Stage 2
adds a live "running" status computed the same way from an in-flight store.

Verified commands and results:

```bash
uv sync --extra dev --extra graph --extra api        # installs fastapi, uvicorn, sse-starlette, httpx
uv run pytest                                          # 86 passed, 1 skipped, 1 warning (was 78/1)
uv run ruff check src tests                            # All checks passed!
uv run ruff format --check src tests                   # 94 files already formatted
uv run uvicorn api.app:app --app-dir src --reload      # http://127.0.0.1:8000/api/v1/health
```

`curl` acceptance (verified manually against a copied store with one completed `DSP-2026-90002`
run, via a temporary `uvicorn` process — not a committed script): `GET /api/v1/health`,
`GET /api/v1/cases?limit=2`, `GET /api/v1/runs/{run_id}`, `GET /api/v1/runs/{run_id}/events?limit=3`
and `GET /api/v1/runs/{run_id}/decision` all returned correct, well-formed JSON; the pristine
`data/generated/catcher.sqlite` was confirmed unmodified afterward (`git status` clean on it, and
it still has no `run_events`/`decision_records` tables).

Known limitations carried into Stage 2 (honest, not blocking):

- No execution manager: the API cannot start, cancel or rerun a case yet, and there is exactly one
  configured store per running API process.
- No SSE stream: `/runs/{run_id}/events` is a paged REST snapshot only.
- `/cases` cannot filter or sort by deadline, because deadlines are deliberately not stored in the
  dataset (computed only during a run's `compute_clocks` node). This is unchanged from the
  original design decision documented in the data dictionary, not a new gap.
- `/health` originally also reported `graph_available` (whether the `ladybug` package was
  importable). Removed in the post-Stage-2 cleanup pass below: it measured the wrong library (the
  real optional graph backend is `ladybug`, but the field always read `False` in this environment
  in a way disconnected from whether the NetworkX fallback — which always works — was in use), so
  it was misleading rather than informative. See that pass's entry in the stage history.

### Stage 2 — Execution manager and live stream: COMPLETE

Delivered exactly the planned scope:

- `src/api/run_manager.py` — `RunManager`: one copied store + `LangGraphRuntime` per UI-started run
  under `data/generated/ui/`, plus a durable SQLite registry (`data/generated/ui/registry.sqlite`)
  mapping `run_id -> {store_path, case_id, kind, adapter, auto_resume}` so run history and store
  routing survive an API restart. Live runtime/task objects (for `cancel()` and for knowing whether
  a run's own task is still alive) exist only in this process's memory.
- `POST /runs`, `POST /runs/{run_id}/cancel`, `POST /runs/{run_id}/rerun`, `POST /queue/runs`,
  `GET /queue/runs/{run_id}` (`src/api/routers/runs.py`, `src/api/routers/queue.py`).
  `runtime.portfolio.rank_portfolio` gained an optional `run_id` parameter, backward compatible
  with the CLI's `queue` command, so the API can know a queue run's ID before ranking finishes.
- `GET /runs/{run_id}/events/stream` (`src/api/sse.py`) — polls the run's SQLite store (per the
  design's own guidance), using `sse_starlette.EventSourceResponse`'s `ping=15` for heartbeats and
  `Last-Event-ID`/`after_seq` for gap-free reconnect.
- `src/api/dependencies.py` gained `get_run_manager`, `get_run_connection` (routes a single run to
  its store via the registry, falling back to the app's configured store for Stage-1-style direct
  runs) and `get_all_connections` (every known store, for `GET /runs`'s cross-store merge).
- `tests/test_api_stage2.py` — 8 tests using `httpx.AsyncClient` over an in-process ASGI transport.

**One real bug found and fixed, worth knowing before touching this code**: a run that suspends and
auto-resumes *internally* (an evidence wait mid-investigation, not just the run's true end) emits
one `termination` event **per segment**, not only at the very end — `prepare_wait`'s `_suspend()`
helper in `langgraph_runtime.py` emits it unconditionally, then loops back into the graph when
`auto_resume=True`. Naively closing the SSE stream on the first `termination` event truncates a
live multi-wait run. Fixed with `LangGraphRuntime.is_done(run_id)` / `RunManager.is_task_done`,
which report whether *this process's own asyncio task* for that run has actually finished — true
exactly once, when no more events can ever be appended by it. `api/sse.py` only falls back to the
persisted latest-`termination`/`error` status (safe, because nothing more will ever be written) for
a run this process doesn't manage (historical, or started by a different process).

A second, smaller fix: mixing an `async def` endpoint with a plain sync generator dependency made
FastAPI resolve the dependency in a worker thread while the endpoint body ran on the event loop
thread — `sqlite3` connections are thread-affine, so this crashed with `ProgrammingError`. Fixed by
making `get_run_connection`/`get_all_connections` async generators and every run-lifecycle endpoint
`async def`, so connection creation and use always happen on the same thread.

Verified commands and results:

```bash
uv run pytest                        # 94 passed, 1 skipped (was 86/1)
uv run ruff check src tests          # All checks passed!
uv run ruff format --check src tests # 99 files already formatted
```

Live `curl`/manual acceptance against a temporary `uvicorn` process (not a committed script):
started a case run (`202` immediately), streamed it via `curl -N .../events/stream` from seq 1
to `termination`, started and cancelled a second run, reran the first, started and drained a Q01
queue run (95 open cases ranked, rank 1 shown), listed `GET /runs` merged across stores, and
confirmed via `git status`/sha256 that `data/generated/catcher.sqlite` was byte-identical before
and after every one of those API calls.

Known limitations carried into Stage 3 (honest, not blocking):

- Cancel and SSE liveness both key off this process's in-memory `RunManager`; a run started by a
  different API process (or before a restart) can still be inspected/replayed but not cancelled
  from this process, and its stream closes via the persisted-status heuristic rather than true
  liveness. This matches the design's own scoping note that `LangGraphRuntime` keeps active
  tasks/emitters in-process.
- `GET /queue/runs/{run_id}`'s ranking is cached in `RunManager` memory only (not persisted); it is
  lost on an API restart, though the run's own events (including `portfolio_ranked`) are not.
- No dedicated test forces a failure *after* a large event prefix has already streamed (only an
  immediate bad-`case_id` failure, and a cancel-race test); prefix retention is structural (append-
  only, hash-chained SQLite) rather than something this stage's tests needed to prove separately.
- There is still no `POST /runs/{run_id}/resume` endpoint (it was never in the design's Stage 2
  table); a genuinely suspended (`auto_resume=false`) run stays suspended until resumed some other
  way (CLI `catcher resume`).
- Memory, graph and source read models/routers do not exist yet — planned for Stage 4.

### Stage 3 — Frontend shell and Mission Control: COMPLETE

See the stage history entry below for exactly what was built, the one deliberate design deviation
(hand-rolled SSE parsing instead of `EventSource`), the one real backend bug found and fixed, and
honest known limitations carried into Stage 4.

### Stage 4 — Advanced observability: COMPLETE

- Workflow graph, swimlanes and specialized event inspectors.
- Plans, hypotheses and safe Reasoning Artifacts.
- Decision/provenance/source/blob explorer.
- Memory Explorer and bounded Graph Lab, API and UI.
- Demonstrate C06 replan, C11 subagents/reopen, C13 wait/policy gap and C12/C12b graph contrast.

### Stage 5 — Evaluation and interaction polish (NEXT)

- Capability matrix and proving-event navigation.
- Replay seek/speed/filter/bookmark controls, deep links and command palette.
- Q01 deadline visualization and optional bounded fake-eval trigger.
- Responsive/performance polish on the largest trace.

### Stage 6 — Integrated launcher and final verification

- `scripts/dev.sh` starts FastAPI and Vite, waits for health, forwards `.env` only to backend, and
  traps Ctrl-C to stop both.
- Vite proxy, README commands, Playwright end-to-end path and final build/test/eval validation.

## Existing backend state to preserve

The backend POC is complete and currently supports 20 hero cases plus Q01:

- One route-independent LangGraph runtime with playbook hooks.
- Real checkpoint suspend/resume for evidence, provider records and persona replies.
- Deterministic regulatory/network clocks, computations and termination.
- Automated governance panel, verifier checks and conservative default.
- Persistent, semantic and graph memory with governed lifecycle writes.
- Structured model/tool/subagent/skill/memory/graph/sandbox/harness/action events.
- Field-level decision provenance, blob persistence, event hash chains and CLI replay.
- Fake and real OpenAI Responses adapters.

POC robustness work also removed fixture-specific playbook values and added three presentation
perturbations per route.

Material backend entry points:

| Concern | File |
|---|---|
| Runtime lifecycle and event stream | `src/runtime/langgraph_runtime.py` |
| Canonical event persistence/subscription | `src/observability/emitter.py` |
| Replay/hash verification | `src/replay.py` |
| Decision and field provenance | `src/decisions.py` |
| Runtime construction and isolated stores | `src/bootstrap.py` |
| Shared sqlite connection helper (core + API) | `src/storage.py` |
| Operational reads | `src/data/access.py` |
| Memory | `src/memory/notes.py`, `src/memory/retrieval.py` |
| Entity graph | `src/memory/graph.py` |
| Existing lifecycle commands | `src/cli.py` |
| Event schema + shared row/hash-chain helpers | `src/domain/events.py`, `schemas/trajectory-event.schema.json` |
| API read-only foundation (Stage 1) | `src/api/app.py`, `src/api/dependencies.py`, `src/api/models.py`, `src/api/read_models.py`, `src/api/routers/{meta,cases}.py` |
| API execution manager + SSE (Stage 2) | `src/api/run_manager.py`, `src/api/sse.py`, `src/api/routers/{runs,queue}.py` |
| Frontend shell and Mission Control (Stage 3) | `frontend/src/app/`, `frontend/src/api/`, `frontend/src/features/{mission-control,run-observatory}/`, `frontend/src/projections/runProjection.ts` |

## Last verified baseline

Verified after Stage 3 (see stage history below; this is the current baseline — earlier baselines
are kept below for history):

- Backend unchanged by Stage 3 except the two-file thread-affinity fix in `src/api/dependencies.py`/
  `src/api/routers/cases.py` (see that stage's history entry): `uv run pytest` — **94 passed, 1
  skipped** (same count), `uv run ruff check src tests` / `uv run ruff format --check src tests` —
  both clean.
- Frontend (`frontend/`): `npx tsc -b` clean; `npm run test` (Vitest) — **5 passed**; `npx oxlint` —
  0 errors, 3 warnings (react-refresh export-shape notices and one intentional
  set-state-in-effect); `npm run build` — clean, 370 KB JS / 14 KB CSS (gzip 115 KB / 4 KB).
- Live manual verification: `uv run uvicorn api.app:app --app-dir src --port 8000` +
  `npm run dev` (Vite on `[::1]:5173`, proxying `/api`), driven with a throwaway Playwright script
  (not committed — Stage 6 owns the committed E2E test): launched C02 (`DSP-2026-90002`, fake
  adapter) from Mission Control, timeline reached 132 live events with zero browser console errors,
  run reached `Decided` with the cardholder/network decision panel visible, all without a reload.
  Also exercised the Q01 queue launcher and a 390px mobile viewport. Screenshots were taken to
  self-review the visual design (not committed as repo artifacts).

Verified after the post-Stage-2 cleanup pass (prior baseline, kept for history):

- `uv run pytest` — **94 passed, 1 skipped** (unchanged count; the cleanup pass touched behavior,
  not test coverage), ruff check and format both clean (100 files formatted).
- Full fake evaluation (`catcher eval` over all 20 hero cases + Q01, `--adapter fake`) — **21/21**
  passed. `data/generator/validate.py` — **401/401**.
- One live end-to-end run on the real OpenAI adapter (`DSP-2026-90002`, `gpt-5.6-luna`, Responses
  API) against an isolated store copy: reached `decided` with a valid hash chain (396 events,
  `catcher replay --db ... hash_chain_valid=True`); pristine `catcher.sqlite` confirmed
  byte-identical (sha256) before and after.
- Live `uvicorn` smoke test of the full run lifecycle (`POST /runs` → `GET /runs/{id}` →
  `GET /runs` → `POST /runs/{id}/rerun`) against the API, including the rewritten `_runs_for_cases`
  read model and `RunManager`'s config-reuse/finished-run-sweep changes; pristine store confirmed
  unmodified afterward.

Verified at the end of Stage 2 (prior baseline, kept for history):

- `uv run pytest` — **94 passed, 1 skipped** (was 86/1), 1 deprecation warning from
  `starlette.testclient` (an upstream `anyio` alias notice, not our code). The 8 new tests live in
  `tests/test_api_stage2.py`; every Stage 1 test (`tests/test_api.py`) and the prior backend
  baseline are unchanged and still green.
- `uv run ruff check src tests` — all checks passed. `uv run ruff format --check src tests` — all
  99 files already formatted.
- Live `curl`/manual acceptance against a temporary `uvicorn` process, described above under
  Stage 2.
- Pristine `data/generated/catcher.sqlite` confirmed unmodified (sha256 identical before/after) by
  every API-started run in both the automated tests and the manual live-server session, including
  a run that fails immediately on an unknown case ID.

Not re-verified since the post-Stage-2 cleanup pass (unchanged, still assumed good):

- All 20 routes × 3 presentation perturbations and the built wheel — the cleanup pass did not touch
  playbook logic or packaging, only shared infrastructure exercised by the eval/live-run checks
  above. Rerun before a demo if playbook or packaging code changes next.

The `.env` contains the user's OpenAI key. Never print, copy, commit or send its value to the browser.

## Known limitations relevant to the console

- The frontend now covers Mission Control and a basic live Run Observatory (`frontend/`); it does
  not yet cover the workflow graph, swimlanes, Reasoning Artifacts, the full Decision & Provenance
  explorer, Memory Explorer or Graph Lab — all Stage 4/5. See "Known limitations carried into
  Stage 4" under the Stage 3 entry below for this frontend slice's own honest gaps (hand-mirrored
  types instead of a generated client, polled rather than streamed run-status badge/nav list, no
  committed E2E test yet). See "Known limitations carried into Stage 3" under the Stage 2 entry
  above for the execution layer's own honest gaps (cancel/liveness is per-process, no queue-ranking
  persistence, no resume endpoint, no memory/graph/source routers yet — all still true).
- `LangGraphRuntime` still keeps active tasks/emitters in-process by design; `RunManager` wraps it
  with a durable store registry but does not (and per the architecture doc should not) make a run
  controllable or its liveness knowable from a different API process.
- Cancellation records a terminal segment and keeps a checkpoint, but automatic restart scheduling
  remains outside this POC. UI labeling must be honest.
- Decision provenance currently attaches the same collected source/event set to each leaf. The UI can
  display it accurately; finer per-field provenance is a future backend improvement, not a reason to
  invent specificity.
- Model request/response bodies are blob-backed. The API must load them lazily.
- The persona harness is scripted. Present it as simulated external input, not a live human.
- Presentation perturbations do not cover wholly new graph topologies or date/amount boundary cases.

## Dirty worktree and commit state

Standing rule from the user (2026-09-14, Stage 1 wrap-up): commit and push at the end of every
completed stage, without needing to ask each time. This is a durable authorization for this
repository, not a one-off — it replaces the earlier per-session "do not commit unless asked"
caution for the specific act of closing out a stage. Still never use destructive git operations
(force-push, history rewrite, `reset --hard`, etc.) without an explicit in-session instruction, and
always keep `.env` and generated runtime/evaluation artifacts out of any commit.

Stage 0 and Stage 1 were completed before this standing rule existed and were committed together
retroactively once the user gave it. From Stage 2 onward, each stage should land as its own commit
(or commits) pushed to `main` right after its handoff update, per the "Mandatory handoff
maintenance" checklist above.

Do not use destructive reset/checkout commands. Work around unrelated changes and inspect before
editing.

## Mandatory handoff maintenance after every stage

Before reporting any stage complete:

1. Update `Last updated`, `Current phase` and `Next stage` at the top.
2. Mark the completed stage and move the exact next stage into focus.
3. Record all material files and architecture/API changes.
4. Record exact backend/frontend/test/build/eval commands and results.
5. Record every red test, shortcut, changed decision and unresolved question honestly.
6. Update the design and README when implemented behavior changes.
7. Append a dated entry to the stage history.
8. Commit every file changed in the stage (including this handoff) and push to the remote. This
   supersedes the general "never commit unless asked" default for this repository specifically:
   the user has given standing authorization to commit and push at the end of every completed
   stage, so no per-stage confirmation is needed for that commit/push — only for anything outside
   normal stage completion (force-push, history rewrite, unrelated destructive operations, etc.).

## Stage history

### 2026-09-14 — backend POC through functional robustness

- Completed all 20 hero cases and Q01 with trajectory/capability evaluation.
- Flattened Python source to `src/`, generalized authored fixture values, added 60 perturbation runs,
  fixed strict OpenAI tool schemas and verified one live end-to-end route.
- Final baseline: 78 passed / 1 skipped tests, 21/21 fake evaluation and 401/401 data checks.
- No commit was requested or created.

### 2026-09-14 — Dispute Observatory Stage 0 design complete

- Defined the dark interactive experience, safe reasoning-artifact policy, five primary views,
  three-pane workspace and capability-specific visual treatments.
- Selected FastAPI + native SSE and React/TypeScript/Vite + TanStack Query + React Flow + Tailwind.
- Specified API endpoints, reconnect semantics, isolated run management, deterministic frontend
  projections, source/memory/graph boundaries, tests and one-command launcher.
- Split implementation into six gated stages and set Stage 1 read-only API as the next task.
- This was a documentation-only stage; no dependencies or executable source were changed and no
  commit was requested or created.

### 2026-09-14 — Dispute Observatory Stage 1 read-only API complete

- Built `src/api/` (app factory, error envelope, DTOs, sqlite read models, static workflow-graph
  description, `meta`/`cases`/`runs` routers) as a pure presentation adapter: `mode=ro` sqlite
  connections only, no writes, no dependency on `LangGraphRuntime` or the agent tool executor.
- Added the `api` optional dependency group (`fastapi`, `uvicorn`, `sse-starlette`) and `httpx` to
  `dev`; generated and checked in `schemas/openapi.json`.
- Added `tests/test_api.py` (8 tests) covering pagination, filters, decision provenance, 404s for
  unknown case/run/decision, a suspended-run's wait payload, and that neither `OPENAI_API_KEY` nor
  the prohibited `birth_year` field ever appears in a response.
- Found and fixed a real bug during manual verification: naively deriving run status from the
  highest-`seq` event row reports `running` for an already-decided run, because `checkpoint_saved`
  commits after `terminate`'s `termination`/`run_completed` events. Fixed by deriving status from
  the latest `error`/`termination` event specifically; documented in both this file and the code.
- Verified end-to-end with a live `uvicorn` process and `curl`, and confirmed the pristine
  `data/generated/catcher.sqlite` was left unmodified.
- Final baseline: 86 passed / 1 skipped tests (was 78/1), ruff check and format both clean.
- Updated `README.md` (new "Dispute Observatory API" section) and
  `docs/design/07-observability-console.md` (Stage 1 marked complete with what was actually built).
- No commit was requested or created; the worktree remains uncommitted from `795e5ff`.

### 2026-09-14 — Dispute Observatory Stage 2 execution manager and live SSE complete

- Built `src/api/run_manager.py` (`RunManager`: isolated per-run copied stores under
  `data/generated/ui/`, a durable SQLite run registry, case-run and Q01-queue lifecycle) and
  `src/api/sse.py` (SQLite-tailing, reconnectable SSE stream via `sse_starlette`).
- Added `POST /runs`, `POST /runs/{run_id}/cancel`, `POST /runs/{run_id}/rerun`,
  `GET /runs/{run_id}/events/stream`, `POST /queue/runs`, `GET /queue/runs/{run_id}`
  (`src/api/routers/runs.py`, new `src/api/routers/queue.py`); `GET /runs` now merges results
  across every store the API knows about instead of Stage 1's single configured store.
- Made one additive change each to `src/runtime/langgraph_runtime.py` (`LangGraphRuntime.is_done`,
  plus retrieving a fire-and-forget `start()` task's exception so a failed run doesn't log an
  "exception was never retrieved" warning) and `src/runtime/portfolio.py` (`rank_portfolio` gained
  an optional `run_id` parameter); both are backward compatible with the existing CLI.
- Found and fixed two real bugs during implementation/testing: (1) a run that suspends and
  auto-resumes internally emits one `termination` event per segment, not just at the end, which
  would have closed the SSE stream on the first wait of a live multi-wait run — fixed with
  `is_done`/`is_task_done` reporting true process-local task completion, falling back to the
  persisted-status heuristic only for runs this process doesn't manage; (2) mixing `async def`
  endpoints with sync generator sqlite dependencies crashed with a cross-thread `sqlite3`
  `ProgrammingError` — fixed by making the connection dependencies async and their endpoints async.
- Added `tests/test_api_stage2.py` (8 tests, `httpx.AsyncClient` over an in-process ASGI transport):
  gap-free/dup-free streaming to a decision, exact-suffix reconnect by `after_seq` and
  `Last-Event-ID`, two simultaneous isolated runs with the pristine store hashed unchanged,
  cancel-idempotency + rerun, rerun-rejection for an unmanaged run, a full Q01 queue run, an
  immediate-failure run that never touches the pristine store, and cross-store `GET /runs` merging.
- Verified end-to-end with a live `uvicorn` process: start/stream/cancel/rerun/queue all worked via
  `curl`, and `data/generated/catcher.sqlite`'s sha256 was identical before and after.
- Final baseline: 94 passed / 1 skipped tests (was 86/1), ruff check and format both clean.
- Updated `README.md` ("Dispute Observatory API" section rewritten with an execution-endpoint
  table) and `docs/design/07-observability-console.md` (Stage 2 marked complete with what was
  actually built, including the two bugs above).
- Regenerated `schemas/openapi.json`. Added `data/generated/ui/` to `.gitignore` (per-run copied
  stores and the run registry; never committed).
- Committed and pushed per the standing authorization below.

### 2026-09-15 — Dispute Observatory Stage 4 advanced observability complete

- Extended the pure frontend `RunProjection` with active/completed workflow nodes, committed
  edges/back-edges, paired tool and subagent exchanges, versioned plan/hypothesis artifacts,
  skills, verifier checks and panel events. Added a React Flow workflow canvas, actor swimlanes,
  safe Reasoning Artifacts, run memory/graph overlays and type-aware event/blob inspection.
- Expanded Decision & Provenance to show every persisted field path with clickable sequence links
  and allowlisted source previews. Blob content remains lazy and is already redacted by
  `EventEmitter.put_blob`; no private chain-of-thought field or fabricated explanation exists.
- Added Memory Explorer (subject/status/as-of controls and lifecycle metadata) and Graph Lab
  (operational JSONL graph only, depth 1–3 and 250-node hard cap). Added explicit API routers/read
  models for memory notes and run operations, bounded case neighborhoods, run graph overlays,
  allowlisted case/transaction/communication/packet/document/note sources and run-scoped blobs.
  No endpoint accepts SQL or a filesystem path; ground-truth/simulation data remain unreachable.
- Added `tests/test_api_stage4.py` and `runProjection.test.ts`. Backend coverage proves memory
  filtering, source boundaries, graph bounds/referential integrity, isolated-run memory/graph
  overlays and secret-free blobs; frontend coverage proves deterministic back-edge, verifier,
  plan and tool-exchange reconstruction.
- Fixed a Stage 3 projection bug exposed by C13: its mid-run auto-resume suspension emits
  `termination(final_status="suspended")`, which the old reducer treated as the final end of the
  run. `RunProjection.terminal` now becomes true only for decided/cancelled/ranked/failed terminal
  statuses; a regression test covers the suspend → termination → resume prefix.
- Acceptance traces re-run with the fake evaluator: **5/5 passed**, all hash chains valid and
  replay reconciled. C06 (`90007`) recorded one replan; C11 (`90012`) recorded subagents,
  graph query/write, panel and automatic reopen; C12 (`90013`) recorded a positive ring graph
  write; C12b (`90014`) recorded a negative graph query and no forbidden ring-membership write;
  C13 (`90015`) recorded wait/resume/clock advance, panel and policy-gap action.
- Verification: `uv run pytest` — **97 passed, 1 skipped**; `ruff check` and `ruff format --check`
  clean. Frontend `tsc -b` clean; Vitest **7 passed**; oxlint 0 errors / 3 pre-existing warnings;
  production build clean at 567 KB JS / 36 KB CSS (gzip 177 KB / 7 KB), with Vite's non-blocking
  >500 KB chunk warning after React Flow. Five-case fake evaluation above passed 5/5.
- Known limitations carried into Stage 5: workflow node positions are deterministic but not yet
  persisted/user-customizable; source preview stays local to the provenance chip instead of
  deep-linking selection into the URL; Memory Explorer exposes persistent notes while semantic
  retrieval activity is run-scoped in the Memory & Graph tab; React Flow should be route-split
  during Stage 5 performance polish; recent-run status still polls and the desktop inspector/nav
  remain hidden below `lg`; committed Playwright coverage remains Stage 6.
- Updated README, the authoritative design, OpenAPI and this handoff; committed and pushed per the
  standing stage-completion authorization.

### 2026-09-14 — Post-Stage-2 cleanup pass (`/simplify`, then targeted efficiency follow-ups)

A code-quality pass over all of `src/`/`tests/` (four parallel reuse/dead-code/efficiency/altitude
reviews, findings applied directly), followed by a second, more targeted pass at the user's request
to also address the riskier efficiency items the first pass had deliberately skipped. Not a staged
feature addition — no new endpoints, no new UI-visible behavior, no change to the six-stage plan.

**API surface change (breaking for any Stage 3 frontend code, still unwritten):**

- `GET /health` no longer returns `graph_available`. It checked whether the `ladybug` package was
  importable, but the real optional graph backend is `ladybug` and the field was disconnected from
  whether a store's graph actually loaded — always misleading, never a source of truth. The
  endpoint table and known-limitations entry above are updated to match.
- `GET /meta/agents` (`AgentSummary`) no longer returns `model_role`. It was always `"default"` in
  every one of the 12 agent configs and never consumed anywhere to select a model — decorative.
  `AgentConfig.model_role`, `ModelsConfig.role_overrides` (and the matching yaml keys) were removed
  with it, since the mechanism they'd have keyed into was equally unused.
- `schemas/openapi.json` regenerated to match.

**Dead code removed:** `domain.case.RunState`/`CaseFile`/`Fact` (superseded by dict-based LangGraph
state, never referenced), `ports.AgentRuntime` (unwired Protocol), `runtime.context.RunContext.root`
and `note_by_id`, `api.errors.denied()`, `observability.emitter.EventEmitter.event_types()`,
`memory.graph.NetworkXGraphMemory` alias (and the now-empty `memory/__init__.py` re-exports).

**Reuse/duplication removed:** the `sqlite3.Row → EventEnvelope` mapping and hash-chain
verification loop were each triplicated across `read_models.py`/`emitter.py`/`replay.py` — now
`domain.events.event_from_row`/`verify_event_chain`, used by all three. `connect_readonly` was
duplicated four times (`meta.py`, `harness/evidence.py`, `run_manager.py`, plus the original in
`read_models.py`) — now one definition in a new `src/storage.py`, used by all of them plus
`dependencies.py`/`sse.py`. `sandbox.py`'s four earlier helpers now call the `_record_computation`
helper the later ones already used instead of hand-rolling the same event payload; a Reg E
"new account" test that had drifted into three separately-maintained copies (`reg_e_deadlines`,
`case_clocks`, `portfolio_case_clocks`, two of them with different field-name plumbing) is now one
`is_new_account()` helper. `actions.py`'s duplicated before/after case-state SELECT factored into
`ActionRepository._case_snapshot()`.

**Bugs fixed:** `memory/curator.py`'s TTL expiry was off by one day at the boundary (`<` should be
`<=`: a note created exactly `TTL_DAYS` before `as_of` should expire that day). `api/sse.py` had a
narrow TOCTOU race — a run whose final event(s) committed in the window between the events query
and the `is_task_done()` check could have its stream close without ever sending them; fixed with
one more poll immediately after observing `done`.

**Efficiency (first pass, low-risk):** `api/sse.py` now holds one sqlite connection for the whole
stream instead of reconnecting every ~150ms poll (verified single-threaded: this generator is only
ever driven from its own asyncio task on the process's one event-loop thread — see the second-pass
note below for why that same argument was extended further). `api/run_manager.py` gained a lazy,
unbounded-safe `run_id → registry row` cache (rows are immutable once written) and sweeps its
in-memory `LangGraphRuntime`/queue-task objects for finished runs on every new run start (memory
growth was unbounded in a long-lived API process before this). `api/workflow_graph.py`'s
already-computed-but-discarded loop-back-edge flag now actually emits `kind="resume"`.
`runtime/langgraph_runtime.py`'s `governance.fairness_violations(...)` was called twice per check
in two places; now once. The CLI's/`evaluation/reliability.py`'s duplicated `case_id == "Q01"`
literal is now one `runtime.portfolio.QUEUE_SCENARIO_ID` constant.

**Efficiency (second pass, at the user's explicit follow-up request — the items the first pass had
flagged as "requires a larger/riskier rewrite"):**

- `data/access.CaseDataAccess` and `memory/graph.GraphMemory` now each hold one connection for
  their lifetime instead of reconnecting per query/write. Verified safe by tracing the concurrency
  model, not by analogy: both are constructed once per run/segment inside
  `LangGraphRuntime._context()` and are only ever touched from that run's own `asyncio.create_task`
  on the process's single event-loop thread (confirmed via `grep` — no `threading`/`to_thread`/
  `run_in_executor`/`ThreadPoolExecutor` anywhere in `src/`). This is a different situation from the
  Stage 2 cross-thread `sqlite3` bug documented above, which was FastAPI running a *sync* dependency
  in a worker thread while the endpoint body ran on the event-loop thread — genuinely two threads.
  `observability/emitter.py`'s per-call connections were deliberately **left alone**: `EventEmitter`
  is the busiest, most heavily-shared object in the system and a mistake there would be much
  costlier to find than in these two narrower, per-run objects.
- `bootstrap.py` split `build_runtime`/`isolated_workspace` into config-accepting variants
  (`build_runtime_from_config`, `copy_scenario_store`) alongside the original disk-loading
  functions (still used by the CLI/tests). `api/run_manager.py` now passes its already-loaded
  `ModelsConfig`/`RoutesConfig`/`ScenarioConfig` (loaded once at app startup) into these instead of
  re-parsing three YAML files on every `POST /runs`/`POST /queue/runs`.
- `api/read_models._runs_for_cases` rewritten from up to ~5 sqlite round trips *per run* (first
  event, last event, status, wait payload, decision existence) to 4 queries total per call
  (aggregate; endpoints via a row-value `IN`; latest status via one `ROW_NUMBER()` window query;
  a decision-availability set), used by both `get_case_detail` and the cross-store `GET /runs`
  listing. `derive_status` itself is untouched and still backs the single-run/SSE path.
- **One real regression caught and fixed before it shipped**: the first version of the
  finished-run sweep also evicted `RunManager._queue_rankings`, but `GET /queue/runs/{run_id}` has
  no fallback to the persisted `portfolio_ranked` event — it only ever reads that in-memory dict.
  That would have turned the documented "ranking is lost on API restart" limitation into "lost as
  soon as any other run starts," a real behavior regression, not cleanup. Caught by re-reading the
  route before shipping and confirmed with a live repro (start a queue run, fetch its ranking,
  start an unrelated case run, fetch the ranking again — now still present). Fixed by sweeping only
  `_runtimes`/`_queue_tasks` (the actually-heavy objects — each `LangGraphRuntime` holds a gateway,
  agent configs and a chat-model wrapper) and leaving `_queue_rankings` alone, matching the
  documented restart-only limitation exactly.
- **`AgentConfig.max_iterations` deliberately left unwired.** It carries real per-agent tuning
  values (2–5) across all 12 agent yaml files, so deleting it would lose authored intent — but
  `deepagents`' `SubAgent` spec has no native per-subagent iteration cap (only LangGraph's
  graph-level `recursion_limit`, and a `middleware` hook that would require writing and testing a
  new iteration-counting `AgentMiddleware` from scratch). That is new engineering with real
  correctness risk (silently truncating a subagent's reasoning under real-model variance, in a
  system making financial decisions) — not a wiring fix a cleanup pass should make opportunistically.
  Revisit as its own scoped task if this is wanted.
- `_build_graph` rebuilding ~20 node closures and recompiling the `StateGraph` on every run
  segment was investigated and **deliberately not touched**: the topology is static but every node
  closure captures `ctx`/`emitter` by reference across ~700 lines, so separating static topology
  from per-run binding would touch nearly all of `LangGraphRuntime`'s largest method. It only runs
  once per run/resume-segment (not per event or per node), so the actual payoff is low relative to
  the size and blast radius of the change. Worth its own planned, incrementally-verified task if the
  frontend or a heavier concurrent-run load later makes this a real bottleneck — not opportunistic.

Verification (both passes together, run before every commit in this entry):

```bash
uv run pytest                          # 94 passed, 1 skipped (unchanged)
uv run ruff check src tests            # All checks passed!
uv run ruff format --check src tests   # 100 files already formatted
uv run catcher eval <20 hero cases> Q01 --adapter fake --runs 1   # 21/21 passed
python3 data/generator/validate.py     # PASS 401 FAIL 0
```

Plus, specific to the changes made: one live end-to-end run on the real OpenAI adapter
(`DSP-2026-90002`, isolated store copy, hash chain verified valid, pristine store sha256
unchanged); a live `uvicorn` smoke test of the full run lifecycle (start/status/list/rerun) with
the pristine store confirmed unmodified; the queue-ranking-survives-a-later-run repro described
above. `data/generated/eval/` output from the eval runs is gitignored, not committed.

No design, API-contract-beyond-the-two-fields, or six-stage-plan changes. Stage 3 remains next and
unaffected in scope.

### 2026-09-15 — Dispute Observatory Stage 3 frontend shell and Mission Control complete

- Scaffolded `frontend/` (Vite + React 19 + TypeScript, Tailwind v4 via `@theme` tokens in
  `src/index.css`, `react-router-dom`, `@tanstack/react-query`, `@xyflow/react` installed now for
  Stage 4's workflow/entity graphs, Vitest + React Testing Library). Manrope (sans) + IBM Plex Mono
  (data/IDs/JSON) from Google Fonts, per the design doc's "humanist sans for prose, mono for
  IDs/dates/amounts/JSON" rule; picked deliberately to avoid both the generic Inter-everywhere
  default and the cliché warm-cream/terracotta AI-generated look — see
  `docs/design/07-observability-console.md`'s Stage 3 entry for the token/typography rationale.
- Built the responsive three-pane shell (`app/Shell.tsx`, `NavigationRail.tsx`, `Inspector.tsx`,
  `InspectorContext.tsx`, `router.tsx`), a typed API layer (`api/types.ts`, `api/client.ts`,
  `api/useRunStream.ts`), a small pure `projections/runProjection.ts` reducer, and the two Stage 3
  features (`features/mission-control/`, `features/run-observatory/`).
- Delivered exactly the planned Stage 3 scope: case browser with regime/status/stage/search
  filters, per-case run launcher (adapter + auto-resume), a separate Q01 queue launcher (`/queue/
  runs`, not `/runs` — Q01 isn't a `/cases` row), recent-runs nav, a live event timeline with a
  per-event inspector, a metrics strip and a basic cardholder/network decision panel once a run
  decides.
- **Deliberately did not use `EventSource` for the SSE stream** (a real deviation from this design
  doc's original wording, made for a documented reason, not an oversight): the backend names each
  SSE frame's `event:` field after the event's `type`, and that vocabulary is meant to keep growing
  through Stage 4/5, so a browser `EventSource` with a fixed set of `addEventListener` calls would
  silently drop any event type this build doesn't know about — exactly the failure mode §6 of the
  design doc forbids. `api/useRunStream.ts` instead parses the stream with `fetch`/`ReadableStream`
  by hand, reading only the `data:` line (the payload's own `seq` is authoritative) and reconnecting
  itself by polling `GET /runs/{run_id}` for a terminal status when the stream ends. See the design
  doc's Stage 3 entry for the full reasoning; the wire format and API are unchanged, so this is
  contained entirely in one file.
- **Found and fixed one real backend bug while manually verifying in a live browser**: `GET
  /cases`/`GET /cases/{case_id}` intermittently 500'd with a cross-thread `sqlite3.ProgrammingError`
  — `api/dependencies.get_connection` was still Stage 1's plain sync generator dependency paired
  with `cases.py`'s sync `def` endpoints, the same FastAPI thread-affinity hazard Stage 2 already
  found and fixed for the run-lifecycle endpoints, just never applied to `cases.py` because Stage
  1/2's own tests don't trigger the race the way a real browser hitting several endpoints
  back-to-back does. Fixed identically: `get_connection` is now `AsyncIterator`, `get_cases`/
  `get_case` are `async def`. `uv run pytest` stayed at 94 passed/1 skipped.
- Also fixed a real frontend correctness bug caught during the same manual verification, before
  calling the stage done: `RunObservatoryPage`'s header status badge and its "has this run decided
  yet" logic were reading only the polled `GET /runs/{run_id}` REST status, which doesn't refetch on
  its own — a run could finish (visible in the live event stream and its 132-event timeline) while
  the header still said "Running" and the decision panel never appeared. Fixed by making the pure
  `runProjection.terminal`/`.failed` flags (derived from the live stream) the primary signal, with
  the polled REST status as a secondary source only for the case ID label and the cancel/rerun
  button states; `runQuery`'s `refetchInterval` is now gated off once the projection says the run is
  terminal instead of running forever.
- Tests added: `api/useRunStream.test.ts` (REST snapshot + SSE tail merge to a sorted, de-duplicated
  event list, via a hand-built `ReadableStream`/`Response` mock — chosen over mocking `EventSource`
  because the hook itself doesn't use `EventSource`, see above), `features/mission-control/
  CaseFilters.test.tsx` (filter state reporting through a small controlled-component test harness),
  `features/mission-control/RunLauncher.test.tsx` (launch mutation → navigation, with `api/client`
  and `useNavigate` mocked). `npm run test` — **5 passed**.
- Verified end-to-end in a real Chromium browser via a throwaway Playwright script (not committed —
  the committed E2E path is Stage 6's, per the design doc's own staging) against the actual `uv run
  uvicorn`/`npm run dev` processes: launched C02 from Mission Control, watched the timeline reach
  132 live events with zero console errors, reached `Decided` with the decision panel visible, all
  without a page reload; also drove the Q01 queue launcher and a 390px mobile viewport, and took
  screenshots to self-review the visual design against the brief (dark navy canvas; cyan/violet/
  amber/emerald/rose/slate fixed accent meanings; Manrope/Plex Mono type pairing) before calling the
  stage done.
- Final baseline: backend 94 passed/1 skipped (unchanged), ruff clean; frontend `tsc -b` clean,
  Vitest 5 passed, oxlint 0 errors, `npm run build` clean.
- Updated `README.md` (new "Dispute Observatory frontend" section with the two-terminal dev
  commands — `scripts/dev.sh` is still Stage 6) and `docs/design/07-observability-console.md`
  (Stage 3 marked complete with what was actually built, the `EventSource` deviation and both bugs
  above, in full).
- Known limitations carried into Stage 4 (honest, not blocking): `api/types.ts` is hand-mirrored
  against `src/api/models.py`, not generated — a backend DTO change needs a matching manual edit
  here; the nav rail's recent-runs list still polls (`refetchInterval: 5000`) rather than
  subscribing to any run's live stream, so a run's status there can lag up to 5 seconds behind
  reality (the run's own page is fully live); no committed Playwright test yet (by design, Stage
  6's job); the rail and inspector are hidden below `lg` rather than becoming a drawer, so mobile
  Stage 4 graph/swimlane work will need its own narrow-viewport treatment, not inherited from Stage
  3's shell.
- Committed and pushed per the standing authorization below.
