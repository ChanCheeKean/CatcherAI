# Dispute Observatory evaluation results

Last run: 2026-09-14  
Scope: 20 hero cases, C12b, and Q01 (20 decision runs + one portfolio run)  
Adapter: deterministic fake model gateway; isolated fresh SQLite/graph stores per attempt

## Result

All 63 fresh attempts passed: **21/21 scenarios at pass^3 = 1.0**. Every attempt had a complete
trajectory, a valid event hash chain, a replay-reconciled output, and the same outcome as its other
two attempts. The one-run CLI acceptance result was also 21/21.

This is a deterministic POC result, not a claim about live-model accuracy. The fake gateway proves
workflow, policy, data, governance, persistence and evaluator determinism. The opt-in OpenAI smoke
test was not run because no API credential was provided; live-model pass^k and calibration therefore
remain unmeasured.

### Scenario results

| Scenario | Route / focus | Attempts | pass^3 | Stable | Reconciled |
|---|---|---:|---:|---:|---:|
| C01 / 90001 | non-receipt, insolvency research, cluster write | 3/3 | 1.0 | yes | 3/3 |
| C02 / 90002 | descriptor confusion, early stop | 3/3 | 1.0 | yes | 3/3 |
| C03 / 90003 | split case, as-of threshold, supersession | 3/3 | 1.0 | yes | 3/3 |
| C04 / 90005 | split clearing, evidence/reply waits | 3/3 | 1.0 | yes | 3/3 |
| C05 / 90006 | folio-line fan-out, partial 13.1 | 3/3 | 1.0 | yes | 3/3 |
| C06 / 90007 | invalid 13.2, verifier re-plan, pro-rata | 3/3 | 1.0 | yes | 3/3 |
| C07 / 90008 | FX explanation, issuer fee reversal | 3/3 | 1.0 | yes | 3/3 |
| C08 / 90009 | Reg E, compromise-point graph | 3/3 | 1.0 | yes | 3/3 |
| C09 / 90010 | CE 3.0 version, reply, claim re-route | 3/3 | 1.0 | yes | 3/3 |
| C10 / 90011 | household authority panel | 3/3 | 1.0 | yes | 3/3 |
| C11 / 90012 | ATO contradiction, automated reopen | 3/3 | 1.0 | yes | 3/3 |
| C12 / 90013 | linked-case graph, bounded ring controls | 3/3 | 1.0 | yes | 3/3 |
| C12b / 90014 | negative linkage control | 3/3 | 1.0 | yes | 3/3 |
| C13 / 90015 | novel agentic payment, wait, policy gap | 3/3 | 1.0 | yes | 3/3 |
| C14 / 90016 | time-zone arithmetic, precedent distinction | 3/3 | 1.0 | yes | 3/3 |
| C15 / 90017 | lifecycle tracks, late response | 3/3 | 1.0 | yes | 3/3 |
| C16 / 90019 | dated listing snapshot, refused return | 3/3 | 1.0 | yes | 3/3 |
| C17 / 90020 | expired rights, value-of-information stop | 3/3 | 1.0 | yes | 3/3 |
| C18 / 90021 | late merchant credit, Reg E reversal | 3/3 | 1.0 | yes | 3/3 |
| C19 / 90022 | current evidence, memory consolidation | 3/3 | 1.0 | yes | 3/3 |
| Q01 | 95-case deadline queue | 3/3 | 1.0 | yes | 3/3 |

Each case passed its expected decision fields, `must_not` assertions, required citations, memory
operations, primary capability signals and trajectory checks. The evaluator treats cardholder outcome
and network action as separate output contracts.

## Q01 portfolio quality

Across all three attempts:

- Kendall τ for the expected top 15: **1.0**.
- Top-15 overlap: **15/15**.
- Next-deadline date accuracy across all 95 open cases: **1.0**.
- Per-case fan-out coverage: **95/95**.
- Two semantically equivalent clock-label differences remain visible in the report:
  `await_agentic_provider_record` vs `awaited_provider_record`, and
  `merchant_minor_refund_window` vs `merchant_refund_window`. Dates and ordering agree.

Q01 uses LangGraph `Send` for one sandboxed clock computation per open case, then isolated
subagents re-check the top 15 without authority to reorder the deterministic deadline queue.

## Capability matrix

Only primary forcing cases are shown. `PASS` means every one of the three fresh attempts produced at
least one of that capability's required trajectory signals.

| Capability | Primary forcing cases | Result |
|---|---|---|
| Agents | C05, C11, C15 | PASS |
| Router | C02, C03, C07, C08, C13, C17, C18, Q01 | PASS |
| Loop termination | C01, C02, C03, C12, C13, C17, C18 | PASS |
| Agent graph | C06, C09, C10, C11, C12, C15 | PASS |
| Subagents | C05, C08, C10, C11, C12, C13, Q01 | PASS |
| Tool calling | C01, C02, C13, C16 | PASS |
| Harness | C02, C03, C04, C09, C10, C13, C15, C19 | PASS |
| Skills | C01, C05, C06, C08, C10, C14 | PASS |
| Persistent memory | C01, C04, C05, C11, C15, C17, C18, Q01 | PASS |
| Graph memory | C02, C08, C10, C11, C12, C12b | PASS |
| Semantic/vector memory | C01, C05, C06, C07, C09, C13, C14, C16 | PASS |
| Sandbox | C04, C05, C06, C07, C08, C09, C14, C15, C17, C18, Q01 | PASS |
| Selective read paths | C03, C06, C08, C09, C11, C16, C19 | PASS |
| Selective write paths | C02, C03, C06, C08, C09, C11, C12, C12b, C13, C19 | PASS |

The machine-readable report contains the expanded capability → case booleans rather than only this
summary.

## Trajectory and operational metrics

Across 63 attempts, the evaluator observed 13,917 canonical events, 1,044 tool calls, 333 completed
model calls, 27 suspensions and 24 plan updates. Mean per attempt was 220.9 events, 16.6 tool calls,
5.3 model calls, 634 input tokens and 254 output tokens. All tool calls had results, all model starts
had terminal events, node entry/exit counts reconciled, sequence numbers and parent spans were valid,
and each decision run contained exactly one provenance-bearing decision event.

All 63 SQLite event chains passed SHA-256 verification. Replaying the final decision event reproduced
the returned decision record; Q01 replay reproduced its single portfolio ranking event. The report's
`trajectory_reconciliation_rate` is 1.0 for every scenario.

The fake adapter reported **$0 cost**. Its recorded call latency totaled 13,302 ms (211 ms mean per
attempt); this is local POC instrumentation and should not be interpreted as production or network
latency. Q01 is the largest trace at 958 mean events and 111 tool calls because it evaluates every
open case. C12 is the largest single-case trace at 336 mean events and 22 tool calls.

## Annotated trajectory: C13

C13 demonstrates the complete high-judgment path. Sequence numbers below are from
`DSP-2026-90015-run-1` in the pass^3 workspace.

| Seq | Event | Why it matters |
|---:|---|---|
| 28 | `route_decision` → `agentic_transaction_novel_l4` | The config router recognizes a novel authorized-agent transaction and selects L4 governance. |
| 34 | `computation` | Reg Z clocks are computed; the latest safe decision is bounded by the resolution deadline. |
| 39–41 | three `skill_loaded` events | Eligibility, agentic-transaction and automated-adjudication instructions become explicit inputs. |
| 47 | `plan_created` | The lead creates a bounded plan rather than stretching a familiar condition. |
| 84 | `evidence_requested` | The determinative TravelMind instruction record is requested. |
| 91–93 | suspend, segment termination, checkpoint | A genuine external wait is recorded and LangGraph state is persisted; no person is awaited. |
| 96–98 | clock advance, arrival, resume | Virtual time moves from Oct 21 to Oct 23, the provider record arrives, and the same run resumes. |
| 119–126 | investigation verifier checks | Sources, every candidate condition, precedent handling, hard constraints, preference parsing, budget and disclosure all pass. |
| 138 | `review_panel_started` | SOP-DSP-003 requires adversarial review because no network condition fits the novel type. |
| 169–170 | independent panel positions | Cardholder and issuer advocates receive the same case-file snapshot and argue independently. |
| 190–195 | adjudication plus panel verifiers | The adjudicator selects H1 at 0.90; threshold, independence, consistency and fairness checks pass. |
| 199–203 | final verifier checks | Outcome separation, arithmetic, citations, fairness and required-panel use are checked before write authority. |
| 204 | `decision_recorded` | The denial/no-chargeback decision is stored with field-level event and source provenance. |
| 209–215 | bounded automated actions | Close, explanation, provider-record and policy-gap actions are executed and evented. |
| 219 | `memory_write` | A source-backed policy-gap note is admitted through the memory gate. |
| 223 | final `termination` | The case ends only after decision, actions, memory maintenance and verifier completion. |

## Reproduction

```bash
python3 data/generator/load_sqlite.py
uv run pytest -q
python3 data/generator/validate.py
uv run ruff check src tests
uv run ruff format --check src tests
uv run inspect eval \
  DSP-2026-90001 DSP-2026-90002 DSP-2026-90003 DSP-2026-90005 DSP-2026-90006 \
  DSP-2026-90007 DSP-2026-90008 DSP-2026-90009 DSP-2026-90010 DSP-2026-90011 \
  DSP-2026-90012 DSP-2026-90013 DSP-2026-90014 DSP-2026-90015 DSP-2026-90016 \
  DSP-2026-90017 DSP-2026-90019 DSP-2026-90020 DSP-2026-90021 DSP-2026-90022 Q01 \
  --adapter fake --runs 3 --workspace data/generated/eval/final-pass-k3 \
  --report data/generated/eval/final-pass-k3/report.json
```

After the POC robustness stage, the suite collects 79 tests: 78 pass and the credential-gated real
OpenAI smoke test is skipped by default. The added test runs all 20 routes through three renamed and
reworded variants (60 perturbations plus 20 baselines), preserving decision semantics and valid event
hash chains. Dataset validation passes 401/401 checks; scoped Ruff and format checks pass.

The opt-in real OpenAI contract smoke also passes. A bounded live end-to-end C02 evaluation passes
1/1 with 4,517 ms recorded API latency. That live test exposed and led to a fix for Responses API
strict tool schemas: every object is now closed with `additionalProperties: false`, and optional
properties are represented as required nullable fields.

## Honest limitations and remaining production work

- Playbooks are deterministic case-family programs. The lead model's plan is logged but does not
  choose tools. Presentation perturbation robustness is established, but wholly new graph topologies
  and date/amount boundary variants are not yet synthesized.
- Panel confidence comes from playbook-assigned evidence weights. Advocate/adjudicator output is
  preserved but does not set the decision score. There is no live-model Brier/ECE calibration yet.
- Persona replies are selected from scripted fixtures by term overlap; there is no persona LLM.
- The latest safe time is represented at 00:00 UTC on its computed date. Reg E latest-safe behavior is
  exercised by C18's late credit, but broader boundary-time variations are still needed.
- Offline curation will not consolidate without a case-verified validity window and does not merge
  graph entities.
- Cancellation is checkpointed, but automatic cancel-to-restart scheduling remains unimplemented and
  untested.
- Deep Agents delegations run inside parallel LangGraph branches for C05/C15/Q01. Correctness is
  deterministic, but production concurrency limits and provider rate behavior are not evaluated.
- `inspect run` without `--db` mutates the shared scenario store. `inspect eval` is isolated and is the
  repeatable evaluation path.
- The evaluator checks required primary signals and structural reconciliation. A production audit
  should additionally reconstruct and compare every intermediate case-file, action and graph overlay,
  validate every blob hash, and test cancellation/error contingencies.
- The contract smoke and one bounded live route passed. Broad live-model outcome variance,
  calibration, rate-limit behavior and prompt sensitivity remain open.
