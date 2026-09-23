# Amex dispute revamp: design

Date: 2026-09-23
Status: approved (grilling session 2026-09-23; decisions in §2)
Branch: `amex-dispute-revamp` (every stage is implemented and committed on this branch, never on `main`)
Supersedes: `2026-09-21-agentic-graph-revamp-design.md` for everything about the domain, graph, tools,
skills, cases, report and frontend. That spec's **agent framework** (§3.1–3.3, §3.5, §6 event
envelope, §7 layout) still holds and is not changed here.

Read with: `CONTEXT.md` (the vocabulary; use its terms in code, prompts and docs) and
`docs/research/02-amex-dispute-research.md` (the facts every policy text and case is grounded in).

## 1. Why

The POC models a Visa issuer (Lanternfield Bank) investigating cardholder disputes, including fraud,
ATO and agentic-commerce cases. We now model **American Express**, which is issuer, network and
acquirer at once: one disputes team hears the Card Member and holds the Merchant's agreement. The
change touches the domain (parties, policies, categories), the evidence graph (static, dispute-only,
schema-as-data), where agents log what they find (a Case Notebook, not the graph), the tools and
skills, the case set (5 new cases), the report (Amex verdicts, a category, System Improvements), a
new, unwired merchant-agent extension, and the frontend.

## 2. Decisions (settled; do not re-open)

| # | Decision |
|---|---|
| D1 | **Pure closed loop.** Amex is issuer, network and acquirer; Merchants contract directly with Amex. No OptBlue acquirers, no GNS partner issuers, no issuer bank anywhere. |
| D2 | **Amex decides the Dispute.** Per charge: `accepted`, `partially_accepted`, `rejected`, `goodwill_credit`, `not_a_dispute`, `fraud_referral`. No network action, reason code, Inquiry/reply cycle, late-reply case or chargeback program. Who funds a credit follows from the verdict (accepted/partial → Merchant; goodwill → Amex). |
| D3 | **Disputes only.** Fraud is out of scope: if the Card Member denies taking part, the verdict is `fraud_referral` and nothing else is decided. All fraud/identity-forensics data (devices, IPs, phones, emails, tokens, account events, agent providers, mandates, households as fraud signal) and the fraud/ATO/agentic/household skills are removed. |
| D4 | **Static graph.** Built once by the generator, opened **read-only** by every run, never copied per run. Agents never write to it. `graph_write_finding`, `Finding`, agent-written edge types, `copy_store` and per-run `.lbug` copies are deleted. |
| D5 | **Case Notebook.** Agents log findings to a per-run notebook in SQLite through `notebook_write` / `notebook_read`; every entry cites graph ids (node/edge, including clause ids). |
| D6 | **Memory Notes** move from the graph to the knowledge SQLite (`kind = memory_note`), searched by `search_knowledge`, written by `memory_write`. `consolidate_memory` stays. |
| D7 | **Dispute-relevant background only.** ~150 Card Members, ~30 Merchants each with its own Merchant Policies, ~3k charges, ~60 past Disputes with outcomes, Offers/enrolments, subscriptions, invoices. No data a dispute investigator would never traverse. |
| D8 | **Policies in both places.** Policy documents and their Clauses are graph nodes (for applicability: which Merchant, program, Offer, order, subscription they govern and which version the Card Member accepted) **and** clause-level search documents (for content). One markdown source is projected into both. No precomputed conflict/"violates" edges. |
| D9 | **Schema as data.** One `data/generator/ontology.yaml`: every label, edge type and property has a `description`; every label has a `group`. `graph_schema` returns it. Prompts, skills and tools never name a label or edge type (a test enforces this). The frontend derives regions and colours from `group`. Changing the graph = editing the YAML + the generator. |
| D10 | **System Improvements** on the report: `system_improvements: list[SystemImprovement]` (target, issue, suggestion, evidence); may be empty. |
| D11 | **Dispute Category** is exactly one of `NKN, RET, CNC, CNR, DMG, DSS, DUP, NRC, OVR, PDD` (CNR = Continuity/Recurring Billing), chosen by the adjudicator on the report and per charge. Triage's `case_type` stays a free label (framework unchanged). |
| D12 | **No time component.** No deadlines, filing windows, response windows, Reg Z clocks or "policy in force on date X" lookups. The policy version a Card Member saw is an explicit edge. Dates remain on records only for realism. Reg Z, Reg E, `EvidenceRequest`, `missing-evidence-default` and `as_of` filtering are removed. |
| D13 | **Merchant agent extension**: built (typed request → `MerchantSubmission` contract, a Deep Agent over the Merchant's own records, a writer that saves submissions for the generator to ingest) but **not wired** into the runtime or config. All showcase evidence is already in the graph. The README documents how to wire it later. |
| D14 | **Merchant Submissions are graph data**, inserted by one function `insert_submission()` used by the case builders now and by the merchant agent's output later (via a rebuild). |
| D15 | **Clean replacement.** All Visa/LFB/Reg E/Reg Z corpus, the 10 old cases, their ground truth, the committed showcase runs and the retired skills are deleted (git history keeps them). |
| D16 | **Framework unchanged.** triage → supervisor ⇄ workers → adjudicator → consolidate_memory, `invoke_structured`, structured outputs, event envelope, loop termination, role catalog in YAML. Only tools, skills, prompts/role text, schemas' domain fields, data and storage change. |
| D17 | **Cleanliness gate.** Every stage ends by running the `simplify` skill over the stage's changed files: elegant code, no dead code, no legacy paths, no shims, no redundant abstraction layers. |

## 3. Domain model

Vocabulary is in `CONTEXT.md`. Research grounding for each rule is cited as `R02 §x` (the research
doc). Policy texts are **paraphrased** from the public Amex sources in R02 with the source URL in
front matter; Merchants and people are fictional.

### 3.1 How an Amex Dispute is decided (what skills and policy text teach)

1. A Merchant Policy is **evidence, not an override**. Amex Policy decides whether it was validly
   disclosed and accepted at purchase, and whether it can reach this situation (R02 §5.1).
2. The Merchant Policy that counts is the **version the Card Member accepted** for that order,
   booking or subscription (an edge), not the Merchant's current website.
3. Terms that are ambiguous, or Merchant conditions that contradict an Amex program's terms the
   Merchant agreed to, resolve **against the drafter** (R02 §5.1 "unambiguous terms", §5.2).
4. An **Amex Offer** is Amex-funded and card-specific; a missing Offer credit is never a Merchant
   error. A **merchant-funded** discount not applied is a genuine OVR (R02 §6.3).
5. Charges by an **Additional Card Member** bill to the Basic Card Member's account and are
   authorized use, not fraud and not a Merchant error.
6. **Goodwill** is Amex's discretion under a written Amex servicing clause, never a default.
7. `not_a_dispute`: the charge was never a Merchant error and the claim rests on a
   misunderstanding of what or who was charged; resolved by explanation. `rejected`: the Card
   Member contests the Merchant's conduct and the Merchant's position is upheld.

### 3.2 Dispute Categories

| Code | Meaning (R02 §4) |
|---|---|
| NKN | No Knowledge: does not recognise the charge (not fraud) |
| RET | Returned / Refused: sent back or refused, no credit |
| CNC | Cancelled: cancelled an order/booking, charged or not refunded |
| CNR | Continuity / Recurring Billing: cancelled or did not agree to recurring charges |
| DMG | Damaged Merchandise |
| DSS | Dissatisfied with Service / not as described |
| DUP | Duplicate / Multiple Transactions |
| NRC | Not Received |
| OVR | Overcharged: amount differs from what was agreed (incl. discounts, fees, re-rating) |
| PDD | Paid by Other Means |

## 4. Evidence graph

### 4.1 Storage and lifecycle

- LadybugDB, built by `uv run python data/generator/gen.py` into `data/generated/evidence.lbug`
  (plus `ontology.json` beside it). Opened `read_only=True` by runtime, tools, API and evaluation.
- The write-keyword guard in `GraphStore.query` stays (defence in depth); `write_finding`,
  `write_note`, `set_note_status`, `_check_edges`, `_create_edge`, `copy_store` are removed.
- `GraphStore.node(id)` returns one node by id using the prefix → label map, so no caller writes a
  label to fetch a node.

### 4.2 Ontology (`data/generator/ontology.yaml`)

Four groups: **parties**, **commerce**, **terms**, **case**. The full YAML (with descriptions) is in
the plan, Task 1.1. Summary:

| Group | Labels (prefix) |
|---|---|
| parties | CardMember (CMB), CardAccount (ACC), Card (CRD), Merchant (MER), Descriptor (DSC) |
| commerce | Charge (CHG), Order (ORD), LineItem (LIN), Product (PRD), Return (RTN), Subscription (SUB), Invoice (INV), Installment (INS), Payment (PAY), Offer (OFR), Program (PRG) |
| terms | PolicyDocument (POL), Clause (CLS) |
| case | Dispute (DSP), MerchantSubmission (MSB), EvidenceItem (EVI), Communication (COM) |

Edge types: HOLDS{role}, ISSUED_ON, CARRIED_BY, CHARGED_TO, AT_MERCHANT, DESCRIBED_AS, DESCRIBES,
AFFILIATE_OF, FOR_ORDER, HAS_LINE, OF_PRODUCT, REFUNDS, RETURNED_AS, GUARANTEED_WITH,
UNDER_PROGRAM, PARTICIPATES_IN, FOR_SUBSCRIPTION, SUBSCRIBED_WITH, HAS_INSTALLMENT, SETTLES,
BILLED_TO, PAID_BY, OFFER_AT, ENROLLED_ON, PUBLISHED_BY, HAS_CLAUSE, ACCEPTED{method},
BOUND_BY, GOVERNS, FILED_BY, DISPUTES{amount}, HAS_SUBMISSION, HAS_EVIDENCE, CITES, ASSERTS.

Rules: every label, edge and property is used by a case proof, a decoy or the background (a test
checks label/edge usage); no inferred or agent-written edge types; no `valid_from/valid_to`; ids
are `PREFIX-…` (2–3 uppercase letters) and edges `E-…`.

### 4.3 Policy corpus → graph + search

- Source: `data/corpus/policies/amex/*.md` and `data/corpus/policies/merchant/*.md`. Front matter:
  `doc_id` (a `POL-…` id), `title`, `owner` (`amex` | `merchant`), `kind`, `version`, `audience`
  (`card_member` | `merchant`), `source_url` (Amex docs), `publisher` (Merchant id for merchant
  docs). Each `## <number> <heading>` section is a Clause with id `CLS-<doc suffix>-<number>`.
- `data/generator/policies.py::load_policies(dir) -> list[PolicyDoc]` parses them once. The
  generator writes PolicyDocument + Clause nodes + HAS_CLAUSE edges; the case/world builders add
  the applicability edges (PUBLISHED_BY, ACCEPTED, BOUND_BY, GOVERNS). Background merchants get
  template policies generated in code through the same `PolicyDoc` type.
- `data/generator/knowledge.py` indexes **one search document per Clause** (`doc_id` = the clause
  id, `kind = "policy"`, title = document title + clause heading) plus precedents. A search hit is
  therefore also a graph node id the agent can pivot on.
- Amex documents (paraphrased, grounded in R02): Merchant Regulations excerpt (policy disclosure
  and acceptance, credits to the original Card, advance payments and unambiguous terms, lodging
  rate honouring, recurring billing), Card Member Agreement excerpt (Additional Card
  responsibility), Amex Offer terms, Platinum benefit terms (Platinum Stays, Card Member-facing),
  Platinum Stays participation terms (Merchant-facing), and the Amex Dispute Guide (categories,
  verdict meanings, goodwill clause, fraud referral, System Improvements).

### 4.4 Background (`data/generator/world.py`)

Seeded, deterministic. ~150 Card Members (some with two Card Products, ~15 accounts with an
Additional Card Member), ~30 Merchants across retail, lodging, subscription, events/venues and
dining with template Merchant Policies, ~3k charges (purchases, credits, recurring), orders with
line items and products, some returns, ~20 subscriptions, ~10 invoices with installments and
other-means payments, ~12 Amex Offers with enrolments, one Amex program (Platinum Stays) with
~6 participating hotels, and ~60 resolved past Disputes (`status = "resolved"`, `outcome`) with
submissions. Benign look-alikes appear naturally (namesakes, affiliated merchants, standard vs
custom products, several plans at one subscription merchant).

## 5. The five cases

Each is solvable only by connecting graph nodes and policy clauses, has at least one decoy, and
has a misleading surface. Ids and amounts are fixed (full node/edge lists in the plan, Stage 4–5).

| Case | Category | Card Member says | What the graph shows | Decoy | Verdict (credit) | Expected System Improvement targets |
|---|---|---|---|---|---|---|
| **A** DSP-2026-91001 "Final Sale Means Final" | RET | "I returned the sofa within 30 days like the website says; they refused my $2,400 refund." | The line item's fabric option is *Customer's Own Material*, which the product lists as a **custom** option. The order is ACCEPTED (checkbox) against checkout terms v4 whose clause 4.3 says COM and made-to-measure pieces are final sale; the confirmation email repeats it. The Card Member read the website headline (30-day returns), whose own clause points to the checkout terms. Amex disclosure/acceptance rule is satisfied. | Another Card Member's standard-fabric sofa from the same Merchant, returned and refunded. | rejected (0) | none required |
| **B** DSP-2026-91002 "Platinum Rate, Gold Card" | OVR | "The hotel charged $1,300, not the $1,000 Platinum rate." | Booking under the Platinum Stays program, **guaranteed with the Platinum Card**; folio settled with the Card Member's own **Gold Card** and re-rated under the hotel's folio clause 7 ("Platinum rate only if settled with a Platinum Card"). Amex's Card Member benefit clause says "book with your Platinum Card" and is silent on payment; the Merchant-facing participation clauses 3.2 (honour the rate confirmed at booking) and 3.4 (no extra eligibility conditions) bind the hotel. **Amex Policy vs Merchant Policy conflict.** | Another guest's booking guaranteed with a Gold Card, correctly charged the Best Available Rate. | accepted (300, Merchant) | amex_policy, merchant_policy |
| **C** DSP-2026-91003 "The Offer on the Other Card" | OVR | "Northwind should have taken $100 off." | Amex Offer (Amex-funded, spend $500 get $100) ENROLLED_ON the Card Member's **Platinum**; the $540 charge is on their **Gold**. Merchant price correct, no merchant-funded discount. Offer terms: enrolled Card only. Amex Dispute Guide goodwill clause G-2: once per Card Member when the Offer was on another of **their own** Cards and the purchase otherwise qualified; this Card Member has no prior Offer goodwill. | A prior Offer goodwill filed by a **different** Card Member with the same name. | goodwill_credit (100, Amex) | process |
| **D** DSP-2026-91004 "Paid by Transfer" | PDD | "I paid Willow Barn by bank transfer ($1,500 and $4,500), so the $5,000 card charge is a double payment." | Venue invoice $6,000 = deposit $1,500 + balance $4,500. The $1,500 transfer SETTLES the deposit; the $5,000 charge SETTLES the balance → $500 over. The $4,500 transfer went to **Willow Barn Catering** (AFFILIATE_OF the venue) and settles the catering invoice. | The catering transfer. | partially_accepted (500, Merchant) | merchant_policy or process |
| **E** DSP-2026-91005 "Cancelled the Wrong Plan" | CNR | "I cancelled StreamCo and they keep billing me $22.99 as SC*DIGITAL SVCS." | Cancellation confirmation is for the **Individual** plan (subscribed with the Basic Card), which stopped. The three $22.99 charges are the **Family** plan subscribed with the **Additional Card** held by the Additional Card Member on the same account; descriptor resolves to StreamCo. Recurring terms accepted; CMA: Basic Card Member responsible for Additional Card charges. | The Individual plan's last charge, already refunded. | not_a_dispute (0) on all three charges | none required |

Coverage: categories RET, OVR ×2, PDD, CNR; verdicts rejected, accepted, goodwill_credit,
partially_accepted, not_a_dispute (`fraud_referral` is reachable, not exercised). A shows an empty
System Improvements list is valid; B shows the Amex-vs-Merchant clause conflict and two targets.

### 5.1 Ground truth (evaluator-only)

Per case: `expected` (report verdict, category, per-charge verdict/credit/liability, required
System Improvement targets), `solution_node_ids` (5–25), `proof_patterns` and `decoy_patterns`
(Cypher run at build time), `misleading_surface`, `required_capabilities`. Never loaded into the
graph, knowledge store, prompts or tools. The catalog (`case_catalog.json`) holds only title,
Card Member's words, amount and the Card Member-stated claim; never the category or answer.

## 6. Tools

| Tool | Purpose | Adjudicator? |
|---|---|---|
| `graph_schema` | ontology with descriptions, groups and counts | yes |
| `graph_query(cypher, params)` | read-only Cypher, row cap, returns node/edge ids | yes |
| `graph_neighbors(id, rel_types?, direction?)` | one-hop expansion (no time filter) | yes |
| `graph_find(text, labels?)` | case-insensitive substring search over every string property of every (or the given) label; returns matching nodes | yes |
| `search_knowledge(query, kinds?)` | hybrid FTS+vector over clauses, precedents, active memory notes (no `as_of`) | yes |
| `notebook_write(kind, text, node_ids, edge_ids)` | append a Case Notebook entry; ≥1 citation; every cited id must exist in the graph | no |
| `notebook_read(kinds?, author?)` | this run's notebook entries | yes |
| `memory_write(op, text, sources, replaces, confidence)` | write/supersede/retract/merge a Memory Note in the knowledge store | no (consolidate_memory only uses it) |
| `python(code)` | restricted arithmetic | no |

Events: `notebook_write` replaces `graph_write`; `memory_write` stays; every `tool_result` still
carries `node_ids`/`edge_ids`.

### 6.1 Case Notebook

SQLite file `data/generated/notebook.sqlite`, table `notebook_entries(entry_id TEXT PK, run_id,
seq INTEGER, author, kind, text, node_ids JSON, edge_ids JSON, created_at)`. `kind` ∈ `fact`,
`hypothesis`, `policy_reading`, `conflict`, `ruled_out`, `improvement_idea`. `src/notebook.py`
holds `write_entry`, `read_entries`; the path is on `RuntimePaths.notebook_db`. The supervisor and
adjudicator inputs include the run's notebook entries.

## 7. Skills (rewritten, label-agnostic)

`graph-investigation`, `case-notebook`, `dispute-categories`, `policy-analysis`,
`offers-and-benefits`, `payments-and-credits`, `recurring-billing`, `dispute-outcomes`,
`memory-hygiene`. Deleted: `agentic-transactions`, `fraud-and-ato-signals`, `household-authority`,
`missing-evidence-default`, `network-reason-codes`, `not-received-and-refunds`, `reg-e-and-reg-z`,
`unrecognized-charges`. Skills teach concepts ("find the policy version the Card Member accepted
for this purchase") and always tell the agent to read `graph_schema` descriptions to find how the
current graph represents it.

## 8. Report (`CaseReport`)

Changes from the previous spec §3.4: `Verdict` gains `goodwill_credit`, `fraud_referral`;
`DisputeCategory` enum; `TransactionDecision` → `ChargeDecision{charge_id, verdict, category,
disputed_amount, credit_amount, card_member_liability, rationale, evidence}` (no network action,
reason code); `CaseReport.claim_family` → `category`; `cardholder_letter` → `card_member_letter`;
`missing_evidence` and `account_actions` removed; `system_improvements: list[SystemImprovement]`
added. Validators: evidence on every charge/hypothesis/improvement; credit + liability = disputed;
`rejected`/`not_a_dispute`/`fraud_referral` → credit 0; `goodwill_credit`/`accepted` → credit > 0.

## 9. Merchant agent extension (unwired)

`src/extensions/merchant_agent/`: `contract.py` (`EvidenceAsk`, `MerchantEvidenceRequest`,
`MerchantSubmission`, `SubmittedItem`, `SubmittedPolicy`), `agent.py` (`respond(request, records_dir,
model, agent_builder) -> MerchantSubmission` via `invoke_structured` over a Deep Agent with
read-only tools on `data/merchant_records/<merchant_id>/`), `store.py` (`save_submission(submission,
dir)` → `data/corpus/submissions/<dispute_id>.json`). The generator's `insert_submission(graph,
submission)` ingests every saved submission on the next build. Nothing in `src/runtime*`, `tools.py`
or `config/` imports or references it. README section "Merchant agent (not wired)".

## 10. API and frontend

API: `GET /graph/ontology` (groups, labels, descriptions) added; the `run_id` graph-copy parameter
and run-graph lookups removed (one static graph); `GET /runs/{id}/notebook` not needed (the
frontend derives the notebook from `notebook_write` events). OpenAPI and trajectory schema
regenerated. Showcase export no longer snapshots run graphs.

Frontend: regions/colours from `/graph/ontology` groups (no hard-coded label table); agent-written
node/edge styling removed; a **Notebook** tab beside Agent flow / Evidence graph listing entries by
author with clickable id chips; Conclusion shows verdict (6 values), category, per-charge table
(charge, category, verdict, disputed, credit, Card Member liability), **System Improvements**,
Card Member letter; network action, reason code, missing evidence, account actions removed.

## 11. Out of scope

Fraud investigation, OptBlue/GNS, Inquiry/chargeback lifecycle, deadlines and clocks, Reg Z/E,
wiring the merchant agent, security hardening, governance.
