## Who you are and what we're building

You are the lead engineer for **CatcherAI**, a proof-of-concept **agentic card-dispute investigation system** for a card issuer. The foundation is already done: domain research, 20 hand-built investigation cases plus a queue scenario with machine-checkable ground truth, a synthetic data ecosystem, a versioned policy corpus, skills (playbooks), seeded agent memory, and a memory/architecture design.

Your job in this session is to **research how best to build it, propose an architecture, and then implement it** initially on **LangChain Deep Agents (`deepagents`) + LangGraph**, using **OpenAI `gpt-5.6-luna` as the default backbone model through the Responses API**. The domain workflow must not be coupled to OpenAI, a LangChain model class, Deep Agents, or any provider SDK: model changes must be configuration-only, and replacing the agent runtime later (for example with the Codex SDK) must require a new adapter rather than changes to dispute logic, tools, memory, governance, evaluation or trajectory consumers. It must robustly solve the use case, be easy to extend, show every step transparently, and look genuinely state-of-the-art.

Work in three phases, with a checkpoint with me after phases 1 and 2 (details at the end).

> **Development-process subagents (not CatcherAI runtime behavior):** If you delegate research, design, implementation, debugging or review work to subagents while carrying out this prompt, use **`gpt-5.6-luna` by default** for normal, well-scoped work. Use **`gpt-5.6-sol`** for genuinely complicated work that needs deeper reasoning or broad cross-cutting synthesis—for example consequential architecture decisions, difficult multi-module debugging, security/compliance review, or resolving conflicting evidence. Prefer Luna unless the task's complexity justifies Sol. This instruction governs the engineering session's own subagent model selection only; it must **not** be implemented as CatcherAI model-routing logic, added to the framework's runtime configuration, or included in product trajectories/evaluations.

> **Non-negotiable: the system is fully automated. No human in the loop.** No human approval gates, no human review queues, no interrupts that wait for a person, no simulated human reviewer. Every case must reach a final, executed decision automatically. Hard or high-impact decisions are handled by automated governance (`data/corpus/policies/internal/LFB-SOP-DSP-003__v6.md`): an adversarial review panel, verifier checks, a 0.75 confidence threshold with a conservative cardholder-favorable default, and bounded automated actions. Runs may suspend **only** for external events (merchant/provider evidence, simulated cardholder replies, scheduled follow-ups) and must decide by the latest safe decision time. (The phase checkpoints below are for our development process, not part of the system.)

> **Non-negotiable: full transparency. No silent steps.** A frontend will replay every run. Every step must be logged as a structured event: every graph node and edge, routing decision, plan change, model call, **tool call (which tool, why, with what arguments, what came back)**, subagent delegation, skill load, **memory access (which store, which query and filters, which records came back, which were used or discarded, what was written, superseded, rejected or deliberately *not* written)**, computation, evidence arrival, clock change, review-panel position, verifier check, decision and termination. Every decision must link back to the events and source IDs that justify it. If it isn't in the event log, it didn't happen. See §5 "Transparency" for the full spec.

---

## 1. Read these first (in this order)

| File | Why |
|---|---|
| `README.md` | The foundation document: use case, domain background, data ecosystem, memory design (§6), evidence and policy ecosystems, generation approach, **architecture component → forcing scenario (§10)**, evaluation design, production gaps, assumptions |
| `docs/research/01-domain-research.md` | How disputes really work: Visa lifecycle (Allocation vs Collaboration), reason codes, Reg Z / Reg E clocks, CE 3.0 (versions before/after 24 Oct 2026), friendly fraud vs account takeover, evidence ecosystem, industry tools (issuer vs merchant side), academic work (τ-bench, RIRAG, FIA, ClaimPilot) |
| `docs/design/02-case-catalog.md` | The 20 hero cases (C01–C19, C12b) + Q01 queue: what each proves, expected investigative path, pivots, traps, rules-engine vs single-prompt failure modes, and the architecture coverage matrix |
| `docs/design/03-data-dictionary.md` | Every file and field, ID joins, temporal fields, `available_at` semantics, evidence packet blocks, memory-note schema, graph schema, **decision-record output schema (§9)**, ground-truth schema (§10), deliberate data-quality issues |
| `data/corpus/policies/**/*.md` | Versioned policy documents (front matter: `doc_id`, `effective_from/to`, `status`, `supersedes`) |
| `data/corpus/skills/*.md` | Existing investigation playbooks (convert to the Deep Agents `SKILL.md` format as needed) |
| `data/generated/manifest.json` | What exists and how much |
| `data/generator/validate.py`, `data/generator/derived.py` | Reference implementations of discoverability queries, business-day and Reg Z billing-cycle math (reuse or port into sandbox helpers) |

Commands:
```bash
python3 data/generator/gen.py && python3 data/generator/validate.py   # regenerate + 401 checks
python3 data/generator/load_sqlite.py                                 # build data/generated/catcher.sqlite
```

**Hard rule:** the agent must **never** read `data/generated/ground_truth/**` or `data/generated/simulation/**`. Those are for the evaluator and the harness only. Enforce this with filesystem permissions or backend routing, not just instructions.

---

## 2. The problem in brief (details in the docs)

### How the industry flow works
Cardholder contacts the issuer → intake and triage (is it a dispute? credit → Reg Z or debit → Reg E? fraud or non-fraud?) → pre-dispute checks (merchant contact, Visa Order Insight / RDR, credits already posted) → regulatory clocks start (Reg Z: acknowledge ≤30 days, resolve ≤2 billing cycles / 90 days; Reg E: 10 or 20 business days to investigate or provisionally credit, then 45/90 days) → fraud reported to the network → dispute filed under a Visa **dispute condition** (10.x fraud, 11.x authorization, 12.x processing, 13.x consumer) → acquirer/merchant responds with evidence → pre-arbitration → arbitration → cardholder resolution (credit, partial, explanation letter, re-bill with notice). **Cardholder outcome and network recovery are separate decisions.**

### How the industry solves it today
- **Issuer-side:** human dispute teams (intake, Tier 1/2, QA) on case platforms (Visa Resolve Online, Mastercom, Pega Smart Dispute with a questionnaire-driven "Reason Code Advisor" and predicted-win routing, Quavo QFD/ARIA with auto-pay / auto-deny / refer buckets). Visa launched issuer AI tools in April 2026: Dispute Intelligence, Dispute Doc Analyzer (structures merchant documents) and Dispute Case Manager.
- **Merchant-side:** chargeback-defense vendors auto-compile evidence by reason code (Stripe Smart Disputes, Chargeflow, Justt, Verifi, Ethoca, Mastercard First-Party Trust).
- **Where they break:** hard-coded reason-code mapping ignores invalid-dispute clauses and rule versions; per-case tools can't see rings or compromise points; evidence arrives late and adversarial; arithmetic on dates, FX and pro-rata is error-prone; stale internal knowledge persists; escalation criteria are applied inconsistently.

### What our system must do
For each case: understand the claim → route it → plan → retrieve the right policy **as of the governing date** → search history → traverse related entities → call tools and subagents → request and wait for evidence → detect contradictions → compute in a sandbox → find and distinguish precedents → revise the plan → track what's known and unresolved → reach an evidence-backed, confidence-qualified decision → explain it → recommend and execute the next action → challenge high-impact decisions through an automated review panel (SOP-DSP-003 v6) → govern its own memory → leave a full auditable trajectory. **All of it without a human.**

The **decision record** (data dictionary §9) is the output contract the evaluator checks against `ground_truth/cases/<case_id>.json`.

---

## 3. Mandatory components — all of these MUST be implemented and demonstrably used

The solution is **not acceptable** unless every component below is implemented, genuinely load-bearing, and **provably used** in the trajectories of the cases that need it:

1. **Agents**
2. **Router**
3. **Loop engineering (with real termination conditions)**
4. **Agent graph engineering**
5. **Subagents**
6. **Tool / function calling**
7. **Harness**
8. **Skills**
9. **Memory: persistent, graph, and semantic/vector** (all three)
10. **Sandbox or REPL for computing over data**
11. **Agent read paths and agent write paths** (selective read, selective write, consolidation and forgetting)

The dataset already contains cases that **cannot be solved without each one**:
- **Per case:** see `required_capabilities` in `data/generated/ground_truth/cases/<case_id>.json`. Each entry gives the capability, `necessity` (primary/supporting), why it's needed, and the trajectory events that prove it was used.
- **Summary:** `data/generated/ground_truth/capability_coverage.json` and §2 of `docs/design/02-case-catalog.md`.

Every component is *primary* in at least three cases:

| Component | Primary cases |
|---|---|
| Agents | C05, C11, C15 |
| Router | C02, C03, C07, C08, C13, C17, C18, Q01 |
| Loop engineering (real termination conditions) | C01, C02, C03, C12, C13, C17, C18 |
| Agent graph engineering | C06, C09, C10, C11, C12, C15 |
| Subagents | C05, C08, C10, C11, C12, C13, Q01 |
| Tool / function calling | C01, C02, C13, C16 |
| Harness | C02, C03, C04, C09, C10, C13, C15, C19 |
| Skills | C01, C05, C06, C08, C10, C14 |
| Memory — persistent (SQLite system of record) | C01, C04, C05, C11, C15, C17, C18, Q01 |
| Memory — graph | C02, C08, C10, C11, C12, C12b |
| Memory — semantic / vector | C01, C05, C06, C07, C09, C13, C14, C16 |
| Sandbox / REPL | C04, C05, C06, C07, C08, C09, C14, C15, C17, C18, Q01 |
| Agent read paths (selective read) | C03, C06, C08, C09, C11, C16, C19 |
| Agent write paths (selective write, consolidation, forgetting) | C02, C03, C06, C08, C09, C11, C12, C12b, C13, C19 |

**Acceptance criteria:**
- The evaluator must check capability usage from the trajectory event log, not just final answers. For every case, each `primary` capability must appear through its trajectory signals (e.g. `route_decision`, `termination{reason}`, `wait_suspended/resumed`, `edge_taken` back-edges, `subagent_started/finished`, `skill_loaded`, `graph_query`/`graph_write`, `retrieval{filters}`, `computation`, `memory_read` + `memory_verified/rejected`, `memory_write/supersede/retract/consolidate`, `write_rejected`).
- A case that reaches the right answer without using its primary capabilities counts as a **capability failure**.
- Report a capability × case matrix of pass/fail in the eval results.
- Honor `memory_ops.must_not_write` in the ground truth: selective write means also **not** writing (and log the decision not to write).
- **Trajectory completeness is scored too:** a run fails if any model call, tool call, memory/graph/vector access, sandbox execution or state-changing node has no matching event, or if any decision-record field lacks provenance links (see §5 Transparency).

### Capability details (minimum bar)

Use README §10 and the catalog's coverage matrix to tie every capability to the cases that force it. Nothing decorative.

| Capability | Minimum bar |
|---|---|
| **Agents** | goal-directed investigators that choose what evidence to pursue next |
| **Router** | case-level: not-a-dispute / regime (Reg Z vs Reg E) / claim family / depth (L1–L4) / novel type; portfolio-level queue prioritization (Q01). Routes must be **data/config-driven** so new routes can be added without touching code |
| **Loop engineering with real termination conditions** | explicit, logged stop reasons: decision record complete and verifier passed; budget exhausted (tool calls / tokens / wall-clock); **suspended waiting for an external event** (virtual clock, `available_at`) with checkpoint and resume (or decide at the latest safe decision time); conservative default applied after the review panel; no-progress detection (N iterations without new facts); max re-plans reached. L1 cases must stop early |
| **Agent graph engineering** | a LangGraph graph with explicit nodes and edges (e.g. intake → route → investigate → verify → review panel (when required) → decide → act/write → memory maintenance), including **back-edges** (verify → re-plan), conditional edges, parallel fan-out, and suspend/resume on external events |
| **Subagents** | specialist subagents via Deep Agents (`task` tool, custom `SubAgent`s; evaluate the **dynamic subagents** feature for parallel fan-out such as per-folio-line or per-linked-case). Likely specialists: transaction/ledger analyst, merchant-evidence analyst, policy analyst (as-of retrieval), graph/link analyst, security/ATO analyst, quant (sandbox), research agent, cardholder liaison, adversarial reviewers (cardholder advocate vs merchant advocate), verifier/critic, memory curator. Research and justify the final set, don't just adopt this list |
| **Tool / function calling** | typed tools (Pydantic schemas) over SQL, graph, vector search, evidence requests, research corpus, messaging to the simulated cardholder, case actions, memory operations, sandbox execution |
| **Harness** | virtual clock and `available_at` gating; simulated cardholder (persona-driven LLM using `simulation/cardholder_personas.json`, τ-bench style); scheduled follow-ups; scenario loader; budgets; trajectory capture; eval runner |
| **Skills** | Deep Agents skills (`SKILL.md`, progressive disclosure) built from `data/corpus/skills/`; route-selected; new skills are drop-in directories |
| **Memory: persistent** | SQLite system of record (case state, transactions, events, memory-notes lifecycle table); LangGraph checkpointer for thread state |
| **Memory: graph** | LadybugDB (embedded Cypher, Kùzu fork) loaded from `graph/*.jsonl`, with a NetworkX fallback behind the same small interface; agent can write hypothesis nodes/edges (`SuspectedRing`, `SUSPECTED_COMPROMISE_POINT`) with evidence edges and `status=active`, and apply bounded controls (watchlists, monitoring) — never account closure |
| **Memory: semantic/vector** | sqlite-vec (same SQLite file) over policies, precedents, communications, research, packets and memory notes, with **metadata filtering by effective date / validity window** plus hybrid keyword search (FTS5 already built) |
| **Working memory** | per-case "case file" (facts with sources, hypotheses, open questions, deadlines, plan) in the Deep Agents virtual filesystem, shared across subagents as a blackboard |
| **Sandbox / REPL** | Python execution for deadlines, business days, billing cycles, pro-rata, FX, time zones, CE 3.0 day counts, SQL/graph analytics; read-only data access; code and output recorded in the trajectory. Evaluate Deep Agents sandbox backends vs a local restricted subprocess |
| **Agent read paths** | **selective read**: retrieval scoped by case, entity, scope, `as_of` date, validity window, confidence and status (never retrieve superseded/retracted notes as current); memory treated as a lead to verify, never as evidence |
| **Agent write paths** | **selective write**: the agent decides *whether* something is worth remembering; a write gate validates schema (`source_refs`, validity, confidence), blocks prohibited content (SOP-DSP-004), and dedupes; case actions and letters are writes too |
| **Consolidation & forgetting** | supersede, retract (with correction note), consolidate (≥3 observations → validity-bounded pattern, merge duplicate entities), time-bound, dedupe, expire (TTL), purge (prohibited content), plus recency/access decay. Seeded examples: MEM-0142, 0150, 0151, 0152, 0160, 0180/0181, 0185, 0196, 0201–0209 (see README §6). Run as an in-case step and as an offline "memory curator" job |
| **Automated governance (no human in the loop)** | the automated review panel from `LFB-SOP-DSP-003@v6`: cardholder-advocate and issuer/merchant-advocate subagents run independently on the same case file, an independent adjudicator decides, verifier checks gate the result; confidence threshold 0.75; conservative cardholder-favorable default below it; bounded automated actions (automatic reopening in the cardholder's favor, watchlists, monitoring, step-up security, policy-gap records); every position, confidence and flip fact recorded (C10, C11, C12, C13) |
| **Transparency / trajectory** | one instrumentation point captures every step (§5); replayable to any `seq`; decision provenance links; a CLI replay viewer before the frontend exists; completeness tests that fail on silent steps |
| **Evaluation** | run all cases; deterministic checks, `must_not`, required facts and contradictions found, required citations, memory ops, budget adherence, **pass^k** reliability, cost/latency, Q01 ranking correlation; optional rubric judge. Trajectory evaluation too, not just final answers |

---

## 4. Research first (phase 1): search broadly, then synthesize

Before designing, research how others build systems like this and bring back **several distinct approaches** we can combine. Use web search, GitHub search and the Context7 docs tool. Cite everything and separate proven practice from marketing.

**Research is not budget-constrained.** Go as wide and deep as the problem needs:
- The directions below are **starting points, not limits**. Follow citations, related repos, issues and discussions wherever they lead, and add directions you discover.
- Read actual source code, not just READMEs: clone relevant repos into a scratch directory and inspect how they implement agents, memory, event streams and evals.
- When docs are unclear or possibly stale, **run small throwaway spikes** (install the package, call the API, inspect the streamed events) to confirm behavior before relying on it.
- Run research threads in parallel (e.g. research subagents per direction) if that is faster.
- Research can continue in phases 2 and 3 whenever a design or implementation question comes up. Record new findings in the research doc.

Directions:

**A. The framework (verify current APIs; the library moves fast)**
- Deep Agents docs and repo (`docs.langchain.com/oss/python/deepagents`, `github.com/langchain-ai/deepagents`): `create_deep_agent` parameters, `SubAgent`/`CompiledSubAgent`, **dynamic subagents** (June 2026), skills, backends (`StateBackend`, `StoreBackend`, `FilesystemBackend`, `CompositeBackend`, sandbox backends, permissions), memory (`AGENTS.md`), `interrupt_on`, summarization/offloading, typed event streams.
- LangGraph: `StateGraph`, conditional edges, `Send` fan-out, subgraphs, `interrupt`/`Command` resume, checkpointers (SQLite), `Store` with namespaces/semantic search, streaming modes (`updates`, `messages`, `custom`, subgraph streaming), time travel/replay.
- LangChain examples: `open_deep_research`, `deep-agents-ui`, `agent-chat-ui`, LangGraph supervisor/swarm patterns, `langmem` (memory extraction/consolidation), `agentevals` (trajectory evaluation), LangSmith tracing and evals.
- OpenAI: `gpt-5.6-luna`, the Responses API, the OpenAI/LangChain integration, structured outputs, tool calling, streaming, reasoning controls, usage/cached-token reporting, retries and prompt caching. Also inspect the Codex SDK as a **future agent-runtime adapter**, and document where its thread/run/event semantics differ from a LangChain chat-model interface. Start with the official docs: `https://developers.openai.com/api/docs/models/gpt-5.6-luna` and `https://developers.openai.com/codex/sdk`.

**B. Multi-agent design: how many agents, which roles**
- Anthropic "How we built our multi-agent research system" and "Building effective agents"; OpenAI "A practical guide to building agents"; Microsoft Magentic-One (orchestrator + ledger); MetaGPT (SOP-driven roles); blackboard architectures; supervisor vs swarm vs hierarchical; when a deterministic workflow should wrap an LLM agent (compliance gates).
- Look for explicit guidance on agent count vs coordination cost, context isolation, and parallelism.

**C. Domain implementations on GitHub and the web**
- Search: "chargeback agent", "dispute resolution agent langgraph", "credit card dispute llm", "fraud investigation agent", "AML investigation copilot", "claims adjudication multi-agent", "KYC agent langgraph", "financial compliance agent graph".
- Cloud reference architectures: AWS / Google Cloud / Azure blogs on agentic dispute resolution, fraud investigation, claims processing.
- Vendors' published workflows: Visa Dispute Intelligence / Doc Analyzer, Quavo ARIA, Pega Smart Dispute agentic automation, Stripe Smart Disputes. Extract decision logic, not marketing.
- Papers: FIA (arXiv 2506.11635, LLM fraud investigation with code execution), ClaimPilot (multi-agent claims adjudication with deterministic policy evaluation and mandatory human review — **we replace that human step with the automated review panel**; study what the human step was catching), τ-bench / τ²-bench (policy-following agents, pass^k), RIRAG/ObliQA (regulatory retrieval).

**D. Memory architectures**
- Zep / **Graphiti** (temporal knowledge graph with validity intervals, very relevant to our versioned policies and time-bounded merchant patterns), Letta/MemGPT, Mem0, A-MEM, Generative Agents (reflection), Cognee, LangMem; consolidation, decay and conflict-resolution strategies; GraphRAG / LightRAG for policy-plus-entity retrieval.

**E. Reasoning and reliability techniques**
- Plan-and-execute with re-planning; Reflexion / self-refine; verifier-critic loops; multi-agent debate / adversarial review; CodeAct (code as actions) and smolagents; structured outputs; confidence calibration; tool-grounded arithmetic.

**F. Transparency and frontend-ready trajectories** (this shapes the event schema, so go deep)
- Protocols and streams: AG-UI protocol (agent ↔ UI events), LangGraph streaming (`updates`, `messages`, `custom`, `debug`, subgraph streaming), Deep Agents typed event streams, LangChain agent middleware hooks around model and tool calls, LangGraph checkpoint history and time travel.
- Tracing and observability tools and their data models: LangSmith run trees, Langfuse, Arize Phoenix / OpenInference, OpenLLMetry, W&B Weave, AgentOps, OpenTelemetry GenAI semantic conventions (agent, tool and retrieval spans). How do they represent nested agent/subagent/tool spans, retrieval results, memory reads and writes, token cost and errors?
- UIs: deep-agents-ui, agent-chat-ui, LangGraph Studio, and trace viewers. What views do they offer (timeline, span tree, state diff, replay), and what event data does each view need?
- Audit and explainability expectations in financial services: model risk management (SR 11-7), EU AI Act record-keeping/logging, CFPB/Reg B adverse-action explanations, dispute audit trails. What must a regulator or QA reviewer be able to reconstruct from the log?
- How do others model a replayable event log with plans, tool calls, subagent spans, memory diffs, decision provenance and state snapshots? How do they keep it complete without scattering logging code everywhere?

**G. Safety for this domain**
- Prompt injection via merchant-supplied documents (evidence packets are adversarial input); least-privilege tools; fairness guardrails (ECOA/Reg B proxies); PII handling.

**H. Anything else that matters**
- Anything state-of-the-art that would make the system more robust, more explainable or more impressive to a technical and financial-services audience (new agent patterns, eval methods, memory systems, releases from the last few months). Bring it back with evidence.

**Phase 1 deliverable:** `docs/design/04-agent-architecture-research.md` with 3–5 candidate architectures (more if research turns them up) (e.g. deterministic LangGraph workflow wrapping one Deep Agent; supervisor Deep Agent with many specialists; hybrid with a verifier gate and an offline memory curator; dynamic-subagent fan-out), each with pros/cons against **our** cases, recommended agent count and roles, what to borrow from each source, a recommended combination, and a **transparency section** (how the recommended stack captures every step, what the frontend can show, gaps). Then **stop and show me the summary.**

---

## 5. Design and implementation requirements

### Stack
- Python 3.11+ managed with `uv`; `deepagents`, `langgraph`, `langchain` provider packages, `pydantic`, `sqlite-vec`, LadybugDB (verify package name and status; NetworkX fallback), `networkx`.
- Model backbone: default every role to **OpenAI `gpt-5.6-luna` via the Responses API** for the first implementation. Central configuration may override the model per role, but do not introduce tiering until eval evidence shows a quality, latency or cost need. Never silently fall back to a different model. Verify the exact model ID, supported capabilities and request options against current official docs.
- Local only, no servers required (SQLite files). Optional LangSmith tracing if a key is present.
- A thin API later for the frontend (e.g. FastAPI with server-sent events streaming trajectory events). Design the event schema now; the API can be minimal.

### Extensibility (things will grow and change)
- **Agents, subagents, routes, skills, tools and scenarios are registries loaded from config or files**, e.g. `agents/*.yaml` (name, description, prompt, tools, model, skills), `routes.yaml` (conditions → graph path / subagents / skills / budget), `skills/<name>/SKILL.md`, a tool registry via a decorator, `scenarios/` pointing at a dataset directory. Adding an agent or skill should be a new file, not a refactor.
- The **data may change**: access the dataset through a small data-access layer keyed by the paths in `manifest.json`; the framework must run against a regenerated or different scenario dataset with no code changes.
- Route logic should support rules (deterministic, auditable) **and** LLM classification with a confidence threshold. The first matching route wins and is recorded.

### Replaceable model and agent-runtime boundary (non-negotiable)
- Keep the dispute domain core (state, tools, policies, memory, governance, decisions, events and evals) independent of model/provider SDK types. Provider request/response objects must not cross the adapter boundary.
- Define two deliberately small boundaries because a LangChain chat model and the Codex SDK operate at different levels:
  1. a **model gateway** used by the current Deep Agents/LangGraph runtime, accepting provider-neutral messages, tools, structured-output schema, reasoning/latency budget and cancellation, and yielding normalized text/tool-call/usage/stream events;
  2. an **agent-runtime interface** for start/run-or-stream/resume/cancel so a future Codex SDK runtime can replace the current Deep Agents/LangGraph runtime without changing the domain core.
- Implement only what is needed now: an OpenAI Responses-backed model adapter for `gpt-5.6-luna`, a Deep Agents/LangGraph runtime adapter, and deterministic fake adapters for tests. Document—not implement unless justified by phase-1 findings—the future Codex SDK adapter. Avoid a broad class hierarchy or a lowest-common-denominator wrapper.
- Load provider, model ID and role overrides from one validated config surface (for example `config/models.yaml` plus environment-variable overrides). Resolve it once at startup and attach the immutable resolved config snapshot to every run. A model/provider swap must not require edits to graph nodes, agents, prompts, tools or evaluators.
- Make capabilities explicit (`structured_output`, `tool_calling`, `streaming`, `vision`, `reasoning_controls`, `usage_reporting`, `prompt_caching`, thread resume). Validate required capabilities at startup and fail clearly; never silently drop an option or emulate an unsupported safety-critical capability.
- Normalize only semantics the application consumes: messages/content blocks, tool definitions and calls, structured outputs, finish/error categories, usage/cached tokens, latency, provider request ID and stream events. Preserve provider-specific metadata in an opaque namespaced field for debugging.
- Centralize timeouts, bounded retries/backoff, rate-limit handling, concurrency limits and cancellation in the adapter. Every attempt and fallback decision must use the same trajectory instrumentation as other model calls. Do not retry non-retryable authentication, validation or permission errors.
- Credentials come only from environment/secret storage (`OPENAI_API_KEY` for the initial adapter), are validated at startup, and must never appear in config snapshots, prompts, events, blobs, exceptions or replay output.
- Add a provider contract test suite. The same scripted tool-call and structured-output scenarios must pass against the fake adapter and the OpenAI adapter (real API smoke test opt-in), and the L1 end-to-end test must run without domain-code changes when the configured model adapter changes. Add an architecture test that prevents imports of concrete provider SDKs outside adapter modules.

### Transparency (non-negotiable: a frontend will display every trajectory)

For any run, the frontend must be able to show **exactly what happened, in order, and why**: which node ran, which agent or subagent acted, which tool it called with what arguments and what came back, which memory it read or wrote (which store, query, filters and records), which skill it loaded, what it computed, what it decided and on what evidence. **No silent steps.**

**Event envelope** (one versioned schema, defined as Pydantic models and exported as JSON Schema for the frontend):
`schema_version, event_id, run_id, case_id, seq, span_id, parent_span_id, ts_wall, ts_virtual, actor {kind: graph_node | agent | subagent | tool | memory | sandbox | harness | evaluator, name}, type, summary (one human-readable line for the timeline), payload, refs (source IDs: txn/evidence/comm IDs, doc_id@version, memory IDs, graph node IDs, checkpoint ID), resolved_runtime/model/provider/adapter versions, tokens/cost/latency, redactions`.

**What must be logged (minimum; extend as the design needs):**

| Step | Event types | Required payload |
|---|---|---|
| Graph | `node_entered`, `node_exited`, `edge_taken` | node, state diff summary, edge from → to, the condition evaluated and its value, back-edge flag, fan-out branch ID |
| Routing | `route_decision` | candidate routes considered, rule matched or LLM classification with confidence, chosen route, depth (L1–L4), budget, selected subagents and skills, rationale; portfolio ranking with scores for Q01 |
| Planning | `plan_created`, `plan_updated`, `todo_updated` | full plan, diff vs the previous plan, reason for the change (e.g. the verifier check or new fact that triggered it) |
| Model calls | `llm_call_started`, `llm_stream_event`, `llm_call`, `llm_call_failed` | actor, provider and adapter, requested and resolved model ID, normalized request/options and prompt/messages (blob ref), tool/structured-output schema hashes, response/output (blob ref), provider request ID, rationale or reasoning summary where exposed, tokens in/out/reasoning/cached, cost, latency, stop reason, attempt/retry classification; `llm_call` is the terminal success event retained for evaluator compatibility; never log hidden chain-of-thought or secrets |
| Tools | `tool_call`, `tool_result` | tool name and version, why it was chosen (a short `rationale` from the calling agent), validated arguments, result (inline or blob ref), duration, errors, retries, permission denials |
| Subagents | `subagent_started`, `subagent_finished` | parent → child, task brief, context and files handed over, tools and skills available, model, result returned, tokens/cost; nested through `parent_span_id` (including dynamic fan-out) |
| Skills | `skill_loaded` | skill name, path/version, why (route selection or agent choice) |
| Memory reads | `memory_read`, `retrieval`, `sql_query`, `graph_query`, `memory_verified`, `memory_rejected` | **which store** (SQLite system of record, graph, vector/FTS, case file, LangGraph Store, checkpointer), namespace/table, query text / SQL / Cypher, filters (`as_of`, validity window, status, scope, entity, confidence), the rule that set `as_of`, results with IDs, versions and scores, **which results were used vs discarded and why**, then verification against evidence (the confirming or contradicting evidence ID) |
| Memory writes | `memory_write`, `memory_supersede`, `memory_retract`, `memory_consolidate`, `memory_expire`, `memory_purge`, `graph_write`, `write_rejected`, `memory_write_skipped` | store, target ID, before → after diff, `source_refs`, validity, confidence, each write-gate check with pass/fail; rejected writes with the failed check; **deliberate decisions not to write**, with the reason, so selective write is visible |
| Working memory | `case_file_updated`, `hypothesis_updated` | file path, diff (facts with sources, hypotheses board, open questions, deadlines, evidence matrix) |
| Computation | `computation` | code, inputs, helper used, stdout/stderr, output, runtime, errors |
| Evidence and harness | `evidence_requested`, `evidence_arrived`, `clock_advanced`, `wait_suspended`, `wait_resumed`, `persona_message`, `persona_reply`, `untrusted_content_flagged` | awaited event, deadline and latest safe decision time, checkpoint ID, virtual-clock before → after, message text (redacted), suspected injection and how it was neutralized |
| Findings | `contradiction_detected`, `evidence_added` | the conflicting facts and their sources, impact on hypotheses |
| Governance | `review_panel_started`, `panel_position`, `adjudication`, `verifier_check`, `guardrail_check`, `conservative_default_applied`, `automated_action` | why the panel was required, each advocate's position, confidence, key evidence and flip fact, adjudicator reasoning; each verifier/SOP-DSP-003/004 code check with pass/fail and details; allowed-action list check for every automated action |
| Decision | `decision_recorded` | every decision-record field, **provenance for each field** (event `seq`s and source IDs), cardholder outcome vs network action, confidence, counterfactual flip fact |
| Loop control | `budget_update`, `no_progress_detected`, `replan_limit_reached`, `termination` | used vs limit (tool calls, tokens, wall-clock, re-plans), termination reason and final state |
| Failures | `error`, `retry`, `fallback`, `access_denied` | what failed, what was tried next (e.g. LadybugDB → NetworkX), blocked access attempts (e.g. `ground_truth/**`) |

**How to capture it:**
- **One instrumentation point, not scattered logging.** Wrap model and tool calls centrally (research the current Deep Agents / LangChain middleware hooks, LangGraph callbacks and stream modes, `get_stream_writer`), and have the memory, graph, vector, sandbox and harness access layers emit through a single `emit()` function. It should be impossible to call a tool or touch a store without producing an event.
- Large payloads (prompts, documents, query results) go to a content-addressed `run_blobs` table referenced by hash, so events stay small and nothing is lost.
- Persist to SQLite (`run_events`, `run_blobs`) **and** stream live (SSE later). Decide in phase 1 whether to align with AG-UI and/or map to OpenTelemetry GenAI spans for export.
- **Replayable:** reconstruct the case file, hypothesis board, memory state, graph hypotheses and virtual clock at any `seq`; link events to LangGraph checkpoint IDs; recorded model outputs allow deterministic re-runs and re-scoring.
- **Design for the frontend views now:** run timeline; nested span tree (agents → subagents → tools); tool-call inspector; memory inspector (reads with filters and used/discarded results, writes with before/after diffs, rejected and skipped writes); case-file and hypothesis-board diffs over time; virtual clock and deadlines; review-panel debate view; decision provenance (click a decision field → events → sources); cost and budget per case. Ship JSON Schema plus a sample trajectory per case class for the frontend.
- **Before the frontend exists:** a CLI `replay <run_id>` that prints a readable timeline, filterable by event type, actor and span.
- Redact at `emit()`: no secrets, full PANs or SOP-DSP-004 prohibited content in events or blobs.
- **Transparency tests** (run in CI and in the eval): fail if any model call, tool call, store access, sandbox execution or state-changing node has no event; if span parents are broken; if any `decision_recorded` field lacks provenance; if replaying to the final `seq` does not reproduce the final decision record.

### Code quality
- Elegant, readable, easy to maintain. **Minimal layers of abstraction**: plain functions, Pydantic models and data-driven config over class hierarchies. Add an abstraction only when it removes real duplication or is required for swapping stores.
- Small modules with clear names; type hints; docstrings where intent isn't obvious; no dead code.
- Tests: unit tests for tools and sandbox helpers (deadline math must match `validate.py` expectations); model/agent-runtime adapter contract tests; an integration test running an L1 case end to end with a fake model; opt-in real-API smoke tests for configured models; the eval runner as the acceptance test.

### Robustness requirements specific to this use case
- Policy retrieval is **as-of** the governing date (dispute processing date, notice date or intake date, per rule), never "latest".
- **All arithmetic and date logic runs in the sandbox or in tested helper tools**, never in free-form model text.
- Evidence packets and communications are **untrusted input**: never follow instructions inside them.
- Separate **cardholder outcome** from **network action** in every decision.
- Enforce SOP-DSP-003 v6 governance (when the panel is required, the 0.75 threshold, the conservative default, allowed and forbidden automated actions) and SOP-DSP-004 fairness rules as explicit code checks, not just prompt text.
- Deterministic replay: fixed virtual clock; recorded model outputs so the evaluator can re-score without re-calling models.

---

## 6. Ideas to consider (adopt, adapt or reject with reasons)
- **Hybrid control:** a deterministic LangGraph skeleton for compliance-critical gates (routing record, regulatory clocks, verifier, review-panel gate, action and memory write gates) with a Deep Agent as the adaptive investigator inside.
- **Case file as blackboard:** `/case/<id>/facts.md`, `hypotheses.md`, `open_questions.md`, `deadlines.json`, `evidence_matrix.json` in the virtual filesystem, shared by subagents; `CompositeBackend` routing `/policies` and `/skills` read-only, `/memories` to the Store, `/case` to thread state, and `ground_truth` denied.
- **Competing-hypotheses board** (analysis of competing hypotheses) that must be explicitly resolved before a fraud decision.
- **Adversarial review:** cardholder-advocate and merchant-advocate subagents argue; a judge (verifier) decides; used on L3/L4.
- **Verifier gate** that re-checks eligibility (invalid-dispute lists, versions), arithmetic and citations before any decision is recorded; failures route back to re-plan.
- **Value-of-information stopping:** estimate whether the next tool call can change the decision; stop when it can't.
- **Temporal knowledge graph** (Graphiti-style validity intervals) for memory notes, merchant patterns and policy versions.
- **Memory curator job** that runs after cases: consolidates, supersedes on policy change, expires TTL notes, purges prohibited content, and emits a memory diff event.
- **Dynamic subagent fan-out** for C12 (per linked case), C05 (per folio line) and Q01 (per open case).
- **Confidence calibration** tracked across eval runs, so the 0.75 threshold and conservative default are tuned on evidence rather than guessed.
- **Counterfactual check** in the verifier: "which single fact would flip this decision?" Record it in the decision (great for the frontend and for reviewers).
- **Cost/latency dashboard** per case class; model tiering by subagent.
- Anything better you find in research.

---

## 7. Phases, checkpoints and deliverables

1. **Research** → `docs/design/04-agent-architecture-research.md`. **Stop and show me.**
2. **Architecture design** → `docs/design/05-agent-architecture.md`: the graph diagram (Mermaid), agent/subagent roster with responsibilities, routes, tool catalog with schemas, skills, memory read/write/consolidation flows, harness (virtual clock, persona simulator, scheduled follow-ups), **model-gateway and agent-runtime boundaries** (normalized contracts, capability matrix, resolved-config example, failure/retry semantics, OpenAI/Deep Agents adapters now and Codex SDK adapter seam later), **trajectory event catalog** (every event type with an example payload, the instrumentation points that emit it, and the frontend view that consumes it), termination conditions, evaluation plan, extension guide ("add an agent / skill / route / scenario / model provider / runtime"), and the capability → case → component mapping. **Stop and show me.**
3. **Implementation**, incrementally:
   - vertical slice: validated model config + OpenAI Responses model adapter (`gpt-5.6-luna`) + fake adapter and provider contract tests + Deep Agents/LangGraph runtime adapter + data access + tools + router + one Deep Agent + **full trajectory capture from day one** (central instrumentation, `run_events`/`run_blobs`, `replay` CLI, transparency tests) + eval on **C02** (L1 stop) and **C04** (sandbox + simulated cardholder). Every later increment must keep the transparency tests green;
   - add policy/vector retrieval with as-of filtering, verifier and re-plan (**C06**, **C03**);
   - add graph memory and specialists (**C08**, **C12/C12b**, **C11**);
   - add the automated review panel, suspend/resume on external events (**C10**, **C11**, **C13**) and the memory curator (**C19**, MEM notes);
   - add the remaining cases and the **Q01** portfolio router;
   - full eval run with pass^k and trajectory completeness; results report `docs/design/06-eval-results.md`, including one fully annotated sample trajectory.

Keep `README.md` updated with how to run the agent, the eval, and how to extend it. Commit only when I ask.

Ask me questions only when you're truly blocked by a decision that's mine to make. Otherwise make a sensible call, note it, and proceed.
