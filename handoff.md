# Dispute Observatory implementation handoff

Last updated: 2026-09-14  
Repository: `/Users/kean/Dev/CatcherAI`  
Branch / starting commit: `main` / `795e5ff`  
Current phase: frontend/API Stage 0 design complete; no frontend or API implementation yet  
Next stage: Stage 1 — read-only FastAPI foundation

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
   source layout, six stages and acceptance gates.
3. `README.md` — current working commands and backend capabilities.
4. `docs/design/05-agent-architecture.md` — runtime boundaries and automation constraints.
5. `docs/design/03-data-dictionary.md` — data stores, joins and private-data boundaries.
6. `schemas/trajectory-event.schema.json` and `src/domain/events.py` — canonical frontend event.
7. `src/observability/emitter.py`, `src/replay.py`, `src/decisions.py` — event persistence, replay,
   blobs, hash chains and decision provenance.
8. `src/runtime/langgraph_runtime.py`, `src/bootstrap.py`, `src/cli.py` — lifecycle methods the API
   must wrap rather than duplicate.
9. For historical implementation context, `docs/prompts/02-implementation-kickoff.md`,
   `docs/design/06-eval-results.md` and the remaining design/research documents.

Do not begin Stage 2 or scaffold the frontend during Stage 1. First make the read-only API contract
solid and tested.

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
- Preserve the dirty worktree. Do not reset or commit unless the user asks.
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

### Stage 1 — Read-only API foundation: NEXT

Deliver only:

- `src/api/` FastAPI app factory, dependencies, stable DTOs, read models and error envelope.
- Health/meta/routes/agents/skills/workflow/event-schema endpoints.
- Paged case list/detail, historical runs, paged/filtered events and decision/provenance endpoints.
- OpenAPI generation and copied-store API tests.

Acceptance:

- Existing 79 tests remain green.
- New tests cover pagination, filters, provenance, missing IDs and private-data denial.
- `curl` can list cases, inspect a historical run and replay ordered events.
- No execution manager, SSE stream or frontend code is required yet.

Safest first implementation steps:

1. Verify current FastAPI/Pydantic testing APIs from official docs.
2. Add backend optional/development dependencies intentionally in `pyproject.toml`.
3. Define DTOs before routers; keep SQLite row conversion in `read_models.py`.
4. Build the app with injected root/default DB so tests never touch the pristine store.
5. Add `/api/v1/health`, then metadata, then cases/runs/events/decision.

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

Verified before this design-only stage:

- `uv run pytest -q` — 79 collected: **78 passed, 1 skipped**. The default skip is the opt-in live
  OpenAI smoke.
- All 20 routes passed three presentation perturbations: 20 baselines + 60 variants.
- Full fake evaluation: **21/21 passed**, including Q01.
- Q01: Kendall τ 1.0, top-15 overlap 15/15, deadline accuracy 1.0, coverage 95/95.
- `python3 data/generator/validate.py` — **PASS 401 FAIL 0**.
- `uv run ruff check src tests` and `uv run ruff format --check src tests` — passed.
- Opt-in real Responses contract smoke — **1 passed**.
- Live OpenAI C02 evaluation — **1/1 passed**, 4,517 ms recorded API latency.
- Wheel built and inspected: `card_dispute_agent-0.1.0-py3-none-any.whl`, 72 files, flat source,
  no old product-named package path.

The `.env` contains the user's OpenAI key. Never print, copy, commit or send its value to the browser.

## Known limitations relevant to the console

- No HTTP API or frontend exists yet.
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

The worktree was intentionally uncommitted from starting commit `795e5ff` during the design stage.
The user has now explicitly authorized committing and pushing this complete snapshot. Keep `.env`
and generated runtime/evaluation artifacts ignored when preparing the commit.

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
7. Preserve the dirty-worktree and commit status.
8. Append a dated entry to the stage history.

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
