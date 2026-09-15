# Dispute Observatory technical implementation guide

This document explains the implemented agentic framework for a developer new to this repository. It
covers the runtime, routing, playbooks, tools, data access, memory, graph analysis, model adapters,
governance, actions, trajectory events, checkpointing, and the FastAPI adapter. The runtime-facing
data model is included; frontend behavior, evaluator internals, data-generation internals, and
domain research are out of scope.

The central design is:

```text
case data + configuration
        |
        v
route-independent LangGraph runtime
        |
        +--> route playbook hooks
        +--> audited data/tools and sandbox computations
        +--> optional Deep Agents subagents and LangGraph fan-out
        +--> deterministic verification and governance
        +--> persisted decision and bounded actions
        |
        v
append-only, redacted, hash-chained trajectory in SQLite
```

The LLM creates bounded plans and performs isolated specialist tasks. It is not given direct access
to the scenario database, memory stores, action writer, or hidden fixtures. Those capabilities are
exposed through explicit Python boundaries.

## 1. Repository map

Application Python is flat under `src/`, so imports use names such as `runtime`, `playbooks`,
`domain`, and `memory` directly.

| Path | Responsibility |
|---|---|
| `src/runtime/langgraph_runtime.py` | Builds and drives the route-independent graph. |
| `src/runtime/context.py` | Per-run dependency container and Deep Agents delegation helper. |
| `src/runtime/gateway_chat_model.py` | LangChain-compatible wrapper around the model port. |
| `src/runtime/subagents.py` | Instruments Deep Agents `task` delegations. |
| `src/playbooks/` | One route-specific module per configured route. |
| `src/routing.py` | Deterministic first-match route selection. |
| `src/tools/` | Tool input schemas and the audited tool executor. |
| `src/data/access.py` | Read-only operational SQLite queries, virtual-time filtering, and one reused connection per run/segment. |
| `src/storage.py` | Shared read-only SQLite connection helper used by runtime-adjacent readers and the API. |
| `src/domain/events.py` | Canonical event models, SQLite-row conversion, and hash-chain verification. |
| `src/memory/retrieval.py` | FTS5 + sqlite-vec policy/precedent/research retrieval. |
| `src/memory/notes.py` | Durable lead notes and their lifecycle gate. |
| `src/memory/graph.py` | Graph queries and bounded hypothesis writes. |
| `src/memory/curator.py` | Shared offline/in-case memory curation rules. |
| `src/sandbox.py` | Deterministic arithmetic and date helpers. |
| `src/governance.py` | Review-panel triggers, scoring, defaults, and fairness checks. |
| `src/actions.py` | Allow-listed action execution and persistence. |
| `src/observability/` | Event emission, model instrumentation, and redaction. |
| `src/adapters/` | Fake and OpenAI model providers. |
| `src/api/` | FastAPI projections over committed data plus isolated run-control endpoints. |
| `src/api/run_manager.py` | Isolated API run stores, durable run registry, background case/queue runs. |
| `src/api/sse.py` | Polling-based reconnectable SSE event stream. |
| `config/` | Model, route, scenario, and agent configuration. |
| `skills/` | Route-loaded Markdown instruction files. |

The runtime is created in `src/bootstrap.py`:

```python
def build_runtime(
    root: Path,
    *,
    adapter: Literal["fake", "openai"] = "fake",
    sqlite_path: Path | None = None,
) -> LangGraphRuntime:
    models = load_models_config(root / "config/models.yaml")
    routes = load_routes_config(root / "config/routes.yaml")
    scenario = load_scenario(root / "config/scenarios/hero.yaml", root)
    return build_runtime_from_config(
        root,
        models=models,
        routes=routes,
        scenario=scenario,
        adapter=adapter,
        sqlite_path=sqlite_path,
    )

def build_runtime_from_config(
    root: Path,
    *,
    models: ModelsConfig,
    routes: RoutesConfig,
    scenario: ScenarioConfig,
    adapter: Literal["fake", "openai"] = "fake",
    sqlite_path: Path | None = None,
) -> LangGraphRuntime:
    if sqlite_path is not None:
        scenario = scenario.model_copy(update={"sqlite_path": sqlite_path.resolve()})
    gateway = (
        OpenAIResponsesGateway(models)
        if adapter == "openai"
        else FakeModelGateway()
    )
    return LangGraphRuntime(
        root=root, models=models, routes=routes, scenario=scenario, gateway=gateway
    )
```

`build_runtime` parses YAML for direct CLI-style use. API-managed runs load the three configs once
and call `build_runtime_from_config`, avoiding repeated YAML parsing. `copy_scenario_store` copies
the pristine SQLite scenario store (and its optional `.lbug` graph file) before an isolated run; the
runtime receives the selected path and does not need to know whether it is pristine or isolated.

## 1.1 Data model from zero

This section explains the data before explaining the agents. A new investigator should think of a
run as answering one question about one `case_id`:

> What happened, what amount is actually disputed, which rule or route applies, what evidence is
> available as of the current time, and what bounded outcome can be recorded?

The project models a fictional bank that issues Visa credit and debit cards. The bank is the
**issuer**. A customer uses an account and card to make a transaction at a merchant. The merchant
uses an **acquirer** to send the transaction through the card **network**. If the customer reports a
problem, the issuer opens a dispute case. The agent investigates that case for the issuer.

The important words are:

| Term | Meaning in this project |
|---|---|
| Customer/cardholder | Person associated with the account or card. `customer_id` identifies them. |
| Account | Bank relationship that holds the card activity. Credit accounts use `REG_Z`; debit/checking accounts use `REG_E`. |
| Card | Payment credential issued on an account. `card_id` links the card to transactions and disputes. |
| Merchant | Card acceptor where the transaction was made. `merchant_id` is the stable join key; the statement `descriptor` may change. |
| Issuer | Lanternfield Bank in the scenario. It receives the claim, investigates, credits the cardholder, and may file a network dispute. |
| Acquirer | Merchant-side payment institution. `acquirer_id` is relevant to merchant identity and network tests. |
| Network | Visa in the generated hero data. `network_condition` is the condition considered for a network filing, such as `13.1` or `10.4`. |
| Dispute case | The complete investigation container. `case_id` has the form `DSP-YYYY-#####`. |
| Claim family | Internal description of the customer's problem, such as `fraud_cnp`, `not_received`, or `duplicate`. |
| Evidence packet | Semi-structured merchant/provider response, stored as JSON and linked to a case and transaction. |
| Event | Append-only fact about something that happened, such as intake, a credit, a request, or a case state change. |
| As-of time | The run's virtual current time. A record whose `available_at` is later than this time must not be visible yet. |

### The storage layers the agent can see

The generated data starts as files under `data/generated/`, but the runtime normally reads the
single SQLite file `data/generated/disputes.sqlite`. `data/generator/load_sqlite.py` imports the
structured tables and selected event/document files into SQLite. The runtime then opens that file
read-only through `CaseDataAccess`.

~~~python
# data/generator/load_sqlite.py: the operational SQLite store is assembled from files.
for path in sorted(glob.glob(os.path.join(GEN, "structured", "*.csv"))):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    name = os.path.splitext(os.path.basename(path))[0]
    _table_from_rows(con, name, rows[0], rows[1:])

# Evidence JSON is indexed by its identity and retained as JSON text.
_table_from_rows(
    con,
    "evidence_packet_documents",
    ["packet_id", "case_id", "txn_id", "available_at", "json"],
    [[p["packet_id"], p["case_id"], p["txn_id"], p["available_at"], json.dumps(p)] for p in packets],
)
~~~

The agent-visible tables are operational inputs and run data. The evaluator-only
`data/generated/ground_truth/` directory and simulation personas are deliberately not loaded into
this store and are blocked by the path guard. This distinction matters: an agent may use a
merchant's `merchant_statement` as a claim to assess, but it must not read a hidden expected answer.

The main data modalities are:

| Modality | Examples | Why it exists |
|---|---|---|
| Relational rows | `customers`, `accounts`, `transactions`, `disputes` | Exact joins, filtering, and amount/date calculations. |
| Append-only events | `account_events`, `dispute_events` | Order and timing matter; a sequence such as login → password reset → purchase can be evidence. |
| Semi-structured JSON | `evidence_packet_documents.json` | Merchants provide different evidence blocks for different claim types. |
| Text documents | communications, research, policies, precedents | The agent must read narratives and retrieve applicable text. |
| Agent memory | `agent_memory_notes` and seeded traces | Prior beliefs may be useful, stale, wrong, or prohibited and therefore require lifecycle checks. |

### The ID chain: how records are linked

The data is joined with IDs, not with display names. The core path is:

~~~text
customer_id
    |
    +--> account_id --> card_id --> txn_id --> merchant_id
    |                      |          |
    |                      |          +--> related_txn_id (refund/fee/adjustment link)
    |                      |
    |                      +--> token_id --> device_id
    |
    +--> account events, communications, prior disputes

case_id --> dispute_transactions --> txn_id
    |
    +--> dispute_events
    +--> communications
    +--> evidence_packets --> packet JSON
    +--> related_case_ids

merchant_id --> merchant_descriptors, merchant research, merchant evidence
customer/account/card/merchant/transaction/case IDs --> facts --> decision --> actions
~~~

The identifiers have deliberately different prefixes so a row can be recognized quickly:

| Prefix/field | Entity | Example | What it links |
|---|---|---|---|
| `CUS-` / `customer_id` | Customer | `CUS-90004` | Accounts, cards, disputes, communications, account events. |
| `ACC-CR-` or `ACC-DDA-` / `account_id` | Credit or deposit account | `ACC-CR-90004` | Cards, transactions, statements, disputes. `CR` is credit; `DDA` is deposit/checking. |
| `CRD-` / `card_id` | Card | `CRD-90004` | Transactions and the dispute intake. |
| `TXN-` / `txn_id` | A transaction or adjustment row | `TXN-9000402` | Case membership, merchant, authorization, refunds/fees through `related_txn_id`. |
| `MER-` / `merchant_id` | Merchant/card acceptor | `MER-90004` | Transactions, descriptor history, evidence, research. |
| `DSP-` / `case_id` | Dispute case | `DSP-2026-90005` | Dispute-to-transaction join rows, communications, evidence, events. |
| `MEP-` / `packet_id` | Merchant evidence packet | `MEP-90004-OI` | The JSON response indexed by `evidence_packet_documents`. |
| `EVT-` or `DEV-EVT-` / `event_id` | Account or dispute event | `DEV-EVT-0000009` | The customer/account or case timeline. |
| `MEM-` / `note_id` | Durable memory note | `MEM-0142` | Subject IDs and source references used to validate the belief. |
| `WEB-`, `PRE-`, policy IDs | Knowledge documents | `PRE-0019` | Retrieved research, precedents, and policy citations. |

Do not infer a relationship from a similar `dba_name`, descriptor, customer name, or amount. For
example, `GIFTLANE CARDS` appears for more than one customer; the relationship is proved by the
transaction's `merchant_id`, not by the text displayed on a statement.

### Core relational tables and field meanings

These are the fields that the agent and playbooks use most often. All imported SQLite values are
stored as text by the loader, so calculations convert monetary values to `Decimal` and dates to
date/datetime objects at the boundary.

#### Customer, account, card, and merchant identity

| Table | Field | Meaning |
|---|---|---|
| `customers` | `customer_id` | Stable person identifier. |
|  | `home_address_id`, `work_address_id` | Foreign keys to `addresses`; useful for address comparison, not as a standalone liability decision. |
|  | `phone`, `alt_phone` | Contact data. A shared alternate phone can become a graph signal, but is not by itself proof. |
|  | `segment`, `preferred_contact` | Service context and communication preference. |
| `accounts` | `account_id` | Stable bank account identifier. |
|  | `primary_customer_id` | Customer who owns the account. Authorized users are represented separately. |
|  | `product` | Credit card or debit checking product. |
|  | `regime` | `REG_Z` for credit or `REG_E` for debit; controls which clock and resolution rules are used. |
|  | `payment_behavior` | Credit-account behavior such as `pay_in_full`, `partial`, or `minimum`; used by the implemented billing-rights logic. |
|  | `statement_cycle_day` | Day the account's billing cycle closes. |
|  | `first_deposit_date` | Debit-account date used by the new-account logic. |
| `account_holders` | `role`, `added_at`, `removed_at` | Whether a customer is primary or authorized, and during which period. |
| `cards` | `account_id`, `customer_id`, `role` | Connects a card to its account and cardholder; `role` can distinguish an authorized user. |
|  | `status`, `issued_at`, `closed_at`, `replaced_card_id` | Card lifecycle. |
| `tokens` | `token_id`, `requestor_type`, `device_id` | Network-token identity and provisioning context, including device wallets and agentic providers. |
| `merchants` | `merchant_id` | Stable card-acceptor key. One business may have multiple merchant IDs. |
|  | `dba_name`, `legal_name` | Display/legal names; the statement descriptor may differ. |
|  | `mcc`, `mcc_description` | Merchant category code and its meaning. |
|  | `channel` | Typical channel such as `in_store`, `ecommerce`, or `recurring`. |
|  | `acquirer_id`, `card_acceptor_id` | Merchant-side processing identity used in network and relationship checks. |
|  | `timezone`, `city`, `state`, `country` | Location/time interpretation for merchant-local deadlines. |
| `merchant_descriptors` | `descriptor`, `first_seen`, `last_seen` | Statement-name history. A descriptor change can explain customer confusion. |

The account/card distinction is important. A dispute's `customer_id` is the customer who made the
claim or is associated with the card row, while `accounts.primary_customer_id` identifies the
account owner. An authorized user can therefore have a different `customer_id` from the account's
primary customer.

#### Disputes, transactions, and amounts

| Table | Field | Meaning |
|---|---|---|
| `disputes` | `case_id` | Primary identifier for the investigation. |
|  | `account_id`, `customer_id`, `card_id` | Intake context; these should agree with the linked transaction unless the case is specifically testing a relationship such as household authority. |
|  | `regime` | Snapshot of the account's regulatory regime for the case. |
|  | `status` | `open` or `closed`. This is the overall case lifecycle. |
|  | `stage` | Operational stage such as `intake`, `investigating`, `awaiting_merchant_evidence`, or `dispute_filed`. |
|  | `opened_at` | Notice/intake timestamp. Regulatory and network clocks start from the appropriate case/transaction anchors, not from when the agent happens to run. |
|  | `claim_summary` | Human-readable intake narrative. It is context, not automatically verified fact. |
|  | `claim_family_initial` | Intake classification. It can be wrong or incomplete; routing and playbooks may correct it. |
|  | `network`, `network_condition` | Network and selected condition when filing is applicable. Blank `network_condition` means it has not yet been selected. |
|  | `dispute_amount` | Amount the case currently disputes. It may be a partial amount or the sum of several linked transactions. |
|  | `provisional_credit_amount`, `provisional_credit_at` | Temporary issuer credit and when it was posted. This is separate from the final outcome. |
|  | `cardholder_outcome`, `network_outcome` | Separate outcomes: the customer may be credited even if the issuer later loses a network dispute. |
|  | `related_case_ids` | Pipe-separated case IDs for linked cases; the agent resolves these into actual rows before relying on them. |
| `dispute_transactions` | `case_id`, `txn_id`, `disputed_amount` | Join table. One case can contain many transactions, and the amount disputed for a row can be less than that transaction's full amount. |
| `transactions` | `txn_id` | Primary key for a posted/authenticated transaction row. |
|  | `account_id`, `card_id`, `customer_id`, `merchant_id` | The identity chain described above. |
|  | `descriptor` | Text printed on the statement at that time; not necessarily the merchant's current name. |
|  | `txn_type` | `purchase`, `credit`, `payment`, `fee`, `account_verification`, `provisional_credit`, or another generated adjustment type. |
|  | `billing_amount`, `billing_currency` | Amount/currency shown on the account statement and normally used for the case amount. |
|  | `txn_amount`, `txn_currency`, `fx_rate` | Original transaction amount/currency and conversion rate when applicable. |
|  | `auth_amount`, `auth_id`, `auth_code` | Authorization-level identity and amount. Several clearing rows can share one authorization. |
|  | `auth_response_code` | Authorization result; `00` is approved. A decline can lack a processing date. |
|  | `auth_timestamp_utc` | Exact authorization instant in UTC. |
|  | `txn_local_datetime`, `merchant_timezone` | Merchant-local wall time and the zone needed to interpret it. |
|  | `processing_date` | Network clearing date. Visa time windows in this project commonly use this date. |
|  | `posting_date` | Date the issuer posted the row to the account; may differ from processing date. |
|  | `pos_entry_mode`, `card_present` | How credentials were captured and whether the card was physically present. |
|  | `channel` | Actual transaction context, such as `in_store`, `ecommerce`, `recurring`, or `agentic_commerce`. |
|  | `cof_type` | Stored-credential context: for example `mit_recurring` or `cit_subsequent`. |
|  | `eci`, `cavv_present`, `three_ds_status` | 3-D Secure/authentication signals. |
|  | `avs_result`, `cvv2_presence`, `cvv2_result` | Address and security-code verification results. Reference tables explain each code. |
|  | `clearing_seq`, `clearing_count` | Position and total number of clearings for one authorization. |
|  | `arn` | Acquirer reference number for the clearing record. |
|  | `related_txn_id` | Link from a refund, fee, or adjustment back to a purchase; it is often blank for real-world refunds. |
|  | `fraud_reported_at` | When issuer fraud reporting occurred. |
|  | `available_at` | When this row became visible to the issuer under virtual time. |

The three amount fields are intentionally different:

~~~text
txn_amount       = original merchant-side amount, possibly EUR
billing_amount   = amount posted to the bank account, possibly USD
disputed_amount  = portion of a transaction that this case challenges
~~~

For example, if a EUR purchase is converted to USD, the agent should not add `txn_amount` to a
USD dispute amount. It should use the implemented FX tool and compare amounts in the appropriate
currency. Likewise, a duplicate or partial-refund case can have a `disputed_amount` that is less
than `billing_amount`.

#### Evidence, communications, and events

| Table/file | Field/block | Meaning |
|---|---|---|
| `evidence_packets` | `packet_id`, `case_id`, `txn_id`, `merchant_id` | Index metadata identifying which response belongs to which case and transaction. |
|  | `source` | Origin such as `order_insight`, `dispute_response`, `pre_arbitration`, or an agentic provider record. |
|  | `requested_at` | When the issuer asked for the packet. It can be blank for a pre-existing response. |
|  | `available_at` | When the response becomes visible to the agent. Late evidence is intentionally possible. |
|  | `path` | Relative file path in the source-file view. |
| `evidence_packet_documents` | `json` | Full packet serialized as JSON. Optional blocks vary by source. |
| packet JSON | `order` | Order ID, items, authorization, total, and promised delivery. |
|  | `shipments` | Tracking events, delivered address, and optional proof of delivery. |
|  | `customer_account`, `session`, `prior_transactions` | Merchant-account and session signals used for digital fraud/identity analysis. |
|  | `refunds`, `return_policy`, `reservation`, `folio` | Claim-specific merchant records. |
|  | `merchant_statement` | The merchant's assertion. It is evidence to test, not an automatically true fact. |
| `communications` | `comm_id`, `case_id`, `customer_id`, `merchant_id` | Communication identity and relationship. |
|  | `direction`, `channel`, `party` | Who sent it and how it arrived, such as inbound cardholder chat. |
|  | `timestamp_utc`, `available_at` | When it happened and when it became visible. |
|  | `body`, `attachments` | Narrative and text descriptions of attached material. |
| `account_events` | `event_id`, `account_id`, `customer_id` | Account/security event identity. |
|  | `event_type`, `timestamp_utc` | Event kind and order in the timeline: login, password reset, phone change, token provisioning, and so on. |
|  | `device_id`, `ip`, `detail` | Technical context and event-specific JSON details. |
| `dispute_events` | `event_id`, `case_id`, `event_type`, `actor` | Case lifecycle event and actor. |
|  | `summary`, `detail.note` | Human-readable event explanation and, for notes, the investigator note. |

The common evidence blocks are not all present in every packet. Code must check for a block before
reading it:

~~~python
packet = json.loads(row["json"])
shipments = packet.get("shipments", [])
proofs = [shipment["proof_of_delivery"]
          for shipment in shipments
          if shipment.get("proof_of_delivery")]
merchant_statement = packet.get("merchant_statement", "")

# A missing block means "not provided", not "false".
has_delivery_proof = bool(proofs)
~~~

### A complete real example: `DSP-2026-90005`

This hero case is useful because the intake says “Charged twice ($64.18 x2) by Parcelwick for one
lamp.” The database represents the merchant's one authorization and its two clearing rows as
follows:

~~~text
disputes
  case_id       = DSP-2026-90005
  account_id    = ACC-CR-90004
  customer_id   = CUS-90004
  card_id       = CRD-90004
  claim_family  = duplicate
  dispute_amount= 64.18

dispute_transactions
  (DSP-2026-90005, TXN-9000402, 64.18)

transactions
  TXN-9000401: billing_amount=64.18, auth_id=AUT-90004-01, clearing_seq=1/2
  TXN-9000402: billing_amount=64.18, auth_id=AUT-90004-01, clearing_seq=2/2
  both rows: merchant_id=MER-90004, auth_amount=128.36, auth_code=A7K2Q9
  the case specifically disputes TXN-9000402 for 64.18

evidence packet MEP-90004-OI
  case_id       = DSP-2026-90005
  txn_id        = TXN-9000402
  order total   = 128.36
  quantity      = 2 lamps
  shipments     = 2, each charged at shipment and delivered
~~~

The `disputed_amount` is `64.18`, while the authorization amount and merchant order total are
`128.36`. That difference is not a typo: it is the question the duplicate-processing playbook
must resolve. The case is linked directly to only `TXN-9000402` through `dispute_transactions`;
the playbook then expands from that transaction's `auth_id` to both clearing rows. Each transaction
is linked to the merchant through `merchant_id`, and the merchant response is linked back through
the same `case_id` and `txn_id`.

The access layer performs this join rather than handing raw database access to the model:

~~~python
def get_case_transactions(self, case_id: str) -> list[dict[str, Any]]:
    return self._query(
        "transactions_for_case",
        """SELECT t.*, m.dba_name AS merchant_name FROM transactions t
           JOIN dispute_transactions dt ON dt.txn_id=t.txn_id
           LEFT JOIN merchants m ON m.merchant_id=t.merchant_id
           WHERE dt.case_id=? AND t.available_at<=?
           ORDER BY t.processing_date, t.txn_id""",
        (case_id, self.emitter.virtual_now.isoformat().replace("+00:00", "Z")),
        refs_column="txn_id",
    )
~~~

For this case, the function's conceptual output is one transaction dictionary containing
`txn_id=TXN-9000402`, `merchant_name=Parcelwick ...`, `billing_amount=64.18`, and the authorization
fields. The `JOIN` is why a case with multiple dispute rows returns multiple transactions, while
the `LEFT JOIN` lets the transaction remain usable even if merchant display metadata is missing.

The packet is then fetched separately and gated by the same as-of rule:

~~~python
def evidence_packets(self, case_id: str) -> list[dict[str, Any]]:
    return self._query(
        "available_evidence_packets",
        """SELECT packet_id, case_id, txn_id, available_at, json
           FROM evidence_packet_documents WHERE case_id=? AND available_at<=?
           ORDER BY available_at""",
        (case_id, self.emitter.virtual_now.isoformat().replace("+00:00", "Z")),
        refs_column="packet_id",
    )
~~~

With the scenario clock at `2026-10-21T13:00:00Z`, the packet's `available_at` is
`2026-10-21T16:00:00Z`, so it is not available yet. A run started after 16:00 can see it. This is
why an agent must not treat the source file's physical presence as proof that the evidence was
available at the decision time.

### What a case input and output look like

The first runtime node loads a case and its linked transactions. The `case` dictionary is the raw
row; `transactions` is the joined list. It is then enriched with route features, deadlines, tool
results, findings, and eventually a typed decision.

~~~python
def load_case(self, state: WorkflowState) -> dict[str, Any]:
    ctx = self.context_for(state["run_id"])
    case = ctx.data.get_case(state["case_id"])
    transactions = ctx.data.get_case_transactions(state["case_id"])
    return {
        "case": case,
        "transactions": transactions,
        "progress_marker": 1,
    }
~~~

Conceptually, the input/output for `DSP-2026-90005` is:

~~~text
INPUT
  case_id = DSP-2026-90005

LOAD_CASE OUTPUT
  case.case_id = DSP-2026-90005
  case.claim_family_initial = duplicate
  case.dispute_amount = "64.18"
  transactions[0].txn_id = TXN-9000402
  transactions[0].merchant_id = MER-90004
  transactions[0].clearing_count = "2"

LATER WORKFLOW OUTPUT
  route = configured duplicate/processing-error route (if its rules match)
  findings = source-linked facts and unresolved questions
  decision = DecisionRecord with cardholder resolution, network actions, clocks, citations
  actions = only allow-listed persisted actions, if governance permits them
~~~

The exact route is determined from `config/routes.yaml` and the computed features; a claim label
alone is not an instruction to the LLM. A `DecisionRecord` is not just a paragraph. Its important
fields mean:

| Decision field | Meaning |
|---|---|
| `case_id`, `regime` | Identity and legal/account regime of the decision. |
| `claim_family` | Corrected or confirmed family used in the final reasoning. |
| `network_actions` | Per-transaction filing, no-file, or follow-up actions, with condition, amount, and certification references. |
| `cardholder_resolution` | Issuer-side result: credit, reversal, liability, redirect, and amounts. |
| `deadlines` | Computed response, filing, provisional-credit, or follow-up clocks. |
| `adjudication` | Whether a review panel was used, its confidence, threshold, positions, and flip fact. |
| `wait` | Required missing evidence or cardholder response instead of premature closure. |
| `citations` | Source IDs that support the decision. |
| `memory_ops` | Bounded memory corrections/writes proposed or applied. |
| `confidence`, `explanation_for_cardholder` | Confidence and a plain-language explanation. |

The Pydantic model defines the contract:

~~~python
class DecisionRecord(BaseModel):
    case_id: str
    regime: str
    is_dispute: bool
    claim_family: str
    network_actions: list[NetworkAction]
    cardholder_resolution: CardholderResolution
    deadlines: dict[str, Any] = Field(default_factory=dict)
    adjudication: Adjudication
    citations: list[dict[str, str]] = Field(default_factory=list)
    confidence: float
    explanation_for_cardholder: str
~~~

### How the same data flows through the agent

The implementation does not send every table and every file to every model call. It progressively
passes the smallest useful result through explicit boundaries:

~~~text
1. case_id
   |
2. get_case + get_case_transactions
   |  raw case row + linked transaction rows
   |
3. route_features
   |  channels, transaction age, prior merchant dispute count, available proof flags
   |
4. deterministic route_case
   |  route ID, depth, budget, selected playbook/skills/subagents
   |
5. playbook tool calls
   |  communications, evidence, account/security events, merchant history, policy, calculations
   |
6. Workflow findings/state
   |  findings carry source refs; hypotheses remain separate from verified facts
   |
7. verify + governance
   |  schema checks, citation checks, deadline checks, fairness checks, panel/default if needed
   |
8. DecisionRecord
   |  persisted decision plus bounded actions and trajectory events
~~~

The tool boundary makes the data flow auditable. A playbook supplies a rationale and arguments,
the executor runs the approved Python function, and the event records the returned IDs. For
example, a not-received playbook asks for case communications rather than opening the database
itself:

~~~python
communications = ctx.call(
    "get_case_communications",
    rationale="Read the cardholder's chronology and any merchant contact before assessing non-receipt.",
    arguments={"case_id": case["case_id"]},
    function=lambda: ctx.data.case_communications(case["case_id"]),
)
~~~

The result is a list of communication rows. For `DSP-2026-90005`, the intake communication says the
cardholder saw two `$64.18` charges for one lamp; for other cases, communications may contain
contradictions or a different claim chronology. The playbook converts that output into findings
with references such as `COM-...`, not into an untraceable model assertion.

### Time and visibility fields

There are several timestamps because they answer different questions:

| Field | Question answered |
|---|---|
| `auth_timestamp_utc` | When did the merchant request authorization? |
| `txn_local_datetime` + `merchant_timezone` | What local time did the transaction appear to occur? |
| `processing_date` | When did the network process/clear it? |
| `posting_date` | When did the issuer post it to the account? |
| `opened_at` | When did the bank receive the dispute notice? |
| `requested_at` | When did the bank request evidence? |
| `available_at` | When was a row/document/event allowed to become visible? |
| event `timestamp_utc` | When did a lifecycle/security event happen? |
| `valid_from` / `valid_to` | During which period was a policy, research page, or memory note valid? |

The data access layer applies visibility filters in SQL and emits a `sql_query` event containing
the query, parameters, result IDs, and as-of filter. This gives a beginner a reliable rule:

> A file can exist on disk, but the agent can only use it when the corresponding `available_at` or
> validity window allows it at the run's virtual time.

~~~python
class CaseDataAccess:
    def __init__(self, db_path: Path, emitter: EventEmitter) -> None:
        self.db_path = db_path
        self.emitter = emitter
        self._connection: sqlite3.Connection | None = None

def _connect(self) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection
~~~

`mode=ro` prevents the operational query layer from changing source data. Mutations happen only
through the explicitly bounded action/persistence layer described later in this guide.

### A practical join recipe for a new playbook

When adding or reading a playbook, follow this order:

~~~python
# 1. Start from the case identity supplied by LangGraph.
case = ctx.data.get_case(case_id)

# 2. Follow the case-to-transaction join table.
transactions = ctx.data.get_case_transactions(case_id)

# 3. Use IDs from the transaction to fetch merchant and related data.
merchant = ctx.data.merchant(transactions[0]["merchant_id"])
history = ctx.data.descriptor_history(
    case["customer_id"], transactions[0]["merchant_id"]
)

# 4. Fetch documents/events through approved tools so visibility and audit rules apply.
packets = ctx.call(
    "read_evidence_packet",
    rationale="Inspect evidence linked to the disputed transaction.",
    arguments={"case_id": case_id, "as_of": ctx.clock.now.isoformat()},
    function=lambda: ctx.data.evidence_packets(case_id),
)
~~~

At every step, preserve the returned IDs in the finding's `source_refs`. If a lookup returns no
rows, record “not found/not available” and consider whether a wait is required; do not silently
replace the missing evidence with a guess.

### Knowledge, reference, and memory records

Not every useful input is a customer or transaction row. The runtime also joins the case to
versioned knowledge and prior agent beliefs:

| Table/file | Field | Meaning |
|---|---|---|
| `documents` | `doc_id` | Stable document ID used in retrieval results and citations. |
|  | `kind` | `policy`, `research`, `precedent`, or `skill`; this controls how the document is used. |
|  | `valid_from`, `valid_to` | Effective/captured/decided validity window. A policy must be selected as of the relevant case date. |
|  | `status`, `meta_json` | Document status and source metadata such as merchant, publisher, or policy version. |
|  | `body` | Searchable document text. |
| `documents_fts` | `doc_id`, `kind`, `title`, `body` | SQLite FTS5 index over document text; it returns candidates, not automatic truth. |
| `agent_memory_notes` | `note_id`, `kind`, `scope` | Memory identity and category, such as semantic, episodic, or procedural. |
|  | `subject_ids` | Entity/document IDs the note is about. |
|  | `content` | The prior belief or observation. It must be verified before being treated as a fact. |
|  | `source_refs` | IDs that support the note. |
|  | `confidence`, `status` | Belief strength and lifecycle (`active`, `superseded`, `retracted`, or `archived`). |
|  | `valid_from`, `valid_to`, `superseded_by` | Temporal and replacement relationships. |
|  | `sensitivity` | Flags restricted content, including prohibited decision bases. |
| `ref_*` tables | code/value + description | Explanations for values such as AVS, CVV2, ECI, POS-entry, MCC, FX, and Visa conditions. |

For example, `VISA-13.1@2026-04-18` is a policy document/version ID, while `13.1` in a case is a
network condition code. A retrieval result may suggest the policy, but the final decision keeps the
document ID in `citations` so a reviewer can tell which version was used. Similarly,
`MEM-0209` is a memory note ID, not a fact; the note's `source_refs`, validity, and status determine
whether it is safe to use.

~~~python
knowledge = ctx.call(
    "retrieve_knowledge",
    "Retrieve the policy effective on the case notice date",
    {
        "query": "Visa 13.1 merchandise services not received",
        "as_of": case["opened_at"][:10],
        "kinds": ["policy"],
    },
    lambda: ctx.knowledge.search(
        "Visa 13.1 merchandise services not received",
        as_of=date.fromisoformat(case["opened_at"][:10]),
        kinds=("policy",),
        limit=8,
    ),
)
~~~

The important distinction is: operational rows describe what the systems recorded; communications
and merchant packets contain claims that must be assessed; policies describe the rule; memory
contains prior beliefs; and the decision connects them with source references.

## 2. Configuration and per-run dependencies

### 2.1 Models

`config/models.yaml` defines the provider, model, capability requirements, token limits, retries,
and concurrency. The configuration is Pydantic-validated and immutable after loading.

```yaml
schema_version: 1
provider: openai
api: responses
default:
  model: gpt-5.6-luna
  reasoning_effort: medium
  timeout_seconds: 60
  max_attempts: 3
  max_output_tokens: 12000
  required_capabilities:
    - structured_output
    - tool_calling
    - streaming
    - reasoning_controls
    - usage_reporting
    - prompt_caching
concurrency:
  model_calls: 8
  per_run: 4
retry:
  initial_backoff_ms: 500
  max_backoff_ms: 8000
```

The model snapshot is hashed and stored in the trajectory:

```python
class ModelsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: int
    provider: str
    api: str
    default: DefaultModelConfig
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)

    @property
    def snapshot_hash(self) -> str:
        raw = json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(raw.encode()).hexdigest()}"
```

The loader supports `DISPUTE_AGENT_MODEL__MODEL` and
`DISPUTE_AGENT_MODEL__REASONING_EFFORT`. The runtime rejects a gateway missing a required
capability.

### 2.2 Agent configuration

Agent YAML files describe available agent identities and limits; they do not contain executable
logic:

```yaml
id: lead_investigator
version: 1
description: Maintains a source-linked plan and chooses the next evidence worth pursuing.
tools: []
skills: []
max_iterations: 4
```

```python
def load_agent_configs(path: Path) -> dict[str, AgentConfig]:
    agents = {
        config.id: config
        for file_path in sorted(path.glob("*.yaml"))
        for config in [AgentConfig.model_validate(_load_yaml(file_path))]
    }
    if len(agents) != len(list(path.glob("*.yaml"))):
        raise ValueError("agent ids must be unique")
    return agents
```

The configured IDs are `lead_investigator`, `cardholder_advocate`, `issuer_advocate`,
`panel_adjudicator`, `queue_clock_analyst`, `reg_e_clock_analyst`, `graph_link_analyst`,
`security_events_analyst`, `merchant_evidence_analyst`, `linked_case_analyst`,
`lifecycle_track_analyst`, and `folio_line_analyst`.

`max_iterations` remains part of the agent configuration metadata, but the current Deep Agents
integration does not enforce it as a native per-subagent iteration cap. Do not treat changing that
field as changing runtime behavior until a separately tested enforcement mechanism is added.

### 2.3 `RunContext`

Every run gets one context. Playbook hooks receive this object rather than constructing clients:

```python
@dataclass
class RunContext:
    db_path: Path
    emitter: EventEmitter
    clock: VirtualClock
    data: CaseDataAccess
    tools: ToolExecutor
    graph: GraphMemory
    knowledge: HybridKnowledgeStore
    notes: MemoryNoteStore
    persona: PersonaHarness
    scheduler: ExternalEventScheduler
    agents: dict[str, AgentConfig]
    chat_model: GatewayChatModel
    model_name: str

    def event(self, kind, name, event_type, summary, payload=None, refs=()):
        return self.emitter.emit(EventDraft(
            actor=Actor(kind=kind, name=name), type=event_type,
            summary=summary, payload=payload or {}, refs=list(dict.fromkeys(refs))
        ))

    def call(self, name, rationale, arguments, function, **kw):
        return self.tools.call(
            name, rationale=rationale, arguments=arguments, function=function, **kw
        )
```

The actual type annotations and event helper are in `src/runtime/context.py`; the excerpt shows the
boundary used by playbooks. The constructor wires the virtual clock, data access, tool executor,
graph, knowledge store, notes, persona, scheduler, model wrapper, and agent definitions.

## 3. Workflow state and LangGraph

### 3.1 State

LangGraph carries a plain TypedDict called WorkflowState. It contains run/case identity, loaded
facts, route and clocks, the bounded plan, findings, evidence and replies, waits,
specialist/parallel-track results, governance status, verifier/replan counters, proposal/decision,
actions, and memory correction IDs.

~~~python
class WorkflowState(TypedDict, total=False):
    run_id: str
    case_id: str
    case: dict[str, Any]
    transactions: list[dict[str, Any]]
    descriptor_history: list[dict[str, Any]]
    route: dict[str, Any]
    clocks: dict[str, Any]
    plan: list[str]
    steps: list[str]
    completed_steps: list[str]
    iterations: int
    progress_marker: int
    stalled_iterations: int
    next_step: str
    findings: dict[str, Any]
    knowledge: list[dict[str, Any]]
    memory_notes: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    replies: list[dict[str, Any]]
    candidate_condition: str
    pending_wait: dict[str, Any] | None
    external_event: dict[str, Any] | None
    waits: list[dict[str, Any]]
    specialist_results: list[dict[str, Any]]
    track: dict[str, Any]
    track_results: Annotated[list[dict[str, Any]], operator.add]
    governance_facts: dict[str, bool]
    verifier_passed: bool
    replan_count: int
    forced_stop: str | None
    proposal: dict[str, Any]
    panel_triggers: list[str]
    decision: dict[str, Any]
    action_ids: list[str]
    memory_correction_ids: list[str]
~~~

The track_results field uses operator.add as its LangGraph reducer. merge_tracks sorts results by
branch_id, so parallel branches do not overwrite each other with last-writer-wins behavior.

### 3.2 Fixed nodes and normal sequence

The graph is the same for all routes. Route-specific behavior is loaded inside nodes from the
serialized route ID.

~~~python
def playbook(state: WorkflowState) -> ModuleType:
    return load_playbook(state["route"]["route_id"])

nodes: dict[str, tuple[Node, str | None, bool]] = {
    "run_start": (run_start, "load_case", False),
    "load_case": (load_case, "route", False),
    "route": (route, "compute_clocks", False),
    "compute_clocks": (compute_clocks, "investigate", False),
    "investigate": (investigate, "assess_progress", False),
    "assess_progress": (assess_progress, None, False),
    "gather_evidence": (gather_evidence, None, False),
    "ask_cardholder": (ask_cardholder, "await_external_event", False),
    "await_external_event": (await_external_event, "apply_external_event", False),
    "apply_external_event": (apply_external_event, "assess_progress", True),
    "run_specialists": (run_specialists, "assess_progress", True),
    "analyze_track": (analyze_track, "merge_tracks", False),
    "merge_tracks": (merge_tracks, "assess_progress", True),
    "verify": (verify, None, False),
    "replan": (replan, "assess_progress", True),
    "propose_decision": (propose_decision, "governance_gate", False),
    "governance_gate": (governance_gate, None, False),
    "review_panel": (review_panel, "record_decision", False),
    "record_decision": (record_decision, "execute_actions", False),
    "execute_actions": (execute_actions, "memory_maintenance", False),
    "memory_maintenance": (memory_maintenance, "terminate", False),
    "terminate": (terminate, "__end__", False),
}

builder = StateGraph(WorkflowState)
for name, (node, next_node, back_edge) in nodes.items():
    builder.add_node(name, _instrument_node(name, node, emitter, next_node, back_edge))
for name, (_, next_node, _) in nodes.items():
    if next_node:
        builder.add_edge(name, END if next_node == "__end__" else next_node)
builder.add_edge(START, "run_start")
~~~

The normal sequence is:

~~~text
START -> run_start -> load_case -> route -> compute_clocks -> investigate
      -> assess_progress -> route-specific steps -> verify -> propose_decision
      -> governance_gate -> optional review_panel -> record_decision
      -> execute_actions -> memory_maintenance -> terminate -> END
~~~

### 3.3 Loading the case

The first data node loads the dispute, exact disputed transactions, and descriptor history. These
database operations are wrapped in ctx.call, which validates and audits them.

~~~python
case = ctx.call(
    "get_case",
    "Load the source dispute and regime",
    {"case_id": case_id, "as_of": ctx.clock.now.isoformat()},
    lambda: ctx.data.get_case(case_id),
)
transactions = ctx.call(
    "get_case_transactions",
    "Identify the exact disputed transactions",
    {"case_id": case_id, "as_of": ctx.clock.now.isoformat()},
    lambda: ctx.data.get_case_transactions(case_id),
)
~~~

The node records loaded case and transaction IDs in a case_file_updated event. Descriptor history
is queried only if transactions are available.

### 3.4 Progress and stopping

The playbook supplies an ordered steps list. The runtime removes completed steps and chooses the
first remaining step. It forces verification when a previous stop exists, the tool budget is
exhausted, or no progress exceeds the configured limit.

~~~python
if forced:
    next_step = "verify"
elif ctx.tools.limit is not None and ctx.tools.calls >= ctx.tools.limit and steps:
    forced, next_step = "budget_exhausted", "verify"
elif stalled > budget["no_progress_iterations"] and steps:
    forced, next_step = "no_progress", "verify"
else:
    next_step = steps[0] if steps else "verify"
~~~

~~~python
def _progress_marker(state: WorkflowState) -> int:
    return (
        sum(
            len(state.get(key, []) or [])
            for key in ("evidence", "replies", "specialist_results", "knowledge", "memory_notes")
        )
        + len(state.get("findings", {}))
        + len(state.get("completed_steps", []))
    )
~~~

A stop does not bypass verification, governance, decision persistence, or action guardrails.

### 3.5 Conditional edges, re-planning, and fan-out

assess_progress returns either a node name or a list of Send objects. A route with independent
tracks is fanned out; all other routes follow one next node.

~~~python
def after_progress(state: WorkflowState) -> Any:
    target = state["next_step"]
    if target == "analyze_tracks":
        tracks = playbook(state).tracks(ctx, state)
        sends = []
        for track in tracks:
            _edge(
                emitter,
                "assess_progress",
                "analyze_track",
                "fan out independent tracks",
                target,
                branch_id=track["branch_id"],
            )
            sends.append(
                Send("analyze_track", {**state, "track": track, "track_results": []})
            )
        return sends
    _edge(emitter, "assess_progress", target, "next planned step or stop test", target)
    return target

builder.add_conditional_edges(
    "assess_progress",
    after_progress,
    ["gather_evidence", "ask_cardholder", "run_specialists", "analyze_track", "verify"],
)
~~~

After verification, a failed check goes to replan only if the playbook implements it and the route
replan budget has not been consumed:

~~~python
def after_verify(state: WorkflowState) -> str:
    passed = state["verifier_passed"]
    remaining = state["route"]["budget"]["replans"] - state.get("replan_count", 0)
    can_replan = hasattr(playbook(state), "replan") and remaining > 0
    if not passed and can_replan:
        return "replan"
    return "propose_decision"

builder.add_conditional_edges("verify", after_verify, ["replan", "propose_decision"])
~~~

## 4. Routing

Routing is deterministic. config/routes.yaml is loaded into Pydantic models and sorted by priority.
The first route whose match expressions all pass wins. There is no LLM route classifier.

~~~python
class RoutesConfig(BaseModel):
    schema_version: int
    route_confidence_threshold: float
    routes: list[RouteConfig]

    @model_validator(mode="after")
    def unique_ordered_routes(self) -> RoutesConfig:
        ids = [route.id for route in self.routes]
        if len(ids) != len(set(ids)):
            raise ValueError("route ids must be unique")
        self.routes.sort(key=lambda route: route.priority)
        return self
~~~

Route features come from operational data: regime, claim family, transaction channels/count,
merchant closed-dispute history, proof-of-delivery presence, transaction age, descriptor history,
and prior merchant purchases. Match suffixes mean:

| Suffix | Comparison |
|---|---|
| no suffix | equality |
| _min | greater than or equal to |
| _max | less than or equal to |
| _in | membership |
| _contains | list/string containment |

~~~python
def _parse_expression(expression: str) -> tuple[str, str]:
    for suffix, operator in (
        ("_min", "gte"),
        ("_max", "lte"),
        ("_in", "in"),
        ("_contains", "contains"),
    ):
        if expression.endswith(suffix):
            return expression.removesuffix(suffix), operator
    return expression, "eq"
~~~

For example, transaction_channels_contains: agentic_commerce tests containment in the computed
channel list. A fallback route always matches if no earlier route matches. The selected route is
serialized as a RouteDecision containing depth, graph path, budgets, agent IDs, skills, and rationale.
Every evaluated rule and its checks are included in a route_decision event.

## 5. Playbooks: the route-specific agentic layer

### 5.1 Playbook contract

Each route has a same-named module under src/playbooks/. The loader is intentionally simple:

~~~python
def load_playbook(route_id: str) -> ModuleType:
    return importlib.import_module(f"{__name__}.{route_id}")
~~~

Only investigate and decide are required. Other hooks are optional and called only for that kind of
work:

~~~text
STEPS: initial ordered steps: gather_evidence, ask_cardholder,
       run_specialists, analyze_tracks
investigate(ctx, state) -> state update
evidence_request(ctx, state) -> request description
on_evidence(ctx, state, packets) -> state update
cardholder_question(ctx, state) -> question/rationale/channel
on_reply(ctx, state, reply) -> state update
on_timeout(ctx, state, wait) -> state update
specialists(ctx, state) -> state update plus task delegations
tracks(ctx, state) -> independent branches
analyze_track(ctx, state) -> one branch result
verify(ctx, state) -> check results
replan(ctx, state) -> state update
decide(ctx, state) -> DecisionRecord
hypotheses(ctx, state) -> review-panel board
curate(ctx, state) -> state update
~~~

The contract in src/playbooks/__init__.py means external access should go through ctx so the step
is auditable. A hook returns only a state update; the runtime owns graph transitions, checkpointing,
verification event emission, decision persistence, and action execution.

### 5.2 Smallest playbook

The L1 descriptor route is the smallest example. It performs graph lookup, merchant research, and
policy retrieval, then asks one clarifying question and returns a non-dispute decision.

~~~python
STEPS = ["ask_cardholder"]

def investigate(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    merchant_id = state["transactions"][0]["merchant_id"]
    variants = ctx.call(
        "graph_descriptor_variants",
        "Traverse the descriptor-to-merchant identity relationship",
        {"merchant_id": merchant_id},
        lambda: ctx.graph.descriptors_for_merchant(merchant_id),
    )
    research = ctx.call(
        "search_research",
        "Verify the payment-facilitator descriptor mapping",
        {"merchant_id": merchant_id, "as_of": ctx.clock.now.isoformat()},
        lambda: ctx.data.research_for_merchant(merchant_id),
    )
    intake = date.fromisoformat(state["case"]["opened_at"][:10])
    query = "LFB SOP DSP 001 pre-dispute descriptor clarification merchant recognition"
    knowledge = ctx.call(
        "retrieve_knowledge",
        "Retrieve the pre-dispute clarification procedure effective at intake",
        {"query": query, "as_of": intake.isoformat(), "kinds": ["policy"]},
        lambda: ctx.knowledge.search(query, as_of=intake, kinds=("policy",), limit=8),
    )
    return {
        "findings": {
            "descriptor_variants": variants,
            "research": research,
            "merchant_name": state["transactions"][0]["merchant_name"],
        },
        "knowledge": knowledge,
    }

def cardholder_question(ctx: RunContext, state: dict[str, Any]) -> dict[str, str]:
    transaction = state["transactions"][0]
    merchant_name = state["findings"]["merchant_name"]
    return {
        "question": (
            f"The statement descriptor {transaction['descriptor']} maps to {merchant_name}, "
            "billed through a payment provider. Do you recognize it?"
        ),
        "rationale": "The answer can resolve the remaining claim-specific question",
    }
~~~

The runtime calls decide only after all planned steps and verification. The playbook constructs a
typed DecisionRecord; it does not write the record directly.

### 5.3 Complete route table

This is the complete route set in config/routes.yaml:

| Route | Match focus | Depth | Advanced hooks |
|---|---|---:|---|
| descriptor_confusion_l1 | Familiar merchant with descriptor history | L1 | Cardholder clarification |
| duplicate_processing_l2 | Duplicate claim | L2 | Evidence wait and cardholder question |
| bundled_not_received_l2 | Multiple not-received transactions | L2 | Evidence and per-transaction treatment |
| recurring_trial_l3 | Cancelled recurring/trial claim | L3 | Evidence, verifier failure, re-plan, unused-portion computation |
| debit_fraud_l3 | Reg E CNP fraud | L3 | Specialists, compromise-point graph, hypotheses, memory/graph writes |
| high_value_cnp_ato_l4 | High-value Reg Z CNP fraud | L4 | Security/graph specialists and review hypotheses |
| single_not_received_graph_check_l2 | One not-received transaction | L2 | Linked identity/case graph and bounded ring hypothesis |
| agentic_transaction_novel_l4 | agentic_commerce channel | L4 | Provider-record wait, policy gap, mandatory panel facts |
| recurring_mid_lifecycle_l3 | Recurring case at pre-arbitration stage | L3 | Cardholder evidence, Send fan-out, one charge per track |
| household_authority_l4 | Multi-transaction household-authority fraud | L4 | Device ownership, cardholder question, review panel |
| merchant_pattern_not_received_l2 | Merchant with repeated closed claims | L2 | Evidence and merchant pattern consolidation |
| reg_e_not_received_credit_check_l1 | Reg E not-received | L1 | Reg E clocks and late merchant-credit check |
| credit_shortfall_fx_l2 | Credit not processed/FX shortfall | L2 | Linked transactions and FX computation |
| lodging_folio_amount_l3 | Incorrect lodging amount | L3 | Evidence, folio specialist, tax arithmetic |
| lodging_cancellation_l2 | Lodging cancellation | L2 | Evidence, local-time conversion, no-show |
| not_as_described_l2 | Not-as-described | L2 | As-of listing snapshot and policy validity |
| stale_claim_timeliness_l2 | Old not-received claim | L2 | Value-of-information stop and credit-outstanding computation |
| cnp_fraud_ce3_digital_l3 | Reg Z CNP fraud with merchant history | L3 | Evidence, reply, CE3 version comparison |
| merchant_nonperformance_not_received_l2 | Not received with no delivery proof | L2 | Research remedy window and evidence request |
| novel_or_ambiguous | Fallback | L4 | Generic investigation metadata and adjudication skill |

STEPS controls which generic nodes are visited:

~~~python
# no external wait
STEPS = []

# one evidence request
STEPS = ["gather_evidence"]

# evidence followed by clarification
STEPS = ["gather_evidence", "ask_cardholder"]

# evidence followed by isolated specialist tasks
STEPS = ["gather_evidence", "run_specialists"]
~~~

### 5.4 Skills

The runtime reads skills/<name>/SKILL.md during investigate, emits skill_loaded, and includes the
content in the lead investigator's planning prompt. The implemented skills are:

| Skill | Role |
|---|---|
| eligibility-check | Eligibility and invalid-dispute checks before merits |
| not-received | Transaction-granular non-receipt and write-off rules |
| recurring-trial | Recurring/trial condition checks and re-planning |
| fraud-cnp | CNP fraud hypotheses, CE3, security, and graph boundaries |
| reg-e-clocks | Reg E notice, liability, and deadline calculations |
| automated-adjudication | Independent positions, adjudicator, and conservative default |
| dispute-lifecycle | Existing network stages and independent charge tracks |
| household-authority | Authority questions, device ownership, and fair review |
| lodging-te | Folio, cancellation, no-show, and local-time handling |
| memory-hygiene | Verification, correction, consolidation, and expiry |
| agentic-transactions | AI-agent payment-provider records and policy gaps |

Skills are guidance, not action authority. A skill cannot bypass a Python verifier or the actions.py
allow-list.

### 5.5 Re-planning example

The recurring trial route starts with candidate condition 13.2. Its verifier can reject that route
when cancellation follows billing, then the playbook adds a 13.5 plan and computes the unused
service portion.

~~~python
if state["candidate_condition"] == "13.2":
    return [
        check(
            "13.2_cancellation_before_transaction",
            cancelled <= billing,
            {
                "billing_date": billing.isoformat(),
                "cancellation_date": cancelled.isoformat(),
                "invalid_when_after": True,
            },
            ["VISA-13.2@2026-04-18", packet_id],
        )
    ]

result = ctx.call(
    "compute_unused_portion",
    "Compute the 13.5 unused portion with an explicit day count",
    {
        "amount": subscription["price"],
        "service_start": start,
        "service_end": end,
        "used_through": used_through.isoformat(),
    },
    lambda: unused_portion(
        amount=Decimal(subscription["price"]),
        service_start=date.fromisoformat(start),
        service_end=date.fromisoformat(end),
        used_through=used_through,
        emitter=ctx.emitter,
    ).model_dump(mode="json"),
)
~~~

The replan hook records plan_updated, changes candidate_condition to 13.5, and returns the new
computed finding. The runtime increments replan_count and returns to assess_progress.

### 5.6 Novel agentic-transaction route

The agentic transaction playbook demonstrates a wait for a provider record and a policy gap. It
requests the record with a special request tool:

~~~python
def evidence_request(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": "request_record",
        "wait_kind": "provider_record",
        "provider": state["findings"]["provider"],
        "summary": "Requested the cardholder instruction record from the agentic payment provider",
        "evidence_types": [
            "instruction_record",
            "consent",
            "options_evaluated",
            "booking_notification",
        ],
        "target_txn_ids": [row["txn_id"] for row in state["transactions"]],
        "rationale": "Only the provider's record shows whether refundable was a hard constraint",
    }
~~~

After the packet arrives, the playbook distinguishes hard constraints from preferences and evaluates
10.4, 13.1, 13.5, and 13.7. If none fits, its decision has is_dispute=False, a no_dispute network
action, a Reg Z explanation, and a machine-readable policy_gap_record automated action. The route
also sets novel_transaction_type, which makes the governance panel mandatory.

## 6. Audited tools and operational data

### 6.1 Tool schemas

Named tool schemas validate input before a function runs. Unknown fields are rejected:

~~~python
class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

_SCHEMAS: dict[str, type[ToolInput]] = {}

def register_tool_schema(name: str) -> Callable[[T], T]:
    def register(schema: T) -> T:
        if name in _SCHEMAS:
            raise ValueError(f"duplicate tool schema: {name}")
        _SCHEMAS[name] = schema
        return schema
    return register

@register_tool_schema("get_case")
class GetCaseInput(ToolInput):
    case_id: str
    as_of: datetime

def validate_tool_input(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    schema = _SCHEMAS[name]
    return schema.model_validate(arguments).model_dump(mode="json", exclude_none=True)
~~~

The registered schemas cover case/transaction reads, graph queries, policy retrieval, memory reads,
evidence and record requests, account/security lookups, arithmetic helpers, business-day
calculations, and portfolio queue operations. To add a tool, add a schema and a Python implementation
exposed by a playbook or runtime node.

### 6.2 Tool executor

ToolExecutor.call is the single audited boundary for a playbook operation. It requires a rationale,
validates arguments, checks the route tool budget, emits call/result events, stores the result as a
content-addressed blob, and increments the count.

~~~python
def call(
    self,
    name: str,
    *,
    rationale: str,
    arguments: dict[str, Any],
    function: Callable[[], T],
    actor: str = "lead_investigator",
    version: int = 1,
) -> T:
    if not rationale.strip():
        raise ValueError("tool rationale is required")
    validated_arguments = validate_tool_input(name, arguments)
    if self.limit is not None and self.calls >= self.limit:
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.HARNESS, name="budget_manager"),
                type="access_denied",
                summary=f"Denied {name}; tool-call budget is exhausted",
                payload={"tool": name, "dimension": "tool_calls",
                         "used": self.calls, "limit": self.limit},
            )
        )
        raise RuntimeError("tool-call budget exhausted")
    call_id = f"tool-{uuid.uuid4().hex}"
    self.calls += 1
    parent_span = self.emitter.current_span
    with self.emitter.span(call_id):
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.TOOL, name=name),
                type="tool_call",
                summary=f"Called {name}: {rationale}",
                payload={"call_id": call_id, "tool": name, "version": version,
                         "rationale": rationale, "arguments": validated_arguments,
                         "calling_actor": actor},
                span_id=call_id,
                parent_span_id=parent_span,
            )
        )
        result = function()
        blob = self.emitter.put_blob(result)
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.TOOL, name=name),
                type="tool_result",
                summary=f"{name} returned successfully",
                payload={"call_id": call_id, "status": "success",
                         "result_blob": blob, "retry_count": 0},
                span_id=call_id,
                parent_span_id=parent_span,
            )
        )
    return result
~~~

The source has the full EventDraft payloads; the excerpt shows the ordering. The function is run
only after validation and budget checks. Deep Agents task calls are counted through
account_external_call("task"), so specialist work also consumes the route budget.

### 6.3 Read-only SQLite access

CaseDataAccess opens SQLite with mode=ro. Each `CaseDataAccess` instance creates one connection on
first use and reuses it for that run/segment. This is safe because the runtime owns one access
object per run/segment and executes its synchronous SQLite calls on that run's event-loop thread.
Time-sensitive queries apply available_at <= virtual_now and emit a sql_query event.

~~~python
def _connect(self) -> sqlite3.Connection:
    if self._connection is None:
        self._connection = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        self._connection.row_factory = sqlite3.Row
    return self._connection

def get_case_transactions(self, case_id: str) -> list[dict[str, Any]]:
    return self._query(
        "transactions_for_case",
        """SELECT t.*, m.dba_name AS merchant_name FROM transactions t
           JOIN dispute_transactions dt ON dt.txn_id=t.txn_id
           LEFT JOIN merchants m ON m.merchant_id=t.merchant_id
           WHERE dt.case_id=? AND t.available_at<=?
           ORDER BY t.processing_date, t.txn_id""",
        (case_id, self.emitter.virtual_now.isoformat().replace("+00:00", "Z")),
        refs_column="txn_id",
    )
~~~

Available data is not automatically evidence. A playbook decides how a returned row is used and
keeps its source ID in state and/or decision citations.

PathGuard is the filesystem boundary for relative agent paths. Absolute paths, .., and denied
components such as ground_truth and simulation are rejected:

~~~python
def resolve(self, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or self.denied_parts.intersection(pure.parts):
        raise AccessDenied(f"agent data path denied: {relative}")
    resolved = (self.root / Path(*pure.parts)).resolve()
    if self.root not in resolved.parents and resolved != self.root:
        raise AccessDenied(f"agent data path escapes root: {relative}")
    if self.denied_parts.intersection(resolved.parts):
        raise AccessDenied(f"agent data path denied: {relative}")
    return resolved
~~~

## 7. Evidence, cardholder communication, and waits

Evidence and cardholder replies are external events. The runtime never blocks a person directly.

### 7.1 Evidence request

If the scheduler finds a future evidence packet, gather_evidence calls the playbook evidence_request
hook and creates a wait:

~~~python
request = module.evidence_request(ctx, state)
request_id = f"request-{expected['packet_id']}"
ctx.call(
    request.get("tool", "request_evidence"),
    request["rationale"],
    {
        "case_id": state["case_id"],
        "provider": request["provider"],
        "evidence_types": request["evidence_types"],
        "target_txn_ids": request["target_txn_ids"],
    },
    lambda: _request_evidence(ctx, request, request_id, expected),
)
wait = _wait(
    state,
    kind=request.get("wait_kind", "merchant_evidence"),
    wait_id=request_id,
    awaited_ref=expected["packet_id"],
    expected_at=expected["available_at"],
    provider=request["provider"],
)
return {**update, "pending_wait": wait, "waits": [*state.get("waits", []), wait]}
~~~

If the packet is already available, the runtime reads it immediately with _read_evidence; no wait is
created. Evidence JSON is untrusted data. The runtime emits untrusted_content_flagged and calls
on_evidence if the playbook implements it.

If a route includes `gather_evidence` but no current or scheduled packet exists, that absence is a
runtime state rather than an empty value left for playbook code to interpret. The graph emits
`evidence_unavailable`, records `required_evidence_unavailable`, skips later evidence-dependent
steps and re-plans, and sends a zero-confidence `insufficient_required_evidence` proposal through
the governance gate. The automated panel then applies the cardholder-favorable conservative
default, takes no network dispute action, and records no reusable memory fact. This shared boundary
prevents route hooks from indexing an empty packet list or reading findings that could only have
been produced from a packet; absence remains an availability fact, never adverse evidence.

### 7.2 Cardholder clarification

ask_cardholder calls the route question hook, sends the message through PersonaHarness, and waits
for its scheduled reply:

~~~python
prompt = module.cardholder_question(ctx, state)
message = ctx.call(
    "message_cardholder",
    prompt["rationale"],
    {
        "case_id": state["case_id"],
        "question": prompt["question"],
        "channel": prompt.get("channel", "secure_message"),
    },
    lambda: ctx.persona.send(
        state["case_id"],
        prompt["question"],
        channel=prompt.get("channel", "secure_message"),
    ),
)
wait = _wait(
    state,
    kind="cardholder_reply",
    wait_id=message["message_id"],
    awaited_ref=message["message_id"],
    expected_at=message["expected_at"],
    message=message,
)
~~~

The persona harness is simulation-only. It chooses a scripted reply by question relevance and exposes
only the sent question and eventual reply to the workflow.

### 7.3 Real interrupt and resume

The actual suspension is the LangGraph interrupt:

~~~python
async def await_external_event(state: WorkflowState) -> dict[str, Any]:
    resolution = interrupt(state["pending_wait"])
    return {"external_event": resolution, "pending_wait": None}
~~~

The graph is compiled with AsyncSqliteSaver and uses run_id as the LangGraph thread ID. On
suspension, the runtime emits wait_suspended, termination with final_status suspended, and
checkpoint_saved. With auto_resume=True, the scheduler advances virtual time and returns a
Command(resume=payload). With auto_resume=False, RunSuspended is raised so another process can
resume the checkpoint.

~~~python
payload = external_event if external_event is not None else ctx.scheduler.deliver(wait)
return Command(resume=payload)
~~~

The scheduler accepts only merchant_evidence, provider_record, or cardholder_reply. It advances to
the expected arrival if that is before latest_safe_decision_time; otherwise it advances to the
latest safe time and returns latest_safe_time_reached. Missing evidence is recorded as an
availability fact, not evidence against the cardholder.

### 7.4 Scheduler implementation

~~~python
def deliver(self, wait: dict[str, Any]) -> dict[str, Any]:
    if wait["kind"] not in WAIT_KINDS:
        raise ValueError(f"suspension is not allowed for {wait['kind']}")
    latest_safe = parse_time(wait["latest_safe_decision_time"])
    expected = parse_time(wait["expected_at"]) if wait.get("expected_at") else None
    arrives = expected is not None and expected <= latest_safe
    before = self.clock.now
    self.clock.advance_to(
        max(before, expected if arrives else latest_safe),
        cause="scheduled_external_event" if arrives else "latest_safe_decision_time",
        refs=[wait["awaited_ref"]],
    )
    if not arrives:
        return {
            "status": "latest_safe_time_reached",
            "wait_id": wait["wait_id"],
            "awaited_ref": wait["awaited_ref"],
            "at": self.clock.now.isoformat(),
        }
    if wait["kind"] == "cardholder_reply":
        reply = self.persona.reply(wait["message"])
        return {"status": "arrived", "wait_id": wait["wait_id"], "reply": reply}
    return {"status": "arrived", "wait_id": wait["wait_id"],
            "packet_id": wait["awaited_ref"]}
~~~

## 8. Specialist subagents and parallel tracks

### 8.1 Deep Agents delegation

Playbooks return task descriptions rather than constructing subagents themselves:

~~~python
def specialists(ctx: RunContext, state: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    return (
        {"governance_facts": {"cross_customer_finding": True}},
        [
            {
                "subagent_type": "graph_link_analyst",
                "description": "Assess the supplied source-linked graph findings only",
            }
        ],
    )
~~~

RunContext.delegate creates one Deep Agents supervisor with configured child subagents. The
supervisor is instructed to call task once per supplied delegation. Child tools are empty in this
implementation; each task receives a source-linked brief.

~~~python
subagents = [
    {
        "name": name,
        "description": self.agents[name].description,
        "system_prompt": system_prompt,
        "tools": [],
        "model": self.chat_model.model_copy(update={"actor": name, "case_id": case_id}),
        "interrupt_on": None,
    }
    for name in sorted({item["subagent_type"] for item in items})
]
agent = create_deep_agent(
    model=self.chat_model.model_copy(
        update={"actor": "specialist_supervisor", "case_id": case_id}
    ),
    tools=[],
    subagents=subagents,
    middleware=[observer],
    system_prompt="Delegate every supplied task with the task tool. Do not omit tasks.",
    interrupt_on=None,
    name=supervisor,
)
~~~

SubagentTrajectoryMiddleware instruments task with a tool span, subagent_started,
subagent_finished, and tool_result events. It also counts the delegation against the route budget.
The supervisor must complete exactly as many results as requested.

### 8.2 LangGraph Send fan-out

A route can return independent case tracks. The runtime creates one Send("analyze_track", ...)
per track. Each branch receives its own track field and an empty track_results list. The route
module's analyze_track function must return a branch_id.

~~~python
def tracks(ctx: RunContext, state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"branch_id": f"track-{case_id}", "case_id": case_id}
        for case_id in state["findings"]["related_case_ids"]
    ]

async def analyze_track(ctx: RunContext, state: dict[str, Any]) -> dict[str, Any]:
    case_id = state["track"]["case_id"]
    # The implementation loads and decides this charge using only this branch's case_id.
    return {"branch_id": state["track"]["branch_id"], "case_id": case_id}
~~~

merge_tracks sorts branches and records a deterministic merge event. The recurring lifecycle route
uses this mechanism so each charge keeps its own stage and clocks.

## 9. Portfolio queue graph

The Q01 portfolio path is separate from a single-case WorkflowState. rank_portfolio loads every open
case, fans out one clock computation per case with LangGraph Send, deterministically sorts the full
ranking, then delegates a top-15 clock re-check to queue_clock_analyst. Specialists cannot reorder
the deterministic queue.

~~~python
rows = sorted(
    state["clocks"],
    key=lambda row: (
        0 if row["overdue_clocks"] else 1,
        row["next_deadline"] or "9999-12-31",
        -Decimal(row["amount"] or "0"),
    ),
)
ranking = [
    {
        "rank": index,
        **row,
        "score": {
            "overdue": bool(row["overdue_clocks"]),
            "next_deadline": row["next_deadline"],
            "exposure": row["amount"],
        },
    }
    for index, row in enumerate(rows, start=1)
]
~~~

The order is overdue clocks first, then earliest next hard deadline, then larger exposure. The
portfolio graph is:

~~~text
START -> load_open_cases -> Send(case_clock for each open case)
      -> rank -> review_top -> END
~~~

Its queue-specific state uses a reducer for clock results:

~~~python
class PortfolioState(TypedDict, total=False):
    portfolio: dict[str, Any]
    case: dict[str, Any]
    clocks: Annotated[list[dict[str, Any]], operator.add]
    ranking: list[dict[str, Any]]
~~~

For each open case, portfolio_case_clocks includes Reg Z acknowledgement/resolution, Reg E
provisional-credit/investigation, pre-arbitration, Visa filing, merchant remedy windows, and awaited
provider records. The completed queue run emits route_decision, portfolio_ranked, termination with
final_status ranked, and run_completed.


## 10. Knowledge retrieval and graph memory

### 10.1 Hybrid knowledge retrieval

HybridKnowledgeStore.search combines vector nearest-neighbor candidates from sqlite-vec and
keyword candidates from SQLite FTS5. It filters by document kind and validity interval for the
supplied as_of date, combines rankings with reciprocal rank fusion, and emits used/discarded IDs.

~~~python
for candidate in candidates.values():
    reason = _ineligibility_reason(candidate, as_of, kinds)
    if reason:
        discarded.append({"id": candidate["doc_id"], "reason": reason})
        continue
    candidate["hybrid_score"] = _rrf(candidate)
    eligible.append(candidate)
eligible.sort(key=lambda row: (-row["hybrid_score"], row["doc_id"]))
used = eligible[:limit]
~~~

Validity is independent of ranking: a future or expired document cannot become eligible because it
has a high vector score. The embedding implementation is deterministic token hashing to a
96-dimensional vector; it is an index mechanism, not a model-provider call.

~~~python
def _rrf(candidate: dict[str, Any], constant: int = 60) -> float:
    score = 0.0
    if candidate.get("vector_rank"):
        score += 1 / (constant + candidate["vector_rank"])
    if candidate.get("keyword_rank"):
        score += 1 / (constant + candidate["keyword_rank"])
    return round(score, 8)
~~~

### 10.2 Graph boundary and fallback

GraphMemory exposes descriptors_for_merchant, common_compromise_points,
shared_delivery_network, shared_identity_component, device_fingerprint_owners, and
disputes_for_customers. It first tries LadybugDB and falls back to NetworkX with query parity. Its
SQLite hypothesis state connection is also created once per `GraphMemory` instance and reused for
that run/segment, matching the single-run ownership model of `CaseDataAccess`.

~~~python
class GraphMemory:
    def __init__(self, graph_root: Path, state_db_path: Path, emitter: EventEmitter) -> None:
        self.graph_root = graph_root
        self.state_db_path = state_db_path
        self.emitter = emitter
        self._state_connection = sqlite3.connect(state_db_path)
~~~

~~~python
def _query(
    self,
    template_id: str,
    cypher: str,
    parameters: dict[str, Any],
    fallback: Callable[[], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    started = time.perf_counter()
    backend = self.backend_name
    try:
        rows = self._ladybug.query(cypher, parameters) if self._ladybug else fallback()
    except Exception as exc:
        backend = "networkx"
        rows = fallback()
        self.emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.MEMORY, name="graph_query_router"),
                type="fallback",
                summary=f"Used NetworkX parity for {template_id}",
                payload={
                    "from": "ladybug",
                    "to": "networkx",
                    "reason": type(exc).__name__,
                },
            )
        )
    # The source emits graph_query with template, query, parameters, results and node IDs.
    return rows
~~~

Graph hypotheses are bounded writes. Allowed kinds are SuspectedRing,
SuspectedCompromisePoint, and SuspectedDropAddress. Writes require evidence references, subjects,
and confidence in [0, 1]:

~~~python
checks = [
    {
        "check": "allowed_hypothesis_kind",
        "pass": kind in {"SuspectedRing", "SuspectedCompromisePoint", "SuspectedDropAddress"},
    },
    {"check": "evidence_refs_present", "pass": bool(evidence_refs)},
    {"check": "subjects_present", "pass": bool(subject_ids)},
    {"check": "confidence_in_range", "pass": 0 <= confidence <= 1},
]
if not all(check["pass"] for check in checks):
    raise ValueError("graph hypothesis failed write gate")
~~~

The durable hypothesis row is stored in SQLite and the graph projection is updated. If evidence
linkage is missing, skip_hypothesis_write records the skip instead of writing guilt by association.

## 11. Durable notes and memory lifecycle

Durable memory is a source-linked lead store, not a source of truth. read_current returns only
active, confidence-qualified notes whose validity interval contains as_of, whose sensitivity is
normal, and whose subject/scope matches. It ranks results with confidence, recency decay, and
access count.

~~~python
sql = f"""SELECT * FROM agent_memory_notes
          WHERE status='active' AND confidence>=?
            AND valid_from<=? AND (valid_to IS NULL OR valid_to='' OR valid_to>=?)
            AND ({clauses}){" AND scope=?" if scope else ""}"""
~~~

The rank score is:

~~~python
def _rank_score(note: dict[str, Any], as_of: date) -> float:
    last = datetime.fromisoformat(note["last_accessed_at"].replace("Z", "+00:00")).date()
    age = max((as_of - last).days, 0)
    recency = 0.5 ** (age / DECAY_HALF_LIFE_DAYS)
    access = 1 + math.log1p(note["access_count"]) / 10
    return round(note["confidence"] * recency * access, 4)
~~~

All writes go through MemoryNoteStore.write. The gate checks kind/scope, source references, valid
interval, confidence, prohibited bases/character labels, full PAN or secret content, customer risk
labels, and the minimum three-source requirement for pattern notes.

~~~python
def _gate(self, note: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"check": "allowed_kind_and_scope",
         "pass": note["kind"] in KINDS and note["scope"] in SCOPES},
        {"check": "source_refs_present", "pass": bool(note["source_refs"])},
        {"check": "validity_window_valid",
         "pass": bool(note["valid_from"]) and (
             not note["valid_to"] or note["valid_to"] >= note["valid_from"])},
        {"check": "confidence_in_range",
         "pass": 0 <= float(note["confidence"]) <= 1},
        {"check": "sop_004_prohibited_content_absent",
         "pass": not PROHIBITED_BASES.search(note["content"])
         and not CHARACTER_LABELS.search(note["content"])},
        {"check": "no_full_pan_or_secret", "pass": not PAN.search(note["content"])},
        {"check": "no_customer_risk_label",
         "pass": note["scope"] != "customer" or not CUSTOMER_RISK_LABEL.search(note["content"])},
        {"check": "merchant_pattern_has_3_sources",
         "pass": "pattern" not in note["tags"] or len(note["source_refs"]) >= 3},
    ]
~~~

If a check fails, no row is inserted and write_rejected is emitted. Active duplicates are also
rejected. Operational notes expire on the TTL boundary itself: a note is expired when
`created_at + TTL <= as_of`, not only after that date. Lifecycle operations preserve history:

| Operation | Effect |
|---|---|
| verify | Records checking against current evidence; does not make a note evidence. |
| reject | Records that a note should not be current truth. |
| supersede | Ends the old validity interval and points to a newer note/document. |
| retract | Marks a contradicted note retracted and writes a sourced correction. |
| consolidate | Converts at least three observations into a bounded merchant pattern and archives inputs. |
| dedupe | Keeps the earliest equivalent note and archives later duplicates. |
| expire | Ends an operational note after its TTL. |
| purge | Replaces prohibited content with a non-sensitive audit tombstone. |
| skip | Records why a candidate was intentionally not written. |

~~~python
def expired(notes: list[dict[str, Any]], as_of: date) -> list[dict[str, Any]]:
    return [
        note
        for note in notes
        if note["scope"] in TTL_DAYS
        and date.fromisoformat(note["created_at"][:10])
        + timedelta(days=TTL_DAYS[note["scope"]])
        <= as_of
    ]
~~~

The offline curator and in-case curation share these methods. The curator applies prohibited-content
purge, TTL expiry, duplicate detection, stale policy supersession, and pattern handling; it does not
write directly to the table.

## 12. Deterministic sandbox and clocks

The sandbox owns arithmetic and date calculations so the agent does not infer money or deadlines in
prose. Every helper emits a computation event with code, inputs, output, status, and source
references.

Examples include split clearing, write-off eligibility, unused service, local-time conversion,
folio tax, FX refund breakdown, credit outstanding, CE3 prior transaction aging, business-day
offsets, and portfolio case clocks.

The Reg E new-account predicate is defined once and reused by `reg_e_deadlines`, `case_clocks`,
and `portfolio_case_clocks`. This prevents the three clock paths from drifting apart:

~~~python
def is_new_account(
    first_deposit_date: date | str | None, transaction_dates: Iterable[date]
) -> bool:
    if not first_deposit_date:
        return False
    first_deposit = (
        first_deposit_date
        if isinstance(first_deposit_date, date)
        else date.fromisoformat(first_deposit_date)
    )
    return any(0 <= (txn_date - first_deposit).days <= 30 for txn_date in transaction_dates)
~~~

~~~python
def unused_portion(
    *,
    amount: Decimal,
    service_start: date,
    service_end: date,
    used_through: date,
    emitter: EventEmitter,
) -> UnusedPortionResult:
    days_in_period = (service_end - service_start).days + 1
    days_used = (used_through - service_start).days + 1
    days_unused = days_in_period - days_used
    value = (amount * Decimal(days_unused) / Decimal(days_in_period)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return UnusedPortionResult(
        days_in_period=days_in_period,
        days_used=days_used,
        days_unused=days_unused,
        amount=amount,
        unused_portion=value,
        used_portion=amount - value,
    )
~~~

All sandbox helpers use one `_record_computation` helper for the event shape. The helper records the
helper name, executable rule description, inputs, output, status, and source references:

~~~python
def _record_computation(
    emitter: EventEmitter,
    helper: str,
    summary: str,
    *,
    code: str,
    inputs: dict[str, Any],
    output: dict[str, Any],
    refs: list[str],
) -> None:
    emitter.emit(
        EventDraft(
            actor=Actor(kind=ActorKind.SANDBOX, name=helper),
            type="computation",
            summary=summary,
            payload={
                "helper": helper,
                "code": code,
                "inputs": inputs,
                "stdout": "",
                "stderr": "",
                "output": output,
                "runtime_ms": 0,
                "status": "success",
            },
            refs=refs,
        )
    )
~~~

This consolidation changes the implementation location of event construction, not the public
helper results.

The core case clock calculation computes applicable Reg Z, Reg E, pre-arbitration, and Visa
deadlines, then sets the latest safe decision date to two business days before the earliest
governing deadline:

~~~python
governing = min(deadlines, key=lambda name: deadlines[name])
result = ClockResult(
    deadlines=deadlines,
    governing_clock=governing,
    latest_safe_decision_date=add_business_days(deadlines[governing], -2, holiday_set),
)
~~~

VirtualClock refuses to move backwards:

~~~python
def advance_to(self, value: datetime, *, cause: str, refs: list[str] | None = None) -> None:
    if value < self.now:
        raise ValueError("virtual clock cannot move backward")
    before = self.now
    self.now = value
    self.emitter.set_virtual_now(value)
    self.emitter.emit(
        EventDraft(
            actor=Actor(kind=ActorKind.HARNESS, name="virtual_clock"),
            type="clock_advanced",
            summary=f"Advanced virtual clock for {cause}",
            payload={"before": before.isoformat(), "after": value.isoformat(), "cause": cause},
            refs=refs or [],
        )
    )
~~~

Reg E helpers use business days and bank holidays; Reg Z resolution uses the second complete
billing cycle capped at 90 days. The playbook supplies the date/rule context, and the computed
clock result is stored in workflow state and the final decision.

## 13. Model abstraction and adapters

### 13.1 Provider-neutral port

The runtime depends on ModelGateway, not a provider SDK:

~~~python
class ModelGateway(Protocol):
    @property
    def capabilities(self) -> frozenset[Capability]: ...

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]: ...
~~~

Neutral requests contain actor, rationale, messages, tool schemas, optional output schema, reasoning
settings, token limits, timeout, and metadata. Neutral responses contain text, normalized tool calls,
structured output, finish category, usage, provider request ID, and provider metadata.

### 13.2 LangChain bridge

Deep Agents and LangChain receive GatewayChatModel. It converts messages and bound tool schemas
to neutral types and streams until a completed response:

~~~python
request = ModelRequest(
    call_id=f"model-{uuid.uuid4().hex}",
    actor=self.actor,
    rationale="Create or revise the investigation plan",
    messages=neutral_messages,
    tools=[_normalize_tool(tool) for tool in self.bound_tools],
    reasoning_effort=self.reasoning_effort,
    max_output_tokens=self.max_output_tokens,
    timeout_seconds=self.timeout_seconds,
    metadata={"case_id": self.case_id, "role": self.actor},
)
response = None
async for event in self.gateway.stream(request):
    if event.type == "completed":
        response = event.response
~~~

The bridge maps normalized tool calls to LangChain AIMessage.tool_calls and exposes usage metadata.

### 13.3 Instrumentation, retries, and concurrency

InstrumentedModelGateway wraps the selected gateway. It limits concurrent model calls with a
semaphore, emits request/stream/completion/failure events, records usage, and retries only
retryable failures before content has been emitted.

~~~python
retryable = (
    _is_retryable(exc) and not emitted_content and attempt < self.max_attempts
)
if not retryable:
    raise
backoff_ms = min(
    self.initial_backoff_ms * (2 ** (attempt - 1)), self.max_backoff_ms
)
await asyncio.sleep(backoff_ms / 1000)
~~~

Authentication, permission, and validation errors are not retryable. Model-token usage and route
tool-call usage are separate budget dimensions.

### 13.4 Fake and OpenAI adapters

The fake adapter is deterministic and needs no credentials. Its lead-investigator response is a JSON
plan; its supervisor response produces one task call per delegation:

~~~python
if request.actor != "lead_investigator":
    return (
        json.dumps({
            "status": "complete",
            "specialist": request.actor,
            "assessment": "The supplied source-linked facts were independently checked.",
        }),
        [],
    )
return (
    json.dumps({
        "steps": [
            "Confirm the claimed transaction and account regime",
            "Test the route-specific alternative explanation",
            "Verify evidence and stop when the outcome cannot change",
        ]
    }),
    [],
)
~~~

The OpenAI adapter uses the Responses API with stream=True and store=False, maps output text and
function calls to neutral types, and reports usage. strict_function_schema recursively closes JSON
Schema objects and makes formerly optional properties nullable because strict function tools require
closed objects and all properties in required.

## 14. Verification, governance, and decisions

### 14.1 Route verification

A playbook verifier returns check dictionaries. The runtime emits each one and sets
verifier_passed to all checks passing:

~~~python
checks = module.verify(ctx, state) if hasattr(module, "verify") else []
for item in checks:
    ctx.event(
        ActorKind.AGENT,
        "verifier",
        "verifier_check",
        f"Verifier {item['check']}: {'pass' if item['pass'] else 'fail'}",
        {
            "check": item["check"],
            "pass": item["pass"],
            "details": item["details"],
        },
        refs=item["refs"],
    )
return {"verifier_passed": all(item["pass"] for item in checks)}
~~~

Verification proves source retrieval, condition eligibility, arithmetic, evidence interpretation, and
the separation of cardholder and network outcomes. A failed check can cause route-specific replanning.

### 14.2 Decision shape

DecisionRecord keeps cardholder resolution separate from network recovery:

~~~python
class DecisionRecord(BaseModel):
    case_id: str
    regime: str
    is_dispute: bool
    claim_family: str
    split_case_required: bool = False
    network_actions: list[NetworkAction]
    cardholder_resolution: CardholderResolution
    case_resolutions: list[dict[str, Any]] = Field(default_factory=list)
    deadlines: dict[str, Any] = Field(default_factory=dict)
    adjudication: Adjudication
    automated_actions: list[dict[str, Any]] = Field(default_factory=list)
    follow_ups: list[dict[str, Any]] = Field(default_factory=list)
    wait: dict[str, Any] | None = None
    citations: list[dict[str, str]] = Field(default_factory=list)
    hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float
    explanation_for_cardholder: str
~~~

A case may credit the cardholder while filing no network action, or deny the cardholder while
accepting a network response. These are separate fields and separate checks.

### 14.3 Governance panel

governance.panel_triggers is deterministic. Triggers include high-value fraud denial, cardholder
contest of issuer evidence, reopening a closed case, authority determinations, no applicable rule or
novel transaction, and cross-customer abuse findings.

~~~python
def panel_triggers(
    case: dict[str, Any],
    proposal: DecisionRecord,
    facts: dict[str, bool],
) -> list[str]:
    denied = proposal.cardholder_resolution.outcome.startswith("denied")
    amount = Decimal(str(case.get("dispute_amount") or "0"))
    triggers = []
    if denied and case.get("claim_family_initial", "").startswith("fraud") and amount >= 500:
        triggers.append("unauthorized_use_denial_500_or_more")
    if denied and facts.get("cardholder_contests_issuer_evidence"):
        triggers.append("cardholder_contests_issuer_evidence")
    if facts.get("authority_determination"):
        triggers.append("authority_household_determination")
    if facts.get("no_applicable_rule") or facts.get("novel_transaction_type"):
        triggers.append("no_applicable_rule_or_novel_type")
    return triggers
~~~

When triggers are non-empty, the runtime sends a source-linked hypotheses board to independent
cardholder_advocate and issuer_advocate subagents, then to panel_adjudicator. The deterministic
code computes the actual positions and ruling; subagent outputs are recorded but do not control the
gate.

~~~python
def score(hypothesis: dict[str, Any]) -> dict[str, float]:
    support = sum(float(item["weight"]) for item in hypothesis["evidence_for"])
    opposition = sum(float(item["weight"]) for item in hypothesis["evidence_against"])
    total = support + opposition
    return {
        "support": support,
        "opposition": opposition,
        "net": support - opposition,
        "confidence": round(support / total, 3) if total else 0.0,
    }
~~~

The threshold is 0.75. If panel independence, confidence threshold, proposal alignment,
investigation verification, or fairness checks fail, apply_conservative_default credits the disputed
amount, removes adverse network actions, and adds issuer_absorbs_loss.

## 15. Decision persistence and bounded actions

### 15.1 Field-level provenance

DecisionRepository.save persists one complete JSON decision and a provenance map for every leaf path.
Each leaf points to all event sequence numbers and source IDs used by the run:

~~~python
record = decision.model_dump(mode="json")
provenance = {
    path: {"event_seqs": source_event_seqs, "source_ids": source_ids}
    for path in _leaf_paths(record)
}
self.emitter.emit(
    EventDraft(
        actor=Actor(kind=ActorKind.GRAPH_NODE, name="record_decision"),
        type="decision_recorded",
        summary="Recorded a complete decision with field-level provenance",
        payload={"record": record, "field_provenance": provenance},
        refs=source_ids,
    )
)
connection.execute(
    "INSERT OR REPLACE INTO decision_records VALUES (?,?,?,?)",
    (self.emitter.run_id, decision.case_id, json.dumps(record), json.dumps(provenance)),
)
~~~

### 15.2 Action writer

ActionRepository.execute translates a decision into close/credit/reversal/network/account/automated
actions and always adds a cardholder explanation. Every action is checked against the allow-list:

~~~python
allowed = action in ALLOWED_ACTIONS
self.emitter.emit(
    EventDraft(
        actor=Actor(kind=ActorKind.GRAPH_NODE, name="action_guard"),
        type="guardrail_check",
        summary=f"Action allow-list check for {action}: "
                f"{'pass' if allowed else 'fail'}",
        payload={
            "check": "bounded_action_allow_list",
            "action": action,
            "allowed_actions": sorted(ALLOWED_ACTIONS),
            "pass": allowed,
        },
        refs=[decision.case_id],
    )
)
if not allowed:
    raise ValueError(f"forbidden automated action: {action}")
~~~

The action row is inserted into case_actions and an automated_action event records the action ID,
details, before/after state when relevant, and source references. Only reopen_case and
credit_reopened_case update a target dispute row in the current implementation; other actions are
recorded as bounded executed actions.

The network actions that ActionRepository executes are file_dispute, write_off_no_chargeback, and
accept_dispute_response. A no_dispute result is retained in the DecisionRecord but is not an
executed network write.

## 16. Trajectory, redaction, and replayability

### 16.1 Event envelope

All runtime activity is represented by EventEnvelope:

~~~python
class EventEnvelope(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    event_id: str
    run_id: str
    case_id: str | None
    seq: int
    span_id: str
    parent_span_id: str | None
    ts_wall: datetime
    ts_virtual: datetime
    actor: Actor
    type: str
    summary: str
    payload: dict[str, Any]
    refs: list[str] = Field(default_factory=list)
    runtime: RuntimeSnapshot
    usage: EventUsage = Field(default_factory=EventUsage)
    redactions: list[Redaction] = Field(default_factory=list)
~~~

Actor kinds are graph_node, agent, subagent, tool, memory, sandbox, harness, and evaluator. The
evaluator kind exists in the shared schema; it is not part of a normal agent run.

### 16.2 Append-only hash chain

EventEmitter.emit assigns the next sequence number, finds the previous hash, redacts the draft,
persists the envelope, and hashes previous_hash + canonical JSON:

~~~python
canonical = json.dumps(serialized, sort_keys=True, separators=(",", ":"))
event_hash = hashlib.sha256(f"{previous_hash or ''}{canonical}".encode()).hexdigest()
connection.execute(
    """INSERT INTO run_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (
        envelope.event_id,
        envelope.run_id,
        envelope.case_id,
        envelope.seq,
        envelope.span_id,
        envelope.parent_span_id,
        envelope.ts_wall.isoformat(),
        envelope.ts_virtual.isoformat(),
        envelope.actor.kind.value,
        envelope.actor.name,
        envelope.type,
        envelope.summary,
        json.dumps(envelope.payload, default=str),
        json.dumps(envelope.refs),
        json.dumps(envelope.runtime.model_dump(mode="json")),
        json.dumps(envelope.usage.model_dump(mode="json")),
        json.dumps([item.model_dump(mode="json") for item in envelope.redactions]),
        event_hash,
        previous_hash,
    ),
)
~~~

`verify_chain` checks contiguous sequence numbers, previous-hash links, and recomputed hashes.
The row-to-envelope conversion and hash-chain algorithm are centralized in `src/domain/events.py`
so the emitter, replay utility, and API cannot silently implement different interpretations of the
same `run_events` row:

~~~python
def event_from_row(row: sqlite3.Row) -> EventEnvelope:
    return EventEnvelope.model_validate(
        {
            "event_id": row["event_id"],
            "run_id": row["run_id"],
            "case_id": row["case_id"],
            "seq": row["seq"],
            "span_id": row["span_id"],
            "parent_span_id": row["parent_span_id"],
            "ts_wall": row["ts_wall"],
            "ts_virtual": row["ts_virtual"],
            "actor": {"kind": row["actor_kind"], "name": row["actor_name"]},
            "type": row["type"],
            "summary": row["summary"],
            "payload": json.loads(row["payload_json"]),
            "refs": json.loads(row["refs_json"]),
            "runtime": json.loads(row["runtime_json"]),
            "usage": json.loads(row["usage_json"]),
            "redactions": json.loads(row["redactions_json"]),
        }
    )

def verify_event_chain(rows: Sequence[sqlite3.Row]) -> bool:
    previous: str | None = None
    for expected_seq, row in enumerate(rows, start=1):
        if row["seq"] != expected_seq or row["previous_event_hash"] != previous:
            return False
        canonical = json.dumps(
            event_from_row(row).model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        computed = hashlib.sha256(f"{previous or ''}{canonical}".encode()).hexdigest()
        if computed != row["event_hash"]:
            return False
        previous = computed
    return bool(rows)
~~~

Large content goes to `run_blobs` by SHA-256; events carry the blob ID.

### 16.3 Spans and subscriptions

The emitter keeps a ContextVar span stack. Graph nodes, tool calls, model calls, subagents, and
branches use spans and parent IDs so events form a causal tree. subscribe first yields persisted
events and then newly committed events until close_stream sends a sentinel.

### 16.4 Redaction

Redaction runs before payload/reference persistence and before blob storage. It removes secrets
matching sk-/sess-/proj- forms, card-number-like values, and prohibited keys such as race, sex,
marital_status, birth_year, and zip_code.

~~~python
if key.lower() in PROHIBITED_KEYS:
    output[key] = "[REDACTED_PROHIBITED_BASIS]"
    records.append(Redaction(path=child_path, category="prohibited_basis"))
else:
    output[key], child = redact(item, child_path)
    records.extend(child)
~~~

Redaction protects observability. The memory and governance gates separately control reusable
knowledge and decisions.

## 17. Runtime lifecycle contract

The public lifecycle implementation is `LangGraphRuntime` itself. The former standalone
`AgentRuntime` protocol was removed because it was never wired into the application. The runtime
exposes start, result, resume, cancel, completion inspection, and event iteration directly:

~~~python
class LangGraphRuntime:
    async def start(
        self, case_id: str, scenario_id: str = "hero", *, auto_resume: bool = True
    ) -> str: ...

    async def run(self, case_id: str, scenario_id: str = "hero") -> DecisionRecord:
        return await self.result(await self.start(case_id, scenario_id))

    async def result(self, run_id: str) -> DecisionRecord: ...

    async def resume(
        self,
        run_id: str,
        external_event: dict[str, Any] | None = None,
        *,
        auto_resume: bool = True,
    ) -> DecisionRecord: ...

    def is_done(self, run_id: str) -> bool: ...
    async def cancel(self, run_id: str) -> None: ...
    async def events(self, run_id: str) -> AsyncIterator[EventEnvelope]: ...
~~~

`start` creates a run UUID and launches `_drive` as an asyncio task. `run` is the convenience method
that starts and awaits the result. `resume` can rebuild context/graph, restore the latest checkpoint
using `run_id` as `thread_id`, and resume with the scheduler or a supplied event. `is_done` is a
synchronous check used by the API/SSE layer to distinguish a run still owned by the current process
from one whose persisted store is historical. `cancel` cancels the active task; its checkpoint can
support a later restart.

~~~python
run_id = await runtime.start(case_id, auto_resume=auto_resume)
try:
    decision = await runtime.result(run_id)
except RunSuspended as suspended:
    return {"run_id": run_id, "status": "suspended", "wait": suspended.wait}
~~~

## 18. Brief API implementation guide

The API is a presentation adapter over the agent runtime and its committed event stores. It supports
API-started case and queue runs through isolated copies under data/generated/ui/, while the case,
run, event, and decision reads remain read-only. It never writes the pristine
data/generated/disputes.sqlite scenario store. API reads do not emit agent sql_query events.

### 18.1 App wiring

~~~python
API_PREFIX = "/api/v1"

def create_app(
    root: Path, db_path: Path | None = None, ui_dir: Path | None = None
) -> FastAPI:
    app = FastAPI(title="Dispute Observatory API", version="0.1.0")
    app.state.root = root
    app.state.db_path = (db_path or root / "data/generated/disputes.sqlite").resolve()
    models, routes, scenario = load_config_state(root)
    app.state.models = models
    app.state.routes = routes
    app.state.scenario = scenario
    app.state.run_manager = RunManager(
        root=root,
        models=models,
        routes=routes,
        scenario=scenario,
        fallback_db_path=app.state.db_path,
        ui_dir=ui_dir,
    )
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(meta.router, prefix=API_PREFIX)
    app.include_router(cases.router, prefix=API_PREFIX)
    app.include_router(runs.router, prefix=API_PREFIX)
    app.include_router(queue.router, prefix=API_PREFIX)
    return app
~~~

Each read route receives a read-only SQLite connection through dependency injection. A run ID is
resolved through the API registry to its isolated store; unknown historical runs fall back to the
configured store. The shared helper now lives in `src/storage.py`, so the core runtime-adjacent
readers and API use the same URI/read-only setup:

~~~python
def connect_readonly(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection

def get_connection(request: Request) -> Iterator[sqlite3.Connection]:
    connection = connect_readonly(request.app.state.db_path)
    try:
        yield connection
    finally:
        connection.close()
~~~

API-started runs are managed by RunManager. It copies the pristine store, builds a runtime bound to
that copy, registers the run, and launches the runtime in the background. It reuses the configs
already loaded by `create_app`:

~~~python
async def start_run(self, *, case_id: str, adapter: Adapter, auto_resume: bool) -> RunHandle:
    self._forget_finished_runs()
    store = copy_scenario_store(self.scenario, self.ui_dir, f"run-{uuid.uuid4().hex}")
    runtime = build_runtime_from_config(
        self.root,
        models=self.models,
        routes=self.routes,
        scenario=self.scenario,
        adapter=adapter,
        sqlite_path=store,
    )
    run_id = await runtime.start(case_id, auto_resume=auto_resume)
    self._runtimes[run_id] = runtime
    await self._register(
        run_id, case_id=case_id, kind="case", store=store,
        adapter=adapter, auto_resume=auto_resume
    )
    return RunHandle(run_id=run_id, case_id=case_id, status="running", store_path=store)
~~~

When a new run is started, `_forget_finished_runs` removes completed runtime/task objects from the
process-local maps, while retaining the registry row, persisted event store, and in-process queue
ranking. This bounds memory for repeated API runs without making finished runs uninspectable or
rerunnable.

### 18.2 Endpoints and links

| Endpoint | What it does | Link to the rest |
|---|---|---|
| GET /api/v1/health | Checks DB existence and the disputes table. | Operational starting point. |
| GET /api/v1/meta | Returns adapter availability, configured model, virtual clock, and feature flags. | Describes configuration and whether execution/SSE are enabled. |
| GET /api/v1/meta/routes | Returns route IDs, priorities, match expressions, depths, graph paths, agents, skills, and budgets. | Explains route_decision events. |
| GET /api/v1/meta/agents | Reads config/agents YAML and returns agent metadata. | Names appear in subagent and event actor fields. |
| GET /api/v1/meta/skills | Reads skills/*/SKILL.md front matter. | Names correspond to route skills and skill_loaded events. |
| GET /api/v1/meta/workflow | Returns the static LangGraph node/edge description, including fixed, conditional, fan-out, and resume edges. | Explains event sequence and transitions. |
| GET /api/v1/schema/events | Returns EventEnvelope JSON Schema. | Defines run event response shape. |
| GET /api/v1/cases | Lists cases with regime/status/stage/claim filters, q, limit, and cursor. | Each item opens with /cases/{case_id}. |
| GET /api/v1/cases/{case_id} | Returns summary, transactions, communications, and latest run refs. | latest_runs[].run_id links to the run endpoints. |
| GET /api/v1/runs | Lists committed runs, optionally by case/status. | Each item links to run detail/events/decision. |
| POST /api/v1/runs | Starts a case run with case_id, adapter, and auto_resume; returns 202 with run/event/stream URLs. | The manager creates an isolated store and drives the runtime. |
| GET /api/v1/runs/{run_id} | Derives status from error/termination events and includes pending wait data. | Use decision_available or wait to choose the next read. |
| POST /api/v1/runs/{run_id}/cancel | Cancels an active API-managed run and returns its persisted summary. | Calls LangGraphRuntime.cancel through RunManager. |
| POST /api/v1/runs/{run_id}/rerun | Starts a fresh isolated run using the original case/adapter settings. | Returns URLs for the new run. |
| GET /api/v1/runs/{run_id}/events | Returns event envelopes after a sequence, with type/actor/ref filters. | Detailed trajectory for the run. |
| GET /api/v1/runs/{run_id}/events/stream | Sends a reconnectable SSE tail of committed events. | Uses Last-Event-ID or after_seq and stops at terminal status. |
| GET /api/v1/runs/{run_id}/decision | Returns saved decision and field-level provenance. | Provenance points back to event sequences/source IDs. |
| POST /api/v1/queue/runs | Starts a portfolio queue run with the selected adapter. | Manager creates an isolated queue store and runs the portfolio graph. |
| GET /api/v1/queue/runs/{run_id} | Returns queue status and ranking when complete. | The ranking is computed by portfolio Send fan-out. |

The case list uses approved fields and parameterized values:

~~~python
if regime:
    clauses.append("regime = ?")
    params.append(regime)
if q:
    clauses.append("(case_id LIKE ? OR customer_id LIKE ?)")
    like = f"%{q}%"
    params.extend([like, like])
sql = f"""SELECT {", ".join(CASE_FIELDS)} FROM disputes {where}
          ORDER BY opened_at DESC, case_id LIMIT ? OFFSET ?"""
~~~

Run status is derived from the trajectory, not a mutable status column. A termination payload
with final_status suspended, cancelled, decided, or ranked maps to the API status; error maps to
failed. The SSE implementation polls the committed SQLite event log, so it works for live runs,
runs resumed in another API process, and historical runs:

~~~python
events, _ = list_events(
    connection,
    run_id,
    after_seq=last_seq,
    event_type=None,
    actor=None,
    ref=None,
    limit=BATCH_LIMIT,
)
for event in events:
    yield {"id": str(event.seq), "event": event.type, "data": event.model_dump_json()}
    last_seq = event.seq
~~~

The stream uses EventSourceResponse with a 15-second ping and stops when the run is terminal. Before
stopping, it performs one final committed-log query after the task/status check. This closes the
race where the driving task commits its terminal event between the normal poll and the stop check.
API case runs can be cancelled or rerun; resume remains a runtime/CLI operation because the API does
not expose a resume request body.

API errors use one envelope:

~~~json
{
  "error": {
    "code": "case_not_found",
    "message": "unknown case DSP-...",
    "details": {"case_id": "DSP-..."}
  }
}
~~~

## 19. End-to-end example

For a descriptor-confusion case:

~~~text
1. build_runtime loads models, routes, scenario and fake/OpenAI gateway.
2. runtime.start creates a run ID and emits run_started.
3. run_start records the immutable model/config snapshot.
4. load_case reads the dispute, transaction and descriptor history.
5. route computes features and selects descriptor_confusion_l1.
6. compute_clocks records the applicable deadline.
7. investigate loads eligibility-check and asks lead_investigator for a bounded plan.
8. the descriptor playbook calls graph_descriptor_variants, search_research and retrieve_knowledge.
9. assess_progress selects ask_cardholder.
10. ask_cardholder sends the question and enters await_external_event.
11. the scheduler advances virtual time and resumes with the scripted reply.
12. assess_progress sees no remaining steps and selects verify.
13. the playbook returns a DecisionRecord with is_dispute=False and no network action.
14. governance_gate sees no panel trigger.
15. record_decision persists the decision and field provenance.
16. execute_actions writes close_case_no_dispute and send_explanation.
17. memory_maintenance skips an unnecessary reusable note.
18. terminate emits termination and run_completed.
~~~

The runtime call is:

~~~python
runtime = build_runtime(project_root, adapter="fake")
decision = await runtime.run("DSP-2026-90002")
print(decision.cardholder_resolution.outcome)
~~~

For an evidence-waiting case, use auto_resume=False to receive RunSuspended, persist the run and
checkpoint, then call resume(run_id) later. For a route with parallel tracks, the same graph uses
Send and the playbook tracks/analyze_track hooks; no new runtime graph is required.

## 20. Safe extension rules

### Add a route

1. Add a route entry to config/routes.yaml with a unique priority and match/output/budget fields.
2. Add src/playbooks/<route_id>.py.
3. Implement investigate and decide; add only required optional hooks.
4. Register new named tool input in src/tools/schemas.py.
5. Use ctx.call, ctx.knowledge, ctx.notes, ctx.graph, and sandbox helpers for external work.
6. Return source IDs in findings, verifier refs, and decision citations.

### Add an agent or skill

Add an agent YAML file under config/agents/ or a SKILL.md under skills/<name>/. Reference a skill in
route output if the lead investigator must load it. Reference a subagent name in delegation data
only when matching agent YAML exists.

### Add a model provider

Implement ModelGateway in src/adapters/. Convert provider request/stream/response types to
ModelRequest and ModelStreamEvent; do not let provider SDK types cross the adapter. Report
capabilities honestly because LangGraphRuntime rejects a gateway missing required capabilities.

### Change runtime lifecycle behavior

Update `LangGraphRuntime` directly; there is no separate `AgentRuntime` protocol to implement.
Keep domain decisions, tools, memory, governance, events, and evaluators independent of Deep Agents
and LangGraph-specific types. Preserve the run-ID/checkpoint contract and update the API manager and
SSE behavior when changing terminal states.

### Rules for new behavior

- Put route-specific reasoning in a playbook.
- Put arithmetic/date logic in sandbox.py and record the computation.
- Put reusable policy/precedent lookup in HybridKnowledgeStore.
- Treat memory as leads and verify it against current source data.
- Keep graph writes evidence-linked and bounded.
- Keep cardholder resolution separate from network action.
- Route uncertain/high-impact cases through governance.
- Execute only actions in the allow-list.
- Emit source references for material findings and decision fields.
- Preserve virtual-time and checkpoint semantics for external waits.
