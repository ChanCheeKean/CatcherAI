# Dispute Observatory: frontend and API design

Status: implementation-ready design  
Date: 2026-09-14  
Scope: interactive local POC console, read/control API, live trajectory streaming, one-command launch

## 1. Outcome

Build a dark, interactive operations console that makes the existing dispute agent understandable
while it runs. A user can select a case, launch the fake or OpenAI adapter, watch the graph advance,
inspect every structured reasoning artifact, follow subagents and tool calls, explore memory and
entity relationships, and trace the final decision back to its evidence.

The console is a projection of the canonical event log. It must not become a second workflow engine,
invent events, infer decisions that were never recorded, or read evaluator-only ground truth and
simulation files.

The working product name for the UI is **Dispute Observatory**. It is presentation copy, not a new
Python package or domain namespace.

## 2. Product principles

1. **Live and replay are the same view.** A live run appends events to the same ordered timeline used
   for historical replay. Seeking to sequence 140 should reconstruct exactly what was visible then.
2. **Progressive disclosure.** The default view explains what happened; one click reveals arguments,
   results, source references, JSON, spans, hashes, usage and runtime metadata.
3. **Evidence before spectacle.** Animation highlights committed state changes. It never fabricates
   token streams, graph activity or “thinking” to make the interface look busy.
4. **Safe reasoning transparency.** The UI exposes recorded plans, rationales, hypotheses,
   contradictions, verifier checks, panel positions and decision explanations. It does not request or
   display private chain-of-thought. `reasoning_tokens` is shown only as a usage count.
5. **Controls do not become approvals.** Users can start, cancel, rerun, filter, seek and change
   playback speed. No button approves or changes an adjudication. External-event handling remains
   automatic unless a developer explicitly starts an existing no-auto-resume harness run.
6. **One source of truth.** SQLite `run_events`, `run_blobs`, `decision_records`, operational tables
   and governed memory are authoritative. Frontend state is disposable.
7. **POC-functional scope.** Optimize for clarity, correctness and a memorable demo. Multi-user auth,
   deployment infrastructure and other production hardening are not part of this stage.

## 3. Experience design

### 3.1 Visual direction

The interface should feel like a high-end investigation workbench, not a generic admin dashboard.

- Near-black navy canvas (`#070A12`) with layered blue-black surfaces rather than pure black.
- Cyan is active execution, violet is model/subagent work, amber is waits or deadlines, emerald is
  verified/success, rose is contradiction/failure, and slate is historical/inactive.
- Thin luminous paths animate only when a real `edge_taken` event arrives.
- Dense information uses a humanist sans face; IDs, dates, amounts and JSON use a mono face.
- Cards have subtle borders and restrained glow. Avoid large gradients, excessive glass blur and
  decorative charts with no investigative meaning.
- Dark mode is the primary and initially only theme. Honor reduced-motion and maintain keyboard focus,
  contrast and non-color status cues.

Tailwind supports tokenized theme variables and explicit dark variants; use it for layout and design
tokens, with small custom CSS for the execution pulse and timeline connector. See the official
[Tailwind theme documentation](https://tailwindcss.com/docs/theme) and
[dark-mode utilities](https://tailwindcss.com/docs/styling-with-utility-classes#targeting-dark-mode).

### 3.2 Global shell

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ ◉ DISPUTE OBSERVATORY   LIVE/REPLAY   virtual 2026-10-21   model   Run ▶     │
├───────────────┬──────────────────────────────────────────┬───────────────────┤
│ CASES / RUNS  │ ACTIVE CANVAS                            │ INSPECTOR         │
│ search        │ ┌ route + workflow graph ──────────────┐ │ selected event    │
│ status chips  │ │ route → investigate → tools → panel  │ │ rationale         │
│ deadline      │ └───────────────────────────────────────┘ │ args / result      │
│               │ ┌ live event timeline / swimlanes ────┐ │ refs / provenance │
│ selected run  │ │ 084 Tool  requested provider record │ │ raw JSON          │
│ metrics       │ │ 091 Wait  checkpoint suspended      │ │                   │
│               │ │ 096 Time  virtual clock advanced    │ │                   │
│               │ └───────────────────────────────────────┘ │                   │
├───────────────┴──────────────────────────────────────────┴───────────────────┤
│ playback  |◀  ▶|  1×  seq 096/223  filters  hash ✓  13 tools  $0.00  4.5s │
└──────────────────────────────────────────────────────────────────────────────┘
```

Desktop uses a resizable 280 px navigation rail, flexible center canvas and 380 px inspector.
Tablet collapses the inspector into a drawer. Mobile is supported for basic run/timeline inspection,
but graph-heavy analysis is explicitly desktop-first.

### 3.3 Primary views

#### Mission Control

- Search and filter existing cases by regime, family, status, stage and deadline.
- Case cards show amount, merchant, route-relevant facts and latest run state.
- A run launcher selects case, adapter (`fake` default, `openai` when the backend reports available),
  and automatic external-event handling.
- Recent runs show running, waiting, decided, failed or cancelled; clicking opens the observatory.
- Q01 queue view shows ranked open cases, deadline pressure and expired-rights indicators.

#### Live Run Observatory

- Workflow graph: all runtime nodes are visible; completed/current/planned branches have distinct
  states. Back-edges, `Send` fan-out and suspend/resume are visible.
- Route card: candidate routes, matched rule, chosen route, depth, agents, skills and budget.
- Event timeline: virtual time is primary, wall time secondary. Events group by graph node/span and
  can switch to actor swimlanes.
- Playback controls: live-follow, pause visualization, single-step, seek, 0.5×/1×/2×/instant replay.
  Pausing playback never pauses the actual agent.
- Filters: graph, agent, subagent, model, tool, memory, sandbox, harness, evaluator; event type; actor;
  text; source reference; errors only.
- Metrics strip: event/tool/model counts, token use, latency, budget, clock, hash-chain state.

#### Decision & Provenance

- Side-by-side cardholder outcome and network action to reinforce that these are separate decisions.
- Conditions considered, hypothesis winner, confidence, panel use, conservative default, deadlines,
  letters, account actions and automated actions.
- Evidence matrix: every decision field path expands to its `event_seqs` and `source_ids`; clicking a
  sequence seeks the timeline and clicking a source opens the source inspector.
- “Why this decision?” is assembled only from recorded explanations, findings and verifier events.
- A final integrity ribbon shows terminal status, verifier result, hash chain and replay reconciliation.

#### Reasoning artifacts

This is the UI interpretation of the requested “thought” view:

| Artifact | Canonical events/data | Rendering |
|---|---|---|
| Plan | `plan_created`, `plan_updated`, `todo_updated` | versioned checklist with visual diff |
| Hypotheses | `hypothesis_updated`, proposal blob | evidence-for/against balance cards |
| Tool rationale | `tool_call` | “why”, typed arguments, duration, matching result |
| Contradiction | `contradiction_detected` | before/after facts and resolution |
| Verification | `verifier_check` | pass/fail matrix with refs |
| Automated panel | `panel_position`, `adjudication` | independent positions then adjudicated result |
| Model activity | `llm_call_started`, stream events, `llm_call` | role, model, usage, request/response blobs |

No component is named “chain of thought,” and no API field asks a model to reveal hidden reasoning.

#### Memory Explorer

- Tabs for persistent notes, semantic retrieval activity and graph hypotheses.
- Read-only query controls: subject, scope, kind, tags, status, confidence floor and `as_of` date.
- Note cards show content, validity, confidence, sources and lifecycle: read, verified, rejected,
  superseded, retracted, consolidated, expired, purged or skipped.
- A run overlay distinguishes records returned, used and discarded.
- Selecting a memory event synchronizes the timeline and relevant graph entities.
- No free-form memory mutation UI in the POC; writes remain governed agent actions.

#### Graph Lab

- Runtime mode shows graph nodes/edges reconstructed from `node_entered`, `node_exited`, `edge_taken`
  and route events.
- Entity mode shows a bounded case neighborhood: customer, account, card, transactions, merchants,
  addresses, devices, phones, disputes and active hypotheses.
- Controls select depth (1–3), relationship types, current-run overlay and historical facts.
- Query results animate as highlighted paths only when the corresponding `graph_query` is selected.
- Graph writes show evidence edges, confidence, status and the event that authorized the write.

React Flow is designed for interactive node-based editors and visualizations, provides custom nodes,
controls and a Vite template, and can render both workflow and bounded entity graphs. Use
`@xyflow/react`; see the official [React Flow quick start](https://reactflow.dev/learn).

#### Evaluation view

- Load existing JSON evaluation reports and show scenario pass rate, pass^k, stability, capability
  matrix, trajectory reconciliation and operational metrics.
- The matrix links each capability/case cell to the proving events in a selected run.
- Starting a full evaluation from the UI is optional in the last stage; viewing existing reports is
  required earlier.

## 4. Technical architecture

```text
React + TypeScript (frontend/)
  ├── REST queries / commands through /api proxy
  ├── EventSource stream with seq de-duplication
  ├── event projection store (disposable)
  └── React Flow canvases + timeline + inspectors
                         │
                         ▼
FastAPI presentation adapter (src/api/)
  ├── routers: meta, cases, runs, memory, graph, sources, evaluation
  ├── RunManager: isolated stores + background runtime tasks
  ├── read models: SQLite rows → stable Pydantic DTOs
  ├── SSE: persisted prefix + committed-event tail
  └── UI run registry: run_id → isolated db/status
                         │
                         ▼
Existing application boundaries (unchanged)
  LangGraphRuntime · EventEmitter · replay · DecisionRepository
  CaseDataAccess · MemoryNoteStore · GraphMemory · evaluator
                         │
                         ▼
SQLite scenario/run stores + checkpoint stores + Ladybug graph
```

### 4.1 Chosen stack

Backend:

- FastAPI with Pydantic response models and generated OpenAPI.
- Uvicorn for local development.
- Native FastAPI `EventSourceResponse`/`ServerSentEvent`; official FastAPI documentation identifies
  SSE as appropriate for AI streaming, live notifications, logs and observability and supports typed
  async iterables. See [FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/).
- Existing `uv` project and pytest suite; add `httpx` for API tests if not already transitive.

Frontend:

- React + TypeScript + Vite in `frontend/`. Vite officially supplies a `react-ts` template; see the
  [Vite guide](https://vite.dev/guide/).
- TanStack Query for REST server state; the current official API supports query caching, dependent
  queries and mutation state. See [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/reference/index).
- A small custom `useRunStream` hook for SSE; do not force an append-only stream into query caching.
- React Flow for workflow and entity graphs.
- Tailwind CSS with CSS-variable design tokens; accessible headless primitives where needed.
- Recharts or small native SVG charts for metrics, selected only after verifying current packages in
  the implementation session.
- Vitest + React Testing Library for component behavior. Testing Library recommends user-visible DOM
  interaction rather than implementation-detail tests; see its
  [official introduction](https://testing-library.com/docs/react-testing-library/intro/).
- Playwright for one real browser end-to-end path once the integrated launcher exists.

Do not add Next.js, server-side rendering, Redux, GraphQL or a WebSocket layer. They add machinery the
local POC does not need. SSE matches the one-way append-only event flow; commands remain ordinary
HTTP requests.

### 4.2 Source layout

```text
src/api/
  app.py                 FastAPI app factory and lifespan
  dependencies.py        root/store/run-manager dependencies
  models.py              stable API DTOs; never expose sqlite rows ad hoc
  run_manager.py         isolated stores, runtime tasks, status registry
  read_models.py         event/case/decision/memory/source projections
  sse.py                 ordered reconnectable event tail
  routers/
    meta.py cases.py runs.py memory.py graph.py sources.py evaluation.py

frontend/
  package.json package-lock.json vite.config.ts tsconfig*.json
  src/
    app/                  router, providers, shell
    api/                  generated/manual types, fetch client, SSE client
    features/
      mission-control/ run-observatory/ decision/ memory/ graph/ evaluation/
    components/           shared primitives and inspector renderers
    projections/          pure event reducers and event presentation registry
    styles/               Tailwind import, tokens, small custom animation CSS
  tests/                  fixtures derived from canonical event schema

scripts/dev.sh            one-command backend + frontend launcher
```

No source is placed under a product-named Python wrapper. Frontend code does not receive or read
`OPENAI_API_KEY`.

## 5. API contract

All endpoints are under `/api/v1`. Errors use one envelope:

```json
{"error":{"code":"run_not_found","message":"…","details":{}}}
```

### 5.1 Metadata and health

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | backend, scenario DB and graph availability |
| GET | `/meta` | adapters, model display, virtual clock, feature flags |
| GET | `/meta/routes` | ordered route definitions without secrets |
| GET | `/meta/agents` | configured roles and descriptions |
| GET | `/meta/skills` | skill names/descriptions and route usage |
| GET | `/meta/workflow` | static runtime nodes and allowed edges for React Flow |
| GET | `/schema/events` | current `EventEnvelope` JSON Schema |

### 5.2 Cases and queue

| Method | Path | Purpose |
|---|---|---|
| GET | `/cases` | paged/filterable case summaries |
| GET | `/cases/{case_id}` | case, transactions, communications summary and latest runs |
| POST | `/queue/runs` | execute Q01 asynchronously |
| GET | `/queue/runs/{run_id}` | ranking and metrics |

The API must use explicit read models. It must never return ground-truth or persona simulation data.

### 5.3 Run lifecycle

`POST /runs`:

```json
{"case_id":"DSP-2026-90015","adapter":"fake","auto_resume":true}
```

Returns `202` with `{run_id, case_id, status, events_url, stream_url}`. The `RunManager` creates a
fresh store under `data/generated/ui/`, copies the matching graph store, starts
`LangGraphRuntime.start()` in a background task, and records the mapping in a small UI registry so
run history survives API reloads.

| Method | Path | Purpose |
|---|---|---|
| GET | `/runs` | recent runs with filters and cursor pagination |
| GET | `/runs/{run_id}` | status, counts, virtual clock, wait and decision summary |
| POST | `/runs/{run_id}/cancel` | cancel an active demo run; never approve/alter a decision |
| POST | `/runs/{run_id}/rerun` | fresh isolated run using the same launch options |
| GET | `/runs/{run_id}/decision` | decision record plus field provenance |
| GET | `/runs/{run_id}/events` | paged events; filters include `after_seq`, type, actor and ref |
| GET | `/runs/{run_id}/events/stream` | ordered SSE stream |
| GET | `/runs/{run_id}/blobs/{sha256}` | redacted request/response/artifact blob |

SSE messages use the event sequence as `id`, canonical type as `event`, and the complete
`EventEnvelope` as JSON `data`. Honor `Last-Event-ID` and `after_seq`; send a heartbeat comment every
15 seconds; close after a terminal event once all committed rows have been sent. De-duplicate by
`(run_id, seq)` in both server and client. A SQLite polling tail is acceptable and preferable for the
first POC because it works for live, replayed and API-reloaded runs; the in-process emitter
subscription can be an optimization later.

### 5.4 Memory, graph and sources

| Method | Path | Purpose |
|---|---|---|
| GET | `/memory/notes` | filters: subject, scope, kind, tags, status, confidence, as-of |
| GET | `/memory/notes/{note_id}` | note plus lifecycle events and source refs |
| GET | `/runs/{run_id}/memory` | memory operations grouped by store/status |
| GET | `/graph/cases/{case_id}` | bounded operational entity neighborhood |
| GET | `/runs/{run_id}/graph` | query/write overlays from run events |
| GET | `/sources/{source_id}` | allowlisted operational/policy/evidence source projection |
| GET | `/evaluation/reports` | available durable report summaries |
| GET | `/evaluation/reports/{report_id}` | report and capability matrix |

Graph responses are `{nodes, edges, legend}` with stable IDs. Every node/edge includes `source_refs`;
run overlays also include `event_seqs`. Source lookup is implemented through an explicit resolver
registry (case, transaction, communication, packet, policy/research, event, note), never arbitrary
SQL or filesystem paths.

## 6. Frontend event projection

The frontend keeps canonical events unchanged and derives a `RunProjection` with pure reducers:

```ts
type RunProjection = {
  status: RunStatus
  currentSeq: number
  virtualNow: string
  route?: RouteDecision
  activeNodes: string[]
  completedNodes: string[]
  activeSpans: Record<string, SpanProjection>
  plans: PlanVersion[]
  hypotheses: HypothesisVersion[]
  tools: ToolExchange[]
  subagents: SubagentRun[]
  skills: SkillLoad[]
  memory: MemoryOperation[]
  graphActivity: GraphOperation[]
  verifierChecks: Check[]
  panel?: PanelProjection
  decision?: DecisionProjection
  usage: UsageTotals
}
```

Reducers must be deterministic and replayable to any sequence. Unknown event types render as generic
event cards and remain in raw JSON; a new backend event must never crash the UI.

Pair exchanges by IDs/spans, not adjacency:

- `tool_call` ↔ `tool_result`
- `llm_call_started` ↔ `llm_call` / `llm_call_failed`
- `subagent_started` ↔ `subagent_finished`
- `wait_suspended` ↔ `wait_resumed`
- `node_entered` ↔ `node_exited`

## 7. Functional behavior and edge cases

- On SSE reconnect, fetch events after the last committed sequence and continue without duplicates.
- If the browser opens a completed run, render immediately from paged REST and do not require SSE.
- If a run fails, retain its entire prefix, show the failure event and keep raw inspection available.
- Large payloads stay behind blob references until expanded.
- Virtual-clock jumps are rendered as explicit gaps; do not animate through simulated days.
- Parallel branches use separate swimlanes and preserve sequence ordering in the unified timeline.
- The API can serve multiple active runs, each with an isolated scenario/checkpoint/graph store.
- Fake is always the default adapter. OpenAI is shown only if the backend sees a configured key;
  the key value is never returned.
- Cancellation is a demo execution control and should be labeled as such. It does not alter an
  already recorded decision.

## 8. Staged implementation plan

Every stage ends with tests, updated docs and a rewritten current-status section in `handoff.md`.
Do not combine stages until the prior acceptance gate passes.

### Stage 1 — Read-only API foundation: COMPLETE (2026-09-14)

Delivered:

- FastAPI app factory (`src/api/app.py`), one error envelope (`src/api/errors.py`) and
  `/api/v1/health`.
- DTO/read-model layer (`src/api/models.py`, `src/api/read_models.py`) for cases, runs, events,
  decisions, metadata and the event schema, reading `run_events`/`decision_records` directly and
  reusing the canonical `EventEnvelope`/`DecisionRecord` Pydantic models rather than re-deriving
  frontend-facing shapes.
- Read-only `/meta`, `/meta/routes`, `/meta/agents`, `/meta/skills`, `/meta/workflow`,
  `/schema/events`, `/cases`, `/cases/{case_id}`, `/runs`, `/runs/{run_id}`,
  `/runs/{run_id}/events`, `/runs/{run_id}/decision`.
- OpenAPI generation (`schemas/openapi.json`) and 8 new API tests against a copied scenario store.

Stage-1-specific decision (see handoff for the honest limitation this implies): the app factory
takes one configured `db_path` rather than a run registry. There is no execution manager yet, so
every endpoint reads whichever single SQLite store the process was started against — matching the
Stage 1 acceptance gate ("inspect a prior run"), not yet the multi-run registry Stage 2 adds.

A run's status is derived, not stored: `_derive_status` in `read_models.py` looks for the latest
`error` or `termination` event (not simply the highest `seq`) because `terminate` emits a trailing
`run_completed` event and the checkpointer wrapper commits `checkpoint_saved` after that — the
naive "read the last row" approach reports `running` for an already-decided run.

Acceptance — met:

- Existing 78-passed/1-skipped backend suite stays green (86 passed/1 skipped with the new API
  tests added).
- New tests prove pagination, filters (regime/status/stage/claim_family/q, after_seq/type/actor),
  decision provenance, unknown case/run/decision 404s, a suspended-run wait payload, and that
  `OPENAI_API_KEY` and the prohibited `birth_year` field never appear in a response body.
- `curl` against a live `uvicorn` process lists cases, inspects a historical run and replays its
  ordered events (verified manually; see handoff for the exact commands and output).

### Stage 2 — Execution manager and live stream: COMPLETE (2026-09-14)

Delivered:

- `src/api/run_manager.py`: `RunManager` — one copied store + `LangGraphRuntime` per UI-started
  run under `data/generated/ui/` (`bootstrap.isolated_workspace`/`build_runtime`, unchanged from
  Stage 1's `catcher run --db` isolation), and a tiny durable SQLite registry
  (`data/generated/ui/registry.sqlite`, table `runs(run_id, case_id, kind, store_path, adapter,
  auto_resume, created_at)`) mapping `run_id -> store path` so run history and store routing
  survive an API process restart. Live `LangGraphRuntime`/task objects (needed to `cancel()` or to
  know whether a run's driving task is still alive) exist only in this process's memory, same as
  the harness's own `_tasks`/`_emitters`.
- `POST /runs`, `POST /runs/{run_id}/cancel`, `POST /runs/{run_id}/rerun`, `POST /queue/runs`,
  `GET /queue/runs/{run_id}` (`src/api/routers/runs.py`, `src/api/routers/queue.py`).
  `runtime.portfolio.rank_portfolio` gained an optional `run_id` parameter (backward compatible
  with the CLI's `queue` command) so the API can know a queue run's ID before it finishes ranking.
- `GET /runs/{run_id}/events/stream` (`src/api/sse.py`): polls the run's SQLite store rather than
  subscribing to the in-process `EventEmitter`, per this design's own Stage 2 guidance — it works
  identically for a live run, a run resumed in a different process, and pure historical replay.
  `sse_starlette.EventSourceResponse`'s `ping=15` supplies the heartbeat; `Last-Event-ID` (falling
  back to `after_seq`) resumes from any sequence with no gap or duplicate.
- The one genuinely new problem this stage had to solve: a run that suspends and auto-resumes
  *internally* (§4.4) emits one `termination` event **per segment**, not just at the very end (an
  agentic-provider or evidence wait mid-investigation still gets one even though the run keeps
  going). Naively closing the SSE stream on the first `termination` event would truncate a live
  C04/C13-style run. The fix: `RunManager.is_task_done(run_id)` reports whether *this process's*
  asyncio task for that run has actually finished — true only once, exactly when no more events
  can ever be appended by it — and `api/sse.py` only falls back to the persisted
  latest-`termination`/`error` status (`api/read_models.derive_status`, safe because nothing more
  will ever be written) when the run is unmanaged by this process (a historical or
  different-process run).
- `src/api/dependencies.py` gained `get_run_manager`, and `get_run_connection`/
  `get_all_connections` — async generators, not the plain sync ones Stage 1 used, because mixing a
  sync generator dependency with an `async def` endpoint dispatches the dependency to a worker
  thread while the endpoint body runs on the event loop thread, and `sqlite3` connections are
  thread-affine; every run-lifecycle endpoint that touches a connection is `async def` for the same
  reason. `GET /runs` now merges results across every store the API currently knows about
  (`read_models.list_runs`, `list[sqlite3.Connection]`) instead of Stage 1's single configured
  store, replacing that shortcut as planned rather than adding a second path alongside it.
- `tests/test_api_stage2.py` (8 tests, `httpx.AsyncClient` over an in-process ASGI transport so the
  SSE stream can be consumed concurrently with the run it follows): gap-free/dup-free streaming to
  a decision, exact-suffix reconnect by both `after_seq` and `Last-Event-ID`, two simultaneous
  case runs with the pristine store hashed unchanged before/after, cancel-is-idempotent + rerun,
  rerun-rejection for an unmanaged run id, a full Q01 queue run, a bad-`case_id` run reaching
  `failed` via a genuine `error` event without ever touching the pristine store, and `GET /runs`
  merging a Stage-1-style direct run with an API-started one.

Acceptance — met:

- `POST /runs` returns `202` immediately (`RunManager.start_run` only awaits
  `LangGraphRuntime.start()`, which itself only schedules the driving task).
- A test consumes the stream from sequence 1 through one terminal decision with no gaps/duplicates.
- Reconnecting from a middle sequence (via `after_seq` and via `Last-Event-ID`) yields exactly the
  missing suffix.
- Two simultaneous fake runs each decide correctly and the pristine store's sha256 is unchanged.
- UI runs never mutate the pristine scenario store, including a run that fails immediately.

Known limitations carried forward (honest, not blocking):

- Cancel and the SSE "is this run still live" check both key off the in-memory `RunManager`
  registry; a run started by a different API process (or before a restart) can still be inspected
  and its history replayed via SSE/REST, but cannot be cancelled from this process, and its stream
  closes using the persisted-status heuristic rather than true liveness. This matches the design's
  own scoping ("LangGraphRuntime keeps active tasks/emitters in-process").
- `GET /queue/runs/{run_id}`'s ranking is cached in `RunManager` memory only, not persisted; it is
  lost on an API restart (the run's events, including `portfolio_ranked`, remain in its store).
- No dedicated failure-injection test exercises a run that fails *after* producing a large event
  prefix (only a run that fails immediately on an unknown case, and a `runtime.cancel()` race); the
  append-only, hash-chained store design makes prefix retention structural rather than something
  this stage's tests needed to prove separately.
- There is still no resume-from-suspension endpoint (`POST /runs/{run_id}/resume` was never in this
  design's Stage 2 endpoint table); a genuinely suspended (`auto_resume=false`) run stays suspended
  until resumed some other way (CLI `catcher resume`).

### Stage 3 — Frontend shell and Mission Control: COMPLETE (2026-09-14)

Delivered:

- `frontend/`: Vite + React 19 + TypeScript, Tailwind v4 (CSS-token `@theme`, no `tailwind.config.js`
  needed), `react-router-dom` for the two Stage 3 routes (`/` Mission Control, `/runs/:runId` Run
  Observatory). The responsive three-pane shell (`app/Shell.tsx`) is a 280px nav rail / flexible
  center / 380px inspector `grid` on `lg+`; the rail and inspector collapse below `lg` (mobile keeps
  the center content, which is the actual workable surface for both routes) rather than becoming a
  drawer — a deliberate, documented trade-off, not an oversight.
- `api/types.ts` (hand-mirrors `src/api/models.py`/`domain/events.py` — no generated client yet),
  `api/client.ts` (typed fetch wrapper, one `ApiError`), `api/useRunStream.ts`.
- `projections/runProjection.ts`: a small, pure, deterministic reducer over the canonical event log
  (event/tool/model/subagent/memory/wait/verifier counts, usage totals, terminal/failed flags) —
  the Stage-3-sized slice of the design's full `RunProjection` (§6); workflow/plan/hypothesis/panel
  projections are Stage 4.
- `features/mission-control/`: `CaseFilters`, `CaseCard`, `RunLauncher` (per-case adapter/auto-resume
  + Run button), `QueueLauncher` (separate component — Q01 is not a `/cases` row, it POSTs
  `/queue/runs`, not `/runs`), `MissionControlPage`.
- `features/run-observatory/`: `EventTimeline` (color-coded by the doc's fixed accent meanings via
  `components/eventColor.ts`), `MetricsStrip`, `DecisionPanel` (cardholder outcome, network actions,
  confidence, explanation — the Stage-3-sized slice of Decision & Provenance; field-level
  `event_seqs`/`source_ids` provenance is Stage 4), `RunObservatoryPage`.
- `app/InspectorContext.tsx` + `app/Inspector.tsx`: selecting a timeline event shows its actor,
  times, refs and raw payload JSON in the right pane.
- Tests: `useRunStream.test.ts` (REST-snapshot + SSE-tail merge, de-duplicated and seq-ordered, via a
  hand-rolled `ReadableStream`/`Response` mock — not `EventSource`, see below), `CaseFilters.test.tsx`
  (filter reporting), `RunLauncher.test.tsx` (mutation → navigation, with `api/client` and
  `react-router-dom`'s `useNavigate` mocked). `npm run test` (Vitest + React Testing Library):
  **5 passed**. `npx tsc -b`: clean. `npx oxlint`: 3 warnings (react-refresh export-shape, one
  set-state-in-effect that is the intended REST-then-stream sequencing), no errors. `npm run build`:
  clean (370 KB JS / 14 KB CSS, gzip 115 KB / 4 KB).

**One real design deviation from this document, made deliberately: `useRunStream` does not use
`EventSource`.** §5.3 says "de-duplicate by `(run_id, seq)` in both server and client" and the SSE
messages are named after the canonical event `type` (`api/sse.py`: `yield {"id": ..., "event":
event.type, "data": ...}`) — and that vocabulary is meant to grow (Stage 4/5 add many more event
kinds; §6 says "a new backend event must never crash the UI"). `EventSource.onmessage` only fires
for the unnamed `message` event; catching every other named event would require either a fixed
`addEventListener` call per known type (silently drops any type not in that fixed list — exactly
the failure mode §6 forbids) or reading `EventSource`'s private frame buffer, which doesn't exist.
`useRunStream.ts` instead fetches the stream with `fetch`/`ReadableStream` and parses the `data:`
line of each frame itself, ignoring `id:`/`event:` (the payload's own `seq` is authoritative
either way). Browser `EventSource` reconnect via `Last-Event-ID` is replaced with an explicit
poll-and-retry loop keyed on the last-seen `seq`, checking `GET /runs/{run_id}` for a terminal
status once the stream ends to decide whether to reconnect or stop — behaviorally equivalent to
what `EventSource` would have done, but able to dispatch on an open-ended `type` vocabulary. If a
future stage regrets this, only `api/useRunStream.ts` needs to change: nothing about the wire
format or the API changed, and no other frontend code touches SSE framing directly.

**One real backend bug found and fixed while manually verifying this stage in a live browser,
worth knowing before touching `src/api/`:** `GET /cases`/`GET /cases/{case_id}` intermittently
500'd with `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that
same thread`. `api/dependencies.get_connection` was still the plain sync generator dependency from
Stage 1, paired with `cases.py`'s `def` (sync) endpoints — the same cross-thread hazard Stage 2's
handoff entry already documents and fixed for the run-lifecycle endpoints (FastAPI dispatches a
sync generator dependency and a sync path-operation function to the worker threadpool
independently, so they can land on different threads for one request), just not yet applied to
`cases.py` because Stage 1/2's own tests happen not to trigger the race. A real browser hitting
`/meta`, `/cases`, `/runs` back-to-back does. Fixed the same way: `get_connection` is now an
`AsyncIterator` and `get_cases`/`get_case` are `async def`. `uv run pytest` stayed at 94 passed / 1
skipped; ruff check/format clean.

Acceptance — met:

- Component tests cover case filtering (`CaseFilters.test.tsx`), the launch mutation
  (`RunLauncher.test.tsx`) and ordered/de-duplicated stream updates (`useRunStream.test.ts`).
- Verified live in a real Chromium browser (Playwright, driven manually against the actual `uv run
  uvicorn`/`npm run dev` processes, not a committed E2E script — that's Stage 6): launched C02
  (`DSP-2026-90002`, fake adapter) from Mission Control, watched the timeline grow to 132 live
  events with no console errors, and reached a `Decided` status with the cardholder/network
  decision panel visible — all without a page reload. Also exercised the Q01 queue launcher and a
  narrow (390px) mobile viewport (see the stage's screenshots directory reference in `handoff.md`
  if kept, or rerun the same manual steps).
- Keyboard: every interactive control is a native `button`/`select`/`input`/link, so Tab order and
  `:focus-visible` (global 2px cyan outline in `index.css`) work without extra wiring; verified one
  Tab reaches the first real button. Reduced motion: the only non-decorative animation
  (`.animate-pulse-edge`, used for the live-status pulse) is disabled globally via
  `prefers-reduced-motion: reduce` in `index.css`.

Known limitations carried into Stage 4 (honest, not blocking):

- No workflow graph, swimlanes, plan/hypothesis/panel views, memory/graph explorers or evaluation
  view yet — all Stage 4/5 by design.
- `api/types.ts` is hand-maintained against `src/api/models.py`, not generated from
  `schemas/openapi.json`; a backend DTO change needs a matching manual edit here until a generator
  is wired in (not currently planned — the design doc never commits to one).
- The nav rail's "Recent runs" list and a run's own header status badge poll (`refetchInterval`)
  rather than stream; only the event timeline and metrics strip are truly live. Acceptable for
  Stage 3's acceptance gate; Stage 4's swimlanes/workflow graph will likely want the same live
  event feed the timeline already has, not more polling.
- No Playwright test is committed yet (planned for Stage 6, per this design's own staging); Stage 3
  acceptance was met by manual Playwright-driven verification instead, not skipped.

### Stage 4 — Advanced observability

Deliver:

- Workflow React Flow canvas with active edge animation, fan-out and back-edge rendering.
- Actor swimlanes and specialized inspectors for route, tool, model, subagent, skill, memory,
  sandbox, wait, clock, verifier and panel events.
- Plan/hypothesis diffs and safe Reasoning Artifacts view.
- Decision/provenance explorer with source and blob navigation.
- Memory Explorer and bounded Graph Lab API + UI.

Acceptance:

- C06 visibly shows verifier failure and replan back-edge.
- C11 shows three specialists, shared-address graph evidence, panel and automatic reopening.
- C13 shows provider wait/resume, condition evaluation and policy-gap write.
- C12/C12b demonstrate positive and negative graph-memory writes without invented nodes.

### Stage 5 — Evaluation and interaction polish

Deliver:

- Evaluation report/capability matrix view and proving-event navigation.
- Replay seek/speed/filter/bookmark controls, URL-deep-linked selections and command palette.
- Queue visualization, deadline pressure and virtual-time treatment.
- Optional UI trigger for bounded fake evaluation.
- Visual polish, responsive behavior and performance profiling on the largest Q01 trace.

Acceptance:

- Capability cells navigate to real proving events.
- Seeking/replaying produces the same final projection hash as a live-follow run.
- Q01 remains responsive with approximately 1,000 events.

### Stage 6 — Integrated launcher and final verification

Deliver:

- `scripts/dev.sh` (and a root `dev.sh` shim if desired) that validates dependencies, loads `.env`
  only for the backend, starts FastAPI on 8000 and Vite on 5173, traps signals and stops both.
- Vite `/api` proxy, clear startup output and health wait.
- Browser end-to-end test, final README usage and screenshots/GIF if useful.

Acceptance:

- From a clean dependency install, one command starts both services and Ctrl-C leaves neither alive.
- Playwright launches a fake case, observes route/tool/subagent or wait activity as applicable, and
  reaches the decision view.
- Backend tests, frontend tests/build/lint, data validation and 21/21 fake evaluation all pass.

## 9. Documentation rules during implementation

- `handoff.md` is updated after every stage with exact commands/results, files changed, failures and
  the next stage only.
- Update this design when an API or UX decision changes; do not let implementation silently diverge.
- Export OpenAPI and event schema as generated artifacts once endpoints exist.
- Add frontend commands and launcher behavior to README at Stage 3/6, not before they work.
- If library APIs differ from this plan, verify current official documentation first and record the
  resolution.

## 10. Definition of done

The frontend initiative is complete when a fresh user can run one script, select any hero case,
watch the actual execution live, pause/seek the visualization, inspect every major capability,
explore memory and graph evidence, trace the final decision to sources, replay historical runs, and
view evaluation coverage—without the UI manufacturing facts or exposing private chain-of-thought.
