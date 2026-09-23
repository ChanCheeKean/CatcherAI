# Amex Dispute Revamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Implement **one stage per session**, following the stage protocol in `handoff.md` §5.

**Goal:** Turn the Visa-issuer dispute POC into an American Express (closed-loop) dispute investigator with a static, schema-as-data evidence graph, a Case Notebook, Amex/Merchant policy clauses, five new cases, System Improvements on the report, and an unwired merchant-agent extension.

**Architecture:** The agent framework (triage → supervisor ⇄ parallel Deep Agent workers → adjudicator → consolidate_memory) is unchanged. The generator builds one read-only LadybugDB graph from `ontology.yaml` + a world + five cases + a policy corpus projected into both the graph (PolicyDocument/Clause nodes) and a clause-level search index. Agents log findings to a per-run SQLite Case Notebook; Memory Notes live in the knowledge SQLite.

**Tech Stack:** Python 3.11, LangGraph, deepagents 0.5.9, LadybugDB (`ladybug` 0.20.x, Cypher), SQLite FTS5 + sqlite-vec, Pydantic v2, FastAPI + SSE, React + TypeScript + Vite + Vitest + Playwright.

**Spec:** `docs/superpowers/specs/2026-09-23-amex-dispute-revamp-design.md` (read it first; decisions D1–D17 are settled). Vocabulary: `CONTEXT.md`. Facts: `docs/research/02-amex-dispute-research.md`.

## Global Constraints

- All work on branch `amex-dispute-revamp`; never commit to `main`. `git push -u origin amex-dispute-revamp` at the end of each stage.
- Framework unchanged (D16): do not add, remove or rewire LangGraph nodes; do not add rule-based gates or per-case Python logic; every LLM output is a Pydantic model via `invoke_structured`.
- The evidence graph is read-only at run time (D4). No code path in `src/` writes to it.
- No label or edge-type name appears in `src/` (except `graph_store.py`'s generic code, which names none), `skills/`, or `config/` (D9; enforced by `tests/test_label_agnostic.py` from Stage 7).
- No time component (D12): no deadlines, windows, `as_of`, `valid_from`/`valid_to`.
- Fraud out of scope (D3); verdicts exactly `accepted, partially_accepted, rejected, goodwill_credit, not_a_dispute, fraud_referral`; categories exactly `NKN, RET, CNC, CNR, DMG, DSS, DUP, NRC, OVR, PDD`.
- Ground truth is evaluator-only: never loaded into the graph, knowledge store, prompts or tools.
- Use `CONTEXT.md` terms: Card Member (not cardholder), Merchant Policy / Amex Policy, Clause, Dispute Category, Case Notebook, System Improvement, Goodwill Credit.
- Robust, not over-engineered: plain functions and data, no class hierarchies or wrappers, no stubs/TODOs/commented-out code, delete anything unused.
- **Every stage ends with the `simplify` skill** over that stage's changed files (D17), then `uv run pytest`, `uv run ruff check src tests data/generator` and `uv run ruff format --check src tests data/generator` must pass (frontend stages: `cd frontend && npx tsc -b && npx vitest run && npm run build`).
- **Keep the suite green without shims.** When a stage removes an API or label that a later stage's module still uses (e.g. `tools.py`, `runtime*.py`, `showcase.py`, `api/` before Stages 6 and 9), delete the *tests* of that old behaviour whose rewrite is scheduled later and list them in the handoff §8 entry; never add compatibility shims, skip markers or stubs. Modules may be temporarily broken at call time between stages (the app is not runnable from Stage 0 to Stage 6), but imports, `uv run pytest` and ruff must pass at the end of every stage.
- Commit messages end with the co-author line used in this repo's recent commits.
- Verify library APIs (ladybug Cypher functions, deepagents) with context7 before relying on them.

---

## Stage 0 — Teardown of the Visa world (Simple)

Delete everything the spec replaces so later stages build forward without legacy. The app is not runnable end to end from here until Stage 6; the frontend until Stage 10.

### Task 0.1: Delete Visa/LFB/regulation data, old cases, showcase and retired skills

**Files:**
- Delete: `data/corpus/policies/internal/`, `data/corpus/policies/network_visa/`, `data/corpus/policies/regulation/`, `data/corpus/author_policies.py`
- Delete: `data/generator/cases/c*.py` (all ten), `data/showcase/` (all), `asset/agent_graph.png`, `asset/evidence_node.png` (re-shot in Stage 12)
- Delete: `skills/agentic-transactions/`, `skills/fraud-and-ato-signals/`, `skills/household-authority/`, `skills/missing-evidence-default/`, `skills/network-reason-codes/`, `skills/not-received-and-refunds/`, `skills/reg-e-and-reg-z/`, `skills/unrecognized-charges/`
- Modify: `data/generator/cases/__init__.py` (builders tuple becomes empty; remove imports), `data/generator/capabilities.py` (`CASE_NEEDS = {}`)
- Modify: `data/corpus/precedents.yaml` → replace contents with `[]` (rewritten in Stage 2)
- Test: `tests/test_cases.py` (delete; recreated in Stage 4), `tests/test_showcase.py` (delete; recreated in Stage 9)

- [ ] **Step 1:** `git rm -r` the paths above.
- [ ] **Step 2:** In `data/generator/cases/__init__.py`, make `build_cases` iterate an empty `builders = ()` and remove the ten imports. Remove `missing_evidence` and `human_effort` from `CaseTruth` (the spec drops them). Rename `transaction_expected` → `charge_expected(charge_id, verdict, disputed, credit)` returning `{"charge_id", "verdict", "disputed_amount", "credit_amount", "card_member_liability"}`.
- [ ] **Step 3:** Run `uv run pytest -x -q 2>&1 | tail -20`. Delete or trim only tests whose subject was deleted (case tests, showcase tests, tool tests that reference fraud labels are rewritten in their own stages; mark nothing as skip). Expected: remaining suites pass.
- [ ] **Step 4:** `rg -n "visa|Visa|LFB|Lanternfield|REGE|REGZ|cardholder" src data skills config tests` — only hits in files later stages rewrite (`schemas.py`, `config/agents.yaml`, `evaluation.py`, `world.py`, `ontology.py`, tests of those). List them in the handoff §8 entry.
- [ ] **Step 5:** Run the `simplify` skill on the changed files; then pytest + ruff.
- [ ] **Step 6:** Commit `Teardown: remove Visa world, old cases, showcase and retired skills` and push.

---

## Stage 1 — Ontology as data and a static graph store (Medium)

### Task 1.1: `ontology.yaml` and its loader

**Files:**
- Create: `data/generator/ontology.yaml`
- Replace: `data/generator/ontology.py`
- Test: `tests/test_ontology.py`

**Interfaces:**
- Produces: `ontology.load(path: Path = PATH) -> dict` returning `{"groups": {id: {title, description}}, "nodes": {label: {prefix, group, description, props: {name: {type, description}}}}, "edges": {type: {description, pairs: [[src, dst], ...], props: {name: {type, description}}}}}`; `ontology.PATH`.

- [ ] **Step 1: Write `data/generator/ontology.yaml`** exactly:

```yaml
# The evidence-graph schema. Changing the graph = editing this file + the generator.
# Every label, edge and property has a description: agents read them through graph_schema.
groups:
  parties: {title: Parties, description: Card Members, their accounts and Cards, and Merchants.}
  commerce: {title: Commerce, description: What was bought, charged, paid, returned or subscribed.}
  terms: {title: Terms, description: Amex Policies and Merchant Policies and their Clauses.}
  case: {title: Case, description: Disputes and the evidence filed with them.}

nodes:
  CardMember:
    prefix: CMB
    group: parties
    description: A person holding an Amex Card, as Basic or Additional Card Member.
    props:
      name: {type: STRING, description: Full name; namesakes exist, so never match people by name alone.}
      member_since: {type: STRING, description: ISO date the person became a Card Member.}
  CardAccount:
    prefix: ACC
    group: parties
    description: An Amex account that Cards bill to; the Basic Card Member is responsible for it.
    props:
      product: {type: STRING, description: Card Product of the account, e.g. Platinum, Gold, Green, Blue Cash.}
      status: {type: STRING, description: open or closed.}
  Card:
    prefix: CRD
    group: parties
    description: A physical or virtual Amex Card issued on an account to one Card Member.
    props:
      last4: {type: STRING, description: Last four digits.}
      product: {type: STRING, description: Card Product, which decides benefit and Offer eligibility.}
      role: {type: STRING, description: basic or additional.}
      status: {type: STRING, description: active or cancelled.}
  Merchant:
    prefix: MER
    group: parties
    description: A business that accepts Amex under a direct agreement with Amex.
    props:
      name: {type: STRING, description: Trading name.}
      category: {type: STRING, description: Line of business, e.g. furniture, lodging, streaming, events.}
      channel: {type: STRING, description: online, in_person or both.}
  Descriptor:
    prefix: DSC
    group: parties
    description: The merchant name text printed on the Card Member's statement.
    props:
      text: {type: STRING, description: Statement text exactly as shown.}
  Charge:
    prefix: CHG
    group: commerce
    description: A posted amount on a Card; negative amounts are credits.
    props:
      date: {type: STRING, description: ISO posting date.}
      amount: {type: DOUBLE, description: Amount in currency units; negative for credits.}
      currency: {type: STRING, description: ISO currency code.}
      kind: {type: STRING, description: purchase, recurring or credit.}
      status: {type: STRING, description: posted.}
  Order:
    prefix: ORD
    group: commerce
    description: A purchase or booking agreed between a Card Member and a Merchant.
    props:
      date: {type: STRING, description: ISO date the order or booking was placed.}
      kind: {type: STRING, description: retail, lodging, event or service.}
      total: {type: DOUBLE, description: Agreed total at the time of ordering.}
      currency: {type: STRING, description: ISO currency code.}
      summary: {type: STRING, description: What was ordered or booked, including rate or options.}
  LineItem:
    prefix: LIN
    group: commerce
    description: One item on an order with the options chosen.
    props:
      description: {type: STRING, description: Item as described on the order.}
      quantity: {type: INT64, description: Units ordered.}
      unit_price: {type: DOUBLE, description: Price per unit.}
      option: {type: STRING, description: Option chosen, e.g. fabric, colour, size, rate plan.}
  Product:
    prefix: PRD
    group: commerce
    description: A catalogue product and the options the Merchant offers for it.
    props:
      name: {type: STRING, description: Product name.}
      standard_options: {type: STRING, description: Options the Merchant stocks as standard.}
      custom_options: {type: STRING, description: Options the Merchant makes to order (custom).}
  Return:
    prefix: RTN
    group: commerce
    description: An attempt to send goods back to a Merchant and what happened to it.
    props:
      method: {type: STRING, description: How the goods were sent back.}
      status: {type: STRING, description: Outcome, e.g. received and refunded, refused.}
      note: {type: STRING, description: Free-text detail recorded with the return.}
  Subscription:
    prefix: SUB
    group: commerce
    description: A recurring billing arrangement for one plan at a Merchant.
    props:
      plan: {type: STRING, description: Plan name.}
      amount: {type: DOUBLE, description: Amount per billing period.}
      frequency: {type: STRING, description: Billing frequency, e.g. monthly.}
      status: {type: STRING, description: active or cancelled.}
  Invoice:
    prefix: INV
    group: commerce
    description: A Merchant's bill to a Card Member, split into installments.
    props:
      date: {type: STRING, description: ISO issue date.}
      total: {type: DOUBLE, description: Invoice total.}
      currency: {type: STRING, description: ISO currency code.}
      description: {type: STRING, description: What the invoice is for.}
  Installment:
    prefix: INS
    group: commerce
    description: One scheduled part of an invoice.
    props:
      label: {type: STRING, description: e.g. Deposit, Balance.}
      amount: {type: DOUBLE, description: Amount due for this part.}
  Payment:
    prefix: PAY
    group: commerce
    description: A payment made by other means than an Amex Card (bank transfer, cheque, cash).
    props:
      date: {type: STRING, description: ISO payment date.}
      method: {type: STRING, description: bank_transfer, cheque or cash.}
      amount: {type: DOUBLE, description: Amount paid.}
      reference: {type: STRING, description: Payment reference text.}
  Offer:
    prefix: OFR
    group: commerce
    description: A spend-and-get deal at a Merchant, funded by Amex (Amex Offer) or by the Merchant.
    props:
      title: {type: STRING, description: Offer as shown to the Card Member.}
      spend_threshold: {type: DOUBLE, description: Minimum qualifying spend.}
      credit_amount: {type: DOUBLE, description: Credit or discount granted.}
      funded_by: {type: STRING, description: amex or merchant.}
  Program:
    prefix: PRG
    group: commerce
    description: An Amex benefit program that participating Merchants honour, e.g. a hotel program.
    props:
      name: {type: STRING, description: Program name.}
      eligible_product: {type: STRING, description: Card Product the program is for.}
  PolicyDocument:
    prefix: POL
    group: terms
    description: One version of an Amex Policy or Merchant Policy.
    props:
      title: {type: STRING, description: Document title.}
      owner: {type: STRING, description: amex or merchant.}
      kind: {type: STRING, description: e.g. merchant_regulations, offer_terms, returns, folio_terms, subscription_terms.}
      version: {type: STRING, description: Version label.}
      audience: {type: STRING, description: card_member or merchant.}
      source_url: {type: STRING, description: Public source the Amex text is paraphrased from; empty for Merchant Policies.}
  Clause:
    prefix: CLS
    group: terms
    description: One numbered provision of a policy document; its id is also a search document id.
    props:
      number: {type: STRING, description: Clause number within its document.}
      heading: {type: STRING, description: Clause heading.}
      text: {type: STRING, description: Full clause text.}
  Dispute:
    prefix: DSP
    group: case
    description: A Card Member's challenge to one or more charges; past ones carry their outcome.
    props:
      filed_at: {type: STRING, description: ISO date filed.}
      amount: {type: DOUBLE, description: Total amount the Card Member disputes.}
      intake: {type: STRING, description: The Card Member's own words.}
      status: {type: STRING, description: open or resolved.}
      outcome: {type: STRING, description: Verdict of a resolved Dispute; empty while open.}
  MerchantSubmission:
    prefix: MSB
    group: case
    description: What a Merchant submitted for a Dispute.
    props:
      statement: {type: STRING, description: The Merchant's own account of the charge.}
  EvidenceItem:
    prefix: EVI
    group: case
    description: A document or record filed as evidence (receipt, log, folio, invoice ledger).
    props:
      kind: {type: STRING, description: e.g. acceptance_log, folio, invoice_ledger, usage_log.}
      source: {type: STRING, description: merchant or card_member.}
      text: {type: STRING, description: Content of the record.}
  Communication:
    prefix: COM
    group: case
    description: A message between a Merchant and a Card Member filed as evidence.
    props:
      channel: {type: STRING, description: email, chat or letter.}
      sender: {type: STRING, description: Who sent it.}
      date: {type: STRING, description: ISO date sent.}
      text: {type: STRING, description: Message text.}

edges:
  HOLDS:
    description: A Card Member holds an account.
    pairs: [[CardMember, CardAccount]]
    props:
      role: {type: STRING, description: basic (responsible for the account) or additional.}
  ISSUED_ON: {description: A Card bills to an account., pairs: [[Card, CardAccount]]}
  CARRIED_BY: {description: The Card Member a Card was issued to., pairs: [[Card, CardMember]]}
  CHARGED_TO: {description: The Card a charge posted to., pairs: [[Charge, Card]]}
  AT_MERCHANT:
    description: The Merchant a record belongs to.
    pairs: [[Charge, Merchant], [Order, Merchant], [Subscription, Merchant], [Invoice, Merchant], [Payment, Merchant]]
  DESCRIBED_AS: {description: The statement descriptor a charge showed., pairs: [[Charge, Descriptor]]}
  DESCRIBES: {description: The Merchant a descriptor belongs to., pairs: [[Descriptor, Merchant]]}
  AFFILIATE_OF: {description: A Merchant is a sister or subsidiary business of another., pairs: [[Merchant, Merchant]]}
  FOR_ORDER: {description: The order a charge pays for or credits., pairs: [[Charge, Order]]}
  HAS_LINE: {description: An order's line items., pairs: [[Order, LineItem]]}
  OF_PRODUCT: {description: The catalogue product a line item is., pairs: [[LineItem, Product]]}
  SOLD_BY: {description: The Merchant whose catalogue lists a product., pairs: [[Product, Merchant]]}
  REFUNDS: {description: A credit reverses (part of) an earlier charge., pairs: [[Charge, Charge]]}
  RETURNED_AS: {description: A return of goods from an order., pairs: [[Order, Return]]}
  GUARANTEED_WITH: {description: The Card used to place or guarantee a booking (may differ from the Card charged)., pairs: [[Order, Card]]}
  UNDER_PROGRAM: {description: A booking made under an Amex benefit program., pairs: [[Order, Program]]}
  PARTICIPATES_IN: {description: A Merchant takes part in an Amex benefit program., pairs: [[Merchant, Program]]}
  FOR_SUBSCRIPTION: {description: The subscription a recurring charge bills for., pairs: [[Charge, Subscription]]}
  SUBSCRIBED_WITH: {description: The Card a subscription bills to., pairs: [[Subscription, Card]]}
  HAS_INSTALLMENT: {description: The installments of an invoice., pairs: [[Invoice, Installment]]}
  SETTLES: {description: A charge or other-means payment pays an installment., pairs: [[Charge, Installment], [Payment, Installment]]}
  BILLED_TO: {description: The Card Member an invoice is addressed to., pairs: [[Invoice, CardMember]]}
  PAID_BY: {description: The Card Member who made an other-means payment., pairs: [[Payment, CardMember]]}
  OFFER_AT: {description: The Merchant an Offer is valid at., pairs: [[Offer, Merchant]]}
  ENROLLED_ON: {description: The specific Card an Offer was added to., pairs: [[Offer, Card]]}
  PUBLISHED_BY: {description: The Merchant that wrote a Merchant Policy., pairs: [[PolicyDocument, Merchant]]}
  HAS_CLAUSE: {description: A document's clauses., pairs: [[PolicyDocument, Clause]]}
  ACCEPTED:
    description: The exact policy version a Card Member accepted for this order, subscription or invoice.
    pairs: [[Order, PolicyDocument], [Subscription, PolicyDocument], [Invoice, PolicyDocument]]
    props:
      method: {type: STRING, description: How acceptance was recorded, e.g. checkbox at checkout, signature, booking confirmation.}
  BOUND_BY: {description: An Amex Policy that binds a Merchant or governs an account., pairs: [[Merchant, PolicyDocument], [CardAccount, PolicyDocument]]}
  GOVERNS: {description: The Amex terms that govern an Offer or program., pairs: [[PolicyDocument, Offer], [PolicyDocument, Program]]}
  FILED_BY: {description: The Card Member who filed a Dispute., pairs: [[Dispute, CardMember]]}
  DISPUTES:
    description: A charge a Dispute challenges.
    pairs: [[Dispute, Charge]]
    props:
      amount: {type: DOUBLE, description: Part of the charge in dispute.}
  HAS_SUBMISSION: {description: A Merchant Submission for a Dispute., pairs: [[Dispute, MerchantSubmission]]}
  HAS_EVIDENCE:
    description: Evidence filed with a Dispute (by the Card Member) or with a submission (by the Merchant).
    pairs: [[Dispute, EvidenceItem], [Dispute, Communication], [MerchantSubmission, EvidenceItem], [MerchantSubmission, Communication]]
  CITES: {description: A policy clause or document a Merchant Submission relies on., pairs: [[MerchantSubmission, Clause], [MerchantSubmission, PolicyDocument]]}
  ASSERTS:
    description: The record an evidence item or message makes a claim about.
    pairs: [[EvidenceItem, Order], [EvidenceItem, Charge], [EvidenceItem, Return], [EvidenceItem, Subscription], [EvidenceItem, Invoice], [EvidenceItem, Installment], [EvidenceItem, LineItem], [Communication, Order], [Communication, Subscription], [Communication, Return]]
```

- [ ] **Step 2: Write the failing test** `tests/test_ontology.py`:

```python
import re

import pytest
import yaml

import ontology


def test_every_item_is_described_and_grouped():
    spec = ontology.load()
    for label, node in spec["nodes"].items():
        assert node["description"] and node["group"] in spec["groups"], label
        assert re.fullmatch(r"[A-Z]{2,3}", node["prefix"])
        assert all(p["description"] for p in node["props"].values()), label
    for etype, edge in spec["edges"].items():
        assert edge["description"] and edge["pairs"], etype
        assert all(p["description"] for p in edge["props"].values()), etype


def test_prefixes_unique_and_pairs_reference_labels():
    spec = ontology.load()
    prefixes = [n["prefix"] for n in spec["nodes"].values()]
    assert len(prefixes) == len(set(prefixes))
    for edge in spec["edges"].values():
        for src, dst in edge["pairs"]:
            assert src in spec["nodes"] and dst in spec["nodes"]


def test_loader_rejects_missing_description(tmp_path):
    raw = yaml.safe_load(ontology.PATH.read_text())
    del raw["nodes"]["Card"]["description"]
    path = tmp_path / "o.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="Card"):
        ontology.load(path)
```

- [ ] **Step 3:** `uv run pytest tests/test_ontology.py -v` → FAIL (`load` missing).
- [ ] **Step 4: Replace `data/generator/ontology.py`:**

```python
"""Load and check the evidence-graph schema from ontology.yaml, the one place it is defined."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

PATH = Path(__file__).with_name("ontology.yaml")
TYPES = {"STRING", "INT64", "DOUBLE", "BOOLEAN"}


def load(path: Path = PATH) -> dict:
    spec = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    groups, nodes, edges = spec["groups"], spec["nodes"], spec["edges"]
    prefixes: set[str] = set()
    for label, node in nodes.items():
        node.setdefault("props", {})
        _require(label, node, "description", "group", "prefix")
        if node["group"] not in groups:
            raise ValueError(f"{label}: unknown group {node['group']!r}")
        if not re.fullmatch(r"[A-Z]{2,3}", node["prefix"]) or node["prefix"] in prefixes:
            raise ValueError(f"{label}: prefix must be 2-3 unique uppercase letters")
        prefixes.add(node["prefix"])
        _check_props(label, node["props"])
    for etype, edge in edges.items():
        edge.setdefault("props", {})
        _require(etype, edge, "description", "pairs")
        for src, dst in edge["pairs"]:
            if src not in nodes or dst not in nodes:
                raise ValueError(f"{etype}: pair {src}->{dst} names an unknown label")
        _check_props(etype, edge["props"])
    return spec


def _require(name: str, item: dict, *keys: str) -> None:
    for key in keys:
        if not item.get(key):
            raise ValueError(f"{name}: missing {key}")


def _check_props(owner: str, props: dict) -> None:
    for prop, spec in props.items():
        _require(f"{owner}.{prop}", spec, "type", "description")
        if spec["type"] not in TYPES:
            raise ValueError(f"{owner}.{prop}: unknown type {spec['type']!r}")
```

- [ ] **Step 5:** Run the test → PASS. Commit `Ontology: schema as data in ontology.yaml`.

### Task 1.2: Graph builder validates against the YAML

**Files:** Modify `data/generator/graph_builder.py`; Test `tests/test_graph_store.py` (rewrite fixture to the new labels).

**Interfaces:**
- Consumes: `ontology.load()`.
- Produces: `Graph()` with `.node(label, id, **props)`, `.edge(type, src, dst, **props)`, `.nodes: dict[id, {"label", "props"}]`, `.edges: list[dict]`, `.write(out_dir)` writing `nodes.jsonl`, `edges.jsonl`, `ontology.json` (the full loaded spec, descriptions included). Edge ids are assigned `E-<n>` in insertion order (deterministic). Unknown label/type/property, wrong id prefix, disallowed pair or dangling endpoint raises `ValueError`.

- [ ] **Step 1:** Read the current `graph_builder.py` (57 lines) and keep its shape; change only: take `spec = ontology.load()`; property names come from `spec[...]["props"]` keys; the id prefix must equal `spec["nodes"][label]["prefix"]`; `write()` dumps `spec` to `ontology.json`.
- [ ] **Step 2:** Rewrite `tests/test_graph_store.py`'s fixture graph with the new labels: two Card Members, one account (HOLDS basic/additional), two Cards, one Merchant, one Charge with CHARGED_TO and AT_MERCHANT, one PolicyDocument with two Clauses (HAS_CLAUSE) whose text includes "final sale". Keep the builder-rejection tests (unknown label, unknown edge, unknown prop, dangling edge) and add `test_builder_rejects_wrong_prefix` (`g.node("Card", "CMB-1")` raises).
- [ ] **Step 3:** Run → fix → PASS. Commit.

### Task 1.3: Static `GraphStore` with descriptions, `node`, `find`; no writes

**Files:** Modify `src/graph_store.py`; Test `tests/test_graph_store.py`.

**Interfaces:**
- Produces:
  - `load(jsonl_dir, db_path) -> GraphStore` (DDL types read from `props[name]["type"]`).
  - `GraphStore(db_path, read_only: bool = True)` — **default read-only now**; `load` opens its own writable instance internally.
  - `schema() -> {"groups": {...}, "nodes": {label: {"group", "description", "props": {name: {"type", "description"}}, "count"}}, "edges": {type: {"description", "pairs", "props", "count"}}}`.
  - `query(cypher, params=None, row_cap=50) -> {"columns", "rows", "truncated", "node_ids", "edge_ids"}` (unchanged).
  - `neighbors(node_id, rel_types=None, direction="both", limit=50) -> {"neighbors", "truncated", "node_ids", "edge_ids"}` (no `since`/`until`).
  - `node(node_id) -> dict` (the node's properties with `_label`; `ValueError` if absent).
  - `find(text, labels=None, limit=25) -> {"matches": [node dict], "node_ids", "edge_ids": []}` — case-insensitive substring over every STRING property.
  - `label_of(node_id)`, `close()`.
  - Removed: `copy_store`, `write_finding`, `write_note`, `set_note_status`, `_check_edges`, `_create_edge`, `_require`, `_active_between`.

- [ ] **Step 1: Failing tests** (add to `tests/test_graph_store.py`):

```python
def test_schema_carries_descriptions_and_groups(store):
    schema = store.schema()
    assert schema["nodes"]["Clause"]["group"] == "terms"
    assert schema["nodes"]["Clause"]["description"]
    assert schema["nodes"]["Clause"]["props"]["text"]["description"]
    assert schema["edges"]["HAS_CLAUSE"]["count"] == 2


def test_node_and_find(store):
    assert store.node("CMB-1")["name"]
    hits = store.find("FINAL SALE")
    assert [m["_label"] for m in hits["matches"]] == ["Clause"]
    assert hits["node_ids"] == [hits["matches"][0]["id"]]
    assert store.find("final sale", labels=["Merchant"])["matches"] == []


def test_store_opened_by_runs_is_read_only(store_path):
    store = graph_store.GraphStore(store_path)
    with pytest.raises(Exception):
        store.conn.execute("CREATE (:Merchant {id: 'MER-X', name: 'x'})")
```

(`store`/`store_path` fixtures: build the fixture graph, `load(...)` then close, reopen with `GraphStore(path)`.)

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement.** `find`:

```python
    def find(self, text: str, labels: list[str] | None = None, limit: int = 25) -> dict:
        """Nodes whose STRING properties contain `text`, ignoring case."""
        matches: list[dict] = []
        seen = _new_seen()
        for label, spec in self.ontology["nodes"].items():
            if labels and label not in labels:
                continue
            fields = ["id", *(k for k, p in spec["props"].items() if p["type"] == "STRING")]
            where = " OR ".join(f"lower(n.{f}) CONTAINS lower($text)" for f in fields)
            result = self.conn.execute(
                f"MATCH (n:{label}) WHERE {where} RETURN n LIMIT {limit}", {"text": text}
            )
            while result.has_next() and len(matches) < limit:
                matches.append(_clean(result.get_next()[0], seen))
        return {"matches": matches, "node_ids": sorted(seen["node_ids"]), "edge_ids": []}
```

Verify `lower()` and `CONTAINS` in ladybug docs via context7 first; if the function is named differently, use the documented one. `node`:

```python
    def node(self, node_id: str) -> dict:
        label = self.label_of(node_id)
        rows = self.query(f"MATCH (n:{label} {{id: $id}}) RETURN n", {"id": node_id}, 1)["rows"]
        if not rows:
            raise ValueError(f"no such node {node_id}")
        return rows[0][0]
```

`schema()` returns the ontology with counts added. Delete the removed functions and their tests.
- [ ] **Step 4:** Run → PASS. Per the keep-green rule, delete `tests/test_tools.py`, `tests/test_runtime.py` and any `tests/test_api.py`/`tests/test_evaluation.py` cases that build graphs with the old labels (recreated in Stages 6, 7, 9). `rg -n "copy_store|write_finding|write_note|set_note_status|since|until" src tests` must only show code later stages rewrite (`tools.py`, `runtime*.py`, `showcase.py`, `api/`); note them in handoff.
- [ ] **Step 5:** `simplify` skill on changed files; pytest + ruff; update handoff; commit `Graph store: static, schema-described, find/node lookups`; push.

---

## Stage 2 — Policy corpus, clause search and memory in the knowledge store (Complex)

### Task 2.1: Amex and Merchant policy markdown

**Files:** Create `data/corpus/policies/amex/{merchant-regulations,card-member-agreement,offer-terms,platinum-benefits,platinum-stays-participation,dispute-guide}.md` and `data/corpus/policies/merchant/{hgf-checkout-v4,hgf-web-v4,hph-reservation-v2,hph-folio-v1,nwo-sale-v1,wbv-contract-v2,wbc-catering-v1,stc-subscription-v3}.md`.

Format (every file):

```markdown
---
doc_id: POL-AMX-MR
title: American Express Merchant Regulations (excerpt)
owner: amex
kind: merchant_regulations
version: "2026-04"
audience: merchant
source_url: https://icm.aexp-static.com/content/dam/gms/en_us/optblue/us-mog.pdf
publisher: ""
---
## 4.1 Disclose your policies
Paraphrased clause text …
```

Clause id rule: `CLS-` + `doc_id` without `POL-` + `-` + number (e.g. `CLS-AMX-MR-4.1`, `CLS-HGF-CO-V4-4.3`).

Required documents and clauses (paraphrase R02 §5.1, §6.1, §6.2; keep each clause 1–4 sentences; never copy Amex text verbatim beyond short phrases):

| doc_id | Clauses (number: heading → substance) |
|---|---|
| POL-AMX-MR (merchant) | 4.1 Disclose policies → sale/return/exchange/cancellation terms at the point of sale, on receipts and on the website (R02 §5.1). 4.2 Acceptance before purchase → have the Card Member accept terms before completing the purchase; keep a record of how. 4.3 Credits to the original Card → refunds go to the Card used, in full or as the policy provides. 4.4 Unambiguous terms → where a dispute turns on terms, Amex resolves in the Merchant's favour only on unambiguous terms the Card Member agreed to. 4.5 Recurring billing → disclose plan, amount, frequency and how to cancel; each recurring arrangement is separate; honour cancellation. 4.6 Lodging reservations → give the rate and cancellation policy at reservation and honour the confirmed rate. 4.7 Paid by other means → a Merchant must not collect twice for the same goods; any amount received beyond what is due must be credited. |
| POL-AMX-CMA (card_member) | 5.1 Additional Cards → the Basic Card Member is responsible for all charges made with Additional Cards on the account, and may cancel an Additional Card at any time. 5.2 Billing disputes → Amex may credit, adjust or decline after reviewing information from the Card Member and the Merchant. |
| POL-AMX-OFFER (card_member) | 1 Enrolment is card-specific → add the Offer to the specific eligible Card and pay with that same Card; Offers added to one Card do not apply to purchases on another. 2 Direct purchases → purchases through third parties may not qualify. 3 Who funds and posts the credit → Amex posts the statement credit; the Merchant charges its normal price and is not responsible for the credit. 4 Minimum spend → the qualifying purchase must meet the spend threshold in one transaction. |
| POL-AMX-PLAT-BEN (card_member) | 2.1 Platinum Stays rate → book a participating property through Platinum Stays with your Platinum Card to receive the Platinum Stays rate. 2.2 Program credits → hotel credits post to the Platinum Card account. (2.1 must **not** say whether payment must also be on the Platinum Card: that silence is the case-B ambiguity.) |
| POL-AMX-PS-PART (merchant) | 3.1 Participation → properties honour Platinum Stays terms for eligible bookings. 3.2 Rate honour → a participating property must honour the Platinum Stays rate confirmed at booking for any reservation made or guaranteed with an eligible Platinum Card. 3.4 No added conditions → a property may not add eligibility conditions beyond these terms. |
| POL-AMX-DG (merchant+card_member; `audience: card_member`) | C-NKN, C-RET, C-CNC, C-CNR, C-DMG, C-DSS, C-DUP, C-NRC, C-OVR, C-PDD → one clause per category with meaning and typical evidence (R02 §4). V-1 Verdicts → the six verdicts and when each applies (spec §3.1 items 6–7). F-1 Fraud referral → if the Card Member denies taking part, refer to fraud; do not decide. G-1 Goodwill → Amex may fund a goodwill credit only under a written goodwill clause. G-2 Offer goodwill → one Offer goodwill per Card Member, only when the Offer was enrolled on another Card held by the same Card Member and the purchase otherwise met the Offer terms; check the Card Member's resolved Disputes for an earlier Offer goodwill. I-1 System improvements → record policy wording, process or data gaps that caused or prolonged the Dispute; record none when the policy was clear and followed. |
| POL-HGF-CO-V4 (merchant, publisher MER-HGF, kind returns) | 4.1 Standard items → returns within 30 days for a full refund to the original Card. 4.2 Return shipping → customer pays return freight. 4.3 Custom orders are final sale → any piece made in Customer's Own Material (COM) or made to measure is final sale and cannot be returned. |
| POL-HGF-WEB-V4 (merchant, MER-HGF, kind returns) | 1 30-day returns → most items can be returned within 30 days. 2 Exceptions → custom orders are final sale; see Checkout Terms §4.3. |
| POL-HPH-RES-V2 (merchant, MER-HPH, kind reservation_terms) | 1 Confirmed rate → the rate on the booking confirmation is the rate charged for the stay. 2 Cancellation → free cancellation up to 48 hours before arrival. |
| POL-HPH-FOLIO-V1 (merchant, MER-HPH, kind folio_terms) | 7 Platinum Stays settlement → the Platinum Stays rate applies only when the folio is settled with an American Express Platinum Card; folios settled with any other card are re-rated at the Best Available Rate. |
| POL-NWO-SALE-V1 (merchant, MER-NWO, kind sale_terms) | 1 Prices → items are charged at the listed price; Northwind promotions are applied only with a Northwind promo code. 2 Card Offers → offers from your card issuer are administered by the issuer. |
| POL-WBV-CONTRACT-V2 (merchant, MER-WBV, kind event_contract) | 3 Payment schedule → deposit $1,500 on signing; balance $4,500 before the event. 4 Payment methods → deposit and balance may each be paid by card or bank transfer. 5 Catering → catering is contracted separately with Willow Barn Catering. |
| POL-WBC-CATERING-V1 (merchant, MER-WBC, kind event_contract) | 2 Payment → catering is invoiced separately and payable in full before the event. |
| POL-STC-SUB-V3 (merchant, MER-STC, kind subscription_terms) | 2 Recurring billing → plans renew monthly until cancelled; the price is shown at sign-up. 4 Cancelling → cancel any time in Account > Plans; billing stops at the end of the period. 5 Separate plans → each plan is a separate subscription; cancelling one plan does not cancel others on the account. |

- [ ] **Step 1:** Write the 14 files. For every Amex clause, the text must be traceable to R02 (add the R02 section in an HTML comment only if needed for review; prefer the `source_url`).
- [ ] **Step 2:** Commit `Corpus: Amex and Merchant policy documents`.

### Task 2.2: One parser, projected into the graph and into search

**Files:** Create `data/generator/policies.py`; Modify `data/generator/knowledge.py`, `src/memory/retrieval.py`; Test `tests/test_knowledge.py` (rewrite), `tests/test_policies.py`.

**Interfaces:**
- Produces:
  - `policies.Clause(id, number, heading, text)`, `policies.PolicyDoc(id, title, owner, kind, version, audience, source_url, publisher, clauses: tuple[Clause, ...])` — frozen dataclasses.
  - `policies.parse(path) -> PolicyDoc`; `policies.load_policies(root: Path) -> list[PolicyDoc]` (sorted by id).
  - `policies.add_to_graph(g: Graph, doc: PolicyDoc) -> None` — PolicyDocument node, Clause nodes, HAS_CLAUSE edges, and PUBLISHED_BY when `doc.publisher`.
  - `knowledge.build_knowledge(docs: list[PolicyDoc], precedents: Path, db_path: Path) -> int` — one search document per clause (`doc_id` = clause id, `kind="policy"`, `title=f"{doc.title} — {clause.number} {clause.heading}"`, body = clause text) + precedents (`PRC-001…`).
  - `retrieval.build(db_path, docs)`; `retrieval.search(db_path, query, *, kinds=("policy","precedent","memory_note"), limit=8) -> list[dict]` (active documents only; **no `as_of`**); `retrieval.add_note(db_path, text, sources: list[str], run_id, confidence) -> str` (returns `MEM-…`); `retrieval.set_status(db_path, doc_id, status)`. Documents table columns: `doc_id, kind, title, body, status, sources, run_id, confidence` (`sources` JSON text).

- [ ] **Step 1: Failing tests** `tests/test_policies.py`:

```python
from pathlib import Path

import policies
from graph_builder import Graph

CORPUS = Path("data/corpus/policies")


def test_clause_ids_and_owner():
    docs = {d.id: d for d in policies.load_policies(CORPUS)}
    hgf = docs["POL-HGF-CO-V4"]
    assert hgf.owner == "merchant" and hgf.publisher == "MER-HGF"
    assert [c.id for c in hgf.clauses] == [
        "CLS-HGF-CO-V4-4.1", "CLS-HGF-CO-V4-4.2", "CLS-HGF-CO-V4-4.3"
    ]
    assert "final sale" in hgf.clauses[2].text.lower()
    assert docs["POL-AMX-OFFER"].source_url.startswith("https://")


def test_add_to_graph_links_clauses_and_publisher():
    g = Graph()
    g.node("Merchant", "MER-HGF", name="Hearth & Grain Furniture", category="furniture",
           channel="online")
    doc = policies.parse(CORPUS / "merchant" / "hgf-checkout-v4.md")
    policies.add_to_graph(g, doc)
    types = sorted(e["type"] for e in g.edges)
    assert types.count("HAS_CLAUSE") == 3 and "PUBLISHED_BY" in types
```

`tests/test_knowledge.py` (rewrite): build from `load_policies(CORPUS)` + a two-entry precedents file in `tmp_path`; assert `search(db, "custom order final sale")[0]["doc_id"] == "CLS-HGF-CO-V4-4.3"`; assert `add_note` returns `MEM-…`, the note is found with `kinds=("memory_note",)`, and after `set_status(db, id, "retracted")` it is not.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement `policies.py`:**

```python
"""Policy documents: one markdown source per version, projected into the graph and the search index."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_HEADING = re.compile(r"^## (\S+) (.+)$", re.M)


@dataclass(frozen=True)
class Clause:
    id: str
    number: str
    heading: str
    text: str


@dataclass(frozen=True)
class PolicyDoc:
    id: str
    title: str
    owner: str
    kind: str
    version: str
    audience: str
    source_url: str
    publisher: str
    clauses: tuple[Clause, ...]


def parse(path: Path) -> PolicyDoc:
    _, front, body = Path(path).read_text(encoding="utf-8").split("---", 2)
    meta = yaml.safe_load(front)
    parts = _HEADING.split(body)[1:]
    suffix = meta["doc_id"].removeprefix("POL-")
    clauses = tuple(
        Clause(f"CLS-{suffix}-{number}", number, heading.strip(), text.strip())
        for number, heading, text in zip(parts[::3], parts[1::3], parts[2::3], strict=True)
    )
    return PolicyDoc(
        id=meta["doc_id"],
        title=meta["title"],
        owner=meta["owner"],
        kind=meta["kind"],
        version=str(meta["version"]),
        audience=meta["audience"],
        source_url=meta.get("source_url") or "",
        publisher=meta.get("publisher") or "",
        clauses=clauses,
    )


def load_policies(root: Path) -> list[PolicyDoc]:
    return sorted((parse(p) for p in Path(root).rglob("*.md")), key=lambda d: d.id)


def add_to_graph(g, doc: PolicyDoc) -> None:
    g.node(
        "PolicyDocument", doc.id, title=doc.title, owner=doc.owner, kind=doc.kind,
        version=doc.version, audience=doc.audience, source_url=doc.source_url,
    )
    for clause in doc.clauses:
        g.node("Clause", clause.id, number=clause.number, heading=clause.heading,
               text=clause.text)
        g.edge("HAS_CLAUSE", doc.id, clause.id)
    if doc.publisher:
        g.edge("PUBLISHED_BY", doc.id, doc.publisher)
```

Then `knowledge.py` and `retrieval.py` per the interfaces (delete `_valid_on`, `_bound`, `load_policies` from knowledge.py, `valid_from`/`valid_to` fields).
- [ ] **Step 4:** Rewrite `data/corpus/precedents.yaml` with 8 resolved Amex write-ups on **analogous but different** facts (never the five showcase cases): a disclosed final-sale clearance item refused (RET, rejected); a restocking fee not shown at checkout (OVR, fee credited); a hotel re-rate where the booking itself used a non-eligible Card (OVR, rejected); an Offer on another of the Card Member's own Cards (OVR, goodwill once); a merchant-funded promo code not applied (OVR, accepted); an overpayment across card + cheque (PDD, partial); a subscription billed to an Additional Card (CNR, not_a_dispute); a charge the Card Member later said they never made (NKN → fraud_referral).
- [ ] **Step 5:** Run → PASS. `simplify`; pytest + ruff; handoff; commit `Knowledge: clause-level policy search and memory notes`; push.

---

## Stage 3 — Background world (Medium)

### Task 3.1: Rewrite `data/generator/world.py`

**Files:** Replace `data/generator/world.py`; Test `tests/test_generator_world.py` (rewrite).

**Interfaces:**
- Consumes: `Graph`, `policies.PolicyDoc`, `policies.add_to_graph`, `policies.load_policies`.
- Produces: `build_world(seed: int = 7, corpus: Path = Path("data/corpus/policies")) -> tuple[Graph, list[PolicyDoc]]` (the graph with the whole background **and every corpus document added via `add_to_graph`**, plus the list of all PolicyDocs — corpus + generated templates — for the knowledge build); `stats(graph) -> None`. Also exports the shared Amex anchors the cases link to: `AMEX_MR = "POL-AMX-MR"`, `AMEX_CMA = "POL-AMX-CMA"`, `AMEX_OFFER = "POL-AMX-OFFER"`, `AMEX_PLAT_BEN = "POL-AMX-PLAT-BEN"`, `AMEX_PS_PART = "POL-AMX-PS-PART"`, `PLATINUM_STAYS = "PRG-PLAT"`.

Requirements (deterministic via `random.Random(seed)`; ids `PREFIX-BG-<n>`; dates in 2026):
- Program `PRG-PLAT` "Platinum Stays" (`eligible_product="Platinum"`) with GOVERNS from POL-AMX-PLAT-BEN and POL-AMX-PS-PART.
- ~150 Card Members; ~60% one Card Product, ~30% two (e.g. Platinum + Gold on separate accounts), ~15 accounts with an Additional Card Member (HOLDS role additional, own Card with `role="additional"`). Every account BOUND_BY POL-AMX-CMA; Platinum accounts also BOUND_BY POL-AMX-PLAT-BEN. Include ≥3 namesake pairs (same `name`, different `member_since` and accounts).
- ~30 Merchants across furniture/apparel retail (with Products having `standard_options` and some `custom_options`), lodging (6 PARTICIPATES_IN PRG-PLAT and BOUND_BY POL-AMX-PS-PART), streaming/subscriptions (with Descriptors, some with a parent-brand descriptor), events/venues (with an AFFILIATE_OF caterer), dining. Every Merchant BOUND_BY POL-AMX-MR. Each background Merchant gets 1–2 generated template PolicyDocs (`POL-BG-<n>`, clauses drawn from a small set of templates per category: returns window, final-sale exceptions, cancellation, recurring, payment schedule) added with `add_to_graph` and returned for indexing.
- ~3k charges over ~1.2k orders (with LineItems/OF_PRODUCT for retail; lodging orders with GUARANTEED_WITH, some UNDER_PROGRAM), ~150 credits with REFUNDS, ~40 Returns (most refunded, some refused under a final-sale clause), ~20 Subscriptions with recurring charges (FOR_SUBSCRIPTION, DESCRIBED_AS), ~10 Invoices with 2–3 Installments settled by Charges and/or Payments, ~12 Offers (mostly `funded_by="amex"`, GOVERNS from POL-AMX-OFFER, OFFER_AT, ENROLLED_ON one Card), orders ACCEPTED against their Merchant's policy doc.
- ~60 resolved past Disputes (`status="resolved"`, `outcome` one of the six verdicts, spread over categories) with FILED_BY, DISPUTES, and a MerchantSubmission for about half (use `insert_submission` once Stage 4 exists — in this stage write the submission nodes directly with the same shape; Stage 4 Task 4.1 switches the world to `insert_submission`).
- Nothing else: no devices, IPs, phones, emails, addresses, tokens, account events.

- [ ] **Step 1: Failing tests** (`tests/test_generator_world.py`):

```python
import world


def test_world_is_deterministic(tmp_path):
    a, _ = world.build_world(seed=7)
    b, _ = world.build_world(seed=7)
    a.write(tmp_path / "a")
    b.write(tmp_path / "b")
    for name in ("nodes.jsonl", "edges.jsonl"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_world_scale_and_policies():
    g, docs = world.build_world()
    labels = [n["label"] for n in g.nodes.values()]
    assert 120 <= labels.count("CardMember") <= 200
    assert 2000 <= labels.count("Charge") <= 5000
    assert labels.count("Dispute") >= 50
    assert {"POL-AMX-MR", "POL-AMX-DG", "POL-HGF-CO-V4"} <= {d.id for d in docs}
    assert any(d.id.startswith("POL-BG-") for d in docs)


def test_every_merchant_bound_by_amex_regulations():
    g, _ = world.build_world()
    merchants = {i for i, n in g.nodes.items() if n["label"] == "Merchant"}
    bound = {e["src"] for e in g.edges if e["type"] == "BOUND_BY" and e["dst"] == "POL-AMX-MR"}
    assert merchants <= bound
```

- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement with small plain functions per area (`_card_members`, `_merchants`, `_orders_and_charges`, `_subscriptions`, `_invoices`, `_offers`, `_past_disputes`). **Step 4:** Run → PASS.
- [ ] **Step 5:** `simplify`; pytest + ruff; handoff; commit `World: Amex dispute-only background`; push.

---

## Stage 4 — Merchant Submission contract, case kit, cases A and B (Complex)

### Task 4.1: Submission contract and `insert_submission`

**Files:** Create `src/extensions/__init__.py`, `src/extensions/merchant_agent/__init__.py`, `src/extensions/merchant_agent/contract.py`, `data/generator/submissions.py`; Test `tests/test_submissions.py`. Modify `world.py` to use `insert_submission` for past Disputes.

**Interfaces:**
- Produces (`contract.py`):

```python
"""Typed contract between the Dispute AI and a Merchant (see README: Merchant agent, not wired)."""

from __future__ import annotations

from schemas import SchemaModel


class EvidenceAsk(SchemaModel):
    topic: str          # e.g. "return policy accepted at purchase"
    detail: str


class MerchantEvidenceRequest(SchemaModel):
    dispute_id: str
    merchant_id: str
    charge_ids: list[str]
    asks: list[EvidenceAsk]


class SubmittedItem(SchemaModel):
    kind: str           # acceptance_log, folio, invoice_ledger, usage_log, …
    text: str
    asserts: list[str]  # graph ids the item is about (orders, charges, subscriptions, …)


class SubmittedMessage(SchemaModel):
    channel: str
    sender: str
    date: str
    text: str
    asserts: list[str]


class MerchantSubmission(SchemaModel):
    submission_id: str  # MSB-…
    dispute_id: str
    merchant_id: str
    statement: str
    items: list[SubmittedItem]
    messages: list[SubmittedMessage]
    cited_ids: list[str]  # clause (CLS-…) or policy document (POL-…) ids
```

- Produces (`submissions.py`): `insert_submission(g: Graph, s: MerchantSubmission) -> None` — MerchantSubmission node (`statement`), `HAS_SUBMISSION` dispute→submission; each item → `EvidenceItem` `EVI-<submission suffix>-<n>` (`source="merchant"`) + `HAS_EVIDENCE` + one `ASSERTS` per id; each message → `Communication` `COM-<submission suffix>-<n>` + `HAS_EVIDENCE` + `ASSERTS`; `CITES` per cited id. `load_saved(dir: Path) -> list[MerchantSubmission]` reads `*.json` (returns `[]` when the directory is absent).

- [ ] **Step 1: Failing test** `tests/test_submissions.py`: build a tiny graph (Card Member, Card, Merchant, Order, Charge, Dispute, one policy doc via `add_to_graph`), insert a submission with one item asserting the order, one message asserting the order, citing one clause; assert node ids `EVI-A01-1`, `COM-A01-1` exist (for `submission_id="MSB-A01"`), edge types `HAS_SUBMISSION, HAS_EVIDENCE×2, ASSERTS×2, CITES` present; `load_saved(tmp_path / "missing") == []`; a saved JSON round-trips.
- [ ] **Step 2–4:** FAIL → implement → PASS. Switch `world._past_disputes` to build `MerchantSubmission` objects and call `insert_submission`.
- [ ] **Step 5:** Commit `Submissions: typed contract and single graph insert path`.

### Task 4.2: Case kit

**Files:** Modify `data/generator/cases/__init__.py`, `data/generator/validate.py`, `data/generator/capabilities.py`; Test `tests/test_cases.py` (new).

**Interfaces:**
- `CaseTruth` keys: `case_id, code, title, intake, misleading_surface, expected, solution_node_ids, proof_patterns, decoy_patterns, required_capabilities`.
- `expected = {"verdict", "category", "charges": [charge_expected(...)], "improvement_targets": list[str]}`.
- `build_cases(g, rng) -> list[CaseTruth]` over `builders = (a_final_sale.build, b_platinum_rate.build, c_offer_card.build, d_paid_transfer.build, e_wrong_plan.build)` (C–E added in Stage 5).
- `validate_cases(store, cases)` unchanged in behaviour; `write_case_outputs(output_dir, cases, graph)` writes catalog entries `{case_id, title, claim, amount, summary}` where `claim` is a neutral phrase from the case module (`"Refund refused after return"`, never the category code).
- `capabilities.CAPABILITIES`: rename signals — `memory_graph` → label "Graph", signals `["graph_query", "graph_find"]`; `write_paths` → signals `["notebook_write", "memory_write"]`; `memory_semantic` → "As-is hybrid retrieval over policy clauses, precedents and memory notes."; delete `read_paths` wording about temporal scope. `CASE_NEEDS` gets entries A–E (Stage 4: A, B; Stage 5: C, D, E), each 3–4 `(capability, primary|supporting, why)` rows.

- [ ] **Step 1:** Write `tests/test_cases.py` (grows in Stage 5):

```python
import random

import pytest
from cases import build_cases
from graph_builder import Graph
from validate import validate_cases, write_case_outputs
from world import build_world

import graph_store


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("gen")
    g, _ = build_world()
    cases = build_cases(g, random.Random(42))
    g.write(out / "graph")
    store = graph_store.load(out / "graph", out / "g.lbug")
    return g, cases, store, out


def test_cases_validate_with_proofs_and_decoys(built):
    g, cases, store, _ = built
    validate_cases(store, cases)
    for case in cases:
        assert case["decoy_patterns"] and case["proof_patterns"]
        assert 5 <= len(case["solution_node_ids"]) <= 25


def test_catalog_never_reveals_category_or_verdict(built):
    g, cases, _, out = built
    write_case_outputs(out, cases, g)
    catalog = (out / "case_catalog.json").read_text()
    for case in cases:
        assert case["expected"]["verdict"] not in catalog
        assert f'"{case["expected"]["category"]}"' not in catalog


def test_ground_truth_not_in_graph(built):
    g, cases, _, _ = built
    text = "\n".join(str(n["props"]) for n in g.nodes.values())
    for case in cases:
        assert case["misleading_surface"] not in text
```

- [ ] **Step 2:** Implement the kit changes; tests pass with an empty builder tuple except `test_cases_validate…` which needs ≥1 case (write Task 4.3 first if running strictly TDD).

### Task 4.3: Case A — "Final Sale Means Final" (RET → rejected)

**Files:** Create `data/generator/cases/a_final_sale.py`.

Full builder (the pattern every case follows):

```python
"""A: the Card Member returned a custom (COM) sofa that the accepted checkout terms made final sale."""

from __future__ import annotations

from graph_builder import Graph
from submissions import insert_submission
from world import AMEX_MR

from cases import CaseTruth, charge_expected
from extensions.merchant_agent.contract import MerchantSubmission, SubmittedItem, SubmittedMessage

DISPUTE = "DSP-2026-91001"
INTAKE = (
    "I returned the sofa within 30 days like Hearth & Grain's website says, and they refused "
    "to refund my $2,400."
)


def _card_member(g: Graph, n: str, name: str, since: str, last4: str) -> str:
    g.node("CardMember", f"CMB-A{n}", name=name, member_since=since)
    g.node("CardAccount", f"ACC-A{n}", product="Gold", status="open")
    g.node("Card", f"CRD-A{n}", last4=last4, product="Gold", role="basic", status="active")
    g.edge("HOLDS", f"CMB-A{n}", f"ACC-A{n}", role="basic")
    g.edge("ISSUED_ON", f"CRD-A{n}", f"ACC-A{n}")
    g.edge("CARRIED_BY", f"CRD-A{n}", f"CMB-A{n}")
    return f"CRD-A{n}"


def _sofa_order(g: Graph, n: str, card: str, option: str, date: str) -> tuple[str, str]:
    order, charge = f"ORD-A{n}", f"CHG-A{n}"
    g.node("Order", order, date=date, kind="retail", total=2400.0, currency="USD",
           summary=f"Alder three-seat sofa, {option}")
    g.edge("AT_MERCHANT", order, "MER-HGF")
    g.node("LineItem", f"LIN-A{n}", description="Alder three-seat sofa", quantity=1,
           unit_price=2400.0, option=option)
    g.edge("HAS_LINE", order, f"LIN-A{n}")
    g.edge("OF_PRODUCT", f"LIN-A{n}", "PRD-ALDER")
    g.edge("ACCEPTED", order, "POL-HGF-CO-V4", method="checkbox at checkout")
    g.node("Charge", charge, date=date, amount=2400.0, currency="USD", kind="purchase",
           status="posted")
    g.edge("CHARGED_TO", charge, card)
    g.edge("AT_MERCHANT", charge, "MER-HGF")
    g.edge("FOR_ORDER", charge, order)
    return order, charge


def build(g: Graph, _rng) -> CaseTruth:
    g.node("Merchant", "MER-HGF", name="Hearth & Grain Furniture", category="furniture",
           channel="online")
    g.edge("BOUND_BY", "MER-HGF", AMEX_MR)
    g.node("Product", "PRD-ALDER", name="Alder three-seat sofa",
           standard_options="Sage linen; Oat linen; Charcoal linen",
           custom_options="Customer's Own Material (COM); made to measure")
    g.edge("SOLD_BY", "PRD-ALDER", "MER-HGF")

    card = _card_member(g, "01", "Priya Raman", "2019-04-02", "1004")
    order, charge = _sofa_order(g, "01", card, "Customer's Own Material (COM)", "2026-07-02")
    g.node("Return", "RTN-A01", method="customer freight", status="refused",
           note="Delivery of the return refused by the Merchant; sofa sent back to customer.")
    g.edge("RETURNED_AS", order, "RTN-A01")
    g.node("Dispute", DISPUTE, filed_at="2026-08-20", amount=2400.0, intake=INTAKE,
           status="open", outcome="")
    g.edge("FILED_BY", DISPUTE, "CMB-A01")
    g.edge("DISPUTES", DISPUTE, charge, amount=2400.0)
    insert_submission(g, MerchantSubmission(
        submission_id="MSB-A01", dispute_id=DISPUTE, merchant_id="MER-HGF",
        statement="This was a custom COM order. Checkout Terms 4.3, accepted at checkout, make "
                  "custom orders final sale, so we refused the return.",
        items=[SubmittedItem(kind="acceptance_log", asserts=[order],
                             text="Checkbox 'I agree to the Checkout Terms (v4)' ticked on "
                                  "2026-07-02 14:03 before payment.")],
        messages=[SubmittedMessage(channel="email", sender="Hearth & Grain", date="2026-07-02",
                                   asserts=[order],
                                   text="Thanks for your order of the Alder sofa in your own "
                                        "material (COM). Custom orders are final sale "
                                        "(Checkout Terms 4.3).")],
        cited_ids=["CLS-HGF-CO-V4-4.3"],
    ))

    # Decoy: a standard-fabric sofa under the same terms, returned and refunded.
    decoy_card = _card_member(g, "02", "Jonah Pike", "2021-01-15", "1027")
    decoy_order, decoy_charge = _sofa_order(g, "02", decoy_card, "Oat linen", "2026-06-11")
    g.node("Return", "RTN-A02", method="customer freight", status="received and refunded",
           note="Standard item returned within 30 days.")
    g.edge("RETURNED_AS", decoy_order, "RTN-A02")
    g.node("Charge", "CHG-A02R", date="2026-06-30", amount=-2400.0, currency="USD",
           kind="credit", status="posted")
    g.edge("CHARGED_TO", "CHG-A02R", decoy_card)
    g.edge("AT_MERCHANT", "CHG-A02R", "MER-HGF")
    g.edge("REFUNDS", "CHG-A02R", decoy_charge)

    return {
        "case_id": DISPUTE,
        "code": "A",
        "title": "Final Sale Means Final",
        "intake": INTAKE,
        "misleading_surface": "The website promises 30-day returns and another customer's "
                              "identical sofa was refunded.",
        "expected": {
            "verdict": "rejected",
            "category": "RET",
            "charges": [charge_expected(charge, "rejected", 2400.0, 0.0)],
            "improvement_targets": [],
        },
        "solution_node_ids": [DISPUTE, charge, order, "LIN-A01", "PRD-ALDER",
                              "POL-HGF-CO-V4", "CLS-HGF-CO-V4-4.3", "RTN-A01", "MSB-A01",
                              "CLS-AMX-MR-4.2"],
        "proof_patterns": [{
            "name": "COM option is a custom option under accepted final-sale clause",
            "cypher": (
                "MATCH (d:Dispute {id: 'DSP-2026-91001'})-[:DISPUTES]->(:Charge)-[:FOR_ORDER]->"
                "(o:Order)-[:HAS_LINE]->(l:LineItem)-[:OF_PRODUCT]->(p:Product), "
                "(o)-[a:ACCEPTED]->(:PolicyDocument)-[:HAS_CLAUSE]->"
                "(c:Clause {id: 'CLS-HGF-CO-V4-4.3'}) "
                "WHERE p.custom_options CONTAINS 'COM' AND l.option CONTAINS 'COM' "
                "RETURN d, o, l, p, c"
            ),
        }],
        "decoy_patterns": [{
            "name": "standard sofa under same terms was refunded",
            "cypher": (
                "MATCH (o:Order {id: 'ORD-A02'})-[:HAS_LINE]->(l:LineItem), "
                "(o)-[:RETURNED_AS]->(r:Return), (cr:Charge)-[:REFUNDS]->(:Charge)-[:FOR_ORDER]->(o) "
                "WHERE r.status CONTAINS 'refunded' RETURN o, l, r, cr"
            ),
        }],
    }
```

Also add `POL-HGF-WEB-V4` applicability: it is PUBLISHED_BY MER-HGF only (via its front matter); never ACCEPTED by an order.

- [ ] **Steps:** add the builder, add `"A"` to `CASE_NEEDS` (`memory_graph`/Graph primary: product options × accepted clause; `skills` primary: policy-analysis; `agents` supporting: website-vs-accepted-terms hypothesis), run `tests/test_cases.py` → PASS, commit `Case A: Final Sale Means Final`.

### Task 4.4: Case B — "Platinum Rate, Gold Card" (OVR → accepted $300)

**Files:** Create `data/generator/cases/b_platinum_rate.py` (same structure as A).

Nodes (id: props):

| id | label | props |
|---|---|---|
| CMB-B01 | CardMember | name "Marcus Bell", member_since "2016-09-12" |
| ACC-B01 / CRD-B01 | CardAccount / Card | Platinum; Card last4 "2002", role basic |
| ACC-B02 / CRD-B02 | CardAccount / Card | Gold; Card last4 "2031", role basic |
| MER-HPH | Merchant | "Harbor Point Hotel", category lodging, channel in_person |
| ORD-B01 | Order | date 2026-06-10, kind lodging, total 1000.0, summary "2 nights, Platinum Stays rate $500/night, arriving 2026-07-18" |
| CHG-B01 | Charge | date 2026-07-20, amount 1300.0, kind purchase |
| DSP-2026-91002 | Dispute | filed 2026-08-02, amount 300.0, intake "Harbor Point charged me $1,300 for a two-night stay I booked at the $1,000 Platinum Stays rate." |
| CMB-B02, ACC-B03, CRD-B03 | decoy Card Member "Ana Ruiz", Gold, last4 "2044" |
| ORD-B02 | Order | lodging, total 1000.0, summary "2 nights, Platinum Stays rate $500/night" |
| CHG-B02 | Charge | amount 1300.0 |
| DSP-HIST-B02 | Dispute | resolved, outcome "rejected", amount 300.0, intake "Hotel charged the full rate instead of the Platinum rate." |

Edges: HOLDS/ISSUED_ON/CARRIED_BY for all Cards; ACC-B01 BOUND_BY POL-AMX-PLAT-BEN and POL-AMX-CMA; MER-HPH BOUND_BY POL-AMX-MR and POL-AMX-PS-PART; MER-HPH PARTICIPATES_IN PRG-PLAT; ORD-B01 AT_MERCHANT MER-HPH, UNDER_PROGRAM PRG-PLAT, **GUARANTEED_WITH CRD-B01**, ACCEPTED POL-HPH-RES-V2 {method "booking confirmation"}; CHG-B01 **CHARGED_TO CRD-B02**, AT_MERCHANT, FOR_ORDER ORD-B01; DISPUTES {amount 300.0}; FILED_BY. Decoy: ORD-B02 UNDER_PROGRAM PRG-PLAT, **GUARANTEED_WITH CRD-B03 (Gold)**, CHG-B02 CHARGED_TO CRD-B03, DSP-HIST-B02 FILED_BY CMB-B02, DISPUTES CHG-B02.

Submission `MSB-B01`: statement "The guest settled the folio with a Gold Card, so under our folio terms clause 7 the stay was re-rated to the Best Available Rate of $650 per night."; items: folio ("Folio: 2 nights re-rated to Best Available Rate $650/night; settled with Amex Gold ending 2031", asserts CHG-B01); booking confirmation ("Platinum Stays rate $500/night, 2 nights, guaranteed with Amex Platinum ending 2002", asserts ORD-B01); cited `CLS-HPH-FOLIO-V1-7`. Decoy submission `MSB-HIST-B02` for DSP-HIST-B02: booking guaranteed with Gold, rate not eligible.

Expected: verdict `accepted`, category `OVR`, charges `[charge_expected("CHG-B01", "accepted", 300.0, 300.0)]`, improvement_targets `["amex_policy", "merchant_policy"]`.
Solution ids: DSP-2026-91002, CHG-B01, CRD-B02, ORD-B01, CRD-B01, PRG-PLAT, MER-HPH, CLS-HPH-FOLIO-V1-7, CLS-AMX-PS-PART-3.2, CLS-AMX-PS-PART-3.4, CLS-AMX-PLAT-BEN-2.1, MSB-B01.
Proof: `MATCH (d:Dispute {id:'DSP-2026-91002'})-[:DISPUTES]->(c:Charge)-[:FOR_ORDER]->(o:Order)-[:GUARANTEED_WITH]->(g:Card), (c)-[:CHARGED_TO]->(p:Card), (o)-[:UNDER_PROGRAM]->(prg:Program)<-[:PARTICIPATES_IN]-(m:Merchant)-[:BOUND_BY]->(:PolicyDocument)-[:HAS_CLAUSE]->(cl:Clause {id:'CLS-AMX-PS-PART-3.4'}) WHERE g.product = 'Platinum' AND p.product = 'Gold' RETURN d, o, g, p, prg, cl`.
Decoy: `MATCH (o:Order {id:'ORD-B02'})-[:GUARANTEED_WITH]->(g:Card) WHERE g.product = 'Gold' MATCH (h:Dispute {id:'DSP-HIST-B02'}) WHERE h.outcome = 'rejected' RETURN o, g, h`.
CASE_NEEDS "B": Graph primary (booking card vs payment card through the program), subagents primary (policy_analyst on three documents in parallel with payments work), skills primary (policy-analysis, offers-and-benefits), agents supporting (reject the precedent-like decoy).

- [ ] **Steps:** builder → tests → PASS → `simplify` over Stage 4 files → pytest + ruff → handoff → commit `Case B: Platinum Rate, Gold Card` → push.

---
## Stage 5 — Cases C, D, E and the end-to-end generator (Complex)

### Task 5.1: Case C — "The Offer on the Other Card" (OVR → goodwill_credit $100)

**Files:** Create `data/generator/cases/c_offer_card.py`.

| id | label | props |
|---|---|---|
| CMB-C01 | CardMember | "Daniel Okafor", member_since "2014-03-08" |
| ACC-C01 / CRD-C01 | Platinum; Card last4 "3003" basic |
| ACC-C02 / CRD-C02 | Gold; Card last4 "3017" basic |
| MER-NWO | Merchant | "Northwind Outfitters", apparel, online |
| OFR-NWO-100 | Offer | title "Spend $500 or more at Northwind Outfitters, get $100 back", spend_threshold 500.0, credit_amount 100.0, funded_by "amex" |
| ORD-C01 | Order | 2026-07-09, retail, total 540.0, summary "Storm parka and trail boots" |
| LIN-C01 / LIN-C02 | LineItem | "Storm parka" 1 × 390.0 option "Navy, M"; "Trail boots" 1 × 150.0 option "Size 10" |
| CHG-C01 | Charge | 2026-07-09, 540.0, purchase |
| DSP-2026-91003 | Dispute | filed 2026-09-01, amount 100.0, intake "I spent $540 at Northwind with the $100-off Amex Offer and never got the $100. They overcharged me." |
| DSP-HIST-C01 | Dispute | resolved, outcome "rejected", amount 64.0, intake "Charged twice for one order at a restaurant." (CMB-C01's own unrelated history) |
| CMB-C02 | CardMember (namesake decoy) | "Daniel Okafor", member_since "2020-11-19"; ACC-C03/CRD-C03 Green last4 "3090" |
| DSP-HIST-C02 | Dispute | resolved, outcome "goodwill_credit", amount 75.0, intake "Added the Offer to my Platinum but paid with my Green card; no credit." |

Edges: account/card edges; ACC-C01 BOUND_BY POL-AMX-PLAT-BEN, POL-AMX-CMA; ACC-C02 BOUND_BY POL-AMX-CMA; MER-NWO BOUND_BY POL-AMX-MR; POL-AMX-OFFER GOVERNS OFR-NWO-100; OFR-NWO-100 OFFER_AT MER-NWO, **ENROLLED_ON CRD-C01**; ORD-C01 AT_MERCHANT, HAS_LINE ×2 (Products PRD-NWO-PARKA, PRD-NWO-BOOT SOLD_BY MER-NWO), ACCEPTED POL-NWO-SALE-V1 {method "checkout"}; CHG-C01 **CHARGED_TO CRD-C02**, AT_MERCHANT, FOR_ORDER; DISPUTES {100.0}; FILED_BY CMB-C01; DSP-HIST-C01 FILED_BY CMB-C01 + DISPUTES a background charge on CRD-C02; DSP-HIST-C02 FILED_BY **CMB-C02** + DISPUTES a background charge on CRD-C03.

Submission `MSB-C01`: statement "Order charged at our listed prices. Northwind ran no promotion on this order; card-issuer offers are administered by the issuer."; item invoice ("Invoice: parka $390 + boots $150 = $540; no promo code applied", asserts ORD-C01); cited `CLS-NWO-SALE-V1-2`.

Expected: `goodwill_credit`, `OVR`, charges `[charge_expected("CHG-C01", "goodwill_credit", 100.0, 100.0)]`, improvement_targets `["process"]`.
Solution ids: DSP-2026-91003, CHG-C01, CRD-C02, OFR-NWO-100, CRD-C01, CMB-C01, CLS-AMX-OFFER-1, CLS-AMX-OFFER-3, CLS-AMX-DG-G-2, DSP-HIST-C01, MSB-C01.
Proof: `MATCH (d:Dispute {id:'DSP-2026-91003'})-[:DISPUTES]->(c:Charge)-[:CHARGED_TO]->(paid:Card)-[:CARRIED_BY]->(cm:CardMember), (o:Offer)-[:ENROLLED_ON]->(enrolled:Card)-[:CARRIED_BY]->(cm), (c)-[:AT_MERCHANT]->(m:Merchant)<-[:OFFER_AT]-(o) WHERE paid.id <> enrolled.id AND c.amount >= o.spend_threshold AND o.funded_by = 'amex' RETURN d, c, paid, enrolled, o, cm`.
Decoy: `MATCH (h:Dispute {id:'DSP-HIST-C02'})-[:FILED_BY]->(x:CardMember), (y:CardMember {id:'CMB-C01'}) WHERE x.name = y.name AND x.id <> y.id AND h.outcome = 'goodwill_credit' RETURN h, x, y`.
CASE_NEEDS "C": Graph primary (Offer → enrolled Card → Card Member → paid Card), agents primary (namesake must not block goodwill), skills primary (offers-and-benefits, dispute-outcomes), tool_calling supporting.

### Task 5.2: Case D — "Paid by Transfer" (PDD → partially_accepted $500)

**Files:** Create `data/generator/cases/d_paid_transfer.py`.

| id | label | props |
|---|---|---|
| CMB-D01 / ACC-D01 / CRD-D01 | "Elena Voss", since "2018-05-30"; Gold; last4 "4004" |
| MER-WBV | Merchant | "Willow Barn Venue", events, in_person |
| MER-WBC | Merchant | "Willow Barn Catering", catering, in_person |
| INV-D01 | Invoice | 2026-03-01, total 6000.0, description "Wedding venue hire, 15 August 2026" |
| INS-D01-DEP / INS-D01-BAL | Installment | "Deposit" 1500.0 / "Balance" 4500.0 |
| INV-D02 | Invoice | 2026-03-04, total 4500.0, description "Wedding catering, 120 guests, 15 August 2026" |
| INS-D02-FULL | Installment | "Catering in full" 4500.0 |
| PAY-D01 | Payment | 2026-03-02, bank_transfer, 1500.0, reference "WILLOW BARN DEP VOSS" |
| PAY-D02 | Payment | 2026-07-20, bank_transfer, 4500.0, reference "WILLOW BARN VOSS" |
| CHG-D01 | Charge | 2026-08-01, 5000.0, purchase |
| DSP-2026-91004 | Dispute | filed 2026-08-25, amount 5000.0, intake "I paid Willow Barn by bank transfer, $1,500 and then $4,500. The $5,000 card charge is a second payment for the same wedding." |

Edges: MER-WBC AFFILIATE_OF MER-WBV; both BOUND_BY POL-AMX-MR; INV-D01 AT_MERCHANT MER-WBV, BILLED_TO CMB-D01, ACCEPTED POL-WBV-CONTRACT-V2 {method "signature"}, HAS_INSTALLMENT DEP & BAL; INV-D02 AT_MERCHANT MER-WBC, BILLED_TO, ACCEPTED POL-WBC-CATERING-V1 {method "signature"}, HAS_INSTALLMENT FULL; PAY-D01 PAID_BY CMB-D01, AT_MERCHANT **MER-WBV**, SETTLES INS-D01-DEP; PAY-D02 PAID_BY, AT_MERCHANT **MER-WBC**, SETTLES INS-D02-FULL; CHG-D01 CHARGED_TO CRD-D01, AT_MERCHANT MER-WBV, **SETTLES INS-D01-BAL**; DISPUTES {5000.0}; FILED_BY.

Submission `MSB-D01`: statement "The card charge paid the balance of the venue invoice; the deposit was paid by bank transfer."; item invoice ledger ("Venue invoice: deposit $1,500 received by transfer 2026-03-02; balance settled by Amex card 2026-08-01", asserts INV-D01, INS-D01-BAL); cited `CLS-WBV-CONTRACT-V2-3`. (It is silent on the $500 difference.)

Expected: `partially_accepted`, `PDD`, charges `[charge_expected("CHG-D01", "partially_accepted", 5000.0, 500.0)]`, improvement_targets `["process"]` (accept `merchant_policy` too: scoring treats a required target as met by either — see Task 7.3).
Solution ids: DSP-2026-91004, CHG-D01, INV-D01, INS-D01-DEP, INS-D01-BAL, PAY-D01, PAY-D02, INV-D02, MER-WBC, MER-WBV, CLS-WBV-CONTRACT-V2-3, CLS-AMX-MR-4.7.
Proof: `MATCH (d:Dispute {id:'DSP-2026-91004'})-[:DISPUTES]->(c:Charge)-[:SETTLES]->(bal:Installment)<-[:HAS_INSTALLMENT]-(inv:Invoice)-[:HAS_INSTALLMENT]->(dep:Installment)<-[:SETTLES]-(p:Payment) WHERE c.amount > bal.amount RETURN d, c, bal, inv, dep, p`.
Decoy: `MATCH (p:Payment {id:'PAY-D02'})-[:SETTLES]->(:Installment)<-[:HAS_INSTALLMENT]-(:Invoice)-[:AT_MERCHANT]->(m:Merchant)-[:AFFILIATE_OF]->(:Merchant {id:'MER-WBV'}) RETURN p, m`.
CASE_NEEDS "D": sandbox primary (6000 vs 1500 + 5000), Graph primary (payment → installment → invoice → merchant), agents supporting (catering transfer is not this invoice).

### Task 5.3: Case E — "Cancelled the Wrong Plan" (CNR → not_a_dispute)

**Files:** Create `data/generator/cases/e_wrong_plan.py`.

| id | label | props |
|---|---|---|
| CMB-E01 | CardMember | "Tom Lindqvist", since "2012-02-17" (Basic) |
| CMB-E02 | CardMember | "Maya Lindqvist", since "2024-09-01" (Additional) |
| ACC-E01 | CardAccount | Blue Cash, open |
| CRD-E01 / CRD-E02 | Card | last4 "5005" role basic / last4 "5013" role additional; both product Blue Cash |
| MER-STC | Merchant | "StreamCo", streaming, online |
| DSC-STC | Descriptor | "SC*DIGITAL SVCS" |
| SUB-E01 | Subscription | plan "Individual", 12.99, monthly, cancelled |
| SUB-E02 | Subscription | plan "Family", 22.99, monthly, active |
| CHG-E01 | Charge | 2026-05-03, 12.99, recurring |
| CHG-E01R | Charge | 2026-05-06, -12.99, credit |
| CHG-E02 / E03 / E04 | Charge | 2026-06-12 / 07-12 / 08-12, 22.99 each, recurring |
| COM-E01 | Communication | email, sender "StreamCo", date 2026-05-04, text "Your StreamCo Individual plan has been cancelled. You won't be charged again for this plan." |
| DSP-2026-91005 | Dispute | filed 2026-08-20, amount 68.97, intake "I cancelled StreamCo in May and got a confirmation email, but SC*DIGITAL SVCS keeps charging me $22.99 every month." |

Edges: HOLDS CMB-E01→ACC-E01 {basic}, CMB-E02→ACC-E01 {additional}; both Cards ISSUED_ON ACC-E01; CRD-E01 CARRIED_BY CMB-E01; CRD-E02 CARRIED_BY **CMB-E02**; ACC-E01 BOUND_BY POL-AMX-CMA; MER-STC BOUND_BY POL-AMX-MR; DSC-STC DESCRIBES MER-STC; SUB-E01 AT_MERCHANT, SUBSCRIBED_WITH CRD-E01, ACCEPTED POL-STC-SUB-V3 {"checkbox at sign-up"}; SUB-E02 AT_MERCHANT, **SUBSCRIBED_WITH CRD-E02**, ACCEPTED POL-STC-SUB-V3; CHG-E01 CHARGED_TO CRD-E01, FOR_SUBSCRIPTION SUB-E01, DESCRIBED_AS DSC-STC, AT_MERCHANT; CHG-E01R CHARGED_TO CRD-E01, REFUNDS CHG-E01, AT_MERCHANT; CHG-E02..04 CHARGED_TO **CRD-E02**, FOR_SUBSCRIPTION SUB-E02, DESCRIBED_AS DSC-STC, AT_MERCHANT; Dispute HAS_EVIDENCE COM-E01 (Card Member's own evidence), COM-E01 ASSERTS SUB-E01; DISPUTES each of CHG-E02..04 {22.99}; FILED_BY CMB-E01.

Submission `MSB-E01`: statement "The Family plan is active and in regular use. It was started with the card ending 5013 and has never been cancelled."; item usage log ("Family plan: 4 profiles, streamed on 41 days since June", asserts SUB-E02); cited `CLS-STC-SUB-V3-5`.

Expected: `not_a_dispute`, `CNR`, charges `[charge_expected(c, "not_a_dispute", 22.99, 0.0) for c in ("CHG-E02", "CHG-E03", "CHG-E04")]`, improvement_targets `[]`.
Solution ids: DSP-2026-91005, CHG-E02, SUB-E02, CRD-E02, CMB-E02, ACC-E01, SUB-E01, COM-E01, DSC-STC, CLS-STC-SUB-V3-5, CLS-AMX-CMA-5.1.
Proof: `MATCH (d:Dispute {id:'DSP-2026-91005'})-[:DISPUTES]->(c:Charge)-[:FOR_SUBSCRIPTION]->(s:Subscription)-[:SUBSCRIBED_WITH]->(card:Card)-[:CARRIED_BY]->(add:CardMember), (card)-[:ISSUED_ON]->(a:CardAccount)<-[h:HOLDS]-(add), (d)-[:HAS_EVIDENCE]->(:Communication)-[:ASSERTS]->(cancelled:Subscription) WHERE h.role = 'additional' AND s.id <> cancelled.id RETURN d, c, s, card, add, cancelled`.
Decoy: `MATCH (cr:Charge {id:'CHG-E01R'})-[:REFUNDS]->(c:Charge)-[:FOR_SUBSCRIPTION]->(s:Subscription {id:'SUB-E01'}) RETURN cr, c, s`.
CASE_NEEDS "E": Graph primary (charge → subscription → Card → Additional Card Member), router_triage primary (surface CNR claim → misunderstanding), skills primary (recurring-billing, dispute-outcomes).

### Task 5.4: End-to-end generator and coverage tests

**Files:** Modify `data/generator/gen.py`, `tests/test_cases.py`.

`gen.py` main becomes:

```python
def main() -> None:
    root = Path(__file__).resolve().parents[2]
    output = root / "data" / "generated"
    graph, docs = build_world()
    cases = build_cases(graph, random.Random(42))
    for submission in load_saved(root / "data" / "corpus" / "submissions"):
        insert_submission(graph, submission)
    graph.write(output / "graph")
    store = graph_store.load(output / "graph", output / "evidence.lbug")
    validate_cases(store, cases)
    store.close()
    write_case_outputs(output, cases, graph)
    count = build_knowledge(docs, root / "data" / "corpus" / "precedents.yaml",
                            output / "knowledge.sqlite")
    print(f"knowledge documents: {count}")
    stats(graph)
```

- [ ] **Step 1:** Add to `tests/test_cases.py`:

```python
import ontology


def test_every_label_and_edge_type_is_used(built):
    g, *_ = built
    spec = ontology.load()
    assert {n["label"] for n in g.nodes.values()} == set(spec["nodes"])
    assert {e["type"] for e in g.edges} == set(spec["edges"])


def test_five_cases_cover_verdicts_and_categories(built):
    _, cases, _, _ = built
    assert [c["code"] for c in cases] == ["A", "B", "C", "D", "E"]
    assert {c["expected"]["verdict"] for c in cases} == {
        "rejected", "accepted", "goodwill_credit", "partially_accepted", "not_a_dispute"
    }
    assert {c["expected"]["category"] for c in cases} == {"RET", "OVR", "PDD", "CNR"}
```

- [ ] **Step 2:** If a label or edge type is unused, either use it realistically in the world or **delete it from `ontology.yaml`** (spec: anything unused is cut). Record which in handoff §8.
- [ ] **Step 3:** `uv run python data/generator/gen.py` succeeds; tests PASS.
- [ ] **Step 4:** `simplify` over Stage 5 files; pytest + ruff; handoff; commit `Cases C, D, E and end-to-end generator`; push.

---

## Stage 6 — Case Notebook, tools and a read-only runtime (Medium)

### Task 6.1: `src/notebook.py`

**Files:** Create `src/notebook.py`; Test `tests/test_notebook.py`.

**Interfaces:**
- `KINDS = ("fact", "hypothesis", "policy_reading", "conflict", "ruled_out", "improvement_idea")`
- `write_entry(db_path: Path, run_id: str, author: str, kind: str, text: str, node_ids: list[str], edge_ids: list[str]) -> dict` → `{"entry_id": "NBK-<8 hex>", "seq": int, ...}`; creates the table on first use.
- `read_entries(db_path: Path, run_id: str, kinds: list[str] | None = None, author: str | None = None) -> list[dict]` ordered by `seq`.

- [ ] **Step 1: Failing test:**

```python
import pytest

import notebook


def test_write_and_read_in_order(tmp_path):
    db = tmp_path / "nb.sqlite"
    a = notebook.write_entry(db, "run-1", "graph_analyst", "fact", "Order accepted v4.", ["ORD-1"], [])
    notebook.write_entry(db, "run-2", "critic", "fact", "Other run.", ["ORD-9"], [])
    b = notebook.write_entry(db, "run-1", "policy_analyst", "conflict", "Clause 7 vs 3.4.",
                             ["CLS-1", "CLS-2"], ["E-4"])
    rows = notebook.read_entries(db, "run-1")
    assert [r["entry_id"] for r in rows] == [a["entry_id"], b["entry_id"]]
    assert rows[1]["edge_ids"] == ["E-4"]
    assert [r["kind"] for r in notebook.read_entries(db, "run-1", kinds=["conflict"])] == ["conflict"]
    assert len(notebook.read_entries(db, "run-1", author="graph_analyst")) == 1


def test_rejects_unknown_kind_and_uncited(tmp_path):
    with pytest.raises(ValueError):
        notebook.write_entry(tmp_path / "nb.sqlite", "r", "a", "gossip", "x", ["ORD-1"], [])
    with pytest.raises(ValueError):
        notebook.write_entry(tmp_path / "nb.sqlite", "r", "a", "fact", "x", [], [])
```

- [ ] **Step 2–4:** FAIL → implement (plain `sqlite3`, JSON-encoded id lists, `seq` = `COALESCE(MAX(seq),0)+1` per run inside one transaction) → PASS. Commit.

### Task 6.2: Tools

**Files:** Modify `src/tools.py`; Test `tests/test_tools.py` (rewrite fixture to new labels).

**Interfaces:**
- `Run(store, emitter, run_id, knowledge_db, notebook_db, actor="worker", visit=1, turn=0, parent_id=None)` — `as_of` removed.
- `make_tools(run) -> list[BaseTool]` in this order: `graph_schema, graph_query, graph_neighbors, graph_find, search_knowledge, notebook_write, notebook_read, memory_write, python`.
- `READ_ONLY_TOOLS = frozenset({"graph_schema", "graph_query", "graph_neighbors", "graph_find", "search_knowledge", "notebook_read"})` (used by the runtime for the adjudicator).
- Arg schemas: `NeighborsArgs(id, rel_types=None, direction="both")`; `FindArgs(text, labels: list[str] | None = None)`; `KnowledgeArgs(query, kinds=["policy","precedent","memory_note"])`; `NotebookWriteArgs(kind: Literal[*KINDS], text, node_ids: list[str] = [], edge_ids: list[str] = [])`; `NotebookReadArgs(kinds: list[...] | None = None, author: str | None = None)`; `MemoryArgs` unchanged except `sources` may be graph ids or `CLS-`/`PRC-` ids.
- `notebook_write` verifies every cited node id with `run.store.node(id)` and every edge id with `MATCH ()-[r]->() WHERE r.id IN $ids RETURN r.id` before writing; unknown ids → `ValueError` returned to the agent as text. Emits a `notebook_write` event (payload: the entry; `node_ids`/`edge_ids` = its citations).
- `memory_write` calls `retrieval.add_note` / `retrieval.set_status`; emits `memory_write`.
- Delete `graph_write_finding`, `EdgeSpec`, `FindingArgs`, `_search_notes`.

- [ ] **Step 1:** Rewrite `tests/test_tools.py`: fixture graph with a Card Member, Card, Merchant, Order, Charge, a PolicyDocument with a "final sale" clause; knowledge built from that clause. Tests: tool names/order; `graph_find("final sale")` returns the clause id in `node_ids`; `notebook_write` happy path emits `notebook_write` with the cited ids and `notebook_read` returns it; `notebook_write` with an unknown id returns `{"error": ...}` and writes nothing; `memory_write` write → found by `search_knowledge(kinds=["memory_note"])` → retract → gone; python and clipping tests kept.
- [ ] **Step 2–4:** FAIL → implement → PASS. Commit.

### Task 6.3: Runtime uses the static graph and the notebook

**Files:** Modify `src/runtime_entry.py`, `src/runtime.py`, `src/runtime_support.py`, `src/api/routers/runs.py`, `src/api/routers/graph.py`, `src/api/context.py` (only the `run_dir`/run-graph references), `tests/test_runtime.py`.

Changes:
- `RuntimePaths`: remove `run_dir`; add `notebook_db: Path = Path("data/generated/notebook.sqlite")`.
- `run_case`: `store = GraphStore(paths.source_graph)` (read-only); no copy.
- `_Runtime.case_context`: `{"dispute": self.store.node(case_id), "neighborhood": self.store.neighbors(case_id, limit=50), "schema": self.store.schema()}`.
- `_agent`: `GraphStore(self.store.db_path)`; `Run(..., notebook_db=self.notebook_db)`; read-only filter uses `READ_ONLY_TOOLS`.
- `_supervisor_input` and the adjudicator input add `"notebook": notebook.read_entries(self.notebook_db, self.run_id)`.
- `runtime_support.as_of` deleted.
- API: `_latest_completed` no longer checks `.lbug` existence; `graph.py` `_store` always opens `ctx.paths.source_graph`; the `run_id` query parameter is removed from graph endpoints.

- [ ] **Step 1:** Update `tests/test_runtime.py`: the fixture graph uses new labels (Card Member, Card, Merchant, Charge, Dispute `DSP-TEST-1`); the fake worker model's tool trace includes one `notebook_write`; assert the adjudicator input includes the notebook entry and that no file matching `*.lbug` is created under `tmp_path` besides the source graph. Keep the parallel-delegation, forced-termination and structured-boundary tests.
- [ ] **Step 2:** Implement; `uv run pytest` PASS.
- [ ] **Step 3:** `simplify` over Stage 6 files; ruff; handoff; commit `Runtime: read-only graph and Case Notebook`; push.

---

## Stage 7 — Report, prompts, skills, evaluation, label-agnostic guard (Complex)

### Task 7.1: Schemas

**Files:** Modify `src/schemas.py`; Test `tests/test_schemas_models.py`.

Replace the report section of `schemas.py` with:

```python
class Verdict(StrEnum):
    ACCEPTED = "accepted"
    PARTIALLY_ACCEPTED = "partially_accepted"
    REJECTED = "rejected"
    GOODWILL_CREDIT = "goodwill_credit"
    NOT_A_DISPUTE = "not_a_dispute"
    FRAUD_REFERRAL = "fraud_referral"


class DisputeCategory(StrEnum):
    NKN = "NKN"
    RET = "RET"
    CNC = "CNC"
    CNR = "CNR"
    DMG = "DMG"
    DSS = "DSS"
    DUP = "DUP"
    NRC = "NRC"
    OVR = "OVR"
    PDD = "PDD"


_NO_CREDIT = {Verdict.REJECTED, Verdict.NOT_A_DISPUTE, Verdict.FRAUD_REFERRAL}
_CREDIT = {Verdict.ACCEPTED, Verdict.PARTIALLY_ACCEPTED, Verdict.GOODWILL_CREDIT}


class EvidenceLink(SchemaModel):
    claim: str
    node_ids: list[str]
    edge_ids: list[str]
    source_excerpt: str | None


class ChargeDecision(SchemaModel):
    charge_id: str
    verdict: Verdict
    category: DisputeCategory
    disputed_amount: Money
    credit_amount: Money
    card_member_liability: Money
    rationale: str
    evidence: list[EvidenceLink]


class HypothesisAssessment(SchemaModel):
    hypothesis: str
    status: Literal["accepted", "rejected"]
    why: str
    evidence: list[EvidenceLink]


class Citation(SchemaModel):
    document_id: str   # a clause (CLS-…), policy document (POL-…) or precedent (PRC-…) id
    why: str


class SystemImprovement(SchemaModel):
    target: Literal["amex_policy", "merchant_policy", "process", "product", "data"]
    issue: str
    suggestion: str
    evidence: list[EvidenceLink]


class CaseReport(SchemaModel):
    case_id: str
    verdict: Verdict
    category: DisputeCategory
    headline: str
    executive_summary: str
    detailed_reasoning: str
    charges: list[ChargeDecision]
    hypotheses: list[HypothesisAssessment]
    decoys_ruled_out: list[str]
    policy_basis: list[Citation]
    system_improvements: list[SystemImprovement]
    confidence: float = Field(ge=0, le=1)
    flip_fact: str
    card_member_letter: str

    @model_validator(mode="after")
    def validate_evidence_and_amounts(self) -> CaseReport:
        for charge in self.charges:
            if not charge.evidence:
                raise ValueError(f"charge {charge.charge_id} requires evidence")
            if charge.credit_amount + charge.card_member_liability != charge.disputed_amount:
                raise ValueError(
                    f"charge {charge.charge_id}: credit_amount + card_member_liability must "
                    "equal disputed_amount"
                )
            if charge.verdict in _NO_CREDIT and charge.credit_amount:
                raise ValueError(f"charge {charge.charge_id}: {charge.verdict} gives no credit")
            if charge.verdict in _CREDIT and not charge.credit_amount:
                raise ValueError(f"charge {charge.charge_id}: {charge.verdict} needs a credit")
        for item in (*self.hypotheses, *self.system_improvements):
            if not item.evidence:
                raise ValueError(f"{type(item).__name__} requires evidence")
        return self
```

Delete `TransactionDecision`, `AccountAction`, the `AliasChoices` shims on `Citation`/`AccountAction` (no legacy). Update `_CATALOG_ROLES` to the Task 7.2 role ids.

- [ ] **Steps:** tests for each validator branch (credit on rejected fails; goodwill with 0 fails; reconcile fails; improvement without evidence fails; valid report with empty `system_improvements` passes) → implement → PASS → commit.

### Task 7.2: `config/agents.yaml`

**Files:** Replace `config/agents.yaml`; Test `tests/test_runtime.py` config load still passes.

```yaml
roles:
  - id: graph_analyst
    description: Explores the evidence graph from the Dispute and separates the path that decides it from look-alikes.
    prompt: Read graph_schema descriptions first, then explore outward from the Dispute. Follow who holds which Card, which Card was used for what, and which records connect the charge to its order, booking, subscription or invoice. Test at least one plausible look-alike and say what separates it. Record facts and ruled-out paths in the Case Notebook with the ids that prove them.
    default_skills: [graph-investigation, case-notebook]
  - id: payments_analyst
    description: Reconciles charges, credits, other-means payments, installments, Offers and what was agreed.
    prompt: Reconcile every disputed charge against what the Card Member agreed to pay, any credits, any payments made by other means and any Offer or discount, using python for arithmetic. Record each reconciliation in the Case Notebook.
    default_skills: [graph-investigation, payments-and-credits, offers-and-benefits, case-notebook]
  - id: evidence_analyst
    description: Reads what the Merchant and the Card Member submitted and tests each claim against the graph.
    prompt: Read every Merchant Submission, evidence item and message on the Dispute. For each claim they make, find the graph record it is about and say whether the record supports or contradicts it. Record the result in the Case Notebook.
    default_skills: [graph-investigation, recurring-billing, case-notebook]
  - id: policy_analyst
    description: Finds the Amex Policies and Merchant Policies that govern the charge and compares their clauses.
    prompt: Find the exact Merchant Policy version the Card Member accepted for this purchase and the Amex Policies that bind the Merchant, the account, the Offer or the program. Search clause text with search_knowledge and confirm applicability in the graph. Quote the clauses that decide the Dispute, and record any ambiguity or conflict between clauses in the Case Notebook as a conflict entry.
    default_skills: [policy-analysis, offers-and-benefits, case-notebook]
  - id: memory_keeper
    description: Keeps durable, source-cited Memory Notes and retires stale ones.
    prompt: Review this run's Case Notebook and report. Write only reusable lessons as Memory Notes citing their sources; supersede or retract notes that this run contradicts.
    default_skills: [memory-hygiene]
  - id: critic
    description: Challenges the leading explanation before a decision.
    prompt: Act as devil's advocate. Read the Case Notebook, find the weakest step in the leading explanation, test an alternative reading of the graph or of a clause, and record what you find in the Case Notebook.
    default_skills: [graph-investigation, policy-analysis, case-notebook]
  - id: adjudicator
    description: Writes the final evidence-cited CaseReport after re-checking the record.
    prompt: Read the Case Notebook, re-check every cited record and clause, then write the CaseReport. Choose the Dispute Category from the Amex Dispute Guide and a verdict per charge following the dispute-outcomes skill. Reconcile amounts, explain look-alikes, and list System Improvements only where a policy, process or data gap caused or prolonged the Dispute; leave the list empty when the policies were clear and followed. Keep the Card Member letter consistent with the verdict.
    default_skills: [dispute-categories, dispute-outcomes, policy-analysis, graph-investigation]

prompts:
  triage: Inspect the Dispute, its first-hop graph neighbourhood and the graph schema. Give the case a short free-text type label (the Amex categories NKN, RET, CNC, CNR, DMG, DSS, DUP, NRC, OVR, PDD are a useful vocabulary), propose competing hypotheses including a misunderstanding and an Amex-side issue where plausible, and create an evidence-seeking plan. The plan is a starting point for the supervisor, not a restriction.
  supervisor: Review the plan, investigation summary, latest findings and the Case Notebook. Delegate focused tasks or decide that investigation is complete. Close, add, drop or waive plan items only with a grounded reason and evidence references.

runtime:
  max_turns: 8
  no_progress_turns: 2
  max_parallel_tasks: 4
```

### Task 7.3: Skills (rewritten; no label or edge names)

**Files:** Replace `skills/graph-investigation/SKILL.md`, `skills/memory-hygiene/SKILL.md`; create `skills/{case-notebook,dispute-categories,policy-analysis,offers-and-benefits,payments-and-credits,recurring-billing,dispute-outcomes}/SKILL.md`.

Write each with front matter `name`, `description` (one line, when to load) and 5–8 numbered or bulleted lines. Required content:

- **graph-investigation:** start with `graph_schema` and read the descriptions to learn how *this* graph represents people, cards, purchases, terms and evidence; anchor on the Dispute; expand with `graph_neighbors`, ask multi-hop questions with `graph_query`, locate records by text with `graph_find`; never match people by name alone (namesakes) — match by the records that connect them; a record that looks similar is only relevant if a path connects it to this Dispute; count how common a pivot is before calling it meaningful; cite only ids seen in tool results; use `python` for arithmetic.
- **case-notebook:** write an entry whenever you establish a fact, read a clause, find a conflict or rule something out; one idea per entry; cite every id; kinds and when to use each; read the notebook before starting so you do not repeat work; the notebook is the shared record of this run, not memory.
- **dispute-categories:** the ten codes with one-line meanings and typical evidence (spec §3.2); choose by what the Card Member alleges, not by the outcome; Dispute ≠ fraud: NKN is not fraud; if the Card Member denies taking part, the verdict is `fraud_referral`; confirm the code's meaning with `search_knowledge` in the Amex Dispute Guide.
- **policy-analysis:** a Merchant Policy is evidence, not an override; find the version the Card Member accepted for this purchase through the graph, not the Merchant's current website; find the Amex Policies that bind the Merchant, account, Offer or program; check disclosure and acceptance; compare clauses: when a Merchant condition contradicts Amex terms the Merchant agreed to, or terms are ambiguous, the reading against the drafter wins; quote clause ids; a clear, disclosed, accepted clause decides the Dispute even if the Card Member did not read it; record ambiguity or conflict as a notebook `conflict` and an `improvement_idea`.
- **offers-and-benefits:** separate Amex-funded Offers and benefits from Merchant-funded discounts; an Amex Offer applies only to the Card it was added to; compare the Card the Offer or benefit was attached to with the Card used for booking and for payment — they can differ; a missing Amex-funded credit is not a Merchant error; a Merchant bound by an Amex program must honour its terms.
- **payments-and-credits:** reconcile what was agreed, charged, credited and paid by other means; match credits and payments through the order, invoice or installment they belong to, not by amount alone; payments to an affiliated business may belong to a different bill; only the amount beyond what was due is recoverable; compute with `python`; credit + Card Member liability = disputed amount per charge.
- **recurring-billing:** identify the exact plan or subscription each recurring charge bills for and the Card it bills to; a cancellation confirmation proves only the plan it names; check who holds the Card a subscription uses (an Additional Card Member's charges bill to the Basic Card Member's account and are authorized); resolve statement descriptors to the Merchant; check recurring disclosure clauses.
- **dispute-outcomes:** the six verdicts and when each applies (spec §3.1 items 6–7); who funds (accepted/partial → Merchant; goodwill → Amex, only under a written goodwill clause whose conditions you verified in the graph); per-charge decisions; System Improvements: record target, issue, suggestion and evidence only when a gap exists, otherwise leave the list empty; the Card Member letter explains what was found in plain words.
- **memory-hygiene:** as before, but notes live in the knowledge store (`search_knowledge` kind `memory_note`, `memory_write`); cite graph ids or clause ids; never store details of one Card Member.

### Task 7.4: Label-agnostic guard

**Files:** Create `tests/test_label_agnostic.py`.

```python
"""Prompts, skills and runtime code must not depend on how the graph is modelled (spec D9)."""

import re
from pathlib import Path

import ontology

SCANNED = [*Path("src").rglob("*.py"), *Path("skills").rglob("*.md"), *Path("config").glob("*.yaml")]
EXEMPT = {Path("src/graph_store.py")}


def _names() -> list[str]:
    spec = ontology.load()
    labels = [label for label in spec["nodes"] if re.search(r"[a-z][A-Z]", label)]
    return labels + [f"(:{label}" for label in spec["nodes"]] + list(spec["edges"])


def test_no_label_or_edge_names_outside_the_ontology():
    hits = [
        f"{path}: {name}"
        for path in SCANNED
        if path not in EXEMPT
        for name in _names()
        if re.search(rf"(?<![A-Za-z_]){re.escape(name)}(?![A-Za-z_])", path.read_text())
    ]
    assert hits == []
```

(CamelCase labels such as `CardMember` and every `(:Label` pattern and edge type are banned; single English words like "Charge" are allowed in prose.)

### Task 7.5: Evaluation scoring

**Files:** Modify `src/evaluation.py`; Test `tests/test_evaluation.py`.

`score()` becomes: `verdict_ok`, `category_ok`, per-charge `{verdict, credit}` keyed by `charge_id`, `amounts_ok`, `improvements = {"required": [...], "reported": [targets], "ok": all(any(t in reported for t in _alternatives(req)) ...)}` where `_alternatives("process") = {"process", "merchant_policy"}` and every other target maps to itself, `solution_coverage`, `grounding` (unchanged), `capability_signals`, `confidence`. Remove `account_actions` and `missing_evidence_handled`. `passed = verdict_ok and category_ok and amounts_ok and improvements["ok"]`. The summary table swaps "missing ev." for "category" and "improvements" columns. `_trajectory_ids` also collects ids from `notebook_write` events.

- [ ] **Steps (7.1–7.5):** tests first per task, implement, `uv run pytest` PASS, `simplify` over Stage 7 files, ruff, handoff, commit `Report, prompts, skills and evaluation for Amex disputes`, push.

---

## Stage 8 — Merchant agent extension, not wired (Medium)

**Files:** Create `src/extensions/merchant_agent/agent.py`, `src/extensions/merchant_agent/store.py`, `data/merchant_records/MER-HGF/{orders.json,checkout-terms-v4.md}` (a small realistic sample for tests and future wiring); Test `tests/test_merchant_agent.py`; Modify `README.md`.

**Interfaces:**
- `store.save_submission(submission: MerchantSubmission, out_dir: Path = Path("data/corpus/submissions")) -> Path` writes `<dispute_id>.json`.
- `agent.record_tools(records_dir: Path) -> list[BaseTool]`: `list_records()` (file names under the Merchant's folder) and `read_record(name)` (text, clipped), both read-only and path-confined.
- `agent.respond(request: MerchantEvidenceRequest, records_root: Path, model, agent_builder=create_deep_agent) -> MerchantSubmission`: builds a Deep Agent with `record_tools(records_root / request.merchant_id)`, a system prompt "You are the Merchant's disputes desk. Answer each ask only from your own records; cite the ids the records mention; say plainly when you have no record.", `response_format=provider_strategy(MerchantSubmission)`, and returns `invoke_structured(agent, MerchantSubmission, [HumanMessage(request.model_dump_json())])`.

- [ ] **Step 1: Failing test** with the `StructuredModel` fake from `tests/test_runtime.py` (move it to `tests/conftest.py` so both use it): the fake returns a `MerchantSubmission`; `respond` returns it; `save_submission` then `submissions.load_saved` round-trips; `read_record("../../etc/passwd")` returns an error.
- [ ] **Step 2: Guard test:** `rg`-style assertion that no file in `src/` outside `src/extensions/` imports `extensions`, and `config/` never mentions `merchant_agent`.
- [ ] **Step 3:** Implement → PASS.
- [ ] **Step 4:** README section **"Merchant agent (built, not wired)"**: what it does; that every showcase Merchant Submission is already in the graph; how to try it (`respond(...)` → `save_submission(...)` → `uv run python data/generator/gen.py` rebuilds the static graph with the new submission); how to wire it later (add a `request_merchant_evidence` tool that calls `respond` and a rebuild step, or ingest submissions into the Case Notebook), stating it is intentionally not connected.
- [ ] **Step 5:** `simplify`; pytest + ruff; handoff; commit `Merchant agent extension (not wired)`; push.

---

## Stage 9 — API, showcase and schemas (Medium)

**Files:** Modify `src/api/routers/graph.py`, `src/api/models.py`, `src/showcase.py`, `src/cli.py`, `src/domain/events.py` (event-type list: `graph_write` → `notebook_write`), `schemas/openapi.json`, `schemas/trajectory-event.schema.json`; Tests `tests/test_api.py`, `tests/test_showcase.py` (new).

- `GET /graph/ontology` → `{"groups": {id: {title, description}}, "labels": {label: {group, description}}, "edges": {type: {description}}}` from `GraphStore.ontology`.
- `CaseSummary` fields: `case_id, title, claim, amount, summary, latest_run_id, latest_verdict`.
- `showcase.export`: graph JSONL, ontology, catalog, knowledge, ground truth, eval, per-run events only (delete `_added_to_graph`, `_apply`, run-graph handling). `install` mirrors it. The notebook is reconstructed by the frontend from `notebook_write` events, so it is not exported separately.
- `cli.py`: `run`, `eval`, `showcase-export`, `showcase-install`, `replay`, `export-event-schema` keep working; remove anything referencing run graphs.
- Regenerate `schemas/openapi.json` (`uv run python -c "import json; from api.app import app; print(json.dumps(app.openapi(), indent=2))" > schemas/openapi.json`) and the event schema via `uv run inspect export-event-schema`.
- [ ] Tests: `/graph/ontology` returns every label with a group; `/graph/nodes?ids=` works without `run_id`; `/cases` has `claim` and no category; showcase export→install round-trip in `tmp_path` restores events and graph.
- [ ] `simplify`; pytest + ruff; handoff; commit `API and showcase for the static graph`; push.

---

## Stage 10 — Frontend (Medium)

**Files:** Modify `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/run/graphModel.ts`, `frontend/src/run/store.ts`, `frontend/src/run/useRunEvents.ts`, `frontend/src/run/Conclusion.tsx`, `frontend/src/run/format.ts`, `frontend/src/run/fixtures.ts`, `frontend/src/run/EvidenceGraph.tsx`/`evidenceLayout.ts` (regions), `frontend/src/pages/RunPage.tsx` (tabs), `frontend/src/pages/CasesPage.tsx` (`claim`); Create `frontend/src/run/Notebook.tsx`, `frontend/src/run/Notebook.test.tsx`; update existing tests.

- **Types:** `Verdict` six values; `DisputeCategory` ten codes; `ChargeDecision {charge_id, verdict, category, disputed_amount, credit_amount, card_member_liability, rationale, evidence}`; `SystemImprovement {target, issue, suggestion, evidence}`; `CaseReport` per spec §8.
- **graphModel.ts:** delete the `LABELS` table and `isAgentWritten`. Fetch `/graph/ontology` once (client `getOntology()`), build `regions = Object.entries(groups)` in YAML order, `labelStyle(label)` = region from `labels[label].group`, colour from a fixed 12-colour palette indexed by the label's position within its group (group hue families: parties blue, commerce amber, terms green, case rose), icon from a small map keyed by **group** (`parties: person`, `commerce: swap`, `terms: scroll`, `case: flag`). Unknown labels fall back to the last group.
- **store.ts / useRunEvents.ts:** event types swap `graph_write` → `notebook_write`; `GRAPH_TYPES = new Set(['tool_result', 'notebook_write'])`; the store keeps `notebook: NotebookEntry[]` appended from `notebook_write` payloads (`entry_id, seq, author, kind, text, node_ids, edge_ids`).
- **Notebook tab:** third tab beside "Agent flow" and "Evidence graph": entries in `seq` order, grouped visually by author, with kind badge and clickable id chips that switch to the Evidence graph and highlight those ids (reuse the Conclusion chip handler).
- **Conclusion:** header shows verdict label (six), category code + name; per-charge table columns Charge · Category · Verdict · Disputed · Credit · Card Member liability; new **System Improvements** block (target badge, issue, suggestion, evidence chips; "None — the policies were clear and followed." when empty); letter titled "Letter to the Card Member"; remove network action, reason code, missing evidence, account actions.
- [ ] Tests (Vitest): graphModel builds regions from an ontology fixture; Notebook renders entries and chip click calls the highlight handler; Conclusion renders goodwill verdict, category and an empty-improvements message; store accumulates notebook entries. Update Playwright `e2e/run-page.spec.ts` fixtures to the new report shape.
- [ ] `cd frontend && npx tsc -b && npx vitest run && npm run build && npm run e2e` pass. `simplify` over changed frontend files. Handoff; commit `Frontend: ontology-driven graph, Case Notebook, Amex report`; push.

---

## Stage 11 — Real-LLM evaluation and tuning (Complex)

- [ ] `uv run python data/generator/gen.py`; `uv run inspect eval --k 1` over A–E (needs `.env` `OPENAI_API_KEY`). Record `summary.md` in handoff §8.
- [ ] Target: pass@1 5/5 (verdict, category, amounts, required improvement targets). For each failure, read the trajectory (`uv run inspect replay <run_id>`), identify whether the agent lacked **knowledge** (fix a skill or policy clause wording), **reachability** (fix an ontology description or add a background look-alike that makes the true path distinct) or **judgement** (fix a role prompt). Never add per-case logic, hints naming case ids, or answer-revealing edges.
- [ ] Re-run the failing cases, then all five once more. Then pass@3 if budget allows.
- [ ] `simplify` over files changed; pytest + ruff; handoff with scores; commit `Tune skills and prompts from evaluation`; push.

## Stage 12 — Final cleanup, showcase, README (Simple)

- [ ] `rg -n "visa|Visa|cardholder|issuer|acquirer|Reg E|Reg Z|as_of|valid_from|Finding|graph_write|copy_store|run_dir" src tests skills config frontend/src data/generator README.md` → only intentional hits (e.g. research docs are exempt).
- [ ] Run the app (`./dev.sh`), run each case once from the UI, `uv run inspect showcase-export`, re-shoot `asset/agent_graph.png`, `asset/evidence_node.png` and add `asset/notebook.png`.
- [ ] Rewrite `README.md` for Amex: objective (closed-loop Amex disputes), what you see (three tabs + conclusion with System Improvements), architecture (framework unchanged; static graph; Case Notebook; policy clauses in graph and search), the five cases table (title, category, what it shows — no answers), ontology-as-data ("change the graph by editing `ontology.yaml`"), Merchant agent (built, not wired), commands.
- [ ] Final `simplify` over the whole branch diff (`git diff main...HEAD --stat` to list files). pytest, ruff, frontend checks. Handoff: mark complete. Commit `Final cleanup and showcase`; push. Report to the user; do not merge.

---

## Self-review notes

- Spec coverage: D1–D3 (Stages 0, 2, 7), D4 (1, 6, 9), D5 (6), D6 (2, 6), D7 (3), D8 (2), D9 (1, 7.4, 10), D10 (7.1), D11 (7.1–7.3), D12 (0–2, 6), D13–D14 (4.1, 8), D15 (0), D16 (all; no runtime graph changes), D17 (every stage's last step).
- Type names used across tasks: `PolicyDoc`, `Clause` (policies.py); `MerchantSubmission`, `SubmittedItem`, `SubmittedMessage`, `MerchantEvidenceRequest`, `EvidenceAsk`; `insert_submission`, `load_saved`, `save_submission`, `respond`; `write_entry`, `read_entries`, `KINDS`; `READ_ONLY_TOOLS`; `ChargeDecision`, `SystemImprovement`, `DisputeCategory`, `Verdict`; `charge_expected(charge_id, verdict, disputed, credit)`.
