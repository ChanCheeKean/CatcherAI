# Dispute Observatory implementation handoff

Last updated: 2026-09-14  
Repository: `/Users/kean/Dev/CatcherAI`  
Branch / starting commit: `main` / `795e5ff` (still uncommitted; see below)  
Current phase: Stage 1 (read-only FastAPI foundation) COMPLETE; no frontend yet, no execution
manager or live stream yet  
Next stage: Stage 2 — execution manager and live SSE stream

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
   source layout, six stages and acceptance gates (Stage 1's entry now reflects what was built).
3. `README.md` — current working commands, including the new "Dispute Observatory API" section.
4. `docs/design/05-agent-architecture.md` — runtime boundaries and automation constraints.
5. `docs/design/03-data-dictionary.md` — data stores, joins and private-data boundaries.
6. `schemas/trajectory-event.schema.json` and `src/domain/events.py` — canonical frontend event.
7. `src/observability/emitter.py`, `src/replay.py`, `src/decisions.py` — event persistence, replay,
   blobs, hash chains and decision provenance.
8. `src/runtime/langgraph_runtime.py`, `src/bootstrap.py`, `src/cli.py` — lifecycle methods Stage 2's
   execution manager must wrap rather than duplicate (`start`/`result`/`resume`/`cancel`/`events`).
9. `src/api/app.py`, `src/api/dependencies.py`, `src/api/read_models.py` — the Stage 1 foundation
   Stage 2 extends: read this before adding `RunManager`, start/cancel/rerun endpoints or SSE, so
   the isolated-store registry replaces the single-`db_path` shortcut cleanly instead of alongside it.
10. For historical implementation context, `docs/prompts/02-implementation-kickoff.md`,
    `docs/design/06-eval-results.md` and the remaining design/research documents.

Do not begin Stage 3 (frontend) or add execution/SSE code casually — Stage 2's own acceptance gate
(concurrency-safe start/cancel/rerun, gap-free reconnectable SSE, pristine-store isolation tests)
must pass first.

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
  task and immediately returns `202` with the run ID and stream URL.
- `GET /api/v1/runs/{run_id}/events/stream` sends complete canonical events, SSE `id=seq`, honors
  `Last-Event-ID`, emits heartbeats and closes after the terminal suffix is committed.
- A small durable UI registry maps run IDs to isolated store paths/status so history survives API
  reloads.
- Initial SSE should tail committed SQLite rows. It works for live, replay and reloaded API processes;
  in-process `EventEmitter.subscribe()` may be an optimization later.
- Memory, graph and source endpoints are explicit read models/resolvers. Never accept arbitrary SQL
  or filesystem paths.
- The browser never receives `OPENAI_API_KEY`; it only sees whether the OpenAI adapter is available.

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
| GET | `/health` | store reachability, `scenario_db_path`, `graph_available` (ladybug importable) |
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
- `/health`'s `graph_available` reports whether the `ladybug` package is importable, not whether a
  specific store's graph file loaded successfully; the runtime always has a NetworkX fallback.

### Stage 2 — Execution manager and live stream

- Isolated UI workspaces, durable run registry and background runtime tasks.
- Start/status/cancel/rerun and Q01 endpoints.
- Ordered reconnectable SSE with heartbeat and terminal close.
- Simultaneous-run, reconnect, no-gap/no-duplicate and pristine-store tests.

### Stage 3 — Frontend shell and Mission Control

- Vite React/TypeScript/Tailwind app and responsive three-pane shell.
- Typed REST client, TanStack Query and SSE hook.
- Case browser, recent runs, launcher, status cards and basic live timeline.
- Component tests and a browser-launched C02 decision path.

### Stage 4 — Advanced observability

- Workflow graph, swimlanes and specialized event inspectors.
- Plans, hypotheses and safe Reasoning Artifacts.
- Decision/provenance/source/blob explorer.
- Memory Explorer and bounded Graph Lab, API and UI.
- Demonstrate C06 replan, C11 subagents/reopen, C13 wait/policy gap and C12/C12b graph contrast.

### Stage 5 — Evaluation and interaction polish

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
| Operational reads | `src/data/access.py` |
| Memory | `src/memory/notes.py`, `src/memory/retrieval.py` |
| Entity graph | `src/memory/graph.py` |
| Existing lifecycle commands | `src/cli.py` |
| Event schema | `src/domain/events.py`, `schemas/trajectory-event.schema.json` |

## Last verified baseline

Verified at the end of Stage 1 (this stage):

- `uv sync --extra dev --extra graph --extra api` — resolves cleanly; adds `fastapi`, `uvicorn`,
  `sse-starlette` (runtime `api` extra) and `httpx` (test-only, for `fastapi.testclient`).
- `uv run pytest` — **86 passed, 1 skipped**, 1 deprecation warning from `starlette.testclient`
  (an upstream `anyio` alias notice, not our code). The 8 new tests live in `tests/test_api.py`;
  the prior 78/1 backend baseline is unchanged and still green.
- `uv run ruff check src tests` — all checks passed. `uv run ruff format --check src tests` — all
  94 files already formatted.
- Live `curl` acceptance against a temporary `uvicorn` process, described above under Stage 1.
- Pristine `data/generated/catcher.sqlite` confirmed unmodified by any API read (no `run_events` or
  `decision_records` table present in it; the API only ever opens `mode=ro` connections and Stage 1
  has no write path at all).

Not re-verified this stage (unchanged since the prior baseline, still assumed good):

- All 20 routes × 3 presentation perturbations, full fake evaluation (21/21), Q01 metrics,
  `data/generator/validate.py` (401/401), the real-OpenAI smoke tests, and the built wheel. Rerun
  these before a demo if the runtime/domain code changes; Stage 1 touched only `src/api/` and
  added `tests/test_api.py`.

The `.env` contains the user's OpenAI key. Never print, copy, commit or send its value to the browser.

## Known limitations relevant to the console

- A read-only HTTP API exists (`src/api/`); there is still no frontend, no execution manager and
  no live stream. See "Known limitations carried into Stage 2" under the Stage 1 entry above for
  the API's own honest gaps (single configured store, no deadline filter, REST-only events).
- `LangGraphRuntime` keeps active tasks/emitters in-process; Stage 2 needs a RunManager and durable
  store registry around it.
- `EventEmitter.subscribe()` handles active in-process subscribers, but reconnect/reload semantics are
  not sufficient by themselves. The design chooses a persisted SQLite tail for Stage 2.
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
