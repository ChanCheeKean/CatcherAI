# DisputeAI — Amex dispute revamp: handoff

Last updated: 2026-09-23
Branch: `amex-dispute-revamp` (all work here; never commit to `main`; do not merge)
Current phase: **S0 complete**
Next stage: **S1 — Ontology as data + static graph store**

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
| **S1** Ontology as data + static graph store | Medium | `ontology.yaml` + loader; builder validates against it; `GraphStore` read-only by default, schema with descriptions, `node`, `find`; all write paths and `copy_store` removed. | ☐ |
| **S2** Policy corpus, clause search, memory in knowledge | Complex | 6 Amex + 8 Merchant policy markdown docs grounded in the research; `policies.py` projects them into graph nodes and clause-level search; retrieval without `as_of`; Memory Notes in SQLite; Amex precedents. | ☐ |
| **S3** Background world | Medium | Deterministic dispute-only world (~150 Card Members, ~30 Merchants with template policies, ~3k charges, Offers, program, subscriptions, invoices, ~60 past Disputes). | ☐ |
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
