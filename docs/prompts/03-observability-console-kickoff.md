# Observability console implementation kickoff

You are continuing the card-dispute-agent POC by implementing the planned **Dispute Observatory**
frontend and API. Start with the single current stage named in `handoff.md`; do not jump ahead.

## Read before changing code

Read these files completely, in order:

1. `handoff.md` — current state, exact next stage and validation baseline.
2. `docs/design/07-observability-console.md` — authoritative UI, API, stream and staged plan.
3. `README.md` — runnable system and current commands.
4. `docs/design/05-agent-architecture.md` — runtime boundaries and non-negotiable automation.
5. `docs/design/03-data-dictionary.md` — operational stores and forbidden evaluator/harness data.
6. `schemas/trajectory-event.schema.json` and `src/domain/events.py` — frontend event contract.
7. `src/observability/emitter.py`, `src/replay.py`, `src/decisions.py` — persisted trajectory,
   replay and field provenance.
8. `src/runtime/langgraph_runtime.py`, `src/bootstrap.py`, `src/cli.py` — runtime lifecycle and
   existing entry points.
9. The files named for the active implementation stage in the design document.

## Non-negotiable implementation rules

- The API and UI are presentation/control adapters. Do not move dispute policy, routing, governance,
  action or memory decisions into them.
- Render only canonical events and persisted records. Never manufacture capability events or infer a
  decision that was not recorded.
- “Thought” means safe recorded reasoning artifacts: plans, rationale, hypotheses, contradictions,
  checks, panel positions and explanations. Never expose or request private chain-of-thought.
- No UI approval gate or human adjudication. Controls may launch, cancel, rerun, filter and replay.
- Never expose `data/generated/ground_truth/**`, `data/generated/simulation/**`, arbitrary filesystem
  paths, arbitrary SQL or the value of `OPENAI_API_KEY`.
- Default UI execution to the fake adapter and an isolated copied store. A UI run must not mutate the
  pristine scenario database.
- Keep Python source flat under `src/`; place the separate TypeScript app under `frontend/`.
- Preserve the dirty worktree and do not commit unless explicitly requested.
- Use current official documentation before changing framework/API assumptions.

## Stage workflow

1. Restate the active stage and inspect the relevant existing boundaries.
2. Implement only that stage's deliverables.
3. Add proportionate backend/frontend tests and run the stage acceptance commands.
4. Update affected docs.
5. Rewrite the current status and next stage in `handoff.md`, including exact results and any honest
   limitation. Updating the handoff is part of completion.

The six stages are defined in `docs/design/07-observability-console.md`: read-only API; execution and
SSE; frontend shell; advanced observability; evaluation/polish; integrated launcher/final validation.
