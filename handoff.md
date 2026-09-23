# DisputeAI — Amex dispute revamp: handoff

Last updated: 2026-09-23
Branch: `amex-dispute-revamp` (all work here; never commit to `main`; do not merge)
Current phase: **S3 complete**
Next stage: **S4 — Submission contract, case kit, cases A and B**

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
| **S4** Submission contract, case kit, cases A and B | Complex | `MerchantSubmission` contract + `insert_submission`; case kit for Amex; case A "Final Sale Means Final", case B "Platinum Rate, Gold Card". | ☐ |
| **S5** Cases C, D, E + end-to-end generator | Complex | Case C "The Offer on the Other Card", case D "Paid by Transfer", case E "Cancelled the Wrong Plan"; `gen.py` ingests saved submissions; every ontology label/edge used. | ☐ |
| **S6** Case Notebook, tools, read-only runtime | Medium | `notebook.py`; tools `graph_find`, `notebook_write`/`notebook_read`, memory in knowledge; runtime and API read the static graph; notebook in supervisor/adjudicator input. | ☐ |
| **S7** Report, prompts, skills, evaluation | Complex | Six verdicts, Dispute Category, `ChargeDecision`, `SystemImprovement`; new `agents.yaml`; 9 label-agnostic skills; label-agnostic guard test; eval scoring. | ☐ |
| **S8** Merchant agent extension (not wired) | Medium | `respond()` Deep Agent over merchant records, `save_submission`, guard test that nothing imports it, README section. | ☐ |
| **S9** API, showcase, schemas | Medium | `/graph/ontology`; no run-graph copies; showcase exports events only; OpenAPI + event schema regenerated. | ☐ |
| **S10** Frontend | Medium | Ontology-driven regions/colours; Notebook tab; Conclusion with category, six verdicts, System Improvements. | ☐ |
| **S11** Real-LLM eval + tuning | Complex | pass@1 5/5 on A–E by improving skills, policy wording, ontology descriptions and prompts only. | ☐ |
| **S12** Final cleanup, showcase, README | Simple | Legacy sweep, screenshots, showcase export, Amex README; whole-branch `simplify`. | ☐ |

## 7. Conflicts and open questions

- `docs/research/02-amex-dispute-research.md` marks several points UNVERIFIED: the NKN/RET/…
  abbreviations as Amex's own, Platinum benefit details, and Amex goodwill policy. The policy texts
  are **paraphrased and fictionalised where unverified**; front matter keeps the source URL. Do
  not present them as verbatim Amex text.

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
