# CatcherAI — an agentic card-dispute investigator

CatcherAI is a proof-of-concept of an AI agent system that **investigates and resolves credit and debit card disputes end to end** from the card issuer's side: it receives a cardholder's claim, works out what actually happened, applies the correct network rule *and* the correct regulation as of the right date, recovers money from the merchant when that's justified, protects the cardholder when that's required, and does all of it **fully automatically, with no human in the loop**. High-impact and uncertain decisions are challenged by an automated review panel and fail safe in the cardholder's favor.

This repository contains the foundation and executable POC: domain research, 20 hand-built
investigation scenarios with machine-checkable ground truth, a synthetic data ecosystem (~24k
transactions, 308 disputes, merchant evidence, dated research pages, versioned policies,
precedents and pre-existing agent memory), the architecture design, and transparent end-to-end
implementations of all 20 hero cases plus the Q01 portfolio queue. The deterministic acceptance run
passes all 21 scenarios; see
[`docs/design/06-eval-results.md`](docs/design/06-eval-results.md) for pass^3, trajectory, capability,
cost/latency and limitation details.

The next initiative is the **Dispute Observatory**, a dark interactive frontend plus FastAPI
presentation layer for live runs, replay, routing, tools, subagents, skills, safe reasoning artifacts,
decision provenance, memory and graph exploration. Its implementation-ready design and staged plan
are in [`docs/design/07-observability-console.md`](docs/design/07-observability-console.md). The
console is designed but not implemented yet; the current CLI commands below remain authoritative.

| Document | What's in it |
|---|---|
| [`docs/research/01-domain-research.md`](docs/research/01-domain-research.md) | How disputes really work; Visa rules (April 2026 edition, read from primary text), Reg Z / Reg E, industry tooling, sources and confidence tags |
| [`docs/design/02-case-catalog.md`](docs/design/02-case-catalog.md) | The 20 hero cases + queue scenario: what each proves, expected path, pivots, traps |
| [`docs/design/03-data-dictionary.md`](docs/design/03-data-dictionary.md) | Every file and field, joins, timestamps, deliberate data-quality issues, output schemas |
| [`docs/design/07-observability-console.md`](docs/design/07-observability-console.md) | Planned frontend experience, API/SSE contracts, source layout, staged implementation and acceptance gates |
| `data/corpus/` | Policy corpus (Visa, Reg Z/E, fictional bank SOPs, bulletins) and skills (playbooks) |
| `data/generator/` | Deterministic generator, validator, SQLite loader (stdlib Python 3.9+) |
| `data/generated/` | The dataset (regenerate any time; byte-identical for the same seed) |

```bash
python3 data/generator/gen.py          # generate data/generated/
python3 data/corpus/author_policies.py # (re)write the policy corpus and skills
python3 data/generator/validate.py     # 401 checks: integrity, leakage, invariants, discoverability, ground-truth references
python3 data/generator/load_sqlite.py  # build data/generated/catcher.sqlite (tables + FTS over documents)
```

## Run the agent

Python is managed with `uv`. The fake model adapter is deterministic and needs no credentials; the OpenAI adapter requires `OPENAI_API_KEY` and never silently falls back.

Application code is flat under `src/`: modules import `domain`, `runtime`, `playbooks`, `memory`,
and the other top-level packages directly. There is no product-named Python package wrapper. The
distribution is named `card-dispute-agent`; both `catcher` (compatibility) and `dispute-agent` expose
the same CLI.

```bash
uv python install 3.12
uv sync --extra dev --extra graph
uv run python data/generator/load_sqlite.py

uv run catcher run DSP-2026-90002 --adapter fake   # C02 descriptor confusion, L1 early stop
uv run catcher run DSP-2026-90005 --adapter fake   # C04 split clearing, evidence wait, cardholder reply
uv run catcher run DSP-2026-90003 --adapter fake   # C03 as-of write-off policy, stale-memory supersession
uv run catcher run DSP-2026-90007 --adapter fake   # C06 verifier failure, re-plan back-edge, pro-rata
uv run catcher run DSP-2026-90009 --adapter fake   # C08 Reg E clocks, compromise point, specialists, panel
uv run catcher run DSP-2026-90011 --adapter fake   # C10 household authority, device graph, review panel
uv run catcher run DSP-2026-90012 --adapter fake   # C11 account takeover, drop address, automated reopening
uv run catcher run DSP-2026-90013 --adapter fake   # C12 linked-case fan-out, bounded ring controls
uv run catcher run DSP-2026-90014 --adapter fake   # C12b negative linkage control
uv run catcher run DSP-2026-90015 --adapter fake   # C13 agentic booking, provider-record wait, policy gap
uv run catcher run DSP-2026-90017 --adapter fake   # C15 late Dispute Response, parallel charge tracks
uv run catcher run DSP-2026-90022 --adapter fake   # C19 stale merchant reputation, consolidation
uv run catcher queue --adapter fake                # Q01: rank all 95 open cases by hard deadline

# Same domain workflow through gpt-5.6-luna and the Responses API
OPENAI_API_KEY=... uv run catcher run DSP-2026-90002 --adapter openai
```

`catcher run` writes to the scenario store (`data/generated/catcher.sqlite`) unless `--db` points at a copy; use a copy when you want to rerun a case from pristine memory. Trajectory events and blobs go to that store and LangGraph checkpoints to `<store>_checkpoints.sqlite`.

### Waiting for external events

Runs suspend only for merchant/provider evidence or a simulated cardholder reply. Suspension is a real LangGraph `interrupt` persisted by the SQLite checkpointer. The harness scheduler computes the latest safe decision time (earliest regulatory or network deadline minus two business days), advances the virtual clock to the arrival or that time—whichever is first—and resumes with `Command(resume=...)`. If nothing arrives, the absence is recorded as an availability fact and the case goes through verification, the review panel and, if confidence stays below 0.75, the cardholder-favorable conservative default. No person is ever awaited.

```bash
cp data/generated/catcher.sqlite /tmp/c13.sqlite
uv run catcher run DSP-2026-90015 --db /tmp/c13.sqlite --no-auto-resume   # prints the pending wait
uv run catcher resume <run_id> --db /tmp/c13.sqlite                        # new process resumes from the checkpoint
```

### Replay, evaluate, curate

```bash
uv run catcher replay <run_id> [--db PATH] [--type tool_call] [--actor scheduler] [--to-seq 40]
uv run catcher export-event-schema --output schemas/trajectory-event.schema.json

# Each attempt runs on its own copy of the scenario store under data/generated/eval/<timestamp>/
uv run catcher eval \
  DSP-2026-90001 DSP-2026-90002 DSP-2026-90003 DSP-2026-90005 DSP-2026-90006 \
  DSP-2026-90007 DSP-2026-90008 DSP-2026-90009 DSP-2026-90010 DSP-2026-90011 \
  DSP-2026-90012 DSP-2026-90013 DSP-2026-90014 DSP-2026-90015 DSP-2026-90016 \
  DSP-2026-90017 DSP-2026-90019 DSP-2026-90020 DSP-2026-90021 DSP-2026-90022 Q01 \
  --adapter fake --runs 3 --report data/generated/eval/report.json
uv run pytest

# Offline SOP-DSP-005 memory curator: purge, TTL expiry, dedupe, as-of policy supersession
uv run catcher curate --db /tmp/c13.sqlite --as-of 2026-10-21

# Optional real Responses API provider-contract smoke test
DISPUTE_AGENT_RUN_OPENAI_SMOKE=1 OPENAI_API_KEY=... uv run pytest tests/test_openai_smoke.py
```

The eval report includes every deterministic and capability check, per-attempt operational metrics,
pass rate, pass^k, outcome stability, hash-chain/replay reconciliation, and a capability-by-case
matrix. Ground truth and private simulation data are evaluator/harness-only. The agent-visible SQLite
loader excludes both, the filesystem guard denies both path families, only the persona harness reads
the persona fixtures, and the runtime does not import the evaluator.

The functional-robustness suite also runs every route through three deterministic presentation
variants that rename merchants, the agentic provider and customers and reword intake summaries.
It compares decision semantics and verifies each event hash chain, catching logic that accidentally
depends on an authored display name rather than operational data.

### Dispute Observatory API (read-only, Stage 1)

A FastAPI presentation adapter (`src/api/`) exposes the same SQLite trajectory store read-only,
for the planned frontend console. It never runs a case itself and never mutates the store it reads;
point it at a copy (as `catcher run --db` does) to browse a store that already has runs in it.

```bash
uv sync --extra dev --extra graph --extra api
uv run uvicorn api.app:app --app-dir src --reload   # http://127.0.0.1:8000/api/v1/health

# Regenerate the checked-in OpenAPI document after changing src/api/
uv run python -c "
import json, sys; sys.path.insert(0, 'src')
from pathlib import Path
from api.app import create_app
json.dump(create_app(Path('.').resolve()).openapi(), open('schemas/openapi.json', 'w'), indent=2)
"
```

Endpoints: `/api/v1/health`, `/meta`, `/meta/routes`, `/meta/agents`, `/meta/skills`,
`/meta/workflow`, `/schema/events`, `/cases` (paged/filterable), `/cases/{case_id}`,
`/runs` (paged/filterable by `case_id`/`status`), `/runs/{run_id}`,
`/runs/{run_id}/events` (paged/filtered by `after_seq`/`type`/`actor`/`ref`), and
`/runs/{run_id}/decision`. There is no execution manager or live stream yet — see
[`docs/design/07-observability-console.md`](docs/design/07-observability-console.md) for the full
staged plan, and `handoff.md` for exact current status.

### How the runtime is organized

- `runtime/langgraph_runtime.py` is one route-independent graph: `run_start → load_case → route → compute_clocks → investigate → assess_progress ⟲ {gather_evidence | ask_cardholder → await_external_event → apply_external_event | run_specialists | analyze_track (Send fan-out) → merge_tracks} → verify ⟲ replan → propose_decision → governance_gate → review_panel? → record_decision → execute_actions → memory_maintenance → terminate`.
- `playbooks/<route_id>.py` holds everything route-specific as plain hook functions (`investigate`, `evidence_request`, `on_evidence`, `cardholder_question`, `on_reply`, `specialists`, `tracks`/`analyze_track`, `verify`, `replan`, `decide`, `hypotheses`, `curate`). The hook contract is documented in `playbooks/__init__.py`.
- `governance.py` makes SOP-DSP-003/004 deterministic: panel triggers, evidence-weighted adjudication confidence, the 0.75 threshold, the conservative default and the fairness scan. The advocates and adjudicator still run as isolated Deep Agents subagents and their outputs are recorded.
- `memory/notes.py` is the single write gate and lifecycle boundary (write, skip, reject, supersede, retract, consolidate, dedupe, expire, purge, decay-ranked reads); `memory/curator.py` holds the shared curation rules and the offline job.
- `harness/scheduler.py` and `harness/persona.py` are the only components that move the clock or read persona fixtures.

Durable memory notes are leads only: reads are scoped by subject, validity window, status, sensitivity and confidence, ranked with recency/access decay, and never return superseded, retracted, archived, expired or purged notes as current. Graph memory uses embedded LadybugDB with a transparently logged NetworkX fallback behind the same interface.

## Extend the system

- **Add a route:** add an entry in `config/routes.yaml` (first match wins; every evaluated rule and feature is logged) and a module `src/playbooks/<route_id>.py` implementing the hooks it needs. No graph or runtime edits.
- **Add an agent or skill:** add `config/agents/<id>.yaml` or a drop-in `skills/<name>/SKILL.md` and reference it from the route.
- **Add a scenario:** add `config/scenarios/<id>.yaml`; data locations come from configuration.
- **Add a model provider:** implement the provider-neutral `ModelGateway` port inside `src/adapters/`. Provider SDK imports outside adapters fail an architecture test.
- **Add an agent runtime:** implement the `AgentRuntime` port (`start`/`result`/`resume`/`cancel`/`events`). Dispute state, tools, decisions, memory, governance, events and evaluators do not depend on Deep Agents or LangGraph types.

The researched options and selected design are in [`docs/design/04-agent-architecture-research.md`](docs/design/04-agent-architecture-research.md) and [`docs/design/05-agent-architecture.md`](docs/design/05-agent-architecture.md).

---

## Contents
1. [The use case](#1-the-use-case)
2. [Domain background](#2-domain-background)
3. [Example investigations](#3-example-investigations)
4. [The data ecosystem](#4-the-data-ecosystem)
5. [Relationships and investigative paths](#5-relationships-and-investigative-paths)
6. [Memory design](#6-memory-design)
7. [The evidence ecosystem](#7-the-evidence-ecosystem)
8. [The policy ecosystem](#8-the-policy-ecosystem)
9. [How the dataset is generated](#9-how-the-dataset-is-generated)
10. [Architecture component → the scenario that forces it](#10-architecture-component--the-scenario-that-forces-it)
11. [Agent behavior this data enables](#11-agent-behavior-this-data-enables)
12. [Why this is a compelling demonstration](#12-why-this-is-a-compelling-demonstration)
13. [From POC to production](#13-from-poc-to-production)
14. [Assumptions, inventions, and open questions](#14-assumptions-inventions-and-open-questions)

---

## 1. The use case

### What we investigate
A cardholder of **Lanternfield Bank, N.A.** (a fictional issuer) says something is wrong with a card transaction. The claim might be true, partly true, mistaken, or false. The agent system must decide:

- **Is this even a dispute?** (an unfamiliar merchant name, a refund already on its way, one order that shipped in two boxes)
- **Which body of law applies?** Credit cards fall under Regulation Z. Debit cards fall under Regulation E, which has different clocks, different liability rules, and mandatory provisional credit.
- **What happened?** Merchant failure, merchant billing error, cardholder confusion, family member, account takeover, third-party fraud, organized first-party abuse, or a policy gap nobody has written a rule for yet.
- **What does the issuer owe the cardholder?** And, separately, **can the issuer recover the money from the merchant?** These can have different answers.
- **What must happen next, and by when?** File a chargeback under a specific network reason code, accept a merchant's response, reverse a temporary credit with the right notice, write it off, redirect the customer, reopen a past decision, apply bounded fraud controls, or wait for evidence that is on its way.

### Why it matters
- **Volume and cost.** Visa processed **106 million disputes in 2025**, up 35% from 2019. Mastercard-sponsored research puts issuer cost at **$9–10 per disputed transaction** and about **one back-office employee per $13–14K of disputes**. Most US issuers run hundreds of dispute staff. *(Network-sponsored figures; see research doc §7.3.)*
- **Regulatory exposure.** Regulation Z and Regulation E impose hard deadlines and investigation standards. CFPB exam findings have repeatedly cited late acknowledgments, wrong liability limits, adverse credit reporting on disputed amounts, and inadequate investigations.
- **Two-sided harm.** Approving everything rewards first-party misuse and writes off recoverable losses. Denying too much harms legitimate customers and creates regulatory findings. About 90% of disputes currently resolve in the consumer's favor *(Javelin/Mastercard 2026)*. That is fine if they're right, and expensive if they're not.

### Why it's hard
The difficulty doesn't come from volume of rules. It comes from **how the rules interact with time, evidence, and each other**:

1. **Two clocks that don't agree.** Reg Z gives the cardholder 60 days from the statement and gives the issuer two billing cycles (max 90 days) to resolve. Visa gives 120 days from processing, with 15-day waiting periods and merchant-contact prerequisites that Reg Z doesn't require. Losing the network deadline doesn't cancel the legal obligation.
2. **The obvious reason code is often invalid by rule.** A hotel bill above the quote is expressly **not** an "incorrect amount" (T&E quoted-vs-actual is excluded) and **not** "not as described" (price discrepancies are excluded).
3. **Rules change, and the effective date is keyed to a date you might not expect.** Visa's Compelling Evidence 3.0 changes on **24 October 2026**, keyed to the **dispute processing date**. The subscription rule changed on 18 April 2026.
4. **Liability rules aren't truth rules.** A merchant can satisfy "compelling evidence" with data an account-takeover attacker also has.
5. **The signal lives across cases.** Rings, compromise points, drop addresses and merchant failure clusters are invisible one case at a time.
6. **Evidence is adversarial, late, partial and messy.** Merchant packets advocate. Clearing credits arrive with no link to the original purchase. Proof of delivery can carry a partial address. Timestamps come in someone's local time.

### Why an agent beats a rules engine or a chatbot here

| | Rules engine | Single-prompt LLM | Agent system |
|---|---|---|---|
| Deciding which rule applies | Hard-coded mapping from claim code to reason code; breaks on invalid-dispute clauses and version changes | Picks a plausible code confidently; doesn't know April/October 2026 changes | Retrieves the rule *as of the governing date*, walks invalid-dispute lists, re-plans when a route fails |
| Finding facts | Only reads fields it was coded for | Only sees what's pasted in | Plans, calls tools, requests merchant evidence, waits for it, reads it |
| Contradictions | None; first matching rule wins | Tends to accept the narrative it was given | Tracks hypotheses and evidence for/against; detects conflicts between sources |
| Cross-case patterns | Threshold rules that over-fire (guilt by association) | No memory | Graph traversal over shared identifiers; records findings and applies bounded automated controls |
| Arithmetic and dates | Correct but only for anticipated formulas | Unreliable (pro-rata, FX, business days, time zones) | Sandbox computation with inputs recorded |
| Stale beliefs | Silent config drift | N/A | Governed memory with supersession, retraction, consolidation, expiry |
| Knowing when to stop, wait or challenge itself | Always runs the whole flow or none | Never doubts itself | Value-of-information stopping; suspend/resume on external events; automated review panel with a confidence threshold and a conservative default |

Section 3 of the case catalog lists, case by case, exactly how each alternative fails.

---

## 2. Domain background

*Full detail and citations: [`docs/research/01-domain-research.md`](docs/research/01-domain-research.md).*

### Who's involved
**Cardholder** → **Issuer** (the bank that issued the card; our perspective) → **Card network** (Visa) → **Acquirer** (the merchant's bank) → **Merchant**. Disputes travel issuer → network → acquirer → merchant and back.

### The lifecycle (Visa)
```
Cardholder contact ─► intake & triage ─► (pre-dispute: merchant contact, Order Insight / RDR)
     │                     │
     │                     ├─ Reg Z: acknowledge ≤30 days; resolve ≤2 billing cycles (≤90 days)
     │                     └─ Reg E: investigate ≤10 business days or provisional credit; ≤45/90 days
     ▼
Fraud report (TC40) ─► Dispute filed via Visa Resolve Online
                           │
       ┌───────────────────┴──────────────────────┐
  Allocation (10 Fraud, 11 Authorization)     Collaboration (12 Processing, 13 Consumer)
  acquirer pre-Arb ≤30d                        acquirer Dispute Response ≤30d
  issuer response ≤30d                         issuer pre-Arb ≤30d (must review evidence with cardholder)
  acquirer arbitration ≤10d                    acquirer response ≤30d → issuer arbitration ≤10d
                           │
                           ▼
       Cardholder resolution: credit / partial / explanation letter / re-bill with notice
```

### Reason codes ("dispute conditions")
Visa groups conditions into **10 Fraud** (10.1–10.5), **11 Authorization** (11.1–11.3), **12 Processing Errors** (12.2–12.7) and **13 Consumer Disputes** (13.1–13.9). Each condition has its own **reasons, rights, invalid-dispute list, time limit, and evidence requirements**. Mastercard (4808, 4837, 4853, 4834…), Amex (C02, C08, F29…) and Discover (UA02, RG…) have analogous schemes. The POC models Visa in depth; others are reference only.

### Regulation
- **Reg Z (credit):** billing-error notice within 60 days of the statement; the consumer needn't pay the disputed amount meanwhile; no adverse credit reporting; a reasonable investigation is required (no denying non-delivery without determining delivery; no affidavit under penalty of perjury; no automatic denial for non-cooperation); unauthorized-use liability ≤ $50 and excludes people with actual/implied/apparent authority; "claims and defenses" against the issuer for purchases still unpaid.
- **Reg E (debit):** 10 business days (20 for new accounts) to investigate or provisionally credit; 45/90 days total; $50/$500 liability tiers only when the card is lost or stolen; 5-business-day honoring period when reversing provisional credit.
- **Non-US equivalents** (PSD2, UK s.75, Singapore MAS) are in the research doc; out of POC scope.

### Friendly fraud (first-party misuse)
A cardholder disputes a purchase they made or benefited from. Prevalence estimates **disagree by 3–4×** (Visa: ~20% of fraud disputes; Mastercard-cited and vendor figures: 75–80%), because they measure different denominators and come from parties with different incentives. Networks now provide merchant-side liability shifts (**Visa CE 3.0**, **Mastercard First-Party Trust**) that match prior undisputed transactions on device, IP, login and address. Those decide **who pays**, not **who did it**.

### Where the complexity really comes from
Condition eligibility (invalid lists), time (processing dates, statement dates, business days, local time zones, effective dates), evidence format (full address, clear-text IP), mutual exclusivity (fraud vs non-fraud), amount limits (portion not received, unused portion), and the gap between network outcome and cardholder outcome.

---

## 3. Example investigations

The full set is in the [case catalog](docs/design/02-case-catalog.md). Four examples show why the data ecosystem has the shape it does.

### C11 — Takeover in a Friendly Mask (why graph memory and memory retraction exist)
A long-standing customer disputes a **$1,389** electronics order. The merchant's evidence packet says: same login as two prior undisputed orders, "IP match 198.18.201.x", account verified — **CE 3.0 met, first-party misuse**. Agent memory already holds **MEM-0142**: *"possible first-party misuse — apply heightened scrutiny"*, written after this customer's June claim was denied.
What the agent has to discover:
- The issuer's own event stream shows the phone number was changed via IVR two days earlier, then three failed logins from a VPN IP, then an SMS password reset minutes before the purchase.
- The merchant's packet includes (buried) a password reset, an email change and a new shipping address within 45 minutes of the order.
- The "IP match" is a truncated /24 on a carrier-grade-NAT range, which fails Visa's clear-text IP requirement.
- Graph traversal from the ship-to address finds **three other disputed transactions**, including the customer's **own June case**.

Outcome: credit the customer, file 10.4, lock and secure digital banking, **automatically reopen the June denial and credit $612** (no second network dispute — that transaction was already disputed and its window has passed), add the drop address to the ship-to watchlist, and **retract MEM-0142** with a correction note. A rules engine denies on the CE match. A chatbot trusts the memory note.

### C06 — Trial Trap (why versioned policy retrieval and re-planning exist)
A free trial converted into a **$119.88 annual** charge; the customer cancelled four days later. The obvious route, **13.2 Cancelled Recurring**, is **invalid**: since 18 April 2026 Visa excludes cancellations made after the transaction date. A precedent from March (PRE-0012) won under 13.2, and a memory note says so. The merchant never sent the trial-end notice Visa requires (amount, date, cancellation link, ≥7 days before). That routes to **13.5 Misrepresentation**, limited to the **unused portion**: 360/365 × $119.88 = **$118.24** (sandbox).

### C08 — Pump Six (why the router, the sandbox and graph analytics exist)
A debit customer reports **$1,299** of online fraud. Intake notes suggest a $50/$500 liability tier "because he saw an alert Saturday", and a stale bulletin (and memory) says "10 calendar days". Correct: the card wasn't lost, so **liability $0**. The transfers were within 30 days of the first deposit, so the new-account rule gives **20 business days** for provisional credit. With Columbus Day and Veterans Day in the bank calendar, that deadline is **2026-11-10**. A graph/SQL query over recent fraud victims surfaces **Pinegrove Fuel #22**, used by 9 other victims in the prior month, and a news article confirms a skimmer. The **$59** transaction is below the recovery threshold (credit the customer, don't charge back); the $1,240 goes to 10.4.

### C13 — The Agent Booked It (why suspend/resume and automated adjudication exist)
The customer's AI travel assistant (**TravelMind**, an "Agentic Payment Provider" under Visa's April 2026 rules) booked a **non-refundable** fare. The instruction said *"Refundable fare preferred. Max $450"* and the refundable fare was $489. Visa's agentic rules require the provider to use only cardholder-defined criteria and to get the cardholder's acknowledgment of responsibility, but **no dispute condition covers "my agent went outside my instructions."** The agent must show each condition it considered and why each fails, request the provider's instruction record, **suspend until it arrives on 23 Oct** (well before the latest safe decision date), then resume. The record shows "refundable" was parsed as a preference and confirmed back to the cardholder, and the booking notice disclosed the fare rules. So Reg Z finds no billing error; the review panel confirms; the claim is denied with an explanation and a machine-readable `policy_gap` record. Inventing a rule is the failure mode.

---

## 4. The data ecosystem

*Field-level detail: [data dictionary](docs/design/03-data-dictionary.md).*

### Inventory

| Layer | Content | Volume | Modality |
|---|---|---|---|
| Customers & households | customers, addresses, accounts (credit/debit), account holders (authorized users), cards, tokens | 381 customers · 406 accounts · 434 cards | structured |
| Merchants | merchants with MCC, acquirer, timezone, marketplace parent; descriptor history | 229 merchants · 254 descriptors | structured |
| Transactions | merged authorization + clearing with auth signals (AVS, CVV2, ECI, 3DS), COF type, clearing sequence, ARN, FX, links | 24,158 (3,551 payments, 122 credits) | structured |
| Statements | cycles, transmission dates, balances, payments | 5,264 | structured |
| Issuer security & activity events | logins, failed logins, password resets, phone changes, alerts, deposits, token provisioning | 8.7k | event stream |
| Disputes | cases, case–transaction links, lifecycle state, network references, separate cardholder vs network outcomes | 308 (95 open) | structured |
| Dispute events | intake, acknowledgments, provisional credits, filings, responses, closures, investigator notes | 1.3k | event stream |
| Communications | intake summaries, chats, secure messages, forwarded merchant emails, attachment descriptions | 283 | unstructured |
| Merchant/provider evidence | orders, shipments & tracking, proof of delivery, logins/IPs/devices, prior transactions, usage logs, folios, agreements, agentic instruction records | 82 packets | semi-structured |
| Research corpus | dated news, merchant terms snapshots (as-of), status pages, descriptor directories, provider terms | 19 docs | unstructured (dated) |
| Policy corpus | Visa conditions (versioned), Reg Z/E, internal SOPs (versioned), compliance bulletins (superseded + current), cardholder agreement | 34 docs | knowledge |
| Skills | investigation playbooks | 8 | procedural |
| Precedents | closed-case write-ups incl. contrast pairs, one flawed and one outdated | 39 | unstructured |
| Agent memory seed | notes: valid, stale, wrong, duplicate, noisy, prohibited; 2 episodic run traces | 25 notes | agent memory |
| Reference | code tables, MCCs, Visa conditions, bank holidays, FX rates, IP intelligence, cities | 14 tables | structured |
| Graph projection | nodes/edges derived from all of the above | 25.9k nodes · 49.3k edges | graph |
| Simulation | cardholder personas with disclosure rules and scripted replies | 20 personas (one per hero case) | harness |
| Ground truth | per-case expected decisions, facts, contradictions, computations, must/must-not, memory ops, checks, rubric; queue ranking; background labels | 21 + queue + 238 labels | evaluator only |

### Hero vs background
- **Hero records** (IDs in the `9xxxx` range) are hand-built to make a specific investigation necessary. Their IDs are listed in `ground_truth/hero_index.json`; the `is_hero` flag is **stripped** from every agent-visible file.
- **Planted clusters** mix hero intent with background customers: Oakhollow's insolvency cluster, the Pinegrove skimming victims, the Wharfside drop address, Quillmark's historical failures, and the porch ring.
- **Background** records give the patterns something to hide in: normal spending, subscriptions, refunds, ~200 closed and ~60 open routine disputes with labeled "true nature". About 10% of labeled historical decisions (18 of 180 closed) are deliberately wrong, as they are in real QA samples.

### The simulated clock
`AS_OF = Wednesday 2026-10-21 09:00 America/New_York`. Every record carries `available_at`. The harness advances a virtual clock, so merchant evidence, cardholder replies and late credits arrive **during** an investigation. It sits three days before the CE 3.0 change and inside several regulatory clocks.

---

## 5. Relationships and investigative paths

### The spine
```
Customer ─HOLDS─► Account ─HAS_CARD─► Card ─MADE─► Transaction ─AT─► Merchant ─ACQUIRED_BY─► Acquirer
   │                                              │    ▲                 ▲
   │ LIVES_AT / HAS_PHONE / HAS_EMAIL             │    │ DISPUTES        │ DESCRIBES
   ▼                                              │    │                 │
Address ◄─SHIPPED_TO / DELIVERED_TO───────────────┘  Dispute ─HAS_EVIDENCE─► EvidencePacket
   ▲                                                   │  ▲
   │                                                   │  └─DECIDED── Precedent
Customer ─BANKING_LOGIN_FROM─► Device ─HAS_FINGERPRINT─► DeviceFingerprint ◄─MERCHANT_SAW_FINGERPRINT─ Transaction
Customer ─BANKING_LOGIN_FROM─► IP ◄─MERCHANT_SAW_IP─ Transaction
```

### Paths the cases require (discoverable, not handed over)

| Path | Case | What it reveals |
|---|---|---|
| Transaction → Merchant ← Descriptor (history) ← other Transactions by same Card | C02 | "Unknown merchant" is a regular café renamed |
| Transaction.auth_code → sibling clearings → evidence packet shipments | C04 | one order, two shipments |
| Customer ← Card → Transactions (Ridehop at arrival/departure) | C05 | no car → parking not provided |
| Card ← victims' fraud Disputes → prior card-present Transactions → Merchant (group-by) | C08 | common point of compromise |
| Transaction → MerchantLogin / IP / DeviceFingerprint ← prior Transactions (+ Acquirer) | C09 | CE 3.0 qualification by version |
| Merchant packet `payment_method_events` → DeviceFingerprint ← Device ← Customer (banking logins) | C10 | the parent's phone saved the card |
| Transaction → SHIPPED_TO Address ← other disputed Transactions → Disputes → Customers | C11 | drop address shared with prior denied case |
| Customer → BANKING_LOGIN_FROM Device ← other Customers → FILED Disputes; Customer → HAS_PHONE ← Customer | C12 | four-person ring |
| Customer(90017) → no shared Device/Phone/IP with ring | C12b | negative result protects the innocent |
| Merchant(90023) ≈ Merchant(90024) (same brand) → historical Disputes → memory notes | C19 | pattern bounded in time |
| Disputes (open) → clocks (statement cycle, first deposit, response dates) | Q01 | what's due first |

### What's searchable vs traversable vs computed

| Need | Mechanism | Examples |
|---|---|---|
| **Searchable** (by meaning) | vector + keyword (FTS) | "price discrepancy T&E", "trial not clearly advised", similar precedent, merchant refund policy |
| **Traversable** (by relationship) | graph queries | shared devices/phones/addresses; descriptor → merchant; token → agentic provider |
| **Filterable / aggregable** (exact) | SQL | transactions by card in window; statements; open disputes by clock |
| **Computed** (never stored) | sandbox | deadlines, business days, pro-rata, FX, taxes, time-zone conversion, CE 3.0 day counts |

Deadlines are deliberately **not** stored in the data. A stored deadline would be an answer key.

---

## 6. Memory design

### Chosen stack (POC, local, no servers)
| Store | Technology | Why this one |
|---|---|---|
| Persistent / structured | **SQLite** (`catcher.sqlite`, built by `load_sqlite.py`; FTS5 over documents) | zero setup; exact queries; transactional case state |
| Semantic / vector | **sqlite-vec** in the same SQLite file (embeddings for documents, communications, precedents, packets, memory notes) | one file, filter by metadata (effective dates) *and* similarity |
| Graph | **LadybugDB** (embedded Cypher; community fork of Kùzu) loaded from `graph/*.jsonl`, with **NetworkX** as a fallback behind the same interface | multi-hop traversal without a server; Kùzu itself was archived in Oct 2025 |

Production equivalents behind the same interfaces: Postgres, pgvector, Neo4j (§13).

### What goes where, and why

| Information | Store | Investigative requirement that justifies it |
|---|---|---|
| Transactions, statements, accounts, cards, disputes, case state, deadlines inputs | **Persistent** | exact joins and sums (split clearings, statement cycles, paid-in-full); auditable system of record; transactional updates to case state |
| Account & dispute event streams | **Persistent** (append-only tables) | sequence reasoning (takeover chains), audit trail, late arrival |
| Stable merchant facts (MCC, acquirer, timezone, status), descriptor history | **Persistent**, projected to **graph** | same-acquirer test (CE 3.0), local-time conversion; descriptor → merchant resolution |
| Customer ↔ device / IP / phone / email / address; transaction ↔ ship-to / fingerprint / login; dispute ↔ transaction ↔ customer | **Graph** | rings (C12), drop addresses (C11), compromise points (C08), household authority (C10) are only visible across ≥2 hops |
| Network rules, regulation, SOPs, bulletins, cardholder agreement | **Semantic** (with version metadata; filtered by effective date) | the question is phrased in plain language ("price different from quote"); the answer depends on the date |
| Precedents, investigator notes | **Semantic** (+ graph edge to the decided dispute) | "similar case" retrieval, then **distinguish** on the one fact that differs |
| Communications, research pages, merchant statements | **Semantic** + **persistent** raw | narrative contradictions; dated external facts; exact quote recovery |
| Evidence packets | **Persistent** (raw JSON) + **graph** (identifier edges) + **semantic** (free-text fields) | exact fields for rule tests; identifiers for traversal; rebuttal text for reasoning |
| Code tables, holiday calendar, FX, IP intel | **Persistent** (reference) | deterministic lookups used by the sandbox |
| Agent long-term notes | **Persistent** (system of record for notes) + **semantic** index | retrieval by meaning; lifecycle state must be exact (supersede/retract) |

Rejected alternatives: putting policies in SQL tables only (keyword queries miss paraphrase; version filtering is then the only strength); putting transactions in the vector store (similarity is meaningless for amounts and dates); putting everything in the graph (poor for aggregates and text).

### Other memory kinds

| Kind | Warranted? | Why | Implementation |
|---|---|---|---|
| **Working memory** (per investigation) | **Yes** | L3/L4 cases accumulate 20–40 facts, hypotheses, open questions, computed deadlines; context windows can't hold raw tool output | structured case scratchpad: `facts[] (with sources)`, `hypotheses[]`, `open_questions[]`, `deadlines{}`, `plan[]`, `budget` — compacted between loop iterations |
| **Shared scratchpad** between subagents | **Yes, scoped** | parallel subagents (per folio line C05, per linked case C12, security vs merchant evidence C11) must not duplicate calls and must surface conflicts | append-only blackboard per case; subagents write findings with source IDs; the orchestrator reads and resolves |
| **Episodic memory** (run traces) | **Yes** | QA and post-mortems (the flawed run behind MEM-0142); lessons are derived from traces | `memory_seed/run_traces` schema; every run writes one |
| **Procedural memory** (skills) | **Yes** | condition-specific investigation steps shouldn't live in one giant prompt; loaded on demand by route | `data/corpus/skills/*.md` |
| **Semantic long-term notes** (agent-written) | **Yes, governed** | merchant patterns, procedural lessons, customer facts save work — and go stale | SOP-DSP-005 lifecycle: write / supersede / retract / consolidate / time-bound / dedupe / expire / purge |
| Per-customer "risk profile" memory | **No** (beyond factual history) | turns into labels and bias; SOP-DSP-004 forbids character judgments | facts only, with sources |

### Consolidation and forgetting, concretely
| Operation | Trigger in the data | Expected agent action |
|---|---|---|
| **Supersede** | MEM-0150 ($25 threshold) vs SOP v4 ($15); MEM-0152 (calendar days) vs CB-2025-09; MEM-0160 (13.2 wins) vs April 2026 rule | mark superseded, point to source (C03, C08, C06) |
| **Retract** | MEM-0142 wrong label contradicted by takeover evidence | retract with reason + correction note (C11) |
| **Consolidate** | eight raw Quillmark observations across two merchant IDs + an unbounded "rarely ships" note | one merchant pattern note valid 2026-01-01 → 2026-08-12 with sources; archive raw notes; supersede MEM-0209 (C19) |
| **Time-bound** | Quillmark changed fulfilment 2026-08-12; CE 3.0 same-merchant belief (MEM-0151) expires 2026-10-24 | set `valid_to`, keep history |
| **Dedupe** | MEM-0180 / MEM-0181 | archive duplicate |
| **Expire** | MEM-0185 tool-timeout noise | TTL removal |
| **Purge** | MEM-0196 demeanor/age-based note | purge content, keep tombstone |
| **Write (graph)** | ring (C12), compromise point (C08), drop address (C11) | finding nodes/edges with evidence and `status=active`; bounded controls (watchlists, monitoring) — never account closure |

### Up front vs generated dynamically

| Exists up front | Generated during investigation |
|---|---|
| System-of-record data, events, statements | investigation plan and re-plans |
| Policy corpus with versions; skills | evidence matrix (fact → source → supports/contradicts) |
| Precedents; research corpus | computed deadlines, amounts, CE 3.0 counts (sandbox notebooks) |
| Merchant evidence **once requested and arrived** (`available_at`) | hypotheses and their status |
| Seed memory notes and traces | review-panel positions and adjudications; automated actions; policy-gap records |
| Graph projection of stored relationships | inferred graph edges (ring, compromise point, drop address) |
| | decision record, customer letters, memory writes, run trace |

---

## 7. The evidence ecosystem

### What the agent can discover, compare, validate and weigh

| Evidence | Holder | Discover via | Validate how | Weight depends on |
|---|---|---|---|---|
| Authorization signals (ECI/CAVV, CVV2, AVS, POS entry, COF type) | issuer | transactions | reference tables | condition (ECI 5 + CAVV invalidates 10.4; CVV2 N approved invalidates 10.4) |
| Clearing (processing date, sequence, ARN, FX) | issuer/network | transactions | sandbox grouping | duplicates vs split shipments; time limits |
| Statements & payments | issuer | statements | sandbox | Reg Z windows; claims-and-defenses outstanding balance |
| Security events | issuer | account_events | sequence analysis | takeover vs participation |
| Order / shipment / POD | merchant, carrier | evidence packets (late) | **full address**, photo vs house number, GPS | 13.1 validity |
| Login / IP / device / prior transactions | merchant | Order Insight / pre-Arb packets | **format rules**, version, counting rules, same acquirer | CE 3.0 liability — *not* truth |
| Digital usage logs | merchant | packets | device continuity | participation; refund-policy eligibility |
| Folios, registration cards, valet logs | merchant | packets | line-by-line vs disclosures | partial disputes |
| Agreements, cancellation acknowledgments, badge scans | merchant | packets | dates vs charges | 13.2 validity; post-cancellation use |
| Agentic instruction record | provider | written request (late) | hard constraints vs preferences | policy gap framing |
| Communications | cardholder, merchant | communications | cross-contact consistency | contradictions |
| Research pages | public | research tool | `captured_at` vs relevant date | insolvency waivers; as-of terms |
| Precedents | issuer | semantic search | rule version applied; distinguishing fact | persuasive, never binding |
| Memory notes | agent | memory search | source refs; validity window; current sources | lead only |

### Typically available vs typically missing
- **Always available:** issuer-side authorization, clearing, statements, security events, intake narrative.
- **Often late or missing:** merchant evidence (small merchants aren't enrolled in Order Insight: C16; bankrupt merchants return nothing: C01), provider records on request (C13).
- **Sometimes misleading:** merchant CE claims (C09 overcount; C11 truncated IP), rep coding (C02, C05), stale memory (C03, C19), precedents (C06, C11).

### Conflicts are first-class
Each hero ground truth lists `contradictions[{between, resolution}]`. The evaluator checks that the agent **noticed** each one, not just that the final outcome was right.

---

## 8. The policy ecosystem

### Layers and precedence
1. **Regulation** (Reg Z / Reg E) — binding legal floor for the **cardholder** outcome.
2. **Network rules** (Visa) — govern **recovery** from the merchant; can be stricter or looser than regulation, never a reason to deny a regulatory right.
3. **Internal SOPs** — how Lanternfield operationalizes 1 and 2 (thresholds, automated governance, fairness, memory governance); cannot override 1.
4. **Compliance bulletins** — interpretive updates to SOPs; can be superseded.
5. **Cardholder agreement** — contract terms (FX, authorized users); cannot waive regulatory rights.
6. **Precedents and memory** — persuasive context only.

When a network rule gives no recovery right but regulation requires a credit, the issuer credits and absorbs the loss (PRE-0010, PRE-0017). When a network right exists but the facts show no billing error, the issuer denies despite a winnable chargeback (C09).

### Versioning
Every policy document carries `doc_id@version`, `effective_from`, `effective_to`, `status` (`active` / `superseded` / `scheduled`), and `supersedes`/`superseded_by`.

| Versioned pair | Governing date | Case |
|---|---|---|
| `VISA-10.4@2026-04-18` → `VISA-10.4@2026-10-24` (scheduled) | dispute **processing** date | C09 |
| `VISA-13.2@PRIOR` → `VISA-13.2@2026-04-18` | dispute processing date | C06 (and outdated PRE-0012) |
| `LFB-SOP-DSP-002@v3` → `@v4` ($25 → $15) | intake date | C03 |
| `LFB-CB-2025-03` → `LFB-CB-2025-09` (calendar → business days) | notice date | C08 |

### Exceptions and waivers encoded in the corpus
Insolvency waives the 13.1 waiting period; merchant refusal waives the 13.3/13.7 waiting period; the more-than-one-night no-show rule works independently of cancellation timing; the Reg E new-account and POS extensions; the loss/theft trigger for Reg E liability tiers; Visa certification-in-lieu-of-letter for secure-channel intake; CE 3.0 format and counting footnotes.

### Provenance
Visa documents are **paraphrases** of the public April 2026 rules, with section and rule IDs. Regulation documents are abridged **verbatim** federal text. Everything with `LFB-` is **invented** for the POC. See `provenance` in each file's front matter.

---

## 9. How the dataset is generated

### Principles
- **Entity- and event-sequence-based, with explicit relationship seeding.** Research shows row-independent tabular generators (CTGAN, TVAE, GaussianCopula) can't reproduce temporal bursts or multi-account graph motifs (arXiv 2604.13125). Patterns are planted as relationships, not hoped for.
- **Hero cases are code**, not prose: each builder creates the customer, history, merchant, transactions, events, communications, evidence packets, research pages, persona and ground truth together, so they can't drift apart.
- **Deterministic:** fixed seed; identical output on every run.
- **Validated:** `validate.py` runs 401 checks, including **discoverability queries** — for example, that a plain SQL group-by ranks Pinegrove Fuel #22 as the top compromise point, and that shared banking devices connect exactly the four ring members and not the innocent neighbor.

### Background distributions (current settings)
| Dimension | Setting |
|---|---|
| Cities | 12 US metros, weighted (Columbus 14 … Seattle 7) |
| Products | 75% credit only · 10% debit only · 15% both; 12% of credit accounts have a household authorized user with a shared tablet |
| Tenure | 2008–2026, skewed to recent years |
| Payment behavior | 55% pay in full · 35% partial · 10% minimum |
| Spending (per month, ×0.6) | grocery 1.6 · restaurant 0.9 · fast food 0.6 · fuel 0.6 (70% drive) · e-commerce 0.45 · digital 0.3 · rideshare 0.3 · travel/tickets rare |
| Subscriptions | streaming 50% · telecom 30% · utilities 30% · gym 15% · boxes 10% |
| Refunds | 3% of e-commerce, 0.4% of in-store (≈30% without original-transaction link) |
| Card-absent authentication | 3DS 45%; AVS Y 80% / Z 8% / A 4% / N 3% / U 5% |
| Background disputes | 238, family mix: fraud CNP 37% · not received 16% · recurring 10% · not as described 9% · credit not processed 6% · cancelled 5% · descriptor confusion 5% · duplicate 4% · card-present fraud 4% · incorrect amount 3% |
| True-nature mix within fraud | third-party 70% · first-party 18% · ATO 7% · household 5% |
| Historical decision error rate | ~7% of routine closed disputes labeled incorrect in hindsight (plus the planted flawed ATO denial) |

These are **POC assumptions**, chosen to be plausible and to make patterns neither trivial nor invisible. They are not calibrated to any issuer's real data.

### Planted structures
| Structure | Seeding |
|---|---|
| Merchant insolvency cluster | 4 background non-receipt disputes + 2 earlier fulfilled orders (C01) |
| Compromise point | 9 victims with card-present use at one pump in a 13-day window → CNP fraud 9–14 days later; 25 non-victim visitors earlier (noise) (C08) |
| Drop address | 4 disputed transactions, 3 customers, one wrongly denied (C11) |
| First-party ring | 4 customers, 2 shared banking devices, 1 shared alternate phone, 10 non-receipt claims, 3 merchants; plus a same-area innocent control (C12/C12b) |
| Merchant pattern with a change point | 11 failures Jan–Jul across two merchant IDs; 6 clean orders after the change (C19) |
| Descriptor migration | old descriptor retired, new one introduced (C02); POS vendor descriptors on 50% of grocers |
| Policy changes | effective dates straddling `AS_OF` (C06, C09, C03, C08) |

### Controlling difficulty
| Knob | Easier | Harder |
|---|---|---|
| Signal strength | more shared identifiers; POD photos contradict clearly | fewer shared identifiers; more noise visitors at the compromise point |
| Evidence timing | packets available before `AS_OF` | packets arrive after `AS_OF`; some never arrive |
| Narrative honesty | persona discloses on first question | persona discloses only when shown specific evidence |
| Memory hygiene | no stale notes | more conflicting notes with high `access_count` |
| Policy proximity | `AS_OF` far from effective dates | `AS_OF` straddles changes |
| Background volume | fewer customers per city | more customers, more disputes per merchant |
| Label noise | 0% wrong historical decisions | 10–15% wrong, including precedents |

### Scaling to a fuller dataset
Raise `n_primary` and `RATE_MULT`; add more hero templates as parameterized *scenario families* (e.g. generate 50 variants of "trial trap" with varied notice compliance, usage and cancellation timing, each with computed ground truth). Add Mastercard as a second rulebook; add wallet tokens; add multi-network portfolios; add call-audio transcripts with ASR errors.

---

## 10. Architecture component → the scenario that forces it

Machine-checkable version: `data/generated/ground_truth/capability_coverage.json` (generated from `data/generator/capabilities.py`); each case's ground truth lists its `required_capabilities` with necessity, reason and the trajectory signals that prove use, and `validate.py` enforces that every mandatory component is primary in at least two cases.

Each row names the case that breaks if the component is removed.

| Component | Forcing scenario(s) | What breaks without it |
|---|---|---|
| **Agents** (autonomous investigators with goals) | C05, C11, C15 | Fixed scripts can't choose which evidence to pursue next when facts contradict (upgrade initials vs testimony; merchant CE vs issuer security logs; late merchant response) |
| **Router** | C02 (not a dispute), C07 (not a network issue), C08 (Reg E vs Reg Z), C13 (novel type), C17 (expired), Q01 (portfolio) | Every claim runs the same heavy flow: C02 gets a card reissue, C08 gets Reg Z clocks, C13 gets forced into 10.4 |
| **Loop engineering** with termination | C02, C03, C17, C18 stop early; C09 and C15 wait for events; C11/C12 run long | No stopping rule → over-investigation of $12 claims; no wait state → decisions made before evidence arrives (C03 packet at 11:00, C13 record on 23 Oct) |
| **Agent graph** (plan → gather → verify → decide → act, with re-plan edges) | C06 (verifier invalidates 13.2 → re-plan), C09 (claim family changes mid-case), C15 (new evidence flips one charge) | Linear chains commit to the first route; no edge back from "verify" to "plan" |
| **Subagents** | C05 (per folio line), C08 (graph analyst + Reg E clock specialist), C11 (security events vs merchant packet vs graph), C12 (per linked case), Q01 (per case clock computation) | One context holds 10 cases' evidence and loses track; no independent perspectives for adversarial review |
| **Tool / function calling** | every case | Data, evidence requests, messaging, research and memory are only reachable through tools |
| **Harness** | C03/C09/C13/C18 (virtual clock & `available_at`), C02/C04/C09/C10/C15/C19 (simulated cardholder), C03/C13/C15 (suspend & resume), all (budgets, trace capture) | Nothing arrives late, nobody replies, runs can't checkpoint and resume on events, evaluation can't replay runs |
| **Skills** | C05 (lodging), C06 (recurring/trial), C08 (Reg E clocks), C09/C11 (CNP fraud), C01/C12 (not received), C10–C13 (automated adjudication) | A monolithic prompt with every condition's rules; condition-specific steps get skipped or mixed |
| **Persistent memory** | C04 (clearing sequences), C15 (lifecycle state + billing cycles), C17 (paid-in-full), C18 (out-of-order credit) | Exact joins, sums and case state are impossible to answer from text retrieval |
| **Graph memory** | C08 (compromise point), C11 (drop address), C12 (ring), C12b (negative result), C10 (household device) | Patterns only exist across entities; per-case retrieval never finds them; SQL self-joins become unmaintainable at 3+ hops |
| **Semantic / vector memory** | C05 (12.5/13.3 exclusions phrased differently from the claim), C06 (trial language), C14/C05/C06/C17 (similar precedents to distinguish), C16 (policy snapshots) | Keyword search misses paraphrase; the agent can't find the rule or the look-alike precedent |
| **In-case working memory / scratchpad** | C11 (hypotheses), C12 (10 cases), C15 (two tracks), C05 (line decisions) | Facts and open questions scroll out of context; hypotheses collapse early |
| **Memory write (agent chooses)** | C01 (merchant insolvency), C08/C11/C12 (graph hypotheses), C09 (factual note, not label), C11 (correction) | Lessons don't persist; the next analyst repeats the work — or the wrong label persists |
| **Consolidation & forgetting** | C19 (consolidate + time-bound), C03/C06/C08 (supersede), C11 (retract), memory seed (dedupe, expire, purge) | Stale beliefs outvote current policy; wrong labels harm customers; memory grows without bound |
| **Sandbox / REPL** | C04, C05, C06, C07, C08, C14, C15, C17, C18, Q01 | Pro-rata, FX, tax, time zones, business days, billing cycles computed by an LLM → wrong deadlines and amounts |
| **Research** | C01 (bankruptcy waiver), C02 (descriptor directory), C06/C16 (dated snapshots), C08 (skimmer report), C10 (minor refund window), C13 (provider terms), C17 (refund portal), C19 (fulfilment change) | The decisive fact isn't in the bank's systems |
| **Agent read paths** | all — data, events, packets, policy, precedents, research, memory, graph | — |
| **Agent write paths** | case state/decisions (all), evidence requests & messages (C02, C04, C09, C10, C13, C15, C19), memory ops (C03, C06, C08, C11, C12, C19), graph hypotheses (C08, C11, C12), case split (C03) | The agent can only advise; no auditable actions |
| **Automated governance (replaces human-in-the-loop)** | C10 (authority judgment), C11 (reopen closed case), C12 (organized abuse), C13 (policy gap); `LFB-SOP-DSP-003@v6` | Without an adversarial review panel, confidence threshold, conservative default and bounded controls, an unsupervised agent either oversteps (closes accounts, invents rules, denies on linkage) or can't decide the hard cases at all |
| **Evaluation** | every case's `deterministic_checks`, `must_not`, `contradictions`, `memory_ops`, `rubric`, `budget`; Q01 ranking; background labels; pass^k | No way to tell a lucky demo from a reliable system |

### Evaluation design
- **Deterministic checks** against the decision record: condition, amounts (with tolerance), outcome, adjudication (panel used, conservative default), automated actions, deadlines, memory operations.
- **Process checks:** required key facts found (by source ID), contradictions surfaced, `must_not` actions absent, required policy versions cited.
- **Rubric (LLM-as-judge, calibrated against the deterministic checks and ground-truth rubric notes):** explanation quality, tone, distinguishing precedents, quality of review-panel arguments and flip facts.
- **Reliability:** pass^k over repeated runs (τ-bench style). A dispute decision that flips between runs is itself a compliance defect.
- **Efficiency:** tool calls vs `budget.expected_tool_calls`; early termination on L1 cases.
- **Portfolio:** Q01 ranking correlation (Kendall τ) with ground truth; background open-case label accuracy.
- **Safety & fairness:** zero prohibited-basis content in memory writes and letters; no guilt-by-association (C12b).

---

## 11. Agent behavior this data enables

Behaviors the data makes **necessary**, not just possible:

- **Changing course mid-investigation** — C06 (route invalidated), C09 (claim becomes a quality complaint), C15 (late response flips one charge), C11 (hypothesis overturned).
- **Detecting contradictions** — testimony vs signed documents (C05), narrative vs order quantity (C04), merchant "verified" vs merchant's own account-change log (C11), memory vs policy (C03, C08), yesterday's reputation vs today's delivery scan (C19).
- **Deciding further digging isn't worth it** — C02, C03 ($12.49), C17 (all windows closed), C18 (credit arrived).
- **Stopping to ask** — C09 (show evidence, then ask), C10 (did you ever save the card?), C15 (certification requires cardholder review).
- **Challenging its own decision** — review panel on C10, C11 (reopen), C12, C13; conservative default when confidence stays below 0.75.
- **Waiting instead of guessing** — C03 (packet due today), C13 (instruction record due 23 Oct), C15/C09 (cardholder replies).
- **Separating "who pays" from "what happened"** — C08 ($59 credited, not charged back), C09 (network might favor the cardholder; facts don't), PRE-0010 (issuer absorbs).
- **Reasoning about which of several policies governs** — C05 (12.5 vs 13.3 vs 13.1), C06 (13.2 vs 13.5), C16 (13.3 vs 13.7), C17 (13.1 vs Reg Z 13 vs 12(c)).
- **Temporal reasoning** — processing vs transaction dates, statement transmission, business days, time zones, effective dates, snapshot capture dates, memory validity windows.
- **Distinguishing precedents** — PRE-0007 (no initials), PRE-0012 (old rule), PRE-0019 (late call), PRE-0017 (balance outstanding), PRE-0031 (flawed).
- **Fairness under suspicion** — C09 (no labels), C12b (innocent neighbor), MEM-0196 (purge).
- **Governing its own memory** — every lifecycle operation appears at least once.

Where sophisticated behavior **emerges** rather than being scripted: the order in which the agent gathers evidence (C11 can start from the merchant packet or the security log); whether it discovers the ring from the trigger case or the queue; which precedent it finds first; how it phrases a partial denial. The ground truth constrains outcomes and required findings, not the path.

---

## 12. Why this is a compelling demonstration

### For a financial-services audience
- It uses **real, current rules**: the April 2026 Visa edition, including changes effective in the demo week, Visa's agentic-commerce rules, and actual Reg Z/E standards. The traps are the ones QA teams find.
- It separates **cardholder outcome** from **recovery**, which is how issuers actually lose money and draw regulatory findings.
- It shows **judgment, not just automation**: fast closes on trivial cases, deep work on ambiguous ones, and hard judgment calls decided automatically through an auditable review panel that records every position, the confidence and the fact that would flip the outcome.
- It treats **fairness and memory governance** as operational controls, not slogans.

### For an AI-engineering audience
- Every component is **load-bearing**, with a named scenario that fails without it.
- It exercises the hard parts of agents: **versioned retrieval, late evidence, re-planning, cross-case graph reasoning, tool-grounded arithmetic, suspend/resume on external events, self-adjudication without humans, and memory that can be wrong**.
- It's **evaluable**: deterministic checks, process checks, reliability over k runs, and portfolio-level metrics, all on reproducible synthetic data.
- The non-obvious insights make the audience lean forward: *CE 3.0 is a liability rule, not a truth rule*; *the regulatory clock and the network clock are different races*; *the most dangerous memory is the one that's confidently stale*; *there is a live payments rulebook for AI agents with no dispute path yet*.

---

## 13. From POC to production

| Area | POC | Production |
|---|---|---|
| Data | synthetic, 380 customers | real system-of-record integrations (card processor, core banking, CRM, VROL/Mastercom APIs, Order Insight, Ethoca), streaming ingestion, PII vaulting, tokenized PANs |
| Stores | SQLite + sqlite-vec + LadybugDB | Postgres (+ pgvector) with row-level security, Neo4j/graph service, object store for documents; lineage and retention policies |
| Rules | paraphrased Visa excerpts; Visa only | licensed full rulebooks for all networks, owned by a rules team, change-managed with effective-date releases and regression suites; Mastercard/Amex/Discover |
| Regulation | Reg Z/E, US only | legal-reviewed interpretations, state law, UDAAP, ECOA/Reg B, FCRA furnishing, SCRA; non-US regimes where issuing |
| Decisions | agent decides L1–L3 in simulation | autonomy by case class gated on measured accuracy; review-panel thresholds tuned on historical outcomes; automated kill switches and rollback when accuracy or complaint metrics drift |
| Explainability & audit | run traces | immutable audit logs, reproducible model/prompt/tool versions per decision, examiner-ready case files, adverse-action-style explanations |
| Model risk | none | SR 11-7-style model risk management: validation, bias testing, drift monitoring, challenger models, periodic revalidation |
| Evaluation | 20 hero cases + labels | thousands of labeled historical cases, continuous QA sampling, shadow mode against historical decisions, pass^k gates on release |
| Security | none | prompt-injection defense on merchant-supplied documents (they are adversarial inputs), tool permissioning, least privilege, secrets management, red-teaming |
| Memory governance | SOP document | enforced schemas, write approvals for high-impact notes, automated expiry/revalidation jobs, privacy deletion workflows |
| Operations | batch runs | queue integration, SLAs and deadline alerting, degraded-mode automation on outages (conservative defaults, deadline-first queues), cost controls per case class |
| Fairness | guardrail rules and checks | disparate-impact monitoring on outcomes by protected-class proxies (analysis only), documented remediation |
| Vendor landscape | — | integrate or compete with Visa Dispute Intelligence / Doc Analyzer / Case Manager, Quavo, Pega Smart Dispute; decide build vs buy per layer |

---

## 14. Assumptions, inventions, and open questions

### Invented for the POC (flagged in data provenance)
- Lanternfield Bank and all its SOPs, thresholds ($15 write-off, $100 fraud recovery, $500 review-panel threshold, 0.75 confidence threshold), automated governance rules, memory governance, bulletins and cardholder agreement.
- Every person, merchant, address, research page, provider (TravelMind) and product name.
- Background distributions (§9), historical error rate, analyst names.
- Operational interpretation of the pre-October CE 3.0 rule as "same merchant" (from Visa's change summary, not explicit text).
- Reg Z "two complete billing cycles" computed as the end of the second cycle after the one containing the notice.

### Not verified in research (see research doc §11)
Mastercard lifecycle and fee details (official guide blocked); AVS/CVV2/ECI/3DS code tables (practitioner knowledge); Singapore MAS timelines; Capital One–Discover network status; human-operations tiers and handle times.

### Choices between alternatives
- **Issuer-side** rather than merchant-side (the brief's "issuer must investigate"; regulatory obligations make it harder and more interesting).
- **Visa in depth** rather than shallow coverage of four networks (rule precision is the point).
- **Paraphrased rules** rather than verbatim (copyright; the POC needs structure and IDs, not the full text).
- **Evidence packets as documents** rather than full merchant databases (issuers only see what merchants send).
- **Deadlines computed, not stored** (stored deadlines leak answers).
- **`AS_OF` in October 2026** rather than today (to straddle real rule changes).

### Questions that would improve this (not blocking)
1. Which **LLM provider/models and agent framework** will the POC use? Tool schemas and the decision-record contract could be tailored.
2. The system is **fully automated** by design. Should regulator-facing letters also be generated automatically, or only the decision record?
3. Is a **second network (Mastercard)** worth the added corpus for your audience, or is Visa depth enough?
4. Do you want **scenario families** (many parameterized variants per hero) for statistically meaningful evaluation, or are 20 hand-built cases the right size for now?
5. Will the audience include **compliance/legal** reviewers? If so, add verbatim Reg Z/E commentary and a legal-review flag on the fictional SOPs.
