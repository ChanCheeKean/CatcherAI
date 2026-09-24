# DisputeAI — Amex dispute revamp: handoff

Last updated: 2026-09-24
Branch: `amex-dispute-revamp` (all work here; never commit to `main`; do not merge)
Current phase: **S11 complete (pass@1 3/5, pass@3 4/5; target not yet met); F1, F2 complete**
Next stage: **F3 — Agents over time**. S11b (eval tuning) is
still open and does not depend on the F stages; it should start with the `ontology.yaml`
description bug in §8 "F1 (part 2)".

This file is the single entry point for any agent continuing this work. The previous handoff (the
Visa graph-discovery revamp, S0–S14) is in git history: `git show main:handoff.md`.

---

## 1. Read first (in order)

1. This file, completely.
2. `docs/superpowers/specs/2026-09-23-amex-dispute-revamp-design.md`: the approved design,
   decisions D1–D17. If this handoff and the spec disagree, the spec wins; record the conflict in §7.
3. `docs/superpowers/plans/2026-09-23-amex-dispute-revamp.md`: **only your stage's section**, plus
   its "Global Constraints" block at the top.
4. `CONTEXT.md`: the vocabulary. Use its terms in code, prompts, skills and docs.
5. `docs/research/02-amex-dispute-research.md`: only when your stage writes policy text, skills or
   cases (Stages 2, 4, 5, 7).
6. Only the files listed in your stage's tasks. Do not read the whole repo.

## 2. What we are building (one paragraph)

The card-dispute POC (agents + graph) is rebuilt for **American Express**. Amex is issuer, network
and acquirer at once, so one disputes team hears the Card Member and holds the Merchant's
agreement: no issuer bank, no chargeback exchange. The agent framework stays exactly as it is:
triage → supervisor ⇄ parallel Deep Agent workers → adjudicator → consolidate_memory. What
changes:
- **The evidence graph.** It is static, read-only, dispute-only, and its schema is defined as data
  in `ontology.yaml`, with a description on every item.
- **Policies.** Amex Policies and Merchant Policies are stored as documents and clauses. Each is
  both a graph node and a search document.
- **Findings.** Agents log findings to a per-run **Case Notebook** instead of writing to the graph.
- **Memory Notes** live in the knowledge store.
- **Tools and skills** are rewritten to be label-agnostic.
- **Five new cases** (A–E) cover these verdicts: rejected, accepted with an Amex-vs-Merchant clause
  conflict, goodwill_credit for an Offer used with the wrong Card, partially_accepted for a
  paid-by-transfer case, and not_a_dispute for a wrong-plan cancellation.
- **The report** gains Amex verdicts, a Dispute Category, and **System Improvements**.
- **Merchant agent extension.** It is built but not wired in.
- **Frontend** changes follow from all of the above.

## 3. Non-negotiable rules for every stage

- **Framework unchanged.** Do not add, remove or rewire LangGraph nodes. Add no rule-based gates
  and no per-case Python. Every LLM output goes through `invoke_structured` as a Pydantic model.
  Only the loop-termination rules are hard-coded.
- **Static graph.** No code in `src/` writes to the evidence graph at run time. There are no
  per-run graph copies.
- **Schema as data.** Labels, edges and properties live only in `data/generator/ontology.yaml`.
  Prompts, skills, config and runtime code never name them; `tests/test_label_agnostic.py`
  enforces this from Stage 7.
- **Disputes only, no time component.** No fraud investigation, no deadlines, windows, `as_of` or
  `valid_from`/`valid_to`.
- **Ground truth is evaluator-only.** Never load it into the graph, knowledge, prompts or tools.
- **Robust, not over-engineered.** Use plain functions and data. No wrappers, class hierarchies,
  shims, stubs, TODOs or commented-out code. Delete anything unused. Add a node, tool, field or
  file only when a case or the demo needs it.
- **Keep the suite green without shims.** See the plan's Global Constraints.
- **Verify library APIs** against live docs (context7) before relying on them: ladybug Cypher
  functions, deepagents.

## 4. Environment and commands

- Python: `uv sync --extra dev --extra api`. Tests: `uv run pytest`. Lint:
  `uv run ruff check src tests data/generator`. Format:
  `uv run ruff format src tests data/generator`.
- Generator: `uv run python data/generator/gen.py` writes to `data/generated/` (graph, knowledge,
  catalog, ground truth).
- Frontend: `cd frontend && npm ci && npx tsc -b && npx vitest run && npm run build`; E2E with
  `npm run e2e`.
- Real LLM: `.env` holds `OPENAI_API_KEY`, and the model is set in `config/models.yaml`. Tests
  marked `@pytest.mark.llm` are skipped by default. Eval: `uv run inspect eval --k 1`.
- Launcher: `./dev.sh` (backend :8000, frontend :5173). It is broken from S0 until S9/S10 by design.

## 5. Stage protocol (every stage, no exceptions)

1. `git checkout amex-dispute-revamp && git pull`. Read §1–§4, then your stage in the plan.
2. Implement only your stage's scope, following the plan's tasks and steps (tests first). If the
   stage turns out bigger than described, stop at a coherent point, add the remainder as a new
   stage in §6, and finish this protocol.
3. `uv run pytest` and ruff must pass (frontend stages also run the frontend checks).
4. **Run the `simplify` skill over every file changed in this stage.** The goals are elegant code,
   no dead code, no legacy paths, no redundant abstraction layers and no leftovers from the Visa
   design. Re-run the tests afterwards.
5. Update this handoff:
   - the header (`Last updated`, `Current phase`, `Next stage`)
   - tick the stage in §6
   - append an entry to §8: what you built, which files, the commands and their results,
     deviations, tests deleted under the keep-green rule, and open issues

   Update the spec only if a design decision changed, and say so in §8.
6. Commit with a descriptive message ending with the co-author line used in this repo's recent
   commits, then `git push -u origin amex-dispute-revamp`.
7. **Stop.** Report a short summary to the user. Do not start the next stage.

Complexity guide (for picking the model):
- **Simple:** mechanical, with clear instructions.
- **Medium:** design judgement within a clear contract.
- **Complex:** data realism, policy writing, or tuning LLM behaviour.

## 6. Stages

Details for each stage are in the plan section of the same name.

| Stage | Complexity | Goal | Done |
|---|---|---|---|
| **S0** Teardown of the Visa world | Simple | Delete Visa/LFB/Reg E/Reg Z corpus, the 10 cases, the showcase data, retired skills and screenshots; empty the case kit. | ☑ |
| **S1** Ontology as data + static graph store | Medium | `ontology.yaml` + loader; builder validates against it; `GraphStore` read-only by default, schema with descriptions, `node`, `find`; all write paths and `copy_store` removed. | ☑ |
| **S2** Policy corpus, clause search, memory in knowledge | Complex | 6 Amex + 8 Merchant policy markdown docs grounded in the research; `policies.py` projects them into graph nodes and clause-level search; retrieval without `as_of`; Memory Notes in SQLite; Amex precedents. | ☑ |
| **S3** Background world | Medium | Deterministic dispute-only world (~150 Card Members, ~30 Merchants with template policies, ~3k charges, Offers, program, subscriptions, invoices, ~60 past Disputes). | ☑ |
| **S4** Submission contract, case kit, cases A and B | Complex | `MerchantSubmission` contract + `insert_submission`; case kit for Amex; case A "Final Sale Means Final", case B "Platinum Rate, Gold Card". | ☑ |
| **S5** Cases C, D, E + end-to-end generator | Complex | Case C "The Offer on the Other Card", case D "Paid by Transfer", case E "Cancelled the Wrong Plan"; `gen.py` ingests saved submissions; every ontology label/edge used. | ☑ |
| **S6** Case Notebook, tools, read-only runtime | Medium | `notebook.py`; tools `graph_find`, `notebook_write`/`notebook_read`, memory in knowledge; runtime and API read the static graph; notebook in supervisor/adjudicator input. | ☑ |
| **S7** Report, prompts, skills, evaluation | Complex | Six verdicts, Dispute Category, `ChargeDecision`, `SystemImprovement`; new `agents.yaml`; 9 label-agnostic skills; label-agnostic guard test; eval scoring. | ☑ |
| **S8** Merchant agent extension (not wired) | Medium | `respond()` Deep Agent over merchant records, `save_submission`, guard test that nothing imports it, README section. | ☑ |
| **S9** API, showcase, schemas | Medium | `/graph/ontology`; no run-graph copies; showcase exports events only; OpenAPI + event schema regenerated. | ☑ |
| **S10** Frontend | Medium | Ontology-driven regions/colours; Notebook tab; Conclusion with category, six verdicts, System Improvements. | ☑ |
| **S11** Real-LLM eval + tuning | Complex | pass@1 5/5 on A–E by improving skills, policy wording, ontology descriptions and prompts only. | ☑ (3/5; remainder in S11b) |
| **S11b** Finish tuning | Complex | Fix the truncated `ontology.yaml` descriptions (§8 "F1 (part 2)"), then re-run eval on the final S11 skills and policy text (the case C fixes are untested live); tune until pass@1 5/5, then pass@3; refresh the showcase. | ☐ |
| **S12** Final cleanup, showcase, README | Simple | Legacy sweep, screenshots, showcase export, Amex README; whole-branch `simplify`. | ☐ |
| **F1** Demo: replay, funnel, cited graph + polish | Medium | Verify the replay, header funnel and "Cited only" graph already committed (see §8 "F1"), then the polish: graph colours by region, four-item legend, captions instead of raw ids, formatted money, proof on case cards, no truncated agent names. | ☑ |
| **F2** Demo: report beside the graph | Medium | Claims and their highlighted evidence visible together; Amex-vs-Merchant Clause comparison; decoys ruled out tied to their nodes. | ☑ |
| **F3** Demo: agents over time | Medium | Swimlane timeline of the agent flow (lane per agent, tool-call ticks, Notebook marks, sent-back loops) with tool edges on the map collapsed into per-agent counts; with nothing selected, the inspector narrates the replay. | ☐ |

The F stages come from a frontend review for the demo (the frontend must show how robust the
agents and the graph are). They have no plan section; their scope is in §8 "F1". Run one F stage
per session, in order, under the §5 protocol, and take a screenshot check of the running app
(`./dev.sh`, then open a case, which replays it) before committing.

## 7. Conflicts and open questions

- `docs/research/02-amex-dispute-research.md` marks several points UNVERIFIED: the NKN/RET/…
  abbreviations as Amex's own, Platinum benefit details, and Amex goodwill policy. The policy texts
  are **paraphrased and fictionalised where unverified**; front matter keeps the source URL. Do
  not present them as verbatim Amex text.
- The label-agnostic guard excludes two unavoidable domain contract identifiers: the `ACCEPTED`
  verdict enum member shares a name with a graph edge, and the required `MerchantSubmission`
  class shares a name with a graph label. All other schema names remain guarded.

## 8. Stage log

### Planning — 2026-09-23
- Grilling session settled D1–D17, recorded in the spec §2. Research is in
  `docs/research/02-amex-dispute-research.md`. The glossary is in `CONTEXT.md`.
- Files added on this branch: `CONTEXT.md`, the research doc, the spec, the plan and this handoff.
- The five cases replace the research doc's three sketches:
  - The hotel-deposit time-zone sketch was dropped (D12: no time component).
  - The wrong-card Offer sketch became case C.
  - The NKN subscription sketch became case E's descriptor and Additional Card twist, filed as CNR.

### S0 — 2026-09-23
- Removed the Visa/LFB/Reg E/Reg Z policy corpus and author script, all ten old case builders,
  committed showcase data, eight retired skills, and two screenshots. Emptied
  `data/generator/cases/__init__.py`'s builder tuple, updated its truth contract and charge helper,
  reset `CASE_NEEDS` in `data/generator/capabilities.py`, and set
  `data/corpus/precedents.yaml` to `[]`.
- Deleted `tests/test_cases.py` and `tests/test_showcase.py` with their subjects. Also deleted
  `tests/test_knowledge.py` (its policy, precedent, and retired-skill assertions depend on the
  removed corpus) and `tests/test_tools.py` (its Visa/Reg E, fraud-label, and graph-write behavior
  is replaced in S6). No tests were skipped or replaced with compatibility shims.
- `uv run pytest -x -q`: 49 passed. `uv run ruff check src tests data/generator`:
  passed. `uv run ruff format --check src tests data/generator`: passed.
  `git diff --check`: passed. The `simplify` skill was not installed, so the changed files
  received a manual dead-code and legacy-path review.
- The prescribed `git pull` could not run because this new local branch has no upstream; origin
  has no `amex-dispute-revamp` branch yet. The stage push will create it.
- Remaining legacy-term scan hits are confined to files scheduled for later stages:
  `data/generator/world.py` (S3), `src/schemas.py` and `config/agents.yaml` (S7),
  `skills/graph-investigation/SKILL.md` (S7), and
  `tests/test_schemas_models.py` / `tests/test_runtime.py` (S7/S6).
- No design decision changed; the spec was not edited. The app remains intentionally
  unrunnable end to end until later stages restore the generated world and runtime.

### S1 — 2026-09-23
- Added the described schema in `data/generator/ontology.yaml` and a validating loader in
  `ontology.py`. `Graph` now validates labels, prefixes, properties and edge pairs from that YAML
  and exports the full spec. Tests cover descriptions, references and builder rejection.
- `GraphStore` opens read-only by default; the bulk loader explicitly opens writable. Its schema
  includes groups and descriptions, and it provides `node` and case-insensitive `find` lookups.
  Removed graph mutation methods, temporal neighbor filtering and `copy_store`. Escaped graph
  identifiers in Cypher so the `Order` label works with Ladybug.
- `runtime_entry.py` now opens the shared graph read-only. `showcase.py` exports run events without
  per-run graph differences and no longer restores graph copies. These small changes keep imports
  valid until the full runtime and showcase rewrites in S6 and S9; the app is still not runnable.
- Deleted `tests/test_runtime.py`, `tests/test_api.py`, `tests/test_evaluation.py` and
  `tests/test_generator_world.py`: they exercise old labels, copied graphs or the old world, and
  are scheduled for replacement in S3/S6/S7/S9. No shims or skips were added.
- Verified Ladybug `lower()` and `CONTAINS` in its official text-function documentation.
  `uv run pytest -q`: 30 passed. `uv run ruff check src tests data/generator` and
  `uv run ruff format --check src tests data/generator`: passed. `git diff --check`: passed.
  The `simplify` skill is not installed; manually reviewed all changed files for dead code,
  legacy paths and redundant abstractions, then reran the checks.
- No design decision changed. Remaining old tool, API and frontend graph-copy references are
  assigned to their later stages.

### S2 — 2026-09-23
- Wrote 14 policy documents: `data/corpus/policies/amex/` (Merchant Regulations, Card Member
  Agreement, Offer terms, Platinum benefit terms, Platinum Stays participation terms, Dispute
  Guide) and `data/corpus/policies/merchant/` (HGF checkout v4 and returns page v4, HPH
  reservation v2 and folio v1, NWO sale v1, WBV contract v2, WBC catering v1, STC subscription
  v3). They hold 50 clauses. Amex texts are paraphrased (Platinum Stays and the goodwill clauses
  are fictional). Each Amex file opens with a one-line disclaimer before its first clause, and
  the parser drops that line. PLAT-BEN 2.1 does not say which Card must pay (the case-B gap).
- Added `data/generator/policies.py` (`Clause`, `PolicyDoc`, `parse`, `load_policies`,
  `add_to_graph`). `knowledge.py` now indexes one search document per clause (the doc id is the
  clause id) plus precedents. It has no validity dates.
- `src/memory/retrieval.py`: removed `as_of`/`valid_from`/`valid_to`. The documents table columns
  are now `doc_id, kind, title, body, status, sources, run_id, confidence`. Added `add_note`
  (returns `MEM-0001`…) and `set_status`. Search returns active documents only. The kind and
  status filter runs inside both candidate queries: vec0 metadata columns (checked on sqlite-vec
  0.1.9) and an FTS join. Retired notes or excluded kinds therefore never crowd out hits.
- `data/corpus/precedents.yaml`: 8 Amex write-ups. Each is analogous to a showcase case, but none
  uses a showcase case's facts. `gen.py` loads the policies once, projects them into the graph and
  passes them to `build_knowledge`. The memory capability text in `capabilities.py` no longer
  says "as-of".
- Tests: new `tests/test_policies.py`. `tests/test_knowledge.py` was rewritten to cover clause
  search, the kind filter, the Memory Note lifecycle, and that precedents cite only real clause
  ids. `uv run pytest`: 36 passed. `ruff check` and `ruff format --check`: passed.
- `simplify` ran as four review agents (reuse, simplification, efficiency, altitude).
  - Applied: one set of document defaults inside `_insert`; dropped redundant `Path()` wraps;
    filtering at candidate time (above).
  - Skipped: storing policy metadata as a dict, and a list-taking `add_to_graph`. The plan's
    Task 2.2 interfaces fix both. Also skipped the minor efficiency notes (counting ids,
    `executemany`), which make no difference at this corpus size.
- Open issue for S3/S4: `gen.py` currently adds the policies after `build_cases`. ACCEPTED,
  BOUND_BY and GOVERNS edges from world and case builders need the policy nodes to exist first,
  and merchant docs need their publisher Merchant first. S3 should add policies inside world
  building, right after the Merchant nodes. The background template `PolicyDoc`s must go into
  the same list that is passed to `build_knowledge`.
- Open issue for S6: `src/tools.py` still calls `retrieval.search(..., as_of=…)` and the old
  graph-note store methods. It imports cleanly but fails at call time until S6 rewrites it.
- No design decision changed; the spec was not edited.

### S3 — 2026-09-23
- Rewrote `data/generator/world.py`. `build_world(seed=7, corpus=…)` returns `(graph, docs)` and exports
  the Amex anchors (`AMEX_MR`, `AMEX_CMA`, `AMEX_OFFER`, `AMEX_PLAT_BEN`, `AMEX_PS_PART`,
  `PLATINUM_STAYS`). The world is deterministic and dispute-only:
  - 150 Card Members: 135 Basic, a third of them holding two Card Products, and 15 Additional Card
    Members on others' accounts. There are three namesake pairs.
  - 180 accounts, each BOUND_BY the CMA; Platinum accounts are also BOUND_BY PLAT-BEN.
  - 30 Merchants across furniture, apparel, lodging, streaming, events, catering and dining.
    Benign look-alikes include "Northwind Outdoor Supply", "Harbor Point Inn" and
    "Harbor Point Marina Grill", plus two streaming Merchants that share the parent-brand
    descriptor "NVP*NOVAPLAY".
  - 31 generated template policies (`POL-BG-…`); background retailers have a v1 and a stricter v2,
    and orders from 2026-05-01 accept v2.
  - 1,200 orders (retail with line items and products; lodging GUARANTEED_WITH the paying Card).
    Platinum Stays bookings are made only with a Platinum Card at the 6 participating hotels.
  - 2,949 charges: 137 of them are credits with REFUNDS. There are 35 returns (16 refused as
    custom/final sale), 20 subscriptions, and 10 invoices with 22 installments settled by
    charges or other-means payments.
  - 12 Offers (10 Amex-funded with GOVERNS and ENROLLED_ON; 2 merchant-funded).
  - 60 resolved past Disputes spread over the ten categories and all six verdicts. 33 have a
    Merchant Submission, written in the node shape `insert_submission` will use
    (`EVI-<submission suffix>-1`).
  - The world uses every edge type. The only label it leaves unused is Communication, which the
    cases supply.
- **Deviation: the world owns the six corpus-publisher Merchants.** `build_world` must add every
  corpus policy, and PUBLISHED_BY needs the publishing Merchant to exist first. `world.py`
  therefore creates MER-HGF/NWO/HPH/STC/WBV/WBC, their BOUND_BY POL-AMX-MR, MER-HPH's
  PARTICIPATES_IN/PS-PART, MER-WBC AFFILIATE_OF MER-WBV, and DSC-STC. The plan now has a note at
  the top of Stage 4: case builders reference these and must not create them. These Merchants
  also carry background activity; case proofs and decoys stay anchored on case ids. This closes
  the S2 open issue about policy ordering.
- `gen.py` calls `build_world()` and indexes its docs; the separate policy load and add loop are
  gone. `uv run python data/generator/gen.py` succeeds: 136 knowledge documents, and the graph
  loads into Ladybug.
- Two infrastructure fixes surfaced by real data:
  - `Graph.node`/`Graph.edge` parameters are positional-only, because the ontology's
    `Installment.label` property collided with the `label` argument.
  - `graph_store.load` COPY now passes `auto_detect=false` plus an explicit delimiter, quote and
    escape. Ladybug sniffs the CSV dialect from the first rows and decided "no quoting" when
    850 unquoted order rows came before the first summary containing a comma. This was verified
    against the Ladybug CSV import docs (context7). There is a regression test in
    `tests/test_graph_store.py`.
- Tests: new `tests/test_generator_world.py` (determinism, scale and policies, every Merchant
  BOUND_BY MR, corpus publishers and program wiring, installments add up and are settled in
  full). `uv run pytest`: 42 passed. `ruff check` and `ruff format --check`: passed. No tests
  were deleted.
- `simplify` ran as four review agents.
  - Efficiency: no findings; `build_world` takes about 30 ms.
  - Applied:
    - One `_merchants_in(*categories)` helper replaces five tuple-unpacking filters.
    - `_offers` excludes corpus Merchants by `_CORPUS_TERMS` rather than by list position.
    - `_issue` derives the Card role.
    - Removed the dead DUP evidence entry and the `setdefault` idiom.
    - `_lodging` computes its total once.
    - `_invoices` uses if/else instead of `continue`.
    - `gen.py` uses the default corpus path.
    - The read-only world tests share a module fixture.
    - `Graph.edge` is also positional-only, and the CSV dialect is stated explicitly.
  - Skipped:
    - A shared `clause_id` helper for `policies.parse` and the template generator. It would be
      two call sites of one f-string.
    - Deriving `_CORPUS_TERMS` from front matter. It records which of a Merchant's corpus
      documents customers accept (HGF and HPH each publish two), which front matter does not say.
- No design decision changed; the spec was not edited. The plan gained the Stage 4 ownership note
  above.

### S4 — 2026-09-23
- **Submission contract.** Added `src/extensions/merchant_agent/contract.py` (`EvidenceAsk`,
  `MerchantEvidenceRequest`, `SubmittedItem`, `SubmittedMessage`, `MerchantSubmission`), plus
  empty package `__init__.py` files. Added `data/generator/submissions.py`:
  - `insert_submission` writes the MerchantSubmission, `EVI-<suffix>-<n>` items and
    `COM-<suffix>-<n>` messages with HAS_EVIDENCE and ASSERTS, and CITES.
  - `load_saved(dir)` returns `[]` when the directory is absent. Nothing calls it yet; `gen.py`
    starts ingesting saved submissions in S5.
  - `world._past_disputes` now builds `MerchantSubmission`s and calls `insert_submission`. The old
    `_submission` helper is gone, and the world's JSONL output is byte-identical to S3.
- **Case kit.**
  - `build_cases` runs `a_final_sale`, then `b_platinum_rate`. It imports them inside the function
    to avoid the import cycle, and it fills in `required_capabilities` for each case.
  - `CaseTruth` gained a `claim` key (deviation from the plan's key list). The catalog now writes
    `{case_id, title, claim, amount, summary}`, so `claim_type` is gone.
  - `validate_cases` checks solution ids with `store.node`, because the old unescaped `MATCH` broke
    on `Order`. The unused `min_rows` option was dropped.
  - `capabilities.py`: renamed the Graph and write-path signals, removed the temporal wording, and
    added `CASE_NEEDS` A and B.
- **Cases.**
  - `cases/a_final_sale.py` (DSP-2026-91001, RET, rejected). Case A is the COM sofa under
    `CLS-HGF-CO-V4-4.3`; the decoy is a refunded Oat-linen sofa.
  - `cases/b_platinum_rate.py` (DSP-2026-91002, OVR, accepted $300). The booking is guaranteed with
    CRD-B01 (Platinum) and charged to CRD-B02 (Gold). The decoy is ORD-B02 guaranteed with Gold,
    resolved by DSP-HIST-B02 (rejected) with submission MSB-HIST-B02 citing PS-PART 3.2.
  - Both reference the world-owned Merchants and create no Merchants. Their accounts are BOUND_BY
    the CMA, as in the world.
- **Shared builders.** `world.py` now exports `open_account`, `issue_card`, `post_charge` and
  `file_dispute`, which take fixed ids. The world and both cases use them.
- **Cypher escaping.** Ladybug rejects `(o:Order)` (ORDER is a keyword), so case patterns write
  ``(o:`Order`)``. The plan now has a "Changed in Stage 4" note before Task 4.1 covering this, the
  shared builders, and `claim`.
- **Tests.** New `tests/test_submissions.py` and `tests/test_cases.py`. `uv run pytest`: 47
  passed. `ruff check` and `ruff format --check`: passed. `uv run python
  data/generator/gen.py` builds, loads and validates both cases (136 knowledge documents). No
  tests were deleted.
- **`simplify`** ran as four review agents.
  - Efficiency: no findings.
  - Applied:
    - Shared world builders instead of three copies of the account, card, charge and dispute
      shapes.
    - Explicit `status`/`outcome` parameters instead of `**status`.
    - Dropped `min_rows`.
    - Removed test asserts that repeated `_check_case`.
  - Skipped:
    - Defaulting `messages`/`cited_ids` on the contract, since S8 will need strict structured
      output with every field required.
    - Moving `CaseTruth` into `cases/contract.py` to avoid the lazy import. It is small and matches
      the old kit.
    - Extracting order and return builders, since the cases diverge from the world there on
      purpose.
    - Renaming the `Order` label (see the open issue below).
- **Open issue for S6/S7.** The agent's `graph_query` passes raw Cypher, and an LLM will naturally
  write `(o:Order)`, which fails to parse. Choose one of:
  - handle it in `GraphStore.query` or the tool (auto-escape ontology labels, or return a hint on
    parse errors);
  - document backticks in the tool description or `graph_schema`;
  - rename the label, which is a spec change (§4.2).
- **Open issue for S9/S10.** `src/api/models.py`, `frontend/src/api/types.ts`,
  `frontend/src/pages/CasesPage.tsx` and `tests/e2e_server.py` still read the catalog's
  `claim_type`. Switch them to `claim`.
- No design decision changed; the spec was not edited.

### S5 — 2026-09-24
- **Cases.** Ids, amounts and patterns follow the plan.
  - `cases/c_offer_card.py` (DSP-2026-91003, OVR, goodwill_credit $100). The Amex Offer OFR-NWO-100
    is ENROLLED_ON CRD-C01 (Platinum), and the $540 charge is on CRD-C02 (Gold). The Card Member's
    own history holds DSP-HIST-C01, a rejected restaurant duplicate. **Deviation:** the namesake
    decoy CMB-C02 also holds a Platinum Card (CRD-C04) with its own Amex Offer OFR-C02 at
    Linen & Loom. Without it, their past intake ("added the Offer to my Platinum") would contradict
    the graph.
  - `cases/d_paid_transfer.py` (DSP-2026-91004, PDD, partially_accepted $500). The $1,500 transfer
    settles the venue deposit, the $5,000 charge settles the $4,500 balance, and the $4,500
    transfer settles the affiliated caterer's invoice.
  - `cases/e_wrong_plan.py` (DSP-2026-91005, CNR, not_a_dispute on three charges). The Family plan
    is SUBSCRIBED_WITH the Additional Card CRD-E02. The Card Member's own evidence is COM-E01
    (HAS_EVIDENCE from the Dispute), which ASSERTS the cancelled Individual plan.
  - `CASE_NEEDS` has C, D and E entries. The `claim` phrases are "Promised discount not applied",
    "Paid the same bill twice" and "Billed again after cancelling".
- **Generator.** `gen.build()` runs the world, then the cases, then every saved submission
  (`load_saved(data/corpus/submissions)`, which is absent today). `main()` and the
  `tests/test_cases.py` fixture both call it, so the tests check the graph gen.py writes.
  `uv run python data/generator/gen.py` builds, loads and validates all five cases (136 knowledge
  documents).
- **Ontology coverage.** Every label and edge type is used, so nothing was cut from
  `ontology.yaml`. New tests cover label and edge usage and the verdict and category coverage.
- **Shared builders** (from `simplify`):
  - `world.py` gained `add_offer`, `add_subscription`, `bill_subscription`, `add_invoice`,
    `add_installment` and `pay_other_means`. The background and the cases now use them, and the
    world's JSONL output is byte-identical to before.
  - `file_dispute` now takes `{charge: disputed amount}` and sums the Dispute amount. The old
    single-charge form would have put 68.97 on case E's first DISPUTES edge.
  - `cases.basic_card` replaces the account-plus-Card helpers in A, B and C and the inline pairs in
    D and E.
- **Commands.** `uv run pytest`: 49 passed. `ruff check` and `ruff format --check`: passed.
  `git diff --check`: passed. No tests were deleted.
- **`simplify`** ran as four review agents.
  - Applied: the shared builders above; `g.spec` in the coverage test instead of re-loading the
    ontology; case C's one-use `_product` helper inlined; case D keeps the returned Payment ids
    rather than repeating the literals; one pipeline shared by gen.py and the fixture.
  - Skipped: reading case E's descriptor, plan names and prices from `world._DESCRIPTORS` and
    `_PLANS`. They are private tables, and A and B also write their fixed ids literally.
- No design decision changed; the spec was not edited. The S4 open issues (`Order` escaping in
  `graph_query`, `claim_type` in the API and frontend) still stand for S6, S7, S9 and S10.

### S6 — 2026-09-24
- Added `src/notebook.py`: per-run SQLite entries with cited graph ids, ordered sequence numbers,
  filters by kind and author, and serialized writes. `tests/test_notebook.py` covers isolation,
  ordering, filtering and invalid entries.
- Rebuilt `src/tools.py` around the nine S6 tools. `graph_find` searches graph text; notebook
  writes verify every node and edge id and emit a `notebook_write` event; memory writes use the
  knowledge store. Knowledge search includes active Memory Notes and identifies graph-backed
  search hits without naming an ontology label. Tool descriptions explain Cypher backticks for
  labels that are keywords (the S4 `Order` issue). `tests/test_tools.py` covers these paths.
- `src/runtime_entry.py`, `src/runtime.py` and `src/runtime_support.py` use the static read-only
  graph and a `notebook_db` path, with notebook entries in supervisor and adjudicator inputs.
  The adjudicator gets the six read-only tools. `tests/test_runtime.py` restores parallel
  delegation, notebook visibility, forced termination and structured-boundary coverage.
- `src/api/routers/graph.py` always opens the shared graph; graph endpoints no longer accept a
  run id. `src/api/routers/runs.py` no longer looks for graph copies. Updated the CLI's path
  option and the E2E server fixture from `run_dir` to `notebook_db`. `src/api/context.py` needed
  no change because it had no run-graph reference.
- `uv run pytest`: 58 passed. `uv run ruff check src tests data/generator`,
  `uv run ruff format --check src tests data/generator`, and `git diff --check`: passed.
  No tests were deleted. The `simplify` skill is not installed; manually reviewed all changed
  files for dead code, legacy paths and redundant abstraction, then reran checks.
- No design decision changed; the spec was not edited. The remaining `claim_type` API/frontend
  references belong to S9/S10. The old `src/schemas.py`, `config/agents.yaml` and skills are
  replaced in S7, so real-model adjudication is expected to need that stage.

### S7 — 2026-09-24
- Replaced the report domain fields in `src/schemas.py` with six verdicts, ten Dispute Categories,
  per-charge decisions and evidence-cited System Improvements. Updated `src/runtime_support.py`
  to collect references from charge and improvement evidence. Updated schema and runtime tests.
- Replaced `config/agents.yaml` with the seven Amex roles and prompts. Wrote nine label-agnostic
  skills in `skills/`. Added `tests/test_label_agnostic.py`; its two required contract-name
  exceptions are recorded in §7.
- Updated `src/evaluation.py` to score verdict, category, exact charge set and credits, required
  improvement targets, grounding and notebook trajectory ids. Added `tests/test_evaluation.py`.
- `uv run pytest -q`: 61 passed. `uv run ruff check src tests data/generator`,
  `uv run ruff format --check src tests data/generator`, and `git diff --check`: passed.
  No tests were deleted. The `simplify` skill is not installed; manually reviewed every changed
  file for dead code, legacy paths and redundant abstraction, then reran checks.
- No design decision changed; the spec was not edited. Real-LLM case performance remains for S11.

### S8 — 2026-09-24
- Added `src/extensions/merchant_agent/agent.py`: `respond` builds a Deep Agent with the shared
  structured-output boundary and read-only list/read tools confined to one Merchant's records.
  Added `store.py` to save a typed submission as `<dispute_id>.json` for the generator's existing
  `load_saved` path. Added matching sample order and checkout terms under
  `data/merchant_records/MER-HGF/`.
- `tests/test_merchant_agent.py` covers structured response, save/load round-trip, clipped reads,
  path traversal and symlink rejection, and the guard that runtime/config do not import or mention
  the extension. Moved the reusable structured-model fake from `tests/test_runtime.py` into
  `tests/conftest.py`. Extended the label-agnostic guard's required contract-name exception to
  the new extension files. Added the README section for trying and later wiring the extension.
- `uv run pytest`: 65 passed. `uv run ruff check src tests data/generator`,
  `uv run ruff format --check src tests data/generator`, and `git diff --check`: passed.
  No tests were deleted. The `simplify` skill is not installed; manually reviewed every changed
  file for dead code, legacy paths and redundant abstraction, then reran checks.
- No design decision changed; the spec was not edited. The Merchant agent remains intentionally
  unwired, and its real-model behavior is untested until a live run is requested.

### S9 — 2026-09-24
- Added `GET /graph/ontology` in `src/api/routers/graph.py`, returning groups plus label and edge
  descriptions from the static graph ontology. Added typed response models in `src/api/models.py`
  and changed `CaseSummary.claim_type` to `claim` to match the generated catalog.
- Added `tests/test_api.py` for ontology, static graph node lookup and the answer-free case catalog.
  Added `tests/test_showcase.py` for export/install round-trip: graph, events, and idempotent event
  import. `src/showcase.py` and `src/cli.py` already used the static graph and exported per-run
  events only after S1/S6, so no source changes were needed there.
- Regenerated `schemas/openapi.json`, removing stale graph `run_id` query parameters and old report
  fields. Ran `uv run inspect export-event-schema --output schemas/trajectory-event.schema.json`;
  the file was unchanged because `EventEnvelope.type` is a free string, with no event-type list.
- `uv run pytest -q`: 67 passed. `uv run ruff check src tests data/generator`,
  `uv run ruff format --check src tests data/generator`, and `git diff --check`: passed. No tests
  were deleted. The `simplify` skill is not installed; manually reviewed all changed files for
  dead code, legacy paths and redundant abstraction, then reran checks.
- No design decision changed; the spec was not edited. Frontend and E2E fixture references to
  `claim_type` remain for S10.

### S10 — 2026-09-24
- Updated frontend API types and client for the current case catalog, static graph endpoints,
  six verdicts, ten Dispute Categories, per-charge decisions, and System Improvements.
- The graph model now builds regions, colours and group icons from `/graph/ontology`. Removed the
  old label table, agent-written graph styling, and run-specific graph query parameters. The
  layout keeps existing nodes in place when new graph evidence arrives.
- Added a Notebook tab fed by `notebook_write` events. Entries appear in sequence by author;
  clicking a cited id opens and highlights it in the evidence graph. The Conclusion now shows
  category, charges, System Improvements and the Card Member letter.
- Rebuilt the hermetic browser fixture in `tests/e2e_server.py` with the Amex ontology and
  current report contract. Updated frontend fixtures, unit tests and Playwright assertions.
  `frontend/src/run/Fields.tsx` recognises current graph ids in prose.
- `uv run pytest -q`: 67 passed. Ruff check and format check, `git diff --check`, `npx tsc -b`,
  `npx vitest run` (35 passed), `npm run build`, and `npm run e2e` (1 passed) all passed. No
  tests were deleted. The `simplify` skill is not installed; manually reviewed every changed
  file for dead code, old graph paths and redundant abstraction, then reran the checks.
- No design decision changed; the spec was not edited. The frontend flow tests still use old
  synthetic ids in their fixtures; S12's legacy sweep can rename those without changing behavior.

### S11 — 2026-09-24
- **Eval results** (`uv run inspect eval`, gpt-5.6-luna, `data/generated/eval/`):

  | Round | Changes before it | pass@1 | pass@k | Per case |
  |---|---|---|---|---|
  | 1 (k=1) | none (baseline) | 1/5 | – | D ✓; A accepted, C not_a_dispute, E rejected, B missing `amex_policy` |
  | 2 (k=1) | supervisor prompt, skills, MR 4.2 | 4/5 | – | A C D E ✓; B missing `merchant_policy` |
  | 3 (k=3) | `merchant_policy` rule | 3/5 | 4/5 | A 3/3, D 3/3, E 3/3, B 1/3 (two crashes, below), C 0/3 |

  Solution coverage was 1.00 in every run: the agents always reached the proof records, so every
  failure was knowledge or judgement, not reachability. Runs now take about 5 minutes (baseline
  about 20, always forced to decide at max_turns).
- **Judgement: the supervisor never used the role catalog.** It invented ad-hoc roles, so no worker
  received a role prompt or any skill (the trajectory showed zero `skill_loaded` events for
  workers). `config/agents.yaml`'s supervisor prompt now names the catalog roles and the skills,
  and asks for few, broad rounds (all relevant roles at once, then the critic, then decide).
- **Skills.**
  - `dispute-outcomes`: the graph is the complete case file (A had been accepted because
    screenshots and receipts were "missing"). There is an explicit not_a_dispute vs rejected test,
    a mandatory goodwill-clause check, and credit + liability = disputed amount, not the whole
    charge. Per-target rules for System Improvements: address the cause; clear Clauses are not
    `amex_policy` gaps; report a conflicting Merchant Clause even when Amex terms override it;
    report or dismiss every Notebook `conflict`/`improvement_idea`.
  - `policy-analysis`: an acceptance record proves disclosure; note silent Amex Clauses.
  - `offers-and-benefits`: the Offer goodwill test.
  - `recurring-billing`: a wrong plan points to not_a_dispute.
  - `payments-and-credits`: what liability covers.
- **Policy wording.** `merchant-regulations.md` 4.2 now says the acceptance record shows the
  version was disclosed at the point of sale. `offer-terms.md` 1 points to the Dispute Guide's
  Offer goodwill clause. Both are general rules, with no case ids and nothing revealing answers.
- **Infrastructure fixes found by the eval.**
  - `data/generator/validate.py`: stale ground-truth files are deleted before writing. The ten Visa
    truths were still in `data/generated/`, so the first eval tried to run 15 cases.
  - `src/evaluation.py`: the attempt timeout is now `AttemptTimeout(BaseException)`. The old
    `TimeoutError` was swallowed by broad `except Exception` handlers, so hung attempts never timed
    out.
  - `src/models.py`: `invoke_structured` also retries LangChain's
    `StructuredOutputValidationError`. Deep Agents wrap the Pydantic error in it, so the
    documented one retry never happened; this caused the two B crashes in round 3 (liability
    included the undisputed $1,000).
  - `src/showcase.py`: the export keeps only cases in the current catalog (it had shipped ten
    Visa runs and their scores) and prefers each case's newest run that passed evaluation.
- **Tests.**
  - `tests/test_cases.py`: stale truth removal.
  - `tests/test_evaluation.py`: the timeout is not swallowed; checked to hang on the old code.
  - `tests/test_schemas_models.py`: the wrapped validation error is retried; checked to fail on
    the old code.
  - `tests/test_showcase.py`: catalog filter and passing-run preference.
  - `uv run pytest`: 69 passed. `ruff check`, `ruff format --check` and `git diff --check`: passed.
    No tests were deleted.
- **Showcase and README.**
  - `data/showcase/` (2.0 MB) is committed: graph JSONL, ontology, knowledge index, catalog,
    ground truth, merged scores, and one passing run per case (A-3, B-3, D-3 and E-3 from round 3;
    C-1 from round 2).
  - A fresh restore into an empty directory was verified: the graph loads, and five runs load with
    their Notebook entries and decisions.
  - README "How to run" and "The committed showcase" are rewritten for the Amex showcase; the
    rest of the README is still Visa text for S12.
  - The C-1 run predates the `offer-terms.md` sentence, so its events quote the older clause text
    (same clause ids).
- **`simplify`**: manual review of every changed file (the diff is small and mostly prose). No
  dead code or legacy paths remain; the showcase helpers stay plain functions.
- **Open for S11b.**
  - Case C: 0/3 in round 3. Two attempts had the right verdict but gave the improvement target
    `amex_policy`/`data` (timing and field wish-lists) instead of `process`; one missed goodwill
    and rejected. The fixes are the offer-terms cross-reference and the cause-focused improvement
    rules, not yet run live.
  - B's liability fix is not yet run live either.
  - Run `uv run inspect eval --k 3`, then `showcase-export`.
- No design decision changed; the spec was not edited.


### F1 — 2026-09-24 (part 1: replay, funnel, cited graph)
- **Why.** A frontend review for the demo found three problems:
  - a finished run opened already complete, so nothing showed the agents working;
  - the scale of the search (6,509 nodes, 14,621 edges) and the eval's proof (solution facts
    found, decoys named) were invisible;
  - "Cited only" drew about 30 nodes in wide, mostly empty bands, at an unreadable size.
- **Built:**
  - **Replay.**
    - `useRunEvents` now only collects events.
    - `useRunView(stream, cursor)` folds them up to a cursor: forward steps fold only the new
      events, and a step back refolds from the start (runs are about 700 events).
    - `run/replay.ts` shortens gaps to 2 s and halves them (about 1 min replay per 5 min run),
      finds the milestones (triage, delegations, decision sent back, verdict), and formats the
      clock.
    - `run/Timeline.tsx`: Play/Pause, 1×/2×/4× speed, a range scrubber with clickable milestone
      marks, the real run clock, "Skip to verdict", and a live narration line. It appears only
      once a run has finished.
    - Cases with a recorded run open with `?replay`, which autoplays from the start.
    - The header status reads "Replaying".
  - **Funnel.**
    - `run/Funnel.tsx` in the header shows nodes in the graph → examined → cited in the verdict,
      with log-scaled bars.
    - It also shows the eval answer key: squares per solution fact (found = touched) and per decoy
      (named = id in the report JSON), the same definitions as `src/evaluation.py`.
    - Clicking the answer key toggles the graph overlay.
    - Backend: `GraphStore.size()`; `/graph/ontology` returns `node_count` and `edge_count`;
      `schemas/openapi.json` regenerated (only those two fields changed); `tests/test_api.py`
      asserts them.
  - **Cited graph.**
    - After a verdict the graph defaults to "Cited only". The reader's scope choice lives in the
      run page (`graphScope` in `RunContext`), so it survives tab switches.
    - A new scope is laid out afresh.
    - `columnsFor` drops empty regions and uses a 200 px minimum band width; `bandBounds` has a
      smaller minimum height.
    - The graph refits on pane resize.
    - The whole run's ids are fetched up front (`graphIds` in `store.ts`), and the graph draws
      only what exists at the cursor.
    - `Touch` gained `kind` (`node` or `edge`).
    - `useEvidenceGraph` tracks reader-expanded ids.
  - **Bug fix.** `run/useMeasuredNodes.ts` keeps the sizes React Flow measures. Rebuilt node
    objects lose their measured size, and an unmeasured node stays hidden: during replay the agent
    flow went blank and never refit. A fast live run could hit this too.
- **Files.**
  - Frontend, new: `Funnel.tsx`, `Timeline.tsx`, `replay.ts`, `replay.test.ts`,
    `useMeasuredNodes.ts`.
  - Frontend, changed: `RunPage.tsx`, `CasesPage.tsx`, `AgentFlow.tsx`, `EvidenceGraph.tsx`,
    `evidenceLayout.ts`, `RunContext.tsx`, `store.ts`, `useEvidenceGraph.ts`, `useRunEvents.ts`,
    `api/types.ts`, `index.css` (scrubber styles), plus tests and `e2e/run-page.spec.ts`.
  - Backend: `src/graph_store.py`, `src/api/models.py`, `src/api/routers/graph.py`,
    `tests/test_api.py`, `schemas/openapi.json`.
- **Verified.**
  - `npx tsc -b` and `npx oxlint`: no warnings.
  - `npx vitest run`: 40 passed.
  - `npm run e2e`: 1 passed. The spec now expects "Cited only" after the verdict and switches to
    "Everything touched" before counting nodes; it also scrubs to the start and checks
    "Replaying", then "Skip to verdict" and "Decided".
  - `npx vite build`: OK.
  - `uv run pytest`: 69 passed. `ruff check`, `ruff format --check` and `git diff --check`: passed.
  - Screenshots of case B at 1440–1600 px, mid-replay and at the verdict: the flow fills in with
    active agents pulsing, and the graph narrows to the cited evidence at the verdict.
- **Left for F1 (do these, then the polish below, then commit):**
  - Screenshot-check the replay of cases A, C, D and E. D has no decoys, so the Decoys row is
    hidden; C failed its eval.
  - Check the header, funnel and timeline at tablet and phone widths.
  - Check the cases page after the copy change.
  - Run `simplify` over the changed files.
  - Commit and push per §5.
- **Known behaviour, not bugs.**
  - At the verdict the report drawer opens to 34 % of the window, so the cited graph is small
    until "Hide details". F2 addresses this.
  - The answer key fills early: case B finds 12/12 by about 1:10 of 5:35. It is accurate; the
    visible narrowing happens at the verdict.
  - The Timeline has no tests of its own (the replay maths is unit tested; the e2e test covers
    scrubbing).
- **Scope of the remaining F work** (from the same review, with screenshots of the current UI as
  evidence):
  - **F2 Report beside the graph.** Clicking a cited claim now collapses the report
    (`Conclusion.tsx`, `reveal`), so claim and evidence are never on screen together. Show them
    side by side. For clause-conflict cases (B), add an Amex Clause vs Merchant Clause comparison
    with the deciding line highlighted. Tie "Decoys ruled out" to the decoy nodes, so each one can
    light up.
  - **F3, part 1: agent swimlane timeline.** On the agent map every worker connects to every tool,
    which makes a dense bundle, and parallel work and sent-back loops are invisible. Add a
    time-based view: one lane per agent, tool-call ticks, Notebook marks, and a visible break where
    the supervisor looped. On the map, replace tool edges with per-agent tool counts. Every worker
    shows `×1` and "ad hoc", which tells the viewer nothing; drop or condense them.
  - **F3, part 2: inspector narration.** With nothing selected, the inspector wastes a third of the
    screen ("Select an agent…"). During replay, show the supervisor's latest reasoning, the newest
    Notebook finding and the open plan items (the plan list now sits in the bottom `LiveStatus` and
    squeezes the canvas).
  - **F1 polish.**
    - Graph colours: about 20 labels in five similar hues with a 20-item legend that covers nodes.
      Use four clearly different region hues (Case, Commerce, Parties, Terms) with tints per
      label, and a four-item legend.
    - Notebook and inspector show raw ids (`E-0014472`) and unformatted amounts (`1300`); use
      captions and `money()`, with the id on hover.
    - Case cards: add nodes examined, agents, run time and eval pass.
    - Fix truncated names ("consolidate memo…") and tiny band titles.
    - The React Flow attribution (`proOptions.hideAttribution`): check its licence note first.

### F1 — 2026-09-24 (part 2: checks and polish)
- **Checks.** Took screenshots of every case's replay at 1440 px, from mid-run to the verdict:
  - A–E all replay; the flow fills in, the funnel climbs, and the graph narrows to "Cited only".
  - D hides the Decoys row. C's case card shows "Failed evaluation".
  - Header, funnel and timeline wrap without overflow at 820 px and 390 px.
  - The cases page reads well at 1440 px and 390 px.
- **Polish.**
  - **Graph colours.** `graphModel.ts` gives each region one clearly different hue (Parties blue,
    Commerce amber, Terms green, Case crimson), with darker-to-lighter tints per label. The legend
    has one entry per region shown. `regionColor` also colours the band titles.
  - **Captions.**
    - `caption()` derives a name from whichever properties a node has, never from its label: a
      Card as "Gold ··2031", a clause as "4.3 Custom orders", a message as "email from
      StreamCo", "Deposit $1,500.00", "$2,400.00 purchase", "Checkout Terms v4". It falls back to
      the text, then the id.
    - `nameOf()` names nodes and edges for chips (edges by their type in words), with the label
      and id on hover.
    - `Ref` shows the caption; `asId` keeps the id where prose names it (in Prose and the charge
      rationale). With `onClick` it is a button, which is how Notebook chips use it.
    - The inspector heading is the caption, with the label and id below it.
    - Graph nodes show a two-line caption.
  - **Money.** `Fields` formats values under `amount`/`total`/`price`/`threshold` keys with
    `money()`.
  - **Case cards.**
    - `/cases` returns `latest: {run_id, verdict, seconds, agents, nodes_examined, passed}`,
      replacing `latest_run_id`/`latest_verdict`.
    - `nodes_examined` counts the same events as the run page's "examined" (`GRAPH_TYPES`).
    - `passed` comes from the newest eval batch that scored the run.
    - Cards show "449 nodes examined · 9 agents · 5:37 run" and "✓ Passed evaluation".
  - **Truncation.**
    - Agent nodes show `×N` only when N > 1, so "consolidate memory" fits.
    - Evidence-graph band titles sit above their band at a constant on-screen size (14 px ÷ zoom),
      so they stay readable on "Everything touched".
  - **Attribution.** The React Flow attribution stays. Its docs (context7, reactflow.dev
    pro-options) say projects without a Pro subscription are expected to keep it, even though
    MIT does not require it.
  - **Bug fix.** `/graph/nodes` dropped nothing, so every node carried null columns from other
    labels and the inspector counted 44 properties. It now drops null properties.
- **Files.**
  - Backend: `src/api/routers/runs.py`, `src/api/routers/graph.py`, `src/api/models.py`,
    `tests/test_api.py`, `schemas/openapi.json` (regenerated: `CaseSummary.latest`,
    `LatestRun`).
  - Frontend: `graphModel.ts`, `EvidenceGraph.tsx`, `Fields.tsx`, `Notebook.tsx`,
    `GraphItemPanel.tsx`, `AgentFlow.tsx`, `Conclusion.tsx`, `GraphIcon.tsx`, `format.ts`
    (`words` also splits CamelCase), `CasesPage.tsx`, `api/types.ts`, `index.css`
    (`.ref.named`).
  - Tests: `evidenceGraph.test.tsx` (hues, captions, `nameOf`), `Fields.test.tsx` (money), and
    `e2e/run-page.spec.ts`, which clicks the Notebook chip by its caption and checks the id is
    in its title.
- **Verified.**
  - `uv run pytest`: 70 passed. `ruff check` and `ruff format --check`: passed.
    `git diff --check`: passed.
  - `npx tsc -b` and `npx oxlint`: clean. `npx vitest run`: 44 passed. `npm run e2e`: 1 passed.
    `npx vite build`: OK.
- **`simplify`** ran as four review agents.
  - Applied:
    - Notebook chips reuse `Ref` (with `onClick`) instead of a copy.
    - `isMoney` helper.
    - The legend takes the regions the bands already computed.
    - `caption` is computed once per node render.
    - Removed the dead `Icon` `size` prop.
    - The label-to-words regex moved into `words`.
    - Null properties are dropped at the API instead of filtered in the panel.
    - The SQL comment names `GRAPH_TYPES`.
  - Skipped:
    - Caption templates, currency units or region colours declared in `ontology.yaml`. This is a
      better long-term home, but it changes the agent-facing schema; consider it with S11b.
    - One shared reader for `eval/*/summary.json`. The API, `showcase.py` and the new
      `_run_passed` each read the file; `evaluation.py` imports the runtime, so the helper needs a
      new light module. This is outside F1.
    - Caching `/cases` stats. Response time went from 10 ms to 56 ms locally, which is fine.
- **Open issue for S11b: `ontology.yaml` descriptions are truncated.**
  - 19 descriptions are unquoted inside YAML flow mappings, so their commas split them. For
    example, the Parties group reads "Card Members" and CardAccount.product reads "Card Product of
    the account", with the rest parsed as extra keys set to null.
  - Agents see these through `graph_schema`, and the S11 eval ran on them.
  - Fix: quote the descriptions, and have `ontology.py` reject unknown keys so it cannot recur.
    Then re-run the eval.
- **Known, for F2/F3.** At tablet width the run page's canvas is short, because the plan list
  (`LiveStatus`) and the empty inspector take the space. F3 part 2 covers both.

### F2 — 2026-09-24 (report beside the graph)
- **Layout.** The report moved from the bottom drawer into the inspector. With nothing selected
  after a verdict, the inspector shows the report, so a claim and its evidence in the graph are on
  screen together. Selecting a node or agent replaces it, and "← Back to the report" returns.
  - `Conclusion.tsx` is now only the verdict strip (verdict, category, headline) plus the
    pre-verdict `LiveStatus`. The drawer's resize handle, snap heights and `localStorage` height
    are gone.
  - The inspector column is `minmax(28rem, 36%)`. Below `lg` the canvas keeps a 28rem minimum
    height itself, so the long report no longer squeezes it to nothing.
- **Report** (`run/Report.tsx`): written for one column. Charges are cards (disputed, credit and
  liability as a three-cell row), and the sticky section nav wraps. Every cited claim is a
  `ClaimButton`: clicking it lights up its evidence, and it stays pressed (`aria-pressed`, yellow)
  while the graph shows exactly that evidence (`isShown` in `evidence.ts`).
- **Decoys ruled out.** Each row names graph ids in prose; `idsIn` (in `evidence.ts`, with
  `REF_IN_TEXT` moved there from `Fields.tsx`) extracts them, and the row lights them up. Rows that
  name no id stay plain text.
- **Amex Policy vs Merchant Policy** (`run/clauses.ts` + `ClauseComparison`):
  - Which Clauses: those that a System Improvement targeting `amex_policy` or `merchant_policy`
    cites and that the report also lists as policy basis (`comparedClauses`).
  - Which side: each Clause's owner is the `owner` property of its policy document, fetched with
    `/graph/neighbors` (no id parsing, no label names). The block shows only when both sides have
    Clauses: case B shows PS-PART 3.2, 3.4 and PLAT-BEN 2.1 against folio 7 and reservation 1;
    A, C, D and E show nothing.
  - The deciding line: the sentence that report text citing the Clause quotes word for word,
    otherwise the one sharing the most words (`decidingSentence`). It is marked only when the
    Clause has more than one sentence; folio 7 marks "Folios settled with any other card are
    re-rated at the Best Available Rate."
  - Clicking a Clause card lights it up in the graph.
- **Tests.** `fixtures.ts` gained `panels(events, overrides)`, now used by the Conclusion,
  Notebook, evidence-graph and new Report tests instead of four copies of the panels literal.
  `Conclusion.test.tsx` lost the drawer tests (the drawer is gone). New `Report.test.tsx`: a claim
  lights up and stays on screen, the pressed state, decoy ids, the side-by-side comparison with
  the mark, no comparison from one side only, and the `clauses` helpers. The e2e spec returns to
  the report from a node selection and checks the claim is pressed.
- **Verified.** `npx tsc -b`, `npx oxlint`: clean. `npx vitest run`: 48 passed. `npm run e2e`:
  1 passed. `npx vite build`: OK. `uv run pytest`: 70 passed; ruff check/format and
  `git diff --check`: passed. Screenshots of B (claim pressed with the graph focused; the
  comparison), A (a decoy row lit up) and B at 390 px.
- **`simplify`** ran as four review agents.
  - Applied: the Clause cards and claim rows share `ShowButton` (the reuse and simplification
    agents found the same thing), and the mobile minimum height lives on the canvas only.
  - Skipped:
    - Memoizing `comparedClauses`/`decidingSentence`/`idsIn`. A report has a handful of Clauses
      and is shown only after the verdict.
    - Fetching the Clause owners through `graph.expand`, which would mark the documents as
      expanded context and draw them on the evidence graph.
    - Picking the document by edge type rather than by its `owner` property, which would name an
      ontology edge in the frontend.
- No design decision changed; the spec was not edited. No backend change.
