# CatcherAI agent architecture research

**Status:** Phase 1 recommendation  
**Research date:** 13 September 2026  
**Scope:** architecture research for a fully automated, replayable card-dispute investigation system built first on Deep Agents and LangGraph

## Executive conclusion

CatcherAI should use a **hybrid deterministic workflow with a bounded agentic investigation core**:

1. A LangGraph state machine owns intake, routing, clocks, budgets, checkpoints, verifier gates, automated governance, execution, memory write gates, and termination.
2. One Deep Agent is the lead investigator. It maintains a typed case file and chooses the next evidence-gathering action within the route's budget.
3. Specialists are invoked only when a case requires their isolated context or tools. Independent work is fanned out in parallel for folio lines (C05), linked cases (C12/C12b), and the portfolio queue (Q01); ordinary L1/L2 cases do not pay this coordination cost.
4. Policy eligibility, date arithmetic, monetary calculations, confidence-threshold handling, allowed actions, fairness checks, and final record completeness are deterministic code, never free-form model judgments.
5. High-impact or contested decisions go to the automated SOP-DSP-003 v6 panel: independent cardholder and issuer/merchant advocates, an adjudicator, and a verifier. Below 0.75 confidence the system applies the specified conservative cardholder-favorable default. There is no human approval path.
6. An application-owned, append-only event ledger is the audit source of truth. LangGraph checkpoints, LangSmith/OpenTelemetry traces, and AG-UI events are projections or operational aids, not substitutes for it.
7. The dispute core depends on two narrow, provider-neutral seams: a model gateway used by the initial Deep Agents runtime, and an agent-runtime interface. The OpenAI Responses API is the first model implementation; a future Codex SDK integration belongs at the runtime seam because Codex exposes threads, turns, items, resume, and cancellation rather than just chat-model calls.

This combination is less fashionable than a free-form swarm and considerably more defensible. Research repeatedly shows that multi-agent breadth helps when work is genuinely parallel, but it increases token use and coordination failure. In a regulated decision flow, deterministic state transitions and independently checkable artifacts contribute more reliability than adding agents.[^anthropic-effective][^anthropic-research][^claimpilot]

## Research method and evidence standard

The research combined:

- the repository foundation, policy corpus, skills, case catalog, data dictionary, manifest, and generator reference implementations, read in the requested order;
- current official product documentation for OpenAI, LangChain, Deep Agents, LangGraph, AG-UI, and observability standards;
- papers and primary project repositories for multi-agent design, memory, retrieval, evaluation, and domain analogues;
- source inspection of Deep Agents, Codex SDK event types, and representative claims/dispute repositories;
- small source-level/API checks where documentation alone left ambiguity.

The agent did **not** read `data/generated/ground_truth/**` or `data/generated/simulation/**`. Context7 was not available in this environment, so current official documentation and source repositories were used directly instead.

Claims below are labelled as one of:

- **Proven interface:** verified in current official documentation or source.
- **Evaluated practice:** supported by a described benchmark or study; external validity may still be limited.
- **Pattern evidence:** an inspectable implementation that demonstrates a design, not its production efficacy.
- **Marketing claim:** a vendor or repository assertion without independent validation.

## Findings that materially constrain the design

### 1. Deterministic workflows and agents solve different parts of this problem

Anthropic distinguishes workflows, whose paths are predefined in code, from agents, whose control flow is model-directed, and recommends starting with the simplest design that meets the need.[^anthropic-effective] OpenAI's agent guide similarly distinguishes a manager that calls specialists from decentralized handoffs.[^openai-agents-guide] CatcherAI needs both:

- clocks, eligibility, governance, allowed actions, persistence, and termination must be predictable;
- evidence pursuit, contradiction discovery, hypothesis revision, and value-of-information decisions benefit from adaptive reasoning.

A single unconstrained agent cannot prove that every mandatory gate ran. A fully deterministic rules engine cannot handle C05, C06, C10–C13, or novel evidence. The appropriate boundary is therefore a deterministic graph around an agentic investigator.

Magentic-One reinforces this split. Its orchestrator keeps both a task ledger and a progress ledger and replans when progress stalls.[^magentic] For CatcherAI, those ledgers should become typed case state—facts, hypotheses, open questions, deadlines, plan, budgets, and progress—not free-form orchestration chat.

### 2. More agents are useful only when decomposition is real

Anthropic's multi-agent research system reports a large improvement on its breadth-first research evaluation, but about 15 times the tokens of ordinary chat. It identifies parallelizable, high-value, context-heavy research as a good fit and tightly coupled work as a poor fit.[^anthropic-research] Later Anthropic experiments also found that role-labelled hierarchies did not automatically improve long-horizon software work, and that identical agents can converge on correlated mistakes.[^anthropic-multiagent-study] MetaGPT's useful contribution is narrower than its software-company metaphor: SOP-shaped roles exchange standardized artifacts rather than unconstrained chat. CatcherAI borrows that contract discipline, not the domain-specific role hierarchy.[^metagpt]

The consequence for CatcherAI is selective concurrency:

- fan out independent folio lines, linked cases, portfolio cases, and opposing panel positions;
- keep route selection, state ownership, evidence merge, policy gates, and final decision authority centralized;
- require structured specialist returns with source IDs, not conversational consensus;
- cap fan-out, tokens, tool calls, wall time, and re-plans by route.

The current `open_deep_research` implementation is useful source-level pattern evidence: its supervisor dispatches bounded research units concurrently, each researcher loops through tools, and reducers merge notes before final synthesis.[^open-deep-research] CatcherAI should copy the bounded fan-out and reducer pattern, while replacing open-ended research state with case-specific typed artifacts. LangChain's supervisor package now recommends direct tool-based supervision for most new work, while swarm handoffs maintain an `active_agent` and move authority between peers.[^langgraph-supervisor][^langgraph-swarm] The latter is a poor match for a regulated case with one authoritative owner.

Deep Agents now offers three relevant modes. Synchronous `SubAgent`/`CompiledSubAgent` calls isolate context but block until completion. Async subagents run on separate threads and support status, update, and cancellation. Beta dynamic subagents use QuickJS interpreter middleware and an interpreter-level `task()` API to dispatch configured subagents through loops and parallel batches.[^deepagents-subagents][^deepagents-async][^deepagents-dynamic] “Dynamic” does not mean inventing arbitrary trusted roles at runtime: the dispatcher selects registered subagents, optionally with a dynamic response schema. Dynamic fan-out is promising for C05, C12, and Q01, but its beta surface and interpreter dependency make it unsuitable as the sole control plane. LangGraph `Send` fan-out is the more stable default; dynamic subagents can be evaluated behind a registry adapter.

### 3. Framework checkpoints and traces are not an audit ledger

LangGraph can stream state updates, messages, custom events, checkpoints, tasks, debug data, and nested subgraph namespaces.[^langgraph-streaming] Its newer typed v3 event surface exposes projections for messages, values, tool calls, usage, output, and subgraphs; Deep Agents adds per-delegation subagent streams with nested messages, tools, status, and output.[^langchain-event-streaming][^deepagents-event-streaming] These projections are valuable inputs to the instrumentation spine, but the raw protocol stream is still required when exact interleaving matters. Checkpointers support resume, history, and time travel.[^langgraph-persistence][^langgraph-time-travel] However, replaying from a checkpoint re-executes later model and external calls. A checkpoint is a state snapshot, not a deterministic record of why that state arose.

Source inspection confirms the primitives needed for the graph: typed `StateGraph` reducers for concurrent branches, conditional edges, `Send` for map/fan-out, and `Command` for update/resume/goto.[^langgraph-source] LangGraph's `interrupt()` restarts the containing node from its beginning on resume. CatcherAI may use that mechanism only to implement an external-event suspension; any side effect before suspension must be idempotent or moved into a completed prior node. Framework human-interrupt middleware is not part of the product graph.

LangSmith represents nested runs with trace, parent, ordering, inputs, outputs, errors, timing, and usage metadata, and Studio can visualize graph execution and state.[^langsmith-run][^langsmith-studio] It is excellent optional operational tooling, but cloud retention, masking configuration, and non-audit semantics mean CatcherAI cannot make it the system of record.

The system therefore needs an unsampled application ledger that records normalized calls, results, state diffs, source references, decisions, and checkpoints. Recorded model outputs—not merely checkpointed state—provide deterministic re-scoring and replay.

### 4. Current Deep Agents APIs are useful but not a security boundary

**Proven interface.** Source at Deep Agents commit `45b8592` (8 September 2026) shows `create_deep_agent(model, tools, *, system_prompt, middleware, subagents, skills, memory, permissions, backend, interrupt_on, response_format, state_schema, context_schema, checkpointer, store, debug, name, cache)`; it returns a compiled LangGraph runnable. Backends include state, store, filesystem/local shell, and composite routing. Skills follow Agent Skills `SKILL.md` progressive disclosure.[^deepagents-source][^deepagents-customization][^deepagents-skills]

**Implementation validation (14 September 2026).** A local spike against pinned `deepagents`
0.5.9 confirmed declarative `SubAgent` registration, multiple `task` calls in one model turn, async
tool-call middleware around each delegation, and nested model/tool results through the neutral
gateway. This is sufficient for C12's per-case fan-out without adopting the beta interpreter-based
dynamic-subagents surface. A second spike against `ladybug` 0.20.4 confirmed embedded `Database`
and `Connection`, parameterized Cypher, and fast bulk projection through `COPY`; per-row loading was
too slow for the 25.9k-node/49.3k-edge fixture and was rejected.

Custom subagents do not inherit skills by default; compiled subagents must supply compatible message state; permission inheritance differs for declarative, compiled, and remote subagents. `memory` loads configured `AGENTS.md` files into context, while summarization can offload older content to a backend. These conveniences must not be confused with CatcherAI's governed memory lifecycle or canonical event store.

Deep Agents filesystem permissions apply to built-in filesystem tools. The documentation explicitly says they do not govern custom tools or MCP tools, and sandbox execution has separate controls.[^deepagents-permissions] Consequently:

- denying `ground_truth/**` and `simulation/**` must happen in the data-access router and sandbox mount, not only in a prompt or Deep Agents permission rule;
- custom tools need their own capability checks and validated Pydantic inputs;
- `/policies` and `/skills` can be mounted read-only, `/case` can map to thread state, and memory writes must pass a domain write gate;
- the local compute sandbox must see curated read-only datasets, not the repository root.

### 5. The initial OpenAI integration should not leak into domain code

**Proven interface.** The official model page identifies `gpt-5.6-luna` as the exact model ID and documents Responses API support, function calling, structured outputs, streaming, image input, reasoning controls, usage reporting, and a 1.05-million-token context window.[^openai-luna] The Responses API exposes response IDs, status/error categories, usage including cached and reasoning tokens, JSON-schema structured output, tool calls, and typed stream events.[^openai-responses][^openai-function-calling][^openai-structured][^openai-streaming]

The model gateway should normalize only those consumed semantics: messages/content blocks, tools and calls, schemas, output, finish/error classes, usage, latency, provider request ID, and stream events. It must centralize capability validation, timeouts, retry classification, cancellation, rate limiting, and redaction. Provider request objects remain inside the adapter.

The Codex SDK is structurally different. Its official SDK exposes long-lived threads, runs/turns, streamed item events, resume/fork/read/compact, steering, interruption, and sandbox controls.[^codex-sdk] Source types include lifecycle events and items such as agent messages, reasoning summaries, command execution, file changes, MCP tool calls, web search, todos, and errors.[^codex-source] That is an **agent runtime**, not just a chat model. A future Codex adapter should implement `start`, `run_or_stream`, `resume`, and `cancel` at the runtime boundary and map its item tree into CatcherAI events. It should not be forced through a LangChain `BaseChatModel` facade.

### 6. Memory must be temporal, scoped, and distrustful of itself

Graphiti's most relevant idea is separating event/ingestion time from fact-validity time while retaining episode provenance and supporting hybrid semantic, keyword, and graph retrieval.[^graphiti] CatcherAI should borrow the temporal model, not the hosted stack: every policy, relationship, and memory note needs source, `valid_from`, `valid_to`, status, and observation time.

Letta/MemGPT separates always-visible working context from archival memory; LangMem supports semantic, episodic, and procedural memory plus background consolidation.[^memgpt][^langmem] A-MEM and Generative Agents illustrate linked memories and reflection, but model-authored rewriting raises provenance risk in a financial system.[^amem][^generative-agents]

RIRAG/ObliQA provides domain-specific evidence that regulatory retrieval benefits from combining traditional and neural retrieval before grounded generation, although its evaluation is question answering rather than action-taking.[^rirag] GraphRAG's community summaries are useful for corpus-wide themes, while LightRAG emphasizes incremental entity/relation updates; neither replaces governing-date filters or source-of-truth checks for policy.[^graphrag][^lightrag]

The repository's seeded memory cases demand stronger rules than generic memory libraries provide:

- retrieve current, confidence-qualified notes as leads only;
- verify a retrieved note against case evidence before using it;
- exclude superseded or retracted notes from current retrieval;
- log used and discarded results;
- gate all writes for sources, validity, confidence, prohibited content, and duplication;
- support explicit skip, reject, supersede, retract, consolidate, expire, and purge events;
- keep policy truth in the versioned corpus, never in mutable memory summaries.

SQLite remains the system of record and FTS/vector host. LadybugDB is the current name of the Kùzu fork; the project documents `pip install ladybug` and embedded `Database`, `Connection`, and `AsyncConnection` APIs.[^ladybug][^ladybug-python] Its native vector extension is separate from sqlite-vec; no supported direct bridge was found.[^ladybug-vector][^sqlite-vec] CatcherAI should therefore use sqlite-vec for the SQLite hybrid-retrieval path and LadybugDB for Cypher graph traversal, with explicit ETL at load time where embeddings are needed in both. Because the rename and packaging are recent, keep the proposed small graph interface and a tested NetworkX fallback. A fallback must be emitted as an event, not silently selected.

### 7. Tool-grounded computation and state-based evaluation are mandatory

FIA demonstrates a fraud-investigation assistant that plans, gathers evidence, and executes code across hundreds of evaluations, but it remains analyst assistance rather than proof of safe autonomous adjudication.[^fia] CodeAct and smolagents support executable code as an action for checkable arithmetic; smolagents also warns that unrestricted code execution is dangerous.[^codeact][^smolagents]

For CatcherAI, business days, billing cycles, pro-rata, FX, time zones, and CE 3.0 day counts belong in tested helpers executed through a restricted sandbox. Both code and output are events. The model proposes or selects a calculation; code owns the result. macOS builds of Python's `sqlite3` may lack loadable-extension support, so startup capability checks must verify sqlite-vec loading and fail clearly rather than silently degrading to a different retrieval method.[^sqlite-load-extension]

τ-bench evaluates policy-following agents through final environment state and shows that pass@1 hides substantial unreliability; its pass^k metric measures the probability that all repeated runs succeed.[^taubench] τ²-bench adds a simulated user that can act in the shared environment, making it a strong pattern for the persona harness and external-event coordination.[^tau2] CatcherAI should score final records, side effects, prohibited actions, required capability events, trajectory completeness, and pass^k—not prose quality alone. LangChain's `agentevals` can supplement those checks with strict, unordered, subset, and superset tool-trajectory matching, but CatcherAI's source-ID and capability semantics require its own deterministic evaluator.[^agentevals]

### 8. Domain implementations support the pattern but not autonomous trust

ClaimPilot is the strongest close analogue found: strict status transitions, file-backed shared state, append-only audit logs, verify-and-retry wrappers, deterministic adjudication, and independently computed outcomes. Its evaluation reports 97.3% workflow completion and 90.0% overall adjudication accuracy, and it attributes an important improvement to fixing inter-agent contract ambiguity.[^claimpilot] It ends with human approval; CatcherAI must replace that step with its coded automated panel and conservative default.

AWS claims, Databricks KYC/AML, and open-source compliance demos show supervisor/specialist graphs, structured returns, checkpointing, policy retrieval, and deterministic risk gates.[^aws-claims][^aws-claims-eks][^databricks-kyc] They are useful pattern evidence. Their “production-ready,” accuracy, latency, or cost claims are not independent validation and should not determine this architecture.

Visa, Pega, Quavo, and Stripe public materials confirm the industry's emphasis on automated document structuring, reason/condition selection, confidence-based routing, pre-dispute resolution, and evidence assembly.[^visa-ai][^pega][^quavo][^stripe-disputes] These are product descriptions, not transparent technical evaluations. CatcherAI should borrow the workflow primitives, not their evidentiary claims.

## Candidate architectures

### Candidate A — deterministic LangGraph pipeline with one Deep Agent node

```text
intake -> route -> calculate deadlines -> investigate(agent) -> verify -> decide -> act -> memory
```

**Description.** A fixed graph owns almost all flow. One Deep Agent can use all investigative tools but does not delegate.

**Strengths**

- Easiest architecture to reason about, test, replay, and budget.
- Excellent L1 behavior: C02 can stop after a small number of deterministic checks.
- Natural home for versioned policy retrieval, clock math, action gates, and explicit termination.
- Lowest coordination cost and smallest event surface.

**Weaknesses**

- The lead context becomes crowded by C05 folio detail, C12 linked cases, and Q01 portfolio triage.
- Specialist prompts and tool permissions are harder to isolate.
- Does not meet cases where subagents are a primary capability.
- Parallel evidence analysis is awkward unless implemented outside Deep Agents.

**Verdict.** Use its deterministic skeleton, not its single-agent limitation.

### Candidate B — Deep Agent supervisor with a fixed specialist team

```text
supervisor -> {policy, ledger, evidence, graph/security, liaison, research} -> supervisor
```

**Description.** A supervisor Deep Agent chooses specialist `task` calls and composes their results. The graph is thin.

**Strengths**

- Strong context isolation and role/tool specialization.
- Closely matches documented Deep Agents patterns.
- Extensible through agent configuration files.
- Useful on C05, C08, C10–C13, and Q01.

**Weaknesses**

- Model-directed routing can bypass compliance gates or waste calls.
- A conversational supervisor is a weak owner for clocks, retries, suspension, and termination.
- Fixed teams tempt decorative delegation and serial latency.
- Capturing every hidden state transition requires substantial wrapping anyway.

**Verdict.** Good investigation interior, insufficient control plane.

### Candidate C — hybrid compliance graph, selective specialists, and automated review (recommended)

```text
deterministic control graph
  -> route-selected Deep Agent investigator
       -> synchronous specialist for focused work
       -> bounded fan-out for independent units
  -> deterministic verifier
  -> automated adversarial panel when required
  -> action and memory gates
```

**Description.** LangGraph owns authoritative state transitions. The investigator owns adaptive evidence pursuit. Specialists return typed, source-linked findings. Deterministic checks and the automated panel own final admissibility.

**Strengths**

- Meets every mandatory capability without making every case maximally complex.
- Makes early L1 termination and L3/L4 depth explicit.
- Supports verify-to-replan back-edges and checkpointed external-event suspension.
- Keeps separate cardholder outcome and network recovery actions.
- Provides a clean runtime seam and event instrumentation choke points.
- Lets dynamic subagents mature behind a stable fan-out interface.

**Weaknesses**

- More integration work than A or B.
- Requires strict ownership rules for case state and event sequencing across branches.
- Specialist registry and graph routes must be validated together to prevent configuration drift.

**Case fit.** Best overall: C02 early stop; C03/C06 temporal retrieval and replan; C04 calculations/persona; C05 folio fan-out; C08/C11 graph and security; C10–C13 governance; C15 suspend/resume; C19 curation; Q01 portfolio fan-out.

**Verdict.** Adopt.

### Candidate D — event-sourced blackboard with peer agents

```text
agents <-> typed blackboard/event log <-> agents
```

**Description.** Specialists watch and append to a common blackboard until a stopping rule fires.

**Strengths**

- Naturally asynchronous and extensible.
- Event sourcing aligns well with replay.
- Multiple hypotheses can evolve without squeezing into one prompt.

**Weaknesses**

- Unclear authority and conflict resolution.
- High risk of duplicate calls, memory poisoning, premature consensus, and livelock.
- Difficult to guarantee an exact compliance path or bounded cost.
- A mutable free-form blackboard is not adequate evidence provenance.

**Verdict.** Borrow the typed case-file blackboard and append-only events; reject peer-to-peer control.

### Candidate E — runtime-first autonomous thread (future Codex-style runtime)

```text
domain core -> AgentRuntime -> long-lived runtime thread/items/tools
```

**Description.** A capable agent runtime owns planning, tools, files, and thread resume, with the domain core providing tools and governance callbacks.

**Strengths**

- Rich native thread/run/item lifecycle.
- Strong fit for long-running investigations and external-event resume.
- Could reduce framework-specific glue later.

**Weaknesses**

- Moving the compliance graph inside a runtime would obscure mandatory nodes and edges.
- Runtime-specific item semantics do not match a chat-model adapter.
- Current goal is Deep Agents/LangGraph; implementing two runtimes now adds risk without evaluation evidence.

**Verdict.** Preserve the seam and document event mapping; do not implement in the first release.

## Recommended combination

Adopt Candidate C, borrowing:

- Candidate A's explicit LangGraph state machine and early termination;
- Candidate B's context-isolated, tool-limited specialists;
- Candidate D's typed blackboard and event sourcing, but not its decentralized authority;
- Candidate E's runtime-neutral lifecycle boundary;
- Magentic-One's separate plan and progress ledgers;
- ClaimPilot's strict state contracts, deterministic adjudication, and verify/retry pattern;
- Graphiti's bitemporal facts and episode provenance;
- τ-bench's state-based checks and pass^k reliability measurement;
- AG-UI's frontend event vocabulary and OpenTelemetry/OpenInference's span vocabulary as projections.

### Recommended agent roster

Define **twelve configured roles**, while normally activating only the lead plus one to three specialists. Every role has a distinct artifact or authority.

| Role | Responsibility | Why it is separate |
|---|---|---|
| Lead investigator | Maintains plan, hypotheses, open questions, and value-of-information loop | Single authoritative adaptive coordinator |
| Policy and eligibility analyst | Retrieves governing documents as of the correct date; identifies clauses and invalid-dispute conditions | Temporal policy context and narrow read-only access |
| Ledger and quant analyst | Queries transaction/ledger history and invokes calculation helpers | Keeps raw tables and arithmetic out of lead context |
| Merchant-evidence analyst | Extracts claims and contradictions from untrusted evidence packets | Prompt-injection quarantine and evidence-specific schema |
| Graph and security analyst | Traverses entity links, tests compromise/ring hypotheses, recommends bounded security controls | Specialized graph tools and high-risk write isolation |
| Cardholder liaison | Produces bounded questions/messages and interprets simulated replies as untrusted evidence | Conversation policy and external-event lifecycle |
| Research analyst | Searches the internal research corpus for novel claim types | Distinct corpus and never a substitute for binding policy |
| Cardholder advocate | Argues the strongest sourced cardholder position | Independent SOP-DSP-003 panel position |
| Issuer/merchant advocate | Argues the strongest sourced contrary position | Independent opposing position, not shared deliberation |
| Adjudicator/verifier | Reconciles positions, identifies flip fact, checks confidence and record completeness | Independent authority; may return to re-plan |
| Memory curator | Decides skip/write/supersede/retract/consolidate/expire/purge through the write gate | Prevents investigation prompts from directly mutating durable memory |

The verifier can be a compiled deterministic-plus-model subgraph; it should not share the lead's conversational context. The adjudicator and verifier may use the same role definition only if the event log records two independent invocations with isolated inputs. Otherwise keep them distinct in Phase 2.

### Invocation policy by depth

| Depth | Typical model work | Specialists | Stop behavior |
|---|---|---|---|
| L1 | One route/classification call at most; often deterministic | None unless a novel-type classifier is required | Stop immediately when disposition and record are complete |
| L2 | Lead plus one focused specialist | 0–2, sequential or parallel if independent | Verify once; one bounded re-plan |
| L3 | Lead plus evidence/policy/graph specialists | 2–4, selective fan-out | Verifier and panel as required; bounded wait/resume |
| L4 | Lead, broad specialists, and full panel | Bounded dynamic/static fan-out | Latest-safe-time decision and conservative default remain mandatory |

## Case-driven architecture fit

| Cases | Forcing behavior | Recommended component |
|---|---|---|
| C02 | Obvious not-a-dispute/early stop | Deterministic route and L1 termination; no decorative delegation |
| C03, C06 | Governing-date policy, stale memory, verifier re-plan | Temporal hybrid retrieval; memory verification; verify-to-plan back-edge |
| C04, C07, C09, C14, C17, C18 | Exact dates, amounts, FX, pro-rata or time-zone calculations | Read-only sandbox and tested helpers, fully evented |
| C05 | Independent folio-line analysis | Bounded per-line fan-out, then deterministic aggregation |
| C08, C11 | Linked entities, Reg E/security signals | Graph/security specialist with active hypothesis status and bounded controls |
| C10–C13 | Contradiction, high impact, competing positions | Independent automated panel, adjudicator, confidence rule, verifier |
| C12/C12b | Cross-case ring or shared compromise point | Per-linked-case fan-out plus graph hypothesis writes with evidence edges |
| C15 | Late evidence and decision clocks | Checkpoint, external-event suspension/resume, latest-safe-time guard |
| C19 | Conflicting or obsolete memory | Inline and offline curator with explicit lifecycle events |
| Q01 | Portfolio prioritization and per-case work | Deterministic scoring plus bounded per-case fan-out and rank-correlation eval |

## Memory architecture conclusions

### Four distinct planes

1. **Persistent system of record:** SQLite case, transaction, communication, evidence, deadline, decision, action, memory-lifecycle, event, and blob tables; LangGraph SQLite checkpointer keyed by run/thread.
2. **Semantic/hybrid retrieval:** FTS5 plus sqlite-vec over policies, precedents, communications, packets, research, and eligible memory notes. Every query carries scope, entity, status, confidence, and temporal filters.
3. **Graph memory:** LadybugDB behind a tiny Cypher-capable interface, with NetworkX parity for required queries and writes. Hypothesis nodes and edges are never promoted to fact without evidence.
4. **Working case file:** typed facts with sources, hypothesis board, open questions, deadlines, plan/progress, and evidence matrix, exposed through the Deep Agents virtual filesystem as a blackboard.

### Read flow

`route/date rule -> scoped query -> candidate IDs/scores -> used/discarded decision -> evidence verification -> case-file fact or rejected lead`

The log must preserve the rule that selected `as_of`, the query and filters, returned versions and scores, and why each candidate was used or discarded. Memory is a lead; only primary case sources and governing documents are evidence.

### Write and forgetting flow

`candidate observation -> worth-remembering decision -> schema/provenance/fairness gate -> dedupe/conflict check -> write | skip | reject -> lifecycle maintenance`

Consolidation requires at least three sourced observations and a bounded validity interval. Retraction preserves the original and adds a correction; supersession links versions; expiry changes retrieval eligibility; purge is reserved for prohibited content. Recency/access decay may affect ranking but never silently delete provenance.

## Reliability and automated governance

### Planning and loop control

The lead operates a bounded plan-and-execute loop. Each iteration must add a source, eliminate or alter a hypothesis, resolve an open question, change a deadline/action, or explicitly conclude that the next call has no decision-changing value. The graph emits:

- budget consumption after each call;
- progress delta and evidence novelty;
- re-plan reason and plan diff;
- no-progress after N zero-delta iterations;
- max-replan and budget termination;
- wait checkpoint, awaited event, and latest safe decision time.

Reflexion and Self-Refine support bounded critique/revision, but self-critique is correlated with the original model. Their useful contribution is the loop shape, not proof of correctness.[^reflexion][^self-refine] CatcherAI's verifier therefore has isolated context and deterministic checks.

### Governance flow

For routes selected by SOP-DSP-003 v6:

1. snapshot the same source-linked case file for both advocates;
2. run advocates independently and, where possible, concurrently;
3. require each to return position, confidence, key sources, weaknesses, and the single fact that would flip it;
4. pass both artifacts—not their hidden reasoning—to the adjudicator;
5. run deterministic policy, arithmetic, provenance, fairness, and allowed-action checks;
6. if the verifier finds remediable gaps and re-plan budget remains, take the explicit back-edge;
7. otherwise apply the adjudicated result at confidence ≥0.75, or the conservative cardholder-favorable default below it;
8. execute only allow-listed bounded actions and record every check and side effect.

This replaces the human gates used by many reference systems. Suspension is allowed only for an external evidence/persona/follow-up event and cannot cross the latest safe decision time.

## Transparency and frontend-ready trajectories

### Canonical record and projections

```text
instrumented graph/model/tool/store/sandbox/harness boundaries
                           |
                           v
                append-only run_events
                content-addressed run_blobs
                  /          |           \
           replay CLI     AG-UI/SSE     OTEL/OpenInference
                                      (optional LangSmith)
```

The Pydantic event envelope specified in the brief should be the canonical schema and exported as JSON Schema. SQLite events are ordered per run by a transactionally allocated `seq`; nested work uses `span_id` and `parent_span_id`; every state-changing event includes a before/after hash or diff. Large inputs and results live in content-addressed blobs after redaction.

AG-UI provides run, step, text, tool-call, state snapshot/delta, raw, and custom event types over SSE/WebSocket-style transports.[^agui-events] It is a good frontend projection. It does not define authorization, retention, tamper evidence, or PII policy, so it must not be the audit source.

OpenTelemetry's GenAI semantic conventions and OpenInference define useful agent, model, tool, retriever, guardrail, and evaluator span kinds.[^otel-genai][^openinference] The OTel GenAI conventions are still evolving; map CatcherAI events in one export adapter rather than shaping the canonical schema around them.

The observability products examined share a nested-span model but none supplies CatcherAI's memory lifecycle, virtual-clock, field provenance, or regulatory action semantics:

| Product | Useful pattern | Gap for CatcherAI |
|---|---|---|
| Langfuse | nested agent/tool/retriever/generation observations, usage/cost, self-hosting, masking | operational trace, not the authoritative decision ledger[^langfuse] |
| Phoenix/OpenInference | open-source OTLP collector and explicit AI span kinds | no financial authorization or replayable domain-state contract[^phoenix] |
| OpenLLMetry | portable OpenTelemetry auto-instrumentation across models/frameworks/vector stores | no application state diff or decision provenance semantics[^openllmetry] |
| W&B Weave | function/call tracing with parent-child calls, errors, timing, and threads | parallel context needs care; no regulated write/action gate[^weave] |
| AgentOps | agent-session waterfall and automatic tool/model capture | replay and audit claims need source-level validation before reliance[^agentops] |

Use one optional export mapper rather than coupling the canonical event union to any of these products.

### One instrumentation spine

“One instrumentation point” should mean one event API and mandatory choke points, not one magical framework callback:

- LangGraph node wrapper emits node entry/exit, state diff, edge condition/result, fan-out branch, and checkpoint link.
- LangChain middleware `wrap_model_call` and `wrap_tool_call` emits start/terminal/failure/retry events; before/after hooks capture agent boundaries.[^langchain-middleware]
- The model gateway records every provider attempt and normalized response.
- Tool registry invokes tools only through one validated executor.
- Data, vector, graph, case-file, checkpointer, and sandbox interfaces receive an emitter and cannot access storage directly outside their modules.
- Harness owns virtual-clock, evidence, persona, follow-up, resume, and budget events.
- Decision and action repositories require provenance references before commit.
- `emit()` performs schema validation and redaction before either event or blob persistence.

Architecture tests should ban provider SDK imports outside adapters and raw database/open-subprocess calls outside instrumented access modules. Transparency tests reconcile call counters and state changes against events, validate span ancestry and sequence continuity, require decision-field provenance, and reconstruct the final decision at the final sequence.

### Frontend views supported

| View | Required event data |
|---|---|
| Timeline | sequence, virtual/wall time, actor, summary, event type |
| Span tree | span and parent IDs; node/agent/subagent/tool lifecycle |
| Graph execution | node entry/exit, conditional edge, back-edge, branch ID, checkpoint |
| Tool inspector | rationale, validated args, inline/blob result, duration, errors/retries |
| Memory inspector | store/query/filters/results; used/discarded; verification; write diffs and gate checks |
| Case-file time travel | state hashes plus JSON Patch/diff to any sequence |
| Clock/deadline view | virtual-clock changes, deadlines, waits, latest safe time |
| Panel debate | independent positions, confidence, sources, flip facts, adjudication and checks |
| Decision provenance | per-field event sequences and source IDs |
| Cost/budget view | per-call usage/cost/latency and cumulative route budgets |

### Known gaps and mitigations

| Gap | Mitigation |
|---|---|
| LangGraph checkpoint replay re-calls models/tools | Record normalized outputs and provide a replay model/tool adapter |
| Framework streaming does not itself prove every edge or store access | Instrument graph compiler/executor and enforce access-layer architecture tests |
| Deep Agents permissions do not cover custom tools/MCP/sandbox | Enforce capabilities in tool/data backends and sandbox mounts |
| Dynamic and async subagents are beta/preview | Put fan-out behind a small runtime interface; default to LangGraph `Send` or sync compiled subgraphs |
| Hidden chain-of-thought is unavailable and must not be logged | Record concise rationale, structured findings, sources, decisions, and flip facts only |
| Parallel branches can race event sequence/state merges | Allocate sequences transactionally; isolate branch state; deterministic reducer; log merge order |
| Third-party traces may retain prompts or PII | Redact in-process, export only allow-listed fields, make tracing opt-in |
| `deep-agents-ui` was archived in June 2026; generic chat UI passthroughs lack production auth | Build a thin Catcher-specific replay UI/API against the canonical ledger; borrow UI patterns only[^deep-agents-ui][^agent-chat-ui] |

## Safety and financial-services audit implications

### Prompt injection and least privilege

OWASP explicitly treats instructions embedded in documents as indirect prompt injection and recommends separation of untrusted content, tool validation, least privilege, and comprehensive logging.[^owasp-injection] Evidence packets and communications must therefore be represented as typed untrusted content, processed by an extraction-limited specialist, and never inserted into system/developer instructions. Model-proposed tool calls are validated against actor, route, case, and allow-list capabilities after generation.

The compute sandbox gets no credentials or network, a temporary working directory, CPU/time/output limits, and read-only mounted inputs selected through the data layer. Graph writes, credits, notices, monitoring, and security changes use separate narrow tools. The only automated side effects are those allowed by SOP-DSP-003; account closure and unbounded adverse action remain impossible.

PII and secrets are redacted before events or telemetry leave the process. Full PAN, credentials, prohibited-basis attributes, and SOP-DSP-004 prohibited content never enter prompts, blobs, exceptions, or replay output.

### Audit expectations

The Federal Reserve's April 2026 SR 26-2 supersedes SR 11-7, while retaining a risk-based emphasis on model governance and risk management; SR 11-7 remains useful historical design context, not the current citation.[^sr2602][^sr1107] The EU AI Act's current consolidated text includes automatic logging requirements for high-risk systems; whether a particular issuer deployment falls into that classification requires legal analysis, but reconstructability is a sound design baseline.[^eu-ai-act]

CFPB adverse-action circulars concern credit decisions rather than card-dispute adjudication, so they should not be misstated as directly controlling every CatcherAI outcome. They nevertheless demonstrate the expectation that complex models cannot substitute generic reasons for accurate, specific decision causes.[^cfpb-2022][^cfpb-2023] CFPB guidance on consumer-reporting disputes is a closer audit analogy: preserve the dispute information, investigative actions, findings, and resolution, not only the final letter.[^cfpb-disputes]

For CatcherAI, a QA reviewer or regulator must be able to reconstruct:

- the exact data, policy version, date rule, model/runtime configuration, tools, and skills available;
- every retrieved candidate and why it was accepted or discarded;
- every calculation, contradiction, hypothesis change, wait, and deadline;
- independent panel positions and deterministic checks;
- the causal sources and events for every decision-record field;
- the exact bounded action executed, its authorization rule, and resulting state;
- memory intentionally not written as well as memory written or changed.

## What is proven, what is promising, and what not to rely on

| Finding | Evidence level | Design consequence |
|---|---|---|
| LangGraph streams/checkpoints/subgraphs and Deep Agents tools/skills/subagents exist in current APIs | Proven interface | Use them, but wrap and pin versions |
| Responses API exposes the model/tool/schema/stream/usage primitives needed | Proven interface | Implement the OpenAI model adapter first |
| Codex SDK exposes runtime-level threads/turns/items/resume | Proven interface | Future integration belongs at AgentRuntime seam |
| Parallel specialist agents help broad, decomposable work but cost much more | Evaluated practice | Fan out selectively, with caps and isolated context |
| Strict contracts, deterministic policy checks, and state-based evaluation improve reliability | Evaluated practice | Make typed artifacts and coded gates load-bearing |
| Temporal provenance improves changing-fact retrieval | Evaluated system pattern | Implement bitemporal metadata and evidence verification |
| Vendor “agentic disputes/claims” systems are autonomous and accurate | Mostly marketing/pattern evidence | Do not use claims as acceptance evidence |
| A model's self-reported confidence is calibrated | Not established | Track empirical calibration; enforce policy threshold/default in code |
| Framework tracing alone is a complete financial audit trail | False | Keep an application-owned event ledger |
| A large peer swarm is more state-of-the-art for this problem | Unsupported | Prefer bounded manager/worker topology |

## Phase 2 decisions to specify precisely

The architecture document should now fix:

1. the exact LangGraph state schema, node/edge diagram, reducers, and checkpoint boundaries;
2. route configuration schema and deterministic-first/LLM-threshold precedence;
3. role registry, typed specialist outputs, per-route budgets, and fan-out caps;
4. model-gateway and runtime protocols, capability matrix, retry/error taxonomy, and immutable resolved config;
5. tool Pydantic schemas and actor/case capability checks;
6. data-path deny rules and sandbox isolation;
7. bitemporal retrieval and memory lifecycle schemas;
8. the complete event union, blob/redaction format, and event-to-AG-UI/OTel mappings;
9. governance predicates, panel artifacts, verifier checks, and allowed actions;
10. deterministic replay, transparency reconciliation, pass^k, and capability-by-case evaluation.

## Sources

[^anthropic-effective]: Anthropic, [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).
[^openai-agents-guide]: OpenAI, [A practical guide to building agents](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/).
[^anthropic-research]: Anthropic, [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system).
[^anthropic-multiagent-study]: Anthropic, [Multi-agent systems: lessons from large-scale experiments](https://www.anthropic.com/research/multiagent-systems).
[^magentic]: Microsoft Research, [Magentic-One: A generalist multi-agent system](https://arxiv.org/abs/2411.04468).
[^metagpt]: Hong et al., [MetaGPT: Meta programming for multi-agent collaborative frameworks](https://arxiv.org/abs/2308.00352).
[^open-deep-research]: LangChain, [Open Deep Research](https://github.com/langchain-ai/open_deep_research).
[^langgraph-supervisor]: LangChain, [LangGraph supervisor](https://github.com/langchain-ai/langgraph-supervisor-py).
[^langgraph-swarm]: LangChain, [LangGraph swarm](https://github.com/langchain-ai/langgraph-swarm-py).
[^deepagents-subagents]: LangChain, [Deep Agents: subagents](https://docs.langchain.com/oss/python/deepagents/subagents).
[^deepagents-async]: LangChain, [Deep Agents: async subagents](https://docs.langchain.com/oss/python/deepagents/async-subagents).
[^deepagents-dynamic]: LangChain, [Deep Agents: dynamic subagents](https://docs.langchain.com/oss/python/deepagents/dynamic-subagents).
[^deepagents-customization]: LangChain, [Customize Deep Agents](https://docs.langchain.com/oss/python/deepagents/customization).
[^deepagents-source]: LangChain, [Deep Agents `create_deep_agent` source](https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/deepagents/graph.py).
[^deepagents-skills]: LangChain, [Deep Agents skills](https://docs.langchain.com/oss/python/deepagents/skills).
[^deepagents-permissions]: LangChain, [Deep Agents permissions](https://docs.langchain.com/oss/python/deepagents/permissions).
[^langgraph-streaming]: LangChain, [LangGraph event streaming](https://docs.langchain.com/oss/python/langgraph/event-streaming).
[^langchain-event-streaming]: LangChain, [LangChain event streaming](https://docs.langchain.com/oss/python/langchain/event-streaming).
[^deepagents-event-streaming]: LangChain, [Deep Agents event streaming](https://docs.langchain.com/oss/python/deepagents/event-streaming).
[^langgraph-persistence]: LangChain, [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence).
[^langgraph-time-travel]: LangChain, [LangGraph time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel).
[^langgraph-source]: LangChain, [LangGraph `StateGraph` source](https://github.com/langchain-ai/langgraph/blob/main/libs/langgraph/langgraph/graph/state.py).
[^langsmith-run]: LangChain, [LangSmith run data format](https://docs.langchain.com/langsmith/run-data-format).
[^langsmith-studio]: LangChain, [LangSmith Studio](https://docs.langchain.com/langsmith/studio).
[^langchain-middleware]: LangChain, [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom).
[^openai-luna]: OpenAI, [GPT-5.6 Luna model](https://developers.openai.com/api/docs/models/gpt-5.6-luna).
[^openai-responses]: OpenAI, [Create a response](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).
[^openai-function-calling]: OpenAI, [Function calling](https://developers.openai.com/api/docs/guides/function-calling).
[^openai-structured]: OpenAI, [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
[^openai-streaming]: OpenAI, [Streaming API responses](https://developers.openai.com/api/docs/guides/streaming-responses).
[^codex-sdk]: OpenAI, [Codex SDK](https://developers.openai.com/codex/sdk).
[^codex-source]: OpenAI, [Codex SDK TypeScript source](https://github.com/openai/codex/tree/main/sdk/typescript).
[^graphiti]: Zep, [Graphiti temporal knowledge graph](https://github.com/getzep/graphiti).
[^memgpt]: Packer et al., [MemGPT: Towards LLMs as operating systems](https://arxiv.org/abs/2310.08560).
[^langmem]: LangChain, [LangMem reference](https://langchain-ai.github.io/langmem/reference/).
[^amem]: Xu et al., [A-MEM: Agentic memory for LLM agents](https://arxiv.org/abs/2502.12110).
[^generative-agents]: Park et al., [Generative Agents](https://arxiv.org/abs/2304.03442).
[^rirag]: RegNLP, [RIRAG/ObliQA regulatory information retrieval](https://aclanthology.org/2025.regnlp-1.17/).
[^graphrag]: Microsoft Research, [GraphRAG](https://microsoft.github.io/graphrag/).
[^lightrag]: LightRAG, [Simple and fast retrieval-augmented generation](https://lightrag.github.io/).
[^ladybug]: LadybugDB, [Ladybug graph database](https://github.com/LadybugDB/ladybug).
[^ladybug-python]: LadybugDB, [Python API](https://docs.ladybugdb.com/client-apis/python/).
[^ladybug-vector]: LadybugDB, [Vector extension](https://docs.ladybugdb.com/extensions/vector/).
[^sqlite-vec]: Alex Garcia, [sqlite-vec installation](https://github.com/asg017/sqlite-vec/blob/main/site/getting-started/installation.md).
[^sqlite-load-extension]: Python, [`sqlite3.Connection.enable_load_extension`](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.enable_load_extension).
[^fia]: Gao et al., [FIA: An LLM-based framework for financial fraud investigation](https://arxiv.org/abs/2506.11635).
[^codeact]: Wang et al., [Executable code actions elicit better LLM agents](https://github.com/xingyaoww/code-act).
[^smolagents]: Hugging Face, [Secure code execution with smolagents](https://huggingface.co/docs/smolagents/main/tutorials/secure_code_execution).
[^taubench]: Yao et al., [τ-bench: A benchmark for tool-agent-user interaction](https://arxiv.org/abs/2406.12045).
[^tau2]: Sierra Research, [τ²-bench](https://arxiv.org/abs/2506.07982).
[^agentevals]: LangChain, [AgentEvals](https://github.com/langchain-ai/agentevals).
[^claimpilot]: Ghosh et al., [ClaimPilot: Multi-agent claims adjudication](https://www.mdpi.com/1999-5903/18/9/465).
[^aws-claims]: AWS Samples, [Agentic insurance claims processing demo](https://github.com/aws-samples/sample-agentic-insurance-claims-processing-demo).
[^aws-claims-eks]: AWS Samples, [Agentic claims processing on EKS](https://github.com/aws-samples/sample-agentic-insurance-claims-processing-eks).
[^databricks-kyc]: Databricks Industry Solutions, [Proactive KYC/AML demo](https://github.com/databricks-industry-solutions/pkyc-aml-demo).
[^visa-ai]: Visa, [Visa unveils new services to modernize dispute resolution](https://investor.visa.com/news/news-details/2026/Visa-Unveils-New-Services-to-Modernize-Dispute-Resolution-Process/default.aspx).
[^pega]: Pega, [Smart Dispute](https://www.pega.com/industries/financial-services/smart-dispute).
[^quavo]: Quavo, [QFD and ARIA dispute automation](https://www.quavo.com/).
[^stripe-disputes]: Stripe, [Smart Disputes](https://docs.stripe.com/disputes/smart-disputes).
[^reflexion]: Shinn et al., [Reflexion](https://arxiv.org/abs/2303.11366).
[^self-refine]: Madaan et al., [Self-Refine](https://arxiv.org/abs/2303.17651).
[^agui-events]: AG-UI, [Events](https://docs.ag-ui.com/concepts/events).
[^otel-genai]: OpenTelemetry, [Generative AI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/).
[^openinference]: Arize AI, [OpenInference semantic conventions](https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md).
[^langfuse]: Langfuse, [Observability best practices](https://langfuse.com/docs/observability/best-practices).
[^phoenix]: Arize AI, [Phoenix tracing](https://arize.com/docs/phoenix/learn/tracing).
[^openllmetry]: Traceloop, [OpenLLMetry introduction](https://docs.traceloop.com/docs/openllmetry/introduction).
[^weave]: Weights & Biases, [Weave tracing](https://docs.wandb.ai/weave/guides/tracking/tracing).
[^agentops]: AgentOps, [AgentOps introduction](https://docs.agentops.ai/v2/introduction).
[^deep-agents-ui]: LangChain, [deep-agents-ui](https://github.com/langchain-ai/deep-agents-ui).
[^agent-chat-ui]: LangChain, [agent-chat-ui](https://github.com/langchain-ai/agent-chat-ui).
[^owasp-injection]: OWASP, [LLM prompt injection prevention cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html).
[^sr2602]: Federal Reserve, [SR 26-2: Interagency guidance on model risk management](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm).
[^sr1107]: Federal Reserve, [SR 11-7 attachment](https://www.federalreserve.gov/boarddocs/srletters/2011/sr1107a1.pdf).
[^eu-ai-act]: European Union, [Artificial Intelligence Act, consolidated text](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02024R1689-20260727).
[^cfpb-2022]: CFPB, [Circular 2022-03: adverse action and complex algorithms](https://www.consumerfinance.gov/compliance/circulars/circular-2022-03-adverse-action-notification-requirements-in-connection-with-credit-decisions-based-on-complex-algorithms/).
[^cfpb-2023]: CFPB, [Circular 2023-03](https://files.consumerfinance.gov/f/documents/cfpb_adverse_action_notice_circular_2023-09.pdf).
[^cfpb-disputes]: CFPB, [Circular 2022-07: reasonable investigation of consumer-reporting disputes](https://www.consumerfinance.gov/compliance/circulars/consumer-financial-protection-circular-2022-07-reasonable-investigation-of-consumer-reporting-disputes/).
