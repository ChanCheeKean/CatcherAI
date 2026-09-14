# 02 — Case Catalog

> The investigation problems the agent system must solve. Every case is grounded in a rule verified in [`../research/01-domain-research.md`](../research/01-domain-research.md). Every case lists what it proves, the route it forces, the architecture components it exercises, the expected investigative path (including pivots), and what a rules engine and a single prompt get wrong.
>
> Machine-readable ground truth for every case lives in `data/generated/ground_truth/cases/<case_id>.json`. This document is the narrative version.

## 0. The simulated world

| Setting | Value | Why |
|---|---|---|
| Issuer | **Lanternfield Bank, N.A.** (fictional) | Issuer-side perspective |
| Products | Lanternfield Visa Signature (credit → **Reg Z**), Lanternfield Visa Debit (**Reg E**) | Two regulatory regimes, one network |
| Network | Visa (April 2026 rules), paraphrased into `data/corpus/policies/` | Deepest verified rule text |
| Simulation clock `AS_OF` | **Wednesday 2026-10-21 09:00 America/New_York** (13:00 UTC) | Three days before the Visa CE 3.0 change (processing date Sat 24 Oct → first business day Mon 26 Oct); after the 18 Apr 2026 rule changes; mid-way through several Reg E / Reg Z clocks |
| Future-dated records | Every record has `available_at`; tools must not return records whose `available_at` > the harness clock | Late merchant evidence, cardholder replies, and out-of-order clearing records are real |
| Identities | Fictional names; `@example.com/.net/.org` emails; `555-01xx` phone numbers; IPs from `198.18.0.0/15` (benchmark range) and `203.0.113.0/24` (documentation range); masked PANs on BINs `400012`/`400034` | Obviously fake on inspection, correctly formatted |

## 1. Case map

| # | Case ID | Code name | Depth | Regime | Final route | Headline |
|---|---|---|---|---|---|---|
| C01 | DSP-2026-90001 | **Went Dark** | L2 | Reg Z | 13.1 | Furniture never shipped; merchant went bankrupt; research waives Visa's waiting period |
| C02 | DSP-2026-90002 | **Coffee by Another Name** | L1 | Reg Z | no dispute | "Unrecognized" charge is the cardholder's usual café under a new payment-facilitator descriptor |
| C03 | DSP-2026-90003 | **The Stale Threshold** | L1/L2 | Reg Z | split → write-off + 13.1 | Intake bundled two same-merchant claims into one case; one qualifies for write-off under the *current* SOP, the other only under the *superseded* one that agent memory still remembers |
| C04 | DSP-2026-90005 | **Split, Not Double** | L2 | Reg Z | no dispute | "Charged twice" is one authorization cleared in two shipments |
| C05 | DSP-2026-90006 | **The Folio** | L3 | Reg Z | partial 13.1 | Hotel bill above quote: two of three contested lines are valid charges, one (parking, no car) is not — and the obvious reason codes are invalid |
| C06 | DSP-2026-90007 | **Trial Trap** | L3 | Reg Z | 13.5 (not 13.2) | Free trial → annual charge; 13.2 is invalid under the April 2026 rule; missing trial-end notice routes to 13.5 for the unused portion |
| C07 | DSP-2026-90008 | **Lost in Conversion** | L2 | Reg Z | no dispute + fee reversal | "Merchant refunded less" is an exchange-rate movement; the fix is the issuer's own fee, not a chargeback |
| C08 | DSP-2026-90009 | **Pump Six** | L3 | **Reg E** | 10.4 + write-off | Debit CNP fraud on a new account; business-day clocks with a bank holiday; compromise point discovered via graph |
| C09 | DSP-2026-90010 | **The Clock on CE 3.0** | L3 | Reg Z | deny (no dispute) | Digital-goods "fraud" whose network validity flips on 24 Oct; cardholder's story changes after evidence review |
| C10 | DSP-2026-90011 | **The Family Tablet** | L4 | Reg Z | deny (review panel) | Child's in-game purchases; apparent authority vs "never gave permission"; merchant minor-refund window closing |
| C11 | DSP-2026-90012 | **Takeover in a Friendly Mask** | L4 | Reg Z | 10.4 + automated reopen | Merchant "proves" friendly fraud; issuer logs show account takeover; prior denial and a memory label were wrong |
| C12 | DSP-2026-90013 | **Porch Ring** | L4 | Reg Z | deny + automated controls | Ten non-receipt claims across four "unrelated" customers; the ring is only visible by traversal |
| C12b | DSP-2026-90014 | **Wrong House** | L2 | Reg Z | 13.1 | Same merchant, same week, neighboring suburb as the ring — but this one is a genuine misdelivery. Guilt-by-association trap |
| C13 | DSP-2026-90015 | **The Agent Booked It** | L4 | Reg Z | wait → deny (policy gap recorded) | AI travel agent bought a non-refundable fare; Visa agentic rules exist, no dispute condition does |
| C14 | DSP-2026-90016 | **Three Time Zones** | L2 | Reg Z | 13.7 full | Hotel no-show; cancellation was on time in hotel-local time; a precedent that looks identical lost on the same arithmetic |
| C15 | DSP-2026-90017 / -90018 | **Membership Mid-Flight** | L3 | Reg Z | accept response + new 13.2 | Case already in the network lifecycle; merchant's late response flips one charge and not the other |
| C16 | DSP-2026-90019 | **The Listing Changed** | L2 | Reg Z | 13.3 (13.7 acceptable) | Refurbished laptop; return refused under a policy the merchant added *after* the sale; needs a dated page snapshot |
| C17 | DSP-2026-90020 | **Too Late, Still Helpful** | L2 | Reg Z | decline + redirect | Cancelled concert; every dispute window has closed; claims-and-defenses fails because the balance was paid; a refund portal is still open |
| C18 | DSP-2026-90021 | **Refund Crossed in the Mail** | L1/L2 | **Reg E** | no dispute; reverse provisional credit | Marketplace refund posts after provisional credit; Reg E reversal notice rules |
| C19 | DSP-2026-90022 | **Yesterday's Reputation** | L2 | Reg Z | withdrawn | Consolidated memory says this merchant never ships; that stopped being true in August |
| Q01 | — | **Monday Morning Queue** | meta | both | prioritization | Rank the open backlog by the clocks that are actually about to expire |

Depth: **L1** fast path (≤ ~6 tool calls, should terminate early) · **L2** standard investigation · **L3** multi-source, requires computation and re-planning · **L4** cross-case / policy-gap / high-impact decisions that require the automated review panel.

> **Fully automated.** No case involves a human. High-impact or uncertain decisions go through the automated review panel defined in `LFB-SOP-DSP-003@v6` (cardholder advocate, issuer/merchant advocate, independent adjudicator, verifier checks; confidence ≥ 0.75 or a conservative cardholder-favorable default). Runs pause only for external events (merchant evidence, simulated cardholder replies, scheduled follow-ups).

## 2. Required capabilities — every one is needed to solve real cases

These are **mandatory** for the implementation. A capability is *primary* for a case when the case cannot be solved correctly without it. Machine-readable version: `data/generated/ground_truth/capability_coverage.json`; per-case `required_capabilities` (with the reason and the trajectory events that prove use) are in each ground-truth file. `validate.py` fails if any capability is primary in fewer than two cases. Source: `data/generator/capabilities.py`.

| Required capability | Cases that **cannot be solved** without it (primary) | Also used in | Proof in the trajectory |
|---|---|---|---|
| **Agents** | C05, C11, C15 | C01, C04, C06 | plan_created; plan_updated (agent-initiated); hypothesis_updated |
| **Router** | C02, C03, C07, C08, C13, C17, C18, Q01 | C01 | route_decision {route_id, method: rule|llm, confidence} |
| **Loop engineering (real termination conditions)** | C01, C02, C03, C12, C13, C17, C18 | C04, C09, C11, C15, C19 | termination {reason}; wait_suspended {until, latest_safe_decision}; wait_resumed |
| **Agent graph engineering** | C06, C09, C10, C11, C12, C15 | C05, C13, Q01 | node_entered / node_exited; edge_taken {from, to} incl. back-edges |
| **Subagents** | C05, C08, C10, C11, C12, C13, Q01 | C15 | subagent_started {name, parent_span_id}; subagent_finished {result_summary}; panel_position / adjudication |
| **Tool / function calling** | C01, C02, C13, C16 | C04, C07, C08, C12b, C14, C18, C19 | tool_call {tool, args}; tool_result {status, source_ids} |
| **Harness** | C02, C03, C04, C09, C10, C13, C15, C19 | C18, Q01 | clock_advanced; evidence_arrived {packet_id}; persona_reply; eval_scored |
| **Skills** | C01, C05, C06, C08, C10, C14 | C03, C09, C11, C12, C16 | skill_loaded {skill} |
| **Memory — persistent (SQLite system of record)** | C01, C04, C05, C11, C15, C17, C18, Q01 | C07, C08, C12 | tool_call sql_query / get_* with row ids in tool_result |
| **Memory — graph** | C02, C08, C10, C11, C12, C12b | C19 | graph_query {cypher|pattern, node_ids}; graph_write {node|edge, status} |
| **Memory — semantic / vector** | C01, C05, C06, C07, C09, C13, C14, C16 | C03, C10, C12b, C17 | retrieval {query, filters: as_of/status/validity, doc_ids} |
| **Sandbox / REPL** | C04, C05, C06, C07, C08, C09, C14, C15, C17, C18, Q01 | C01, C03 | computation {code, inputs, output} |
| **Agent read paths (selective read)** | C03, C06, C08, C09, C11, C16, C19 | C05, C14 | memory_read {filters}; memory_verified / memory_rejected {note_id, reason} |
| **Agent write paths (selective write, consolidation, forgetting)** | C02, C03, C06, C08, C09, C11, C12, C12b, C13, C19 | C01, C10 | memory_write / memory_supersede / memory_retract / memory_consolidate / memory_purge; write_rejected {reason}; automated_action |

## 2b. Detailed coverage matrix

Legend: ● primary demonstration · ○ exercised

| Component | C01 | C02 | C03 | C04 | C05 | C06 | C07 | C08 | C09 | C10 | C11 | C12 | C12b | C13 | C14 | C15 | C16 | C17 | C18 | C19 | Q01 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Router (triage / regime / claim family / depth) | ○ | ● | ● | ○ | ○ | ○ | ● | ● | ○ | ○ | ○ | ○ | ○ | ● | ○ | ○ | ○ | ● | ● | ○ | ● |
| Loop engineering (termination, budget, wait-for-event) | ○ | ● | ● | ○ | ○ | ● | ○ | ○ | ● | ○ | ○ | ○ | ○ | ○ | ○ | ● | ○ | ● | ● | ● | ○ |
| Agent graph (plan → act → verify → decide) | ○ | ○ | ○ | ○ | ● | ● | ○ | ● | ● | ● | ● | ● | ○ | ● | ○ | ● | ○ | ○ | ○ | ○ | ○ |
| Multiple subagents (parallel fan-out) | ○ | | ○ | ○ | ● | ○ | ○ | ● | ○ | ○ | ● | ● | ○ | ○ | ○ | ● | ○ | | ○ | ○ | ● |
| Tool / function calling | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| Skills (condition playbooks) | ● | ○ | ○ | ○ | ● | ● | ○ | ● | ● | ● | ● | ● | ● | ○ | ● | ● | ● | ○ | ○ | ○ | |
| Persistent memory read | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| Graph memory traversal | ○ | ● | | ○ | | | | ● | ○ | ● | ● | ● | ● | | | | | | | ○ | |
| Semantic retrieval (policy, precedent, text) | ● | ○ | ● | ○ | ● | ● | ● | ● | ● | ● | ● | ○ | ○ | ● | ● | ● | ● | ● | ○ | ○ | |
| Working memory (in-case scratchpad, open questions) | ○ | ○ | ○ | ○ | ● | ● | ○ | ● | ● | ● | ● | ● | ○ | ● | ○ | ● | ○ | ○ | ○ | ○ | ● |
| Agent chooses to write memory | ● | | ○ | | ○ | ○ | | ● | ● | ○ | ● | ● | ○ | ○ | ○ | ○ | ○ | | ○ | ● | |
| Consolidation | | | | | | | | ○ | | | ○ | ● | | | | | | | | ● | |
| Forgetting / retraction / supersession | | | ● | | | ● | | ● | ○ | | ● | | ● | | | | | | | ● | |
| Sandbox / REPL computation | ○ | ○ | ○ | ● | ● | ● | ● | ● | ● | ○ | ○ | ● | | ○ | ● | ● | | ● | ● | ○ | ● |
| Research (dated external sources) | ● | ● | ○ | ○ | ○ | ● | ○ | ○ | ○ | ● | | ○ | | ● | ○ | ○ | ● | ● | ○ | ● | |
| Automated review panel & bounded controls | | | | | ○ | | | ● | | ● | ● | ● | | ● | | | | | | | ○ |
| Simulated cardholder interaction | ○ | ● | | ● | ○ | ○ | ○ | ○ | ● | ● | ○ | | | ○ | ○ | ● | | ○ | | ● | |
| Contradiction detection | | ○ | | ● | ● | ○ | ● | ○ | ● | ● | ● | ● | ● | ○ | | ● | ● | | ○ | ● | |
| Policy versioning / effective dates | ○ | | ● | | | ● | | ● | ● | | ○ | | | ○ | | ○ | ○ | ○ | | | |
| Evaluation (deterministic + rubric) | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● |

Additional agentic methods and where they are *forced* rather than decorative:

| Method | Forcing cases | Why it's necessary there |
|---|---|---|
| Plan → execute → **re-plan** on new evidence | C06, C09, C11, C15 | The initial obvious route is invalid or gets contradicted mid-case |
| **Competing-hypotheses tracking** (explicit H1/H2 with evidence for/against) | C10, C11, C12 | "Friendly fraud" and "account takeover" produce overlapping evidence; premature commitment is the failure mode |
| **Adversarial review** (cardholder-advocate vs merchant-advocate → judge) | C05, C10, C13 | Evidence is contested and the decision must survive the opposing packet at pre-Arbitration |
| **Verifier / critic pass** (check eligibility, citations, arithmetic before deciding) | C03, C06, C08, C14 | Each has a plausible-looking wrong answer that a second look at one rule or one number catches |
| **As-of retrieval** (filter by effective date of the *relevant* date, not today) | C03, C06, C09, C16 | Same query, different correct document depending on which date governs |
| **Tool-grounded arithmetic** (never let the LLM do the math) | C04–C08, C14, C15, C17 | Pro-rata days, FX, taxes, business days, billing cycles |
| **GraphRAG / multi-hop traversal** | C08, C11, C12, C12b | Signal only exists across cases/customers |
| **Value-of-information stopping** | C02, C03, C17, C18 | Further investigation costs more than it can change |
| **Suspend → resume on external events** | C03, C09, C13, C15, C18 | Evidence and replies arrive later; the run must checkpoint, wait on the virtual clock, and resume — or decide at the latest safe time |
| **Automated review panel** (advocates + adjudicator + verifier, confidence threshold, conservative default) | C10, C11, C12, C13 | High-impact decisions with no human reviewer must still be challenged, calibrated and fail safe for the cardholder |
| **Memory reflection** (write lessons, correct past notes) | C11, C19, C03 | Stored beliefs are wrong or stale |
| **User simulation (τ-bench style)** | C02, C09, C10, C15, C19 | Resolution depends on what the cardholder says when asked the right question |
| **pass^k consistency evaluation** | all | A dispute decision that changes across runs is itself a compliance defect |

## 3. Why a rules engine and a single prompt both fail

| Case | Rules engine does | Single-prompt LLM does |
|---|---|---|
| C02 | Descriptor not in history → fraud workflow, card reissue | Can't see 14 prior visits under the old descriptor or the facilitator change |
| C03 | Uses whichever threshold is hard-coded | Retrieves the stale memory note and writes off both |
| C04 | Same date + same amount + same merchant → 12.6 duplicate | Agrees with the cardholder's narrative |
| C05 | T&E + amount mismatch → 12.5 (invalid) or deny all | Picks 12.5 confidently; can't correlate ride-hail transactions with "no car" |
| C06 | Recurring + cancelled → 13.2 (invalid after 18 Apr 2026) | Doesn't know the April change; approximates the pro-rata amount |
| C07 | Credit < debit → 13.6 | Treats FX movement as merchant short-changing |
| C08 | Applies the $50/$500 tier because the customer "saw an alert"; calendar-day deadlines | Can't compute business days with the holiday; can't find the compromise point |
| C09 | Files 10.4 before 24 Oct and "wins" (rewarding misuse), or denies on a CE match that isn't valid yet | Doesn't know which CE 3.0 version applies to the processing date |
| C10 | Approves on "unauthorized" keyword (files a 10.4 that loses) or denies on "household" without examining authority | Moralizes; misses the merchant refund window; can't find the saved-card evidence |
| C11 | Merchant CE match → deny | Trusts the memory label "possible first-party misuse" |
| C12 | Denies each case on proof of delivery; never sees the ring | No cross-case memory |
| C12b | Guilt-by-association ring rule denies the innocent member | — |
| C13 | No rule → default to 10.4 or deny | Invents a dispute condition |
| C14 | Compares timestamps without zones | Converts the time zone wrong half the time; doesn't know "more than one night" is independently invalid |
| C15 | Keeps both charges in dispute | Loses track of which charge is at which lifecycle stage and deadline |
| C16 | Reads today's merchant page ("final sale") → deny | Same |
| C17 | Expired → deny with no help | Invents a goodwill "billing error" credit |
| C18 | Posts dispute; double refund | Misses the out-of-order credit |
| C19 | Merchant risk flag → approve | Trusts consolidated memory |

---

## 4. Cases in detail

Each case below lists: **Proves** · **Setup** · **Expected path** (with pivots ⟲, contradictions ⚡, stops ■, review panel ⚖, waits ⏸) · **Ground truth** · **Traps**.

### C01 — Went Dark · DSP-2026-90001 · L2

**Proves:** research can supply a fact that changes a network rule's applicability (merchant insolvency waives the 15-day waiting period); the agent notices a merchant-level cluster and chooses to write it down.

**Setup.** Cardholder CUS-90001 (Columbus, OH) paid **$1,284.00** on 2026-08-18 to *Oakhollow Furniture Co* (MCC 5712) for a made-to-order dining table, "ships in 3–4 weeks", promised delivery by 2026-09-22. No tracking ever created. Cardholder emailed the merchant 24 Sep, 1 Oct, 8 Oct — no replies. Four other Lanternfield cardholders opened non-receipt disputes against Oakhollow between 30 Sep and 16 Oct. Research corpus has a local news article (5 Oct) reporting the owner filed Chapter 7 and a website snapshot (10 Oct) saying "Oakhollow has closed." Intake 2026-10-20 via secure message. Statement closing day 25 → first statement reflecting the charge was transmitted 2026-08-26.

**Expected path.**
1. Router: non-fraud, goods not received, credit → Reg Z + Visa 13.1 skill.
2. Compute Reg Z notice timeliness: 60 days from 2026-08-26 = **2026-10-25**; notice 10-20 → timely (only 5 days to spare).
3. Check 13.1 prerequisites: expected date passed ✓; attempt to resolve ✓ (three emails); waiting period 15 days — ⟲ research finds bankruptcy → waiting period *does not apply if the merchant is insolvent or bankrupt*.
4. Graph/SQL: other disputes against the merchant → cluster of 4 open cases.
5. ■ Stop: no merchant evidence request needed beyond Order Insight "no data"; file.
6. Write memory: merchant-level note (insolvent, open cluster, date, source doc).

**Ground truth.** Accept; provisional credit per SOP; file **13.1 for $1,284.00** now; Reg Z acknowledgment; merchant note written.
**Traps.** Waiting 15 more days; requesting a police report; missing the 10-25 Reg Z deadline; treating the other four cases as irrelevant.

### C02 — Coffee by Another Name · DSP-2026-90002 · L1

**Proves:** the router can recognize a non-dispute and stop cheaply; history plus a descriptor directory beats a fraud workflow.

**Setup.** CUS-90002 (Boston) reports `TAPR* BLUEFERN CAFE BOSTON` $11.40 (2026-10-14, contactless, card present) as unrecognized. The cardholder has 14 prior card-present purchases at `BLUEFERN COFFEE ROASTERS` (Mar–Aug 2026, same merchant ID family, 0.3 mi from employer address). Bluefern moved to the *Tapr* payment facilitator in September; research has Tapr's merchant directory entry ("formerly billed as Bluefern Coffee Roasters"). Two further September purchases under the new descriptor were never questioned.

**Expected path.** Router → descriptor-confusion check → history lookup by merchant graph (merchant ↔ descriptor variants) → research directory → send clarification → wait for reply (persona replies within ~4 hours: "Oh, that's my coffee place — please cancel") → ■ close as withdrawn.

**Ground truth.** No dispute, no provisional credit, no card reissue; outcome `withdrawn_after_clarification`.
**Traps.** Filing 10.3 (card-present fraud); reissuing the card; continuing to investigate after withdrawal.

### C03 — The Stale Threshold · DSP-2026-90003 (one intake case holding $12.49 + $19.99) · L1/L2

**Proves:** transactions are disputed separately; internal SOP is versioned; agent memory can be stale and must lose to the current source of truth; supersession ("forgetting") is an explicit memory operation.

**Setup.** Intake created a single case containing both transactions — the agent must split it (network disputes are per transaction). CUS-90003 (Austin) bought two font licenses from *Glyphstack Fonts* on 2026-10-11; both download links failed during a merchant outage (research: status page, 11–14 Oct, HTTP 503). Merchant ignored two support emails. SOP-DSP-002 **v4 (effective 2026-07-01)** allows goodwill write-off without chargeback for non-fraud claims **≤ $15.00** where the customer has no other dispute in 12 months; **v3 (superseded)** allowed ≤ $25.00. Memory note MEM-0150 still says "$25."

**Expected path.** Router splits into two cases → retrieve SOP *as of intake date* → ⚡ memory note conflicts with SOP v4 → trust the SOP, supersede the note → $12.49: write-off, ■ stop → $19.99: standard 13.1 digital non-receipt; merchant packet shows 0 successful downloads, activation errors → file 13.1.

**Ground truth.** TXN-9000301: goodwill write-off $12.49, no chargeback. TXN-9000302: file **13.1 $19.99** (receipt says downloads available immediately, so an expected delivery date was specified and no 15-day wait applies). Memory: MEM-0150 marked `superseded` with pointer to SOP-DSP-002 v4.
**Traps.** Writing off both; investigating the $12.49; not correcting the memory.

### C04 — Split, Not Double · DSP-2026-90005 · L2

**Proves:** sandbox grouping over clearing records defeats a surface-level duplicate rule; the obvious explanation is wrong.

**Setup.** CUS-90004 (Pittsburgh) says *Parcelwick Home* charged **$64.18 twice** "for one lamp" (intake 2026-10-13). Reality: one authorization **$128.36** (code A7K2Q9, 2026-10-03) cleared as sequence 1/2 (processed 10-05) and 2/2 (processed 10-09). Order shows **quantity 2** of a $60.55 lamp + 6% PA tax. Shipment 1 delivered 10-08; shipment 2 delivered **10-16** — after intake. Research: Parcelwick shipping FAQ ("orders ship in multiple packages; each package is charged when it ships").

**Expected path.** Sandbox: group by auth code → two clearings sum to auth ✓, sequence numbers 1/2 and 2/2 ⚡ not a duplicate (Visa counts one authorization with multiple clearing sequence numbers as one transaction) → request merchant evidence → quantity 2, both delivered → contact cardholder → persona: "the second one arrived last week; I thought I ordered one — can I return it?" → ■ close; explain merchant return path.

**Ground truth.** No dispute; explanation letter; outcome `no_error_split_shipment`. Computation: 2 × round(60.55 × 1.06, 2) = 128.36.
**Traps.** Filing 12.6; crediting $64.18.

### C05 — The Folio · DSP-2026-90006 · L3

**Proves:** multiple rules appear to apply and the agent must reason about which governs; line-level decomposition; corroboration from the cardholder's own transactions; partial outcome.

**Setup.** CUS-90005 (Chicago) booked *The Larkspur Hotel Nashville* direct: 3 nights 2–5 Oct at $189. The confirmation email says the rate **excludes a $35 nightly destination fee** and taxes (15.25%), with valet parking $32/night "if applicable." The charge on 10-05 is **$1,087.53**: rooms $567 + upgrade $180 (3 × $60) + destination fee $105 + parking $96, room-tax 15.25% on $852 = $129.93, parking tax 10% = $9.60. The cardholder expected $653.47 and disputes **$434.06**, saying the upgrade was "complimentary" and they had no car. Hotel's Order Insight response (available 10-16): folio, registration card with **initials "D.O." beside "UPG KING STE +$60/NT"**, valet log with **no vehicle for room 814**. The cardholder's own card shows ride-hail trips at Nashville airport on 10-02 and 10-05. Cardholder emailed the hotel on 10-07; hotel replied 10-09 "charges are final."

**Expected path.** Router: T&E amount dispute → ⚡ 12.5 invalid (quoted vs actual for T&E), 13.3 invalid (price discrepancy) → decompose folio lines (parallel subagents per line) → destination fee: disclosed → valid charge → upgrade: ⚡ cardholder testimony vs initialed registration card → adversarial review → documented acknowledgment prevails → parking: hotel's own valet log + ride-hail trips → service not provided → **13.1 portion not received** → sandbox amounts → decide.

**Ground truth.** File **13.1 for $105.60** (parking + parking tax). Deny $328.46 with Reg Z explanation (destination fee disclosed; upgrade acknowledged in writing). Precedent PRE-0007 (same hotel, June 2026, upgrade *without* initials → merchant credited it) must be distinguished, not copied.
**Traps.** 12.5 or 13.3 for the full difference; denying everything; crediting the upgrade because a similar precedent did.

### C06 — Trial Trap · DSP-2026-90007 · L3

**Proves:** policy versioning changes the correct route; re-planning after a verifier finds the first route invalid; pro-rata arithmetic; an outdated precedent must be recognized as outdated.

**Setup.** CUS-90006 (Denver) started a 7-day free trial of *Lumafit Plus* on 2026-09-22; an **annual $119.88** recurring charge (merchant-initiated) posted 09-29. The welcome email says the membership "renews at the then-current annual rate" — no amount, no date. No pre-renewal reminder was sent. App usage 9-23, 9-25, 9-27, 9-30. Cancelled in-app **10-03**; support refused a refund on 10-04 ("annual plans are non-refundable"). Intake 10-06.

**Expected path.** Router → recurring skill → propose 13.2 → verifier retrieves 13.2 *as of dispute date* → ⚡ invalid: cancellation after transaction date (effective 18 Apr 2026) → ⟲ re-plan → merchant obligations: trial-end notice ≥7 days before with amount, date and cancellation link → missing → **13.5 Misrepresentation** ("trial… cardholder not clearly advised of further Transactions") → amount limited to unused portion → sandbox: 360/365 × 119.88.

**Ground truth.** File **13.5 for $118.24** (tolerance ±$0.35 for day-count convention). Precedent PRE-0012 (same merchant, March 2026, won under 13.2) and memory note MEM-0160 are outdated by the April 2026 rule.
**Traps.** Filing 13.2; full-amount dispute; citing PRE-0012 as support.

### C07 — Lost in Conversion · DSP-2026-90008 · L2

**Proves:** the sandbox and FX reference data disprove the cardholder's framing; network rules give no remedy; an internal SOP gives a partial one.

**Setup.** CUS-90007 (Seattle) bought ceramics for **€420.00** from *Azulejo Atelier Lisboa* on 2026-08-11 → billed **$462.84** (1.1020) plus a separate 3% foreign transaction fee **$13.89**. Returned; merchant refunded €420.00 on 10-01 → posted **$447.09** (1.0645). Intake 10-08: "they refunded $15.75 less and I still paid a foreign fee."

**Expected path.** Sandbox with `fx_rates` → shortfall = rate movement, merchant refunded 100% in EUR → Visa: credit posted before any dispute → no 13.6 (credit processed) and no FX pre-Arb right (that only exists when the credit follows a dispute) → Reg Z: not a billing error (FX terms disclosed in cardholder agreement) → SOP-DSP-007: reverse the issuer's own foreign-transaction fee on full refunds within 180 days → ■ decide.

**Ground truth.** No dispute; **reverse fee $13.89**; explain the $15.75 FX difference; outcome `no_error_fx_explained_fee_reversed`.
**Traps.** Filing 13.6; crediting $15.75; ignoring the fee SOP.

### C08 — Pump Six · DSP-2026-90009 · L3 · Reg E

**Proves:** regime routing (debit → Reg E); business-day computation with a bank holiday calendar and the new-account extension; the $50/$500 tier does not apply when the card isn't lost; graph discovery of a common point of compromise; separating the cardholder outcome from the chargeback decision.

**Setup.** CUS-90008 (Cleveland) opened checking 2026-09-24, first deposit 09-28. Card used card-present (magstripe fallback) at *Pinegrove Fuel #22* on 09-30. Fraud: 10-09 **$1,240.00** at *VoltCart Online* (AVS N, no 3DS, CVV2 not present, ship-to a Toledo industrial unit) and **$59.00** at *GiftLane Cards*; a third attempt declined 10-10. The cardholder saw an app alert 10-10 but called **10-13** (Tuesday, day after the bank's Columbus Day holiday). Nine other Lanternfield cardholders used Pinegrove Fuel #22 between 20 Sep and 2 Oct and later reported CNP fraud. Research: news 10-15 "skimmer found at pump 6." Internal bulletin CB-2025-03 (superseded) counted calendar days; CB-2025-09 counts business days per the bank calendar. Memory note MEM-0152 repeats the superseded rule.

**Expected path.** Router → debit → Reg E skill → liability: card not lost/stolen → 60-day statement rule only → **$0 liability** (⚡ "saw alert 10-10" is irrelevant to the 2-business-day tier) → timing: transfers within 30 days of first deposit → **new-account**: 20 business days for provisional credit, 90 days to investigate → sandbox with holiday calendar → subagent graph query: common merchants among fraud-victim cards in the 30 days before first fraud → Pinegrove #22 → research corroborates → fraud report → chargeback decision per SOP fraud recovery threshold ($100): file 10.4 for $1,240; write off $59 → ⚖ review panel on the cross-customer finding → automated controls: graph link `SUSPECTED_COMPROMISE_POINT` (active), merchant added to the compromise-point watchlist; optional enhanced monitoring of other cards used there in the window.

**Ground truth.** Cardholder credited **$1,299.00**, liability $0; provisional-credit deadline (if unresolved) **2026-11-10**; investigation deadline **2027-01-11**; 10.4 filed $1,240.00; $59.00 written off; Pinegrove #22 on the compromise-point watchlist; MEM-0152 superseded.
**Traps.** $50 liability; 10-business-day deadline (10-27); calendar-day math; charging back the $59; missing the CPP.

### C09 — The Clock on CE 3.0 · DSP-2026-90010 · L3

**Proves:** network liability ≠ truth; version selection keyed to the *dispute processing date*; merchant evidence double-counting detected; the cardholder's story changes and the claim family must be re-routed; fairness (no "fraudster" label).

**Setup.** CUS-90009 (Los Angeles) disputes **$69.99** *Nebula Forge Games* "Starfall Tactics Deluxe" (2026-10-02, e-commerce, ECI 07, AVS Y, CVV2 M) as unauthorized (intake 10-19, authenticated IVR). Order Insight packet (available 10-20): login `kestrelmoon`; IP `198.18.77.140`; device ID and fingerprint; 37.5 hours of play 10-02→10-18. Prior undisputed purchases: Nebula Forge Games 2026-05-15 ($29.99), sister storefront *Nebula Forge Arcade* 2026-03-20 ($14.99, **same acquirer**), and Nebula Forge Games 2026-09-10 ($9.99, too recent). The merchant packet claims "4 matching elements", counting device ID and fingerprint separately. Issuer's own app logins come from the same home IP that evening. Cardholder has two prior digital-goods fraud claims in 2026, both won.

**Expected path.** Router → CNP fraud skill → CE 3.0: which version? Earliest realistic processing date ≥ 10-21; any contact with the cardholder pushes it past **Sat 10-24 → Mon 10-26** → **new version** → multi-merchant, same-acquirer priors >120 days ✓ (220 days for the Arcade purchase, 164 days for the base game; the September DLC at 46 days does not count) → elements: IP + login ✓ (device ID/fingerprint count once) → dispute would be invalid. Regardless of network: Reg Z reasonable investigation shows participation → contact cardholder with evidence → persona (10-22): "OK, maybe I bought it, but it keeps crashing — I want my money back" → ⟲ fraud claim withdrawn; new non-fraud claim → merchant refund policy (research: refunds within 14 days and < 2 hours played) → cardholder must go to merchant first → ■ deny.

**Ground truth.** No 10.4 filed; fraud claim denied/withdrawn with explanation; non-fraud complaint redirected to merchant; CE 3.0 analysis cites new version; memory: factual note ("fraud claim retracted after evidence review 2026-10-22") — **not** a label.
**Traps.** Filing before 10-24 because the old rule is favorable; counting device ID + fingerprint as two; labeling the customer; denying solely for silence (not the case here — there is confirming evidence).

### C10 — The Family Tablet · DSP-2026-90011 · L4 · deny via review panel

**Proves:** a judgment call that used to need a human can be decided automatically and fairly: competing hypotheses, an adversarial review panel, a calibrated confidence and a recorded flip fact; Reg Z apparent authority; network compelling evidence for household members; a time-sensitive alternative remedy found by research.

**Setup.** CUS-90010 (primary) and authorized user CUS-90011, Columbus. On 2026-02-14 the card was saved to a child's *Pixelhollow Studios* game account from the primary cardholder's phone, for a **$4.99** purchase (undisputed). Between **09-26 and 10-04**, 23 in-game purchases totaling **$486.77** were made from the family tablet (also used for the primary's banking logins), home IP. Intake 10-07: "My 13-year-old used my card without permission. I never gave him my card." Follow-up (when asked about the saved card): "I put it in once in February for a $4.99 skin but told him to ask every time." Research: Pixelhollow help page — parents may request a **one-time refund of purchases made in the last 30 days**.

**Expected path.** Competing hypotheses: H1 unauthorized (no authority) vs H2 authority given then exceeded (cardholder liable until notice, comment 12(b)(1)(ii)-3) → Visa CE item 11 (household member) would defeat 10.4 at pre-Arb → merchant refund window: first purchase ages out **2026-10-26** → ⚖ review panel (cardholder advocate argues H1, issuer advocate argues H2; adjudicator decides H2 with confidence ≥ 0.75; flip fact: evidence the card was never saved with permission, cf. PRE-0010) → decide.

**Ground truth.** No 10.4; unauthorized-use claim **denied with explanation** (use by a person given authority, liable until notice); temporary credit $486.77 reversed with Reg Z notice; 2026-10-07 recorded as notice that the child's use is no longer authorized; cardholder told to request Pixelhollow's minor refund **now** (earliest purchases age out 10-26, last 11-03) and how to remove the stored card; optional scheduled follow-up on 11-04 to confirm the merchant credit; no misuse label.
**Traps.** Filing 10.4; deciding without the review panel; missing the refund window; moralizing language; using the child's or parent's age as a signal.

### C11 — Takeover in a Friendly Mask · DSP-2026-90012 · L4 · approve + automated reopen

**Proves:** contradiction detection across issuer and merchant data; CE 3.0 format rules matter (truncated IP ≠ IP); memory can be wrong and must be retracted; a past decision is reopened automatically when new evidence contradicts it and the correction favors the cardholder; graph traversal reveals a drop address.

**Setup.** CUS-90012 (Brooklyn, customer since 2017) disputes **$1,389.00** at *Orbital Audio* (2026-10-14 02:41 ET). Merchant packet: same login as two undisputed 2026 purchases (Jan $89, Apr $149), "IP match **198.18.201.x**", "account verified", ship-to **88 Wharfside Ave Unit 2, Jersey City NJ**. Buried in the packet: password reset 01:58, email changed 02:05, new device fingerprint first seen 01:57. Issuer data: phone number changed via IVR on **10-12**; three failed app logins from `203.0.113.58` (hosting IP) then an SMS-OTP password reset at 01:54 on 10-14; cardholder calls 10-15 locked out. Prior case **DSP-2026-04471** (closed 2026-06-02): $612 at *Kestrel Outdoor Supply*, denied as first-party misuse on merchant CE — shipped to the **same Wharfside address**. Memory note **MEM-0142** says "possible first-party misuse; heightened scrutiny." Two other Lanternfield fraud disputes also shipped to Wharfside Unit 2.

**Expected path.** Retrieve memory → H1 friendly fraud (merchant CE, MEM-0142) vs H2 ATO → CE 3.0 check: IP is truncated (fails "full IP, clear text"), delivery address ≠ prior → **not met** → ⚡ packet's own account-change log → issuer security events (SIM-swap pattern) → graph: Wharfside Unit 2 ← 4 disputed transactions, 3 customers, includes DSP-2026-04471 → H2 → approve, fraud report, file 10.4 → automated account security (lock digital banking pending step-up, revert unverified phone change, reissue card) → ⚖ review panel on reopening 04471 → reopen and credit $612.00 (no network action: that transaction was already disputed once and its time limit passed 2026-09-01) → drop address to ship-to watchlist → memory: retract MEM-0142, write correction.

**Ground truth.** Credit **$1,389.00**; file 10.4; automated account-security actions; **reopen DSP-2026-04471 and credit $612.00** without a second network dispute; ship-to watchlist entry; MEM-0142 `retracted`.
**Traps.** Denying on merchant CE; trusting MEM-0142; re-disputing TXN-9001203; leaving the June denial in place; not correcting memory.

### C12 — Porch Ring · DSP-2026-90013 · L4 · deny + automated controls

**Proves:** coordinated first-party abuse is invisible per case and visible by traversal; the agent records the finding and applies **bounded** automated controls, never punitive action on linkage alone; Visa's 3-in-30 cardholder-letter rule.

**Setup.** Four customers (CUS-90013…90016, Columbus suburbs, accounts opened Mar–May 2026) filed nine earlier non-receipt claims (DSP-2026-91300…91308) against *Stridevault*, *Kinetic Threads* and *Orbital Audio* between Aug 29 and Oct 19; the trigger claim is the tenth. Merchants' proofs of delivery show full addresses matching each cardholder's own address, photos, and GPS within 20 m. Shared: two device fingerprints across their Lanternfield app logins; one alternate phone number on two profiles. CUS-90014 has **three** Stridevault non-receipt disputes within 30 days. Trigger: CUS-90013's claim of **$412.00** (Stridevault, delivered 10-16, intake 10-19).

**Expected path.** Case-level: POD with full address + photo + GPS → no billing error. Graph subagent: dispute ↔ customer ↔ device/phone → 4-customer component with 10 non-receipt claims → ⚖ review panel on the cross-customer finding → consolidation into a `SuspectedRing` node with evidence edges (status `active`) → automated controls: enhanced monitoring and an evidence-first claims control (signed letter + evidence review before temporary credit) on the four accounts, ring devices to the watchlist, linked open cases enqueued for automated re-review on their own evidence; note the 3-in-30 cardholder-letter requirement on CUS-90014 → ■ no account closures or restrictions.

**Ground truth.** Deny $412.00 with Reg Z explanation; `SuspectedRing` naming exactly CUS-90013…90016 and 10 cases; the automated controls above; 6 linked open cases re-queued; do **not** include CUS-90017.

### C12b — Wrong House · DSP-2026-90014 · L2

**Setup.** CUS-90017 lives in the same ZIP and bought from Stridevault the same week (**$219.00**, 10-11). The POD photo shows house number **1204**; the cardholder lives at **1240**. The carrier record has a partial address ("…Maple Ridge Dr, Westerville OH"). No shared devices or phones with the ring.

**Ground truth.** File **13.1 $219.00** — Visa requires proof of delivery with the *full* delivery address; the photo contradicts it. No ring linkage.
**Trap.** Any ring-association rule that sweeps this case in.

### C13 — The Agent Booked It · DSP-2026-90015 · L4 · wait → decide (policy gap)

**Proves:** the agent recognizes when no network rule exists, says so with evidence, falls back to the regulation instead of inventing a rule, waits for determinative evidence on the virtual clock, and records the policy gap; research across network rules and a third-party provider's terms.

**Setup.** CUS-90018 (Boston) instructed *TravelMind* (an Agentic Payment Provider) on 2026-10-01: "Round trip BOS→DEN, Nov 14 after 3 pm → Nov 17 evening. **Refundable fare preferred. Max $450 total.**" Consent text: "TravelMind may accept fare rules and merchant policies needed to complete bookings within your criteria." Cardholder acknowledged responsibility for agent actions. On 10-02 TravelMind booked *Skylark Air* Basic Economy **$412.60, non-refundable** (refundable Main Cabin was $489.20). Trip cancelled by cardholder 10-09; no refund or credit. Intake 10-16: "my AI agent booked a non-refundable ticket even though I said refundable." The full instruction record is only available from TravelMind on written request (available 10-23). Research: TravelMind terms distinguish "hard constraints" (guaranteed) from "preferences" (best effort).

**Expected path.** Router → agentic transaction flag → retrieve Visa §4.1.24 → search dispute conditions → ⚡ none fit: 10.4 (authorized agent + acknowledged responsibility), 13.7 (policy disclosed and applied), 13.1 (service available), 13.5 (APP is not a merchant) → request instruction record → ⏸ suspend until it arrives (2026-10-23; latest safe decision date 2026-12-30) → resume: record shows 'refundable' parsed as a preference and confirmed back to the cardholder; booking push disclosed non-refundable with 24h free cancellation → Reg Z: no billing error → ⚖ review panel → decide → write `policy_gap` record.

**Ground truth.** No chargeback; claim **denied with explanation** after the record arrives; cardholder pointed to TravelMind's guarantee (hard constraints only) and complaint process; `policy_gap` record listing 10.4, 13.1, 13.5, 13.7 and why each fails.
**Traps.** Filing 10.4; inventing an "agent exceeded authority" condition; deciding before the record arrives; waiting for a human.

### C14 — Three Time Zones · DSP-2026-90016 · L2

**Proves:** timezone arithmetic decides the case; two independent grounds (cancellation vs "more than one night"); precedent that looks the same resolved differently for a reason the agent must articulate.

**Setup.** CUS-90019 (Los Angeles) held a guaranteed reservation at *Harbor & Vine Hotel*, New York: Oct 10–12, $265/night. Policy: cancel by **6:00 PM hotel local time, 2 days before arrival** → 2026-10-08 18:00 ET. Cardholder's phone log: call to the hotel **2026-10-08 2:41 PM** (phone set to Pacific), 4 min. No cancellation code. Hotel billed no-show 10-12 for **2 nights + 14.75% tax = $608.18**. Precedent **PRE-0019** (July 2026, cardholder in Denver called 4:30 PM MT = 6:30 PM ET) was partial.

**Ground truth.** File **13.7 for $608.18** (2:41 PM PT = 5:41 PM ET, before deadline); fallback floor $304.09 (billing more than one night is independently improper).
**Traps.** Comparing 2:41 PM to 6:00 PM without zones in the wrong direction; copying PRE-0019's partial outcome.

### C15 — Membership Mid-Flight · DSP-2026-90017 (Sep) and DSP-2026-90018 (Oct) · L3

**Proves:** the agent can join a case already in the network lifecycle, handle a late-arriving Dispute Response, track two charges on different stages and clocks, and complete the issuer's certification duty.

**Setup.** CUS-90020 (Austin), *Ironwood Athletic Club*, $64.00 monthly on the 1st. Cancellation email **08-28**; merchant auto-reply: "30 days' written notice required per your agreement; your final billing date is September 1." Before the switch to automated operations (1 Oct 2026), an analyst filed **13.2** on the **Sep 1** charge (processed 09-21). Cardholder's intake note (09-18): "haven't been since August." Merchant Dispute Response (processed **10-16**): signed agreement with 30-day notice clause, the auto-reply, **badge scans 09-10 and 09-14**. A new **Oct 1** charge was reported 10-19.

**Expected path.** Load case state → compute pre-Arb deadline (30 days from 10-16 = **11-15**) and Reg Z deadline for the Sep notice (two complete billing cycles after 09-18 with cycle day 5 → **2026-12-05**, earlier than 90 days) → ⚡ badge scans vs "haven't been" → issuer must contact cardholder before a pre-Arb → persona: "Yes, I went twice in September — I thought it ran to the end of the month" → accept merchant response on Sep charge; re-bill with Reg Z notice → Oct charge: after merchant's own "final billing Sep 1" → file **13.2 $64.00**.

**Ground truth.** 90017: accept Dispute Response; re-bill $64.00 with explanation. 90018: file 13.2 $64.00.
**Traps.** Pre-arbitrating the Sep charge; lumping both charges together; missing the certification step.

### C16 — The Listing Changed · DSP-2026-90019 · L2

**Proves:** research with *dated* snapshots; "attempt to return" rules; two plausible conditions with a preferred one.

**Setup.** CUS-90021 (Chicago) paid **$899.00** on 2026-09-19 to *RenewTek Outlet* for a refurbished laptop listed "Grade A, battery health ≥ 85%, 30-day hassle-free returns." Delivered 09-26; diagnostic 09-27: battery 61%. Chat 09-29: "refurbished items are final sale, no RMA." Archive snapshot 09-19 shows "30-day returns"; current snapshot 10-15 shows "All refurbished sales final."

**Ground truth.** File **13.3 for $899.00** (attempted return refused → attempt valid; waiting period doesn't apply when merchant refuses the return). 13.7 accepted as alternative with rationale.
**Traps.** Citing today's page; requiring a completed return.

### C17 — Too Late, Still Helpful · DSP-2026-90020 · L2

**Proves:** stopping correctly — the agent computes that every formal remedy is closed, doesn't manufacture one, and still helps.

**Setup.** CUS-90022 (Denver) bought 2 tickets for **$329.40** from *Gateway Tix* (2026-02-02) for an Apr 25 concert cancelled on Apr 18. No refund received. Intake **2026-10-14**. Visa 13.1 for ticket agencies: 120 days from the last expected service date → expired **2026-08-23**. Reg Z notice: 60 days from the February statement → expired. Claims and defenses (§1026.12(c)): cardholder pays in full each month → no credit outstanding for the purchase. Research: Gateway Tix refund portal for cancelled events open **until 2026-12-31**.

**Ground truth.** Decline dispute and billing-error claim (untimely), no 12(c) right (paid in full), provide the refund portal and deadline.
**Traps.** Filing 13.1; goodwill credit mislabeled as billing error; stopping without the portal.

### C18 — Refund Crossed in the Mail · DSP-2026-90021 · L1/L2 · Reg E

**Proves:** out-of-order data (clearing credit arrives after intake); Visa "apply the credit first"; Reg E provisional-credit reversal notice; avoiding double recovery.

**Setup.** CUS-90023 (Seattle, debit) bought a rug for **$143.20** on *Harborlane Market* (seller Velvet Loom Co), not delivered. Filed marketplace claim 10-10; bank intake 10-15; provisional credit posted 10-16. Merchant credit `HLM*REFUND 7781` $143.20 cleared **10-19**, posted 10-20 (`available_at` 10-20), with no original ARN reference; marketplace email to cardholder confirms refund for order 114-7781.

**Ground truth.** No dispute; reverse provisional credit $143.20 with Reg E notice (funds honored for 5 business days); close `resolved_merchant_credit`.
**Traps.** Filing 13.1; leaving both credits in place.

### C19 — Yesterday's Reputation · DSP-2026-90022 · L2

**Proves:** consolidated memory must carry validity windows; verifying current evidence beats reputation; consolidation and forgetting as explicit, logged operations.

**Setup.** *Quillmark Print* had 11 non-receipt disputes Jan–Jul 2026 (tracking stuck at "label created") — eight raw episodic notes plus MEM-0209: "Quillmark rarely ships; non-receipt claims almost always valid" (no expiry). Research 2026-08-12: Quillmark moved fulfilment to ShipCrest. Since August: six orders delivered normally, zero disputes. CUS-90024 ordered a custom poster (**$86.50**, 10-02, expected by 10-16), reported non-receipt 10-16. Order Insight (available 10-18): delivered **10-17** with full address and photo.

**Ground truth.** No dispute; cardholder confirms receipt (persona) → withdrawn. Memory: consolidate MEM-0201…0208 into one note valid **2026-01-01 → 2026-08-12**; mark MEM-0209 superseded; archive raw notes.
**Traps.** Approving on reputation; deleting the history (it's still true for its window).

### Q01 — Monday Morning Queue · meta

**Proves:** the router/harness works at portfolio level, prioritizing by the clock that expires first rather than by amount or age.

**Setup.** All 95 cases open as of `AS_OF` (heroes, planted clusters and background) with their regime, stage, and dates.

**Ground truth.** `ground_truth/Q01_queue.json` ranks the top 15 by earliest hard deadline (Reg E provisional credit, Reg Z resolution, network response/pre-Arb deadlines, Visa dispute time limits, merchant refund windows), computed deterministically by the generator, with the governing clock for each.

---

## 5. Background population (non-hero)

| Element | Volume | Role |
|---|---|---|
| Customers | ~380 (incl. household members) | Realistic history; authorized users; shared household devices |
| Merchants | ~230 | Descriptor variants, MCC spread, acquirer IDs |
| Transactions | ~24k (incl. 3.5k payments) over Oct 2025 → Oct 2026 | Spending patterns, recurring billing, CNP auth signals |
| Closed disputes | ~200 | History, dispute-count thresholds; 39 precedents in markdown (11 hand-written contrast cases + 28 templated) |
| Open disputes | 95 (incl. heroes) | Queue realism for Q01; lightweight ground-truth labels |
| Planted clusters | Oakhollow (C01), Pinegrove CPP (C08), Wharfside drop address (C11), Quillmark history (C19) | Patterns that must be *discovered* |

Hero records use ID range `9xxxx`; background uses `0xxxx`. Every row carries `is_hero` for filtering, but agents should never be given that column.
