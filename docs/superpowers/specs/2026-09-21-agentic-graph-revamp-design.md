# Agentic graph-discovery revamp — design

Date: 2026-09-21
Status: approved in brainstorming, pending written-spec review

## 1. Why

The current system looks agentic but is scripted:

- 21 route playbooks (`src/playbooks/`, ~6,600 lines) hard-code each case's tool calls and build the
  final `DecisionRecord` in Python, including 53 constant confidences.
- The lead investigator's plan is logged but never consumed; the supervisor sees only finding
  *names* and picks from the playbook's `STEPS`.
- The router asks for depth/budget/agents/skills, then clamps or overrides most of it; all LLM
  output is parsed from free-text JSON.
- Rule-based governance (`governance.py`, review panel, regex fairness checks, guardrail gate),
  a simulation harness (virtual clock, scheduler, persona replies, suspend/resume) and an action
  allow-list add ceremony with no showcase value.
- Most cases are solvable with one lookup plus a rule; the evidence graph is under-used.

Goal: a genuinely agentic **graph-discovery engine**. The LLM decides what to investigate and what
the outcome is; the evidence lives in a rich, temporal property graph; scenarios are built so that
connecting the right nodes makes the answer obvious, while the surface story misleads.

Non-goals: production security, governance, fairness gates, real-time/time-advancing simulation,
portfolio queue scheduling.

## 2. Principles

1. **Config is a starting menu, never a fence.** Router suggestions, catalog roles and skills seed
   the agents; the supervisor may load any skill, define ad-hoc specialists, and revise the plan.
2. **Every LLM decision is a Pydantic model** (`response_format` / structured output), never a JSON
   blob parsed from prompt instructions.
3. **Only termination is hard-coded**: max supervisor turns, no-progress limit, and a `decide`
   precondition (all plan items done or explicitly waived). Nothing restricts *what* is decided.
4. **One representation per fact.** Case evidence lives only in the graph.
5. **Few layers.** Plain functions, one worker factory, one graph builder; no per-case code.
6. **Everything observable.** Every step emits a replayable trajectory event carrying the node and
   edge IDs it touched.
7. **Robust, not over-engineered.** This is a POC that will grow. Add a node, action, tool, schema
   field or config file only when a case or the demo needs it; prefer one generic mechanism (e.g.
   "delegate to a role") over a special-purpose one. Extensibility comes from config and prompts,
   not from abstraction layers.

## 3. Agent core

```text
START → triage → supervisor ─┬─ delegate ──Send──▶ worker (×N, parallel) ─┐
                    ▲          │                                             │
                    └──────────┴──────────── findings merged ◀───────────────┘
                               └─ decide ─▶ adjudicator (CaseReport) ─▶ consolidate_memory ─▶ END
```

Five node kinds in total. Everything else (critique, skill loading, memory work) is a worker task.

### 3.1 Router + planner — `triage` node

One LLM call does routing and planning together (they need the same inputs). Input: the dispute
intake, its first-hop graph neighbourhood, the graph schema and the case-type menu. Output:

```python
class Triage(BaseModel):
    case_type: str                 # a menu case type, or "novel"
    case_type_description: str     # required when novel
    suggested_skills: list[str]
    suggested_roles: list[str]
    hypotheses: list[Hypothesis]
    plan: list[PlanItem]           # id, question, status: open|done|waived, evidence_refs, waiver_reason
    rationale: str
```

No depth, budget, confidence threshold or fallback route. Suggestions are context, not a
whitelist; unknown skills/roles are allowed. The plan is state the supervisor must close out, not a
log line.

### 3.2 Supervisor — `supervisor` node

Input each turn: the plan with item status, `InvestigationSummary`, and the latest worker findings.

```python
class InvestigationSummary(BaseModel):
    hypotheses: list[Hypothesis]      # label, status, support/against as node/edge IDs
    key_facts: list[Fact]             # statement + source node/edge IDs
    open_questions: list[str]
    contradictions: list[str]

class Task(BaseModel):
    role: str                         # catalog role or ad-hoc name
    instructions: str | None          # required for ad-hoc roles
    objective: str
    skills: list[str]                 # any skill from the library
    plan_item_ids: list[str]

class SupervisorTurn(BaseModel):
    reasoning: str
    plan_edits: list[PlanEdit]        # add / drop / mark done (with evidence refs) / waive
    summary: InvestigationSummary
    action: Delegate | Decide
```

- `Delegate{tasks: list[Task]}` fans out with LangGraph `Send`; results merge through a reducer.
  Skills are attached per task; a devil's-advocate review is just a task for the `critic` role.
- `Decide` is accepted only when every plan item is `done` or `waived`; otherwise the runtime
  returns the rejection to the supervisor as the next turn's input.

Termination reasons: `decided`, `max_turns` (then forced `decide` with a note), `no_progress`
(N turns with no new facts/node IDs; then forced `decide`).

### 3.3 Workers — `worker` node

One factory builds a Deep Agent (`create_deep_agent`, `response_format=Findings`) per task:

- system prompt = role prompt (catalog YAML or ad-hoc `instructions`) + graph schema + loaded skills;
- same full toolset for every worker (section 5);
- returns `Findings{facts, hypothesis_updates, suggested_next, node_ids, edge_ids}`.

All configuration lives in one file, `config/agents.yaml`: the case-type menu (id, description,
suggested skills/roles) and the role catalog (id, description, prompt, default skills):
`graph_analyst`, `transaction_analyst`, `evidence_analyst`, `policy_researcher`, `memory_keeper`,
`critic`, `adjudicator`. Adding a role or case type is a YAML entry.

### 3.4 Final adjudicator — `decide` node

The final output is the product the demo is judged on, so it is produced by a dedicated
`adjudicator` Deep Agent (`response_format=CaseReport`). It receives the plan, the final
`InvestigationSummary`, all findings and any critique, and it has read-only graph and knowledge
tools so it can re-check every cited node or policy before committing. One agent produces both the
decision and its explanation, so the reasoning cannot drift from the outcome.

```python
class Verdict(StrEnum):
    ACCEPTED = "accepted"                 # cardholder credited in full
    PARTIALLY_ACCEPTED = "partially_accepted"
    REJECTED = "rejected"
    NOT_A_DISPUTE = "not_a_dispute"       # e.g. descriptor confusion, resolved by explanation

class EvidenceLink(BaseModel):
    claim: str                            # what this evidence shows
    node_ids: list[str]
    edge_ids: list[str]
    source_excerpt: str | None            # quoted property/text when relevant

class TransactionDecision(BaseModel):
    txn_id: str
    verdict: Verdict
    disputed_amount: Decimal
    credit_amount: Decimal
    cardholder_liability: Decimal
    network_action: Literal["file_dispute", "no_dispute", "pre_arbitration", "none"]
    reason_code: str | None               # e.g. Visa 10.4 / 13.1
    rationale: str                        # why this transaction got this outcome
    evidence: list[EvidenceLink]

class HypothesisAssessment(BaseModel):
    hypothesis: str
    status: Literal["accepted", "rejected"]
    why: str
    evidence: list[EvidenceLink]

class CaseReport(BaseModel):
    case_id: str
    verdict: Verdict
    claim_family: str
    headline: str                         # one-sentence outcome
    executive_summary: str                # 3-6 sentences for an analyst/manager
    detailed_reasoning: str               # step-by-step argument from evidence to verdict
    transactions: list[TransactionDecision]
    hypotheses: list[HypothesisAssessment]  # incl. the misleading surface story and why it fails
    decoys_ruled_out: list[str]           # near-miss links considered and why they don't apply
    missing_evidence: list[str]           # what was unavailable and how it was treated
    policy_basis: list[Citation]          # policy/precedent doc IDs + why each applies
    account_actions: list[AccountAction]  # e.g. card reissue, reopen linked case, watchlist
    confidence: float
    flip_fact: str                        # the fact that would change the verdict
    cardholder_letter: str                # plain-language explanation to the customer
```

Rules: every `rationale`/`why` must be backed by at least one `EvidenceLink`; totals across
`transactions` must reconcile with the dispute amount (checked by a Pydantic validator, with the
error returned to the agent for a retry). The missing-evidence cardholder-favourable default is
taught by a skill and policy text, not coded. The `CaseReport` is persisted as the run result and
emitted in the `decision` event.

### 3.5 Memory consolidation — `consolidate_memory` node

One `memory_keeper` pass: write/supersede/retract/merge `MemoryNote`s and graph findings touched
in this run; expire notes past `valid_until`.

## 4. Evidence graph

### 4.1 Storage

- **LadybugDB is the single case-evidence store** (verified 0.20.4 Cypher + variable-length paths).
  Operational SQLite tables, `CaseDataAccess`, `sql_query` and the NetworkX fallback are removed;
  `ladybug` becomes a required dependency.
- **Precomputed** by the generator; **extended on the fly** by agents (`Finding` nodes and inferred
  edges with `run_id`, `confidence`, `evidence_path`), which persist and are visible to later runs.
- SQLite keeps only: knowledge documents (FTS5 + sqlite-vec), trajectory events, LangGraph
  checkpoints.
- API runs copy the pristine graph per run (existing `copy_scenario_store` pattern).

### 4.2 Ontology (~21 labels, ~38 edge types; temporal properties on edges)

Every label and edge type must be used by at least one case's proof or decoy pattern or by the
realistic background; anything unused is cut.

| Area | Nodes | Edges |
|---|---|---|
| Identity | Customer, Account, Card, Token, Device, IP, Phone, Email, Address, MerchantAccount | HOLDS{role,valid_from,valid_to}, ISSUED_ON, CARRIES, TOKENIZED_AS, BOUND_TO_DEVICE, LIVES_AT{valid_from,valid_to}, WORKS_AT, HAS_PHONE{valid_from,valid_to}, HAS_EMAIL, LOGGED_IN_FROM{ts,ip}, MERCHANT_LOGIN_FROM{ts} |
| Commerce | Merchant, Terminal, Descriptor, Authorization, Transaction, Order, Shipment, AgentProvider, Mandate | PAID_WITH, AT_MERCHANT, VIA_TERMINAL, CLEARS{seq}, FOR_ORDER, SHIPPED_AS, DELIVERED_TO{pod,signer}, REFUNDS, FROM_DEVICE, FROM_IP, DESCRIBES{valid_from,valid_to}, SUB_MERCHANT_OF, ACTING_FOR, AUTHORIZED_BY_MANDATE |
| Case | Dispute, EvidenceItem, EvidenceRequest, Communication, AccountEvent, MemoryNote, Finding | FILED_BY, DISPUTES{amount}, RELATED_TO, HAS_EVIDENCE, ASSERTS, REQUESTED{status,deadline,responded_at}, TRIGGERED_BY, CHANGED_PHONE_TO, ABOUT, SUPPORTS, CONTRADICTS, SAME_ACTOR, COMPROMISED_AT |

Rules: every node has a stable prefixed `id`; every edge has a stable `id` (`E-…`) so the frontend
can reference it; every relationship that can change over time carries `valid_from`/`valid_to`
(`FROM`/`TO` are reserved words in Cypher DDL); merchant evidence connects into the identity graph through `ASSERTS` (e.g. "order
placed from device X"); free text (communications, merchant statements) is a node property the
agent reads after reaching the node.

**Missing evidence** is `(:Dispute)-[:REQUESTED]->(:EvidenceRequest{status:'no_response',
deadline, deadline_passed:true})` — a fact to discover, never a simulated wait.

### 4.3 Background and complexity

- ~2–3k customers, ~50k transactions, realistic benign sharing: households, roommates, office IPs,
  CGNAT ranges, recycled phone numbers, marketplace sub-merchants.
- Each case has at least one **decoy** that is only separable through edge properties or an extra
  hop (e.g. same street different unit; phone shared only after `HAS_PHONE.valid_to`; other cards at a
  terminal that were never disputed).
- In ≥6 of 10 cases the intake narrative and/or merchant statement point to the wrong answer.

### 4.4 Case set (10)

| # | Case | Solving subgraph (sketch) | Surface misleads toward |
|---|---|---|---|
| 1 | C02 Descriptor confusion | Descriptor → SUB_MERCHANT_OF → parent Merchant ← cardholder's own prior Transactions | fraud |
| 2 | C04 Split, not double | 2 Transactions → CLEARS → one Authorization; FOR_ORDER → Order → 2 Shipments | duplicate |
| 3 | C08 Pump Six | disputed Cards → earlier Transactions → VIA_TERMINAL → one Terminal (decoy: undisputed cards there too, earlier date window) | isolated fraud |
| 4 | C10 Family tablet | Transaction FROM_DEVICE → Device ← LOGGED_IN_FROM ← household member who HOLDS{role:authorized} | fraud |
| 5 | C11 ATO drop ring (~40 accounts) | AccountEvent phone change → new Device/IP → Shipment DELIVERED_TO drop Address shared by many ATO Disputes; MemoryNote claims friendly fraud | first-party fraud |
| 6 | C12 Porch ring | claimants share Phone/Device/Address component; coordinated not-received Disputes; POD to their addresses | genuine non-receipt |
| 7 | C12b Wrong house (control) | resembles C12 via a recycled phone outside its `valid_from/valid_to`; POD address ≠ LIVES_AT; merchant EvidenceRequest `no_response` | ring member |
| 8 | C13 Agent booked it | Transaction → Token → ACTING_FOR AgentProvider → Mandate constraints vs Order | unauthorized |
| 9 | C18 Refund crossed | unlinked credit Transaction → FOR_ORDER same Order as disputed purchase; EvidenceRequest `no_response` on partial remainder | credit not processed |
| 10 | C19 Yesterday's reputation | merchant Dispute pattern + MemoryNote contradicted by newer Findings/graph facts | trust old note |

Missing-evidence behaviour is exercised in C12b and C18 (plus optionally a third).

Dropped: C01 (merged into C19), C03, C05, C06, C07, C09 (merged into C10), C14, C15 (both), C16,
C17, Q01 queue.

### 4.5 Ground truth

Per case, evaluator-only: expected decision; `solution_subgraph` (5–25 key node IDs);
`proof_patterns` (Cypher that must match); `decoy_patterns` (Cypher that matches but must not flip
the outcome); `required_capabilities` from `capabilities.py`. The generator runs every proof and
decoy pattern at build time and fails if any case is not uniquely resolvable.

## 5. Tools (shared by all workers)

| Tool | Purpose |
|---|---|
| `graph_schema` | labels, edge types, properties, counts (also injected in prompts) |
| `graph_query(cypher, params)` | read-only Cypher (incl. paths); write clauses rejected; row cap; returns node/edge IDs |
| `graph_neighbors(id, rel_types?, direction?, since?, until?)` | temporal-filtered expansion |
| `graph_write_finding(finding, edges)` | Finding node + inferred edges with provenance |
| `search_knowledge(query, kinds?, as_of?)` | hybrid FTS + vector over policies, precedents, memory notes |
| `memory_write(op, note)` | write / supersede / retract / merge a `MemoryNote`; must cite source node IDs |
| `python(code)` | restricted subprocess with timeout for arithmetic, dates, FX, aggregation |

Memory notes are graph nodes, so reading them is just `graph_query` or `search_knowledge` — no
separate read tool. Seven tools in total.

Skills use Deep Agents' native `skills=` support with the `skills/` directory. Skills are rewritten
as generic domain knowledge: graph-investigation techniques, fraud/ATO signals, household
authority, missing-evidence default, Reg E/Z essentials, network reason codes, agentic
transactions, memory hygiene.

## 6. Trajectory and API

Kept: append-only SQLite event log, blobs for large payloads, SSE. Dropped as production concerns
with no demo value: the hash chain and its verification, and payload redaction.

Event types: `run_started`, `triage`, `plan_updated`, `supervisor_turn`,
`delegation_started`, `delegation_finished`, `skill_loaded`, `tool_call`, `tool_result`
(`node_ids`, `edge_ids`), `graph_write`, `memory_write`,
`decision`, `termination`, `node_entered`/`node_exited`, `edge_taken`, `model_call`.

Removed: wait/clock/persona/evidence-arrival, guardrail/verifier/panel/adjudication, todo events.

API: case list/detail read from the graph; run start/stream/replay; new
`GET /runs/{id}/subgraph` (union of touched node/edge IDs, with properties); graph explorer
endpoints for Cypher-backed neighbourhoods; evaluation results. Queue endpoints removed;
`schemas/openapi.json` and `trajectory-event.schema.json` regenerated.

## 7. Frontend

- Run Observatory: supervisor timeline with plan checklist (status + evidence refs); **live evidence
  subgraph** growing from `tool_result` node/edge IDs, with solution-subgraph overlay in eval mode;
  delegation tree (parallel workers, ad-hoc roles highlighted); **case report view** rendering the
  `CaseReport` (verdict, summary, per-transaction rationale, accepted/rejected hypotheses, decoys
  ruled out, cardholder letter) with every `EvidenceLink` clickable into the subgraph.
- Graph Lab: neighbourhood explorer over the new ontology.
- Removed: queue launcher/visualization, wait/clock and governance-panel views.

## 8. Testing and evaluation

- **Deterministic pytest**: generator validation (proof/decoy patterns, referential integrity),
  tool contracts and read-only Cypher guard, Pydantic schemas, event hash chain, API, and a loop
  smoke test with a stub model returning fixed Pydantic objects (plumbing only, never answers).
- **Real-LLM eval CLI** (`inspect eval`): per case — verdict/amount/action match; report
  grounding (every cited node/edge ID exists, and the report cites the solution subgraph and names
  the decoys it ruled out); solution-subgraph
  coverage by trajectory node IDs; decoy non-flip; cardholder-favourable default on
  missing-evidence cases; required-capability signals present; pass@k.
- The fake model adapter with the routing/supervisor oracle is deleted.

## 9. Removal list

`src/playbooks/`, `src/governance.py`, `src/actions.py`, `src/decisions.py` field-level provenance
(the decide node stores the `DecisionRecord`, whose `evidence_path` replaces per-field provenance),
`src/harness/` (clock, scheduler, persona, evidence), `src/runtime/portfolio.py`,
`src/memory/curator.py`, `src/sandbox.py` helpers, `src/data/access.py` operational queries,
`src/adapters/fake_model.py`, `src/adapters/fake_routing.py`, `src/evaluation/perturbations.py`
and `reliability.py` in current form, NetworkX graph backend, `config/routes.yaml`, route-specific
agent YAMLs, tests tied to removed behaviour, `data/generated/eval/*` historic runs,
`data/generated/simulation/`, stale design/plan docs (`docs/superpowers/*/2026-09-16-*`,
`handoff.md`), and sections of `README.md`/`docs/technical.md` describing removed parts (rewritten).

`data/generator/capabilities.py` and `capability_coverage.json` are rewritten for the new case set
and components (harness now = scenario loading, trajectory capture, eval — not simulation).

**Model stack.** The custom provider-neutral gateway (`src/ports.py`, `src/domain/model.py`,
`src/adapters/openai_responses.py`, `src/observability/model_gateway.py`,
`src/runtime/gateway_chat_model.py`) is replaced by LangChain's `init_chat_model` configured from
`config/models.yaml`, plus one LangChain callback handler that emits `model_call` events. Swapping
provider becomes a config change.

## 10. Delivery stages

See `handoff.md` for the authoritative, finer-grained stage list with complexity ratings.


Each stage ends with tests green, a `code-simplifier` pass, and a commit + push.

1. **Graph data**: new generator (ontology, background, 10 cases, decoys, ground truth, validation),
   LadybugDB load, knowledge store rebuild.
2. **Tools**: graph tools, knowledge search, memory tools, python sandbox; contract tests.
3. **Agent core**: triage, supervisor, workers (Send), adjudicator, consolidate; Pydantic
   schemas; termination; trajectory events; removal of old runtime pieces.
4. **Eval**: real-LLM eval CLI with subgraph coverage and decoy checks; first full run.
5. **API + frontend**: new projections and endpoints, live evidence subgraph, cleanup.
6. **Docs**: README and technical guide rewritten; stale docs removed.

## 11. Risks

- **LLM variance** on hard cases → pass@k reporting, strong graph-technique skill, schema injected
  up front, `critic` role available to the supervisor.
- **Cypher errors from the model** → errors returned to the agent as tool results so it can retry;
  schema tool always available.
- **Token cost of large query results** → row caps and compact result formatting (IDs + key props).
- **Generator complexity** → proof/decoy validation at build time keeps cases honest.
