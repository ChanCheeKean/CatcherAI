# 03 — Data Dictionary

> Every file the generator produces, what each field means, how records join, which timestamps matter, and where the data is deliberately messy.
> Regenerate with `python3 data/generator/gen.py`; validate with `python3 data/generator/validate.py`.

## 0. Layout and modality

```
data/
├── corpus/                         AUTHORED KNOWLEDGE (static, versioned)
│   ├── policies/network_visa/      network rules, one file per condition/version         → semantic memory
│   ├── policies/regulation/        Reg Z / Reg E text                                   → semantic memory
│   ├── policies/internal/          Lanternfield SOPs, bulletins, cardholder agreement    → semantic memory
│   ├── skills/                     investigation playbooks                               → procedural memory (skills)
│   └── author_policies.py          source of the corpus
├── generator/                      deterministic generator + validator (stdlib Python)
└── generated/                      SYNTHETIC RECORDS
    ├── structured/*.csv            system-of-record tables                              → persistent memory (SQLite)
    ├── events/*.jsonl              append-only event streams                             → persistent memory (SQLite)
    ├── documents/communications.jsonl   intake transcripts, call summaries, forwarded emails → persistent + semantic
    ├── documents/evidence_packets/*.json merchant / provider evidence (semi-structured)   → persistent + semantic + graph edges
    ├── documents/research/*.md     dated external pages (news, merchant terms, snapshots) → research tool corpus
    ├── precedents/*.md             closed-case write-ups                                 → semantic memory
    ├── memory_seed/                pre-existing agent memory notes + episodic run traces  → agent long-term memory
    ├── simulation/cardholder_personas.json  simulated cardholder behavior                → harness only
    ├── reference/*.csv             code tables, calendars, FX, IP intel                  → tools / sandbox
    ├── graph/nodes.jsonl, edges.jsonl       relationship projection of the above          → graph memory
    ├── ground_truth/               labels, expected traces, queue ranking, hero index    → evaluator only (NEVER agent-visible)
    └── manifest.json
```

| Modality | Files | Why this modality |
|---|---|---|
| Structured tables | `structured/*.csv` | Core-banking and card-processing systems are relational; agents need exact filters, joins, sums |
| Event streams | `events/*.jsonl` | Security and case activity are append-only; **sequence** is the signal (e.g. phone change → password reset → purchase) |
| Semi-structured documents | `evidence_packets/*.json` | Merchant responses vary by merchant and condition; fields are present or missing case by case |
| Unstructured text | `communications.jsonl`, `research/*.md`, `precedents/*.md` | Narratives, contradictions, and policy language need reading, not querying |
| Knowledge / policy | `corpus/policies/**` | Versioned, cited, effective-dated rules — retrieved by meaning *and* filtered by date |
| Procedural | `corpus/skills/*.md` | How-to knowledge loaded on demand |
| Agent memory | `memory_seed/*` | What a previous agent believed — including stale and wrong beliefs |
| Generated artifacts | *(produced at run time)* | Plans, evidence matrices, decision records, letters, memory writes — schema in §9 |

## 1. Identifiers and joins

| ID pattern | Entity | Example | Joins to |
|---|---|---|---|
| `CUS-#####` | customer (hero `CUS-9####`) | `CUS-90012` | accounts.primary_customer_id, account_holders, cards.customer_id, disputes, account_events, communications |
| `ACC-CR-#####` / `ACC-DDA-#####` | credit / deposit account | `ACC-DDA-90008` | cards, transactions, statements, disputes |
| `CRD-######` | card (primary or authorized user) | `CRD-90011` | transactions.card_id, disputes.card_id, tokens |
| `TKN-…` | network token | `TKN-90018-TM` | transactions.token_id |
| `MER-#####` | merchant (card acceptor) | `MER-90014` | transactions, merchant_descriptors, evidence_packets |
| `ACQ-##` | acquirer | `ACQ-07` | merchants.acquirer_id (CE 3.0 same-acquirer test) |
| `TXN-#######` | transaction (purchase, credit, payment, fee, verification) | `TXN-9000401` | dispute_transactions, evidence_packets, related_txn_id |
| `AUT-…` / `auth_code` | authorization | `A7K2Q9` | shared by multiple clearings of one authorization |
| `arn` | 23-digit acquirer reference number | `7441808…` | network-side reference for a clearing record |
| `DSP-YYYY-#####` | dispute case | `DSP-2026-90013` | dispute_transactions, dispute_events, communications, evidence_packets |
| `MEP-…` | merchant/provider evidence packet | `MEP-90012-OI` | evidence_packets.csv → documents/evidence_packets/*.json |
| `DEV-…` | device observed by the **issuer** (banking logins) | `DEV-RING-A` | account_events.device_id, devices |
| `fp_…` | device fingerprint | — | devices.device_fingerprint ↔ merchant packet `device_fingerprint` |
| `ADR-…` | address | `ADR-DROP-WHARFSIDE` | customers.home_address_id / work_address_id; matched to packet address strings |
| `COM-#######` | communication | — | case_id, customer_id |
| `EVT-#######` / `DEV-EVT-…` | account event / dispute event | — | customer/account / case |
| `WEB-#####` | research document | `WEB-04100` | related_merchant_id |
| `PRE-####` | precedent | `PRE-0019` | case_id |
| `MEM-####` | agent memory note | `MEM-0142` | subject_ids, source_refs |
| `VISA-…@date`, `REGZ-…`, `REGE-…`, `LFB-…@vN` | policy document + version | `VISA-10.4@2026-10-24` | cited by decisions and ground truth |

The key investigative path:
`customer → account/card → transaction → merchant → evidence packet (order, shipment, delivery, login/IP/device) → dispute → dispute events → communications → policy (as of date) → precedents → decision`, with side-paths `customer ↔ device/IP/phone/address ↔ other customers ↔ their disputes`.

## 2. Structured tables (`generated/structured/`)

### customers.csv
| Column | Meaning / format |
|---|---|
| customer_id | PK |
| full_name, preferred_name | fictional |
| birth_year | present because real systems have it; **prohibited as a decision signal** (SOP-DSP-004) |
| email | `@example.com/.net/.org` |
| phone, alt_phone | `(AAA) 555-01xx`; `alt_phone` is sparse and can be shared (ring signal) |
| home_address_id, work_address_id | → addresses |
| employer_name | free text; **not** a linkage signal on its own |
| customer_since | ISO date |
| segment | mass / premium / private |
| preferred_contact | app / email / phone |

### addresses.csv
`address_id, line1, line2, city, state, postal_code, country, lat, lon, address_type` — `address_type` ∈ residential, commercial, commercial_mail_drop. Streets are fictional; cities and centroids are real.

### accounts.csv
| Column | Meaning |
|---|---|
| account_id | PK |
| primary_customer_id | → customers |
| product | `lanternfield_visa_signature_credit` or `lanternfield_visa_debit_checking` |
| regime | `REG_Z` (credit) or `REG_E` (debit) — drives which legal clocks apply |
| opened_at | ISO date |
| credit_limit, apr, payment_behavior, autopay | credit only; `payment_behavior` ∈ pay_in_full / partial / minimum (C17 hinges on pay_in_full) |
| statement_cycle_day | day of month the cycle closes (Reg Z "billing cycle" math) |
| first_deposit_date | debit only; Reg E new-account test (C08) |

### account_holders.csv
`account_id, customer_id, role (primary|authorized_user), added_at, removed_at` — authorized users and household members (C10).

### cards.csv
`card_id, account_id, customer_id, role, network, bin, pan_masked, last4, expiry, status, issued_at, closed_at, replaced_card_id` — PANs are always masked (`400012******1234`).

### tokens.csv
`token_id, card_id, token_requestor_type (device_wallet|merchant_cof|agentic_payment_provider), token_requestor_name, provisioned_at, device_id, status`.

### merchants.csv
| Column | Meaning |
|---|---|
| merchant_id | PK (one card acceptor ID). The same business can appear under two IDs (C19: `MER-90023` / legacy `MER-90024`) |
| legal_name, dba_name | |
| mcc, mcc_description | real MCCs |
| country, city, state, timezone | `timezone` is the merchant's local zone (hotel deadlines, local timestamps) |
| channel | in_store / ecommerce / recurring |
| website, phone | `.example` domains, 555 numbers |
| acquirer_id, acquirer_name | CE 3.0 new-version same-acquirer requirement |
| card_acceptor_id | 15-digit MID |
| is_marketplace, parent_merchant_id | marketplaces and sub-merchants (C18) |
| status | active / closed |

### merchant_descriptors.csv
`merchant_id, descriptor, first_seen, last_seen, note` — descriptor history. Payment-facilitator migrations (C02) and POS vendor changes create **multiple descriptors per merchant over time**.

### devices.csv
`device_id, device_type, os, hardware_id (IMEI-like, phones only), device_fingerprint, first_seen, observed_primary_customer_id` — devices seen by the **issuer** in banking sessions. A device can be used by several customers (households, rings).

### transactions.csv — merged authorization + clearing
| Column | Meaning |
|---|---|
| txn_id | PK |
| account_id, card_id, customer_id | `customer_id` is the **card holder** (authorized user for AU cards) |
| token_id | when the transaction used a network token (agentic provider in C13) |
| merchant_id, descriptor, mcc | `descriptor` is as printed on the statement at that date |
| txn_type | purchase, credit, payment, fee, account_verification, provisional_credit |
| billing_amount, billing_currency | USD amount on the statement |
| txn_amount, txn_currency, fx_rate | original currency (C07 EUR) |
| auth_amount | amount authorized (split clearings sum to it — C04) |
| auth_id, auth_code, auth_response_code | response `00` approved; `59` suspected fraud decline (declines have no processing/posting date) |
| auth_timestamp_utc | ISO UTC |
| txn_local_datetime, merchant_timezone | **local wall time without offset** + zone name (mess by design; convert) |
| processing_date, posting_date | clearing/posting (usually 1–3 days after the transaction; weekends lengthen) — **Visa time limits count from processing date** |
| pos_entry_mode | see `reference/pos_entry_modes.csv` (05 chip, 07 contactless, 90 magstripe, 10 COF, 01 manual/e-com) |
| card_present | true/false |
| channel | in_store, ecommerce, recurring, card_not_present, agentic_commerce, payment, fee, adjustment |
| cof_type | none, cit_initial, cit_subsequent, mit_recurring, mit_unscheduled (13.2 validity) |
| eci, cavv_present, three_ds_status, three_ds_browser_ip | authentication; ECI 05 + CAVV → 10.4 invalid; issuer sees the 3DS browser IP |
| avs_result | Y/A/Z/N/U… (`reference/avs_result_codes.csv`) |
| cvv2_presence, cvv2_result | presence 1 + result N + approved → 10.4 invalid |
| clearing_seq, clearing_count | multiple clearings of one authorization (1/2, 2/2) |
| arn | acquirer reference number |
| related_txn_id | link from a credit/fee to its purchase — **often blank for real refunds** (C18) |
| fraud_reported_at | when the issuer reported fraud to the network (TC40) |
| available_at | when this record became visible to the issuer (clearing arrival) |

### statements.csv
`statement_id, account_id, cycle_start, cycle_end, transmitted_at, due_date, previous_balance, purchases, credits, payments, fees, closing_balance, minimum_due` — `transmitted_at` anchors the **Reg Z 60-day notice window** and **Reg E 60-day rule**; the payment sequence proves "paid in full" for §1026.12(c) (C17).

### disputes.csv
| Column | Meaning |
|---|---|
| case_id | PK |
| account_id, customer_id, card_id, regime | |
| status | open / closed |
| stage | intake, investigating, awaiting_merchant_evidence, dispute_filed, pre_arb_decision_due, closed |
| opened_at | intake timestamp = notice received (regulatory clocks start here) |
| intake_channel, intake_authenticated_via | secure channel → issuer certification allowed |
| claim_summary | short rep summary |
| claim_family_initial | what **intake** coded — sometimes wrong on purpose (C02, C05, C13) |
| network, network_condition | condition once filed |
| dispute_amount, provisional_credit_amount, provisional_credit_at | |
| network_case_ref | VROL-style reference |
| dispute_processing_date, response_processing_date, pre_arb_processing_date | network lifecycle anchors |
| cardholder_outcome, network_outcome | **separate** — cardholder can be credited while the issuer loses the chargeback |
| closed_at, assigned_queue, related_case_ids | `related_case_ids` pipe-separated |

### dispute_transactions.csv
`case_id, txn_id, disputed_amount` — many-to-many; one intake case can hold several transactions (C03, C10).

### evidence_packets.csv
`packet_id, case_id, txn_id, merchant_id, source, requested_at, available_at, path` — index to JSON packets. `source` ∈ order_insight, dispute_response, pre_arbitration, agentic_provider_record_on_written_request. `available_at` may be after `AS_OF` (late evidence).

## 3. Event streams (`generated/events/`)

### account_events.jsonl
`event_id, customer_id, account_id, event_type, timestamp_utc, channel, device_id, ip, detail{}, available_at`

| event_type | detail keys | Investigative use |
|---|---|---|
| login_success / login_failed | auth_method, reason, new_device, device_fingerprint | device/IP graph; takeover sequence |
| password_reset | method, otp_sent_to | takeover |
| phone_changed | old_phone_last2, new_phone, verification | SIM-swap indicator (C11) |
| token_provisioned | token_id, requestor, requestor_type, cardholder_verification | agentic consent (C13) |
| alert_sent / alert_opened | alert, merchant, amount, sent_to | "when did the customer learn?" (C08) |
| deposit_received | amount, type, first_deposit | Reg E new-account test |
| ivr_call, card_locked, card_reissue_requested | | intake context |

### dispute_events.jsonl
`event_id, case_id, timestamp_utc, event_type, actor, summary, detail{note}, available_at` — intake_created, ack_letter_sent, provisional_credit_posted/reversed, fraud_reported, order_insight_requested, dispute_filed, dispute_response_received, note_added, case_closed. **Investigator notes live in `detail.note`** of closing events.

## 4. Documents (`generated/documents/`)

### communications.jsonl
`comm_id, case_id, customer_id, merchant_id, direction, channel (phone_summary|chat|secure_message|email_forwarded), party, timestamp_utc, available_at, subject, body, attachments[{name, description}]` — attachments are **text descriptions** of screenshots, emails, PDFs and logs (no binary media). Contradictions live here.

### evidence_packets/*.json (semi-structured; fields vary by source)
Common header: `packet_id, case_id, txn_id, merchant_id, source, requested_at, available_at`. Optional blocks:

| Block | Keys | Typical conditions |
|---|---|---|
| `order` | order_id, placed_at, items[{sku, description, qty, price}], authorization, total, promised_delivery | all |
| `customer_account` | login_id, email, account_created_at, email_verified, account_status | 10.4, 13.x |
| `account_activity_last_24h` | [{ts, event, …}] | ATO detection |
| `session` | ip / ip_match, device_id, device_fingerprint, user_agent | CE 3.0 |
| `prior_transactions` | [{txn_date, merchant, acquirer_id, amount, description, login_id, ip, device_id, device_fingerprint, delivery_address, disputed}] | CE 3.0 |
| `compelling_evidence_claim` | framework, matching_elements[], merchant_assertion | **the merchant's claim, not a fact** |
| `shipping_address` | string | drop-address graph |
| `shipments` | [{carrier, tracking_number, events[{ts, status, address}], proof_of_delivery{address, photo_description, gps_distance_m, signature}}] | 13.1 (full vs partial address!) |
| `digital_delivery` / `digital_usage` | download attempts, playtime, sessions | digital goods |
| `subscription`, `emails_sent`, `app_sessions`, `checkout_disclosure` | trial/renewal evidence | 13.2 / 13.5 |
| `reservation`, `folio`, `registration_card`, `valet_log`, `pms_log`, `charge` | lodging | 12.5 / 13.1 / 13.7 |
| `membership_agreement`, `cancellation`, `badge_scans` | recurring services | 13.2 |
| `payment_method_events`, `purchases` | card saved to account | household authority |
| `instruction`, `cardholder_consent`, `options_evaluated`, `decision_log`, `booking_notification` | agentic provider record | §4.1.24 |
| `refunds`, `return_policy`, `policies_accepted` | | 13.6 / 13.7 |
| `status`, `message` | `no_data`, `not_enrolled` | merchant silent |
| `merchant_statement` | free-text rebuttal | always adversarial |

### research/*.md
YAML front matter: `doc_id, title, url (.example), publisher, published_at, captured_at, doc_type, related_merchant_id` + body. `doc_type` ∈ news, merchant_site_snapshot, merchant_policy, merchant_terms_snapshot, merchant_listing_snapshot, merchant_help, merchant_notice, merchant_press_release, status_page, descriptor_directory, agentic_provider_terms, marketplace_policy, forum_post. **`captured_at` matters**: two snapshots of the same page with different content (C06, C16) test as-of reasoning.

## 5. Precedents (`generated/precedents/*.md`)
Front matter: `precedent_id, case_id, title, decided_at, network_condition, cardholder_outcome, network_outcome, merchant_id, tags[], policy_versions_applied[]`. Sections: Facts, Decision, Reasoning, Investigator notes. 11 hand-written contrast precedents (PRE-0004…PRE-0031) + 28 templated. Note `PRE-0031` is a **flawed** decision recorded as written, and `PRE-0012` was decided under a **superseded** rule. Version labels like `@2025-10` refer to editions not included in the corpus.

## 6. Memory seed (`generated/memory_seed/`)

### agent_memory_notes.jsonl
| Field | Meaning |
|---|---|
| note_id | `MEM-####` |
| kind | semantic / episodic / procedural |
| scope | customer / merchant / policy / procedure / operational |
| subject_ids | entity or document IDs |
| content | the belief |
| created_at, created_by | agent version, analyst, system |
| source_refs | evidence the note came from |
| confidence | 0–1 |
| status | active / superseded / retracted / archived |
| valid_from, valid_to, superseded_by | temporal validity |
| tags, sensitivity | `prohibited_basis` marks content that must be purged |
| last_accessed_at, access_count | recency/frequency for decay |

Planted note states: valid (MEM-0170, 0175, 0190, 0195, 0220, 0221), **stale by policy change** (0150, 0151, 0152, 0160), **wrong** (0142), **stale by world change** (0209), **raw observations to consolidate** (0201–0208), **duplicates** (0180/0181), **noise** (0185), **prohibited** (0196).

### run_traces/*.jsonl
Step-level episodic traces of two prior agent runs: `step, ts, agent, type (plan|tool_call|reasoning|decision|memory_write|human_approval|qa_review), content/tool/args/result_summary, confidence`. `human_approval` steps appear only in these legacy traces from before automated governance took effect on 2026-10-01; current runs never produce them. `TRACE-2026-06-02-DSP-2026-04471` is the flawed run that produced MEM-0142.

## 7. Reference data (`generated/reference/`)
`avs_result_codes, cvv2_result_codes, cvv2_presence_indicators, eci_values, three_ds_trans_status, pos_entry_modes, cof_types, auth_response_codes, mcc_codes, visa_dispute_conditions, bank_holidays_2026, fx_rates_eur_usd, cities, ip_intel`. `ip_intel.csv`: `ip, ip_type (residential|residential_cgnat|mobile_cgnat|hosting|hosting_vpn), isp, city, state, country, note`.
> Code-table meanings are standard industry values recorded from practitioner knowledge; verify against processor specifications before production use.

## 8. Graph projection (`generated/graph/`)
`nodes.jsonl`: `{node_id "Label:key", label, key, props}` · `edges.jsonl`: `{src, rel, dst, props}`.

| Label | Key |
|---|---|
| Customer, Account, Card, Token, Merchant, Acquirer, Transaction, Dispute, EvidencePacket, Precedent | IDs |
| Address | address_id, or `ADR-OBS-<hash>` for addresses seen only in merchant evidence |
| Device, DeviceFingerprint, IP, Phone, Email, Descriptor, MerchantLogin, AgenticProvider | natural keys |

| Relationship | From → To | Source |
|---|---|---|
| LIVES_AT, WORKS_AT, HAS_PHONE{kind}, HAS_EMAIL | Customer → Address/Phone/Email | customers |
| HOLDS{role} | Customer → Account | account_holders |
| HAS_CARD, CARRIES, TOKENIZED_AS, REQUESTED_BY | Account/Customer → Card → Token → AgenticProvider | cards, tokens |
| MADE, AT, USING_TOKEN | Card → Transaction → Merchant | transactions (payments excluded) |
| ACQUIRED_BY, SUB_MERCHANT_OF, DESCRIBES | Merchant → Acquirer / Merchant; Descriptor → Merchant | merchants, descriptors |
| HAS_FINGERPRINT | Device → DeviceFingerprint | devices |
| BANKING_LOGIN_FROM{event,count,first,last} | Customer → Device/IP | account_events (aggregated) |
| FILED, DISPUTES, RELATED_TO, HAS_EVIDENCE | Customer → Dispute → Transaction / Dispute / EvidencePacket | disputes |
| SHIPPED_TO, DELIVERED_TO, MERCHANT_SAW_IP, MERCHANT_SAW_FINGERPRINT, MERCHANT_LOGIN | Transaction → Address/IP/DeviceFingerprint/MerchantLogin | evidence packets |
| DECIDED | Precedent → Dispute | precedents |

No inferred edges (rings, compromise points) are shipped — those are **agent writes**.

## 9. Run-time artifacts the agent produces (schemas)

### Decision record (evaluated against ground truth)
```json
{
  "case_id": "DSP-2026-90006",
  "regime": "REG_Z",
  "is_dispute": true,
  "claim_family": "services_not_received_partial",
  "network_actions": [{"txn_id": "TXN-9000501", "case_id": "DSP-2026-90006", "action": "file_dispute | no_dispute | write_off_no_chargeback | accept_dispute_response | pre_arbitration",
                       "condition": "13.1", "amount": "105.60", "certification": ["…"]}],
  "cardholder_resolution": {"outcome": "partial", "credit_amount": "105.60", "reversal_amount": "328.46", "liability_amount": "0.00"},
  "deadlines": {"reg_z_resolution_deadline": "2026-12-12"},
  "adjudication": {"review_panel_used": false, "positions": [{"role": "cardholder_advocate | issuer_advocate | adjudicator", "summary": "…"}],
                   "confidence": 0.82, "threshold": 0.75, "conservative_default_applied": false, "flip_fact": "…"},
  "automated_actions": [{"action": "reopen_case | credit_reopened_case | watchlist_add | enhanced_monitoring | claims_control_evidence_first | graph_write | lock_digital_banking_pending_step_up | revert_unverified_phone_change | request_record | policy_gap_record | enqueue_automated_rereview", "…": "…"}],
  "follow_ups": [{"at": "2026-11-04", "action": "…"}],
  "wait": {"for": "MEP-…", "available_at": "…", "latest_safe_decision_date": "…"},
  "memory_ops": [{"op": "write | supersede | retract | consolidate | archive | purge", "note_id": "MEM-0150", "content": "…", "source_refs": ["…"]}],
  "account_actions": ["fraud_report_tc40"],
  "citations": [{"doc_id": "VISA-12.5@2026-04-18", "why": "T&E quoted-vs-actual invalid"}],
  "hypotheses": [{"id": "H1", "label": "…", "status": "rejected", "evidence_for": [], "evidence_against": []}],
  "confidence": 0.82,
  "explanation_for_cardholder": "…"
}
```
Also produced: investigation plan and re-plans, evidence matrix (fact → source → supports/contradicts), sandbox notebooks (code + outputs), review-panel record (SOP-DSP-003 v6), customer letters, and the run trace (same schema as `memory_seed/run_traces`).

## 10. Ground truth (`generated/ground_truth/`) — evaluator only

### cases/<case_id>.json
`case_id, as_of, code, title, depth, regime, customer_id, txn_ids, summary, expected{…decision record subset…}, key_facts[{id, fact, evidence}], hypotheses[], contradictions[{id, between, resolution}], pivots[], computations[{name, value, rule}], must_cite[], must_not[], memory_ops{read, write, supersede, retract, consolidate}, precedents{distinguish, outdated}, acceptable_alternatives, components[], deterministic_checks[{path, op, value}], rubric[], budget{expected_tool_calls, early_termination}`.

`deterministic_checks.path` uses a JSONPath-like syntax against the decision record (`network_actions[?txn_id=='TXN-9000301'].action`); ops: eq, approx, in, contains, contains_text, not_contains, not_contains_any, set_eq.

### Q01_queue.json
Deadline-ranked open backlog: `top_15[{rank, case_id, next_clock, next_deadline, overdue_clocks, expired_rights, regime, stage, hero_code}]`, `all_open[…with all_clocks]`.

### background_labels.jsonl
`case_id, family, true_nature, expected_network_condition, expected_cardholder_outcome, status, historical_decision_correct` — `historical_decision_correct=false` marks closed cases a retrospective QA check would overturn (~7%, plus DSP-2026-04471).

### hero_index.json
IDs of hand-crafted records, so evaluators can separate hero vs background. Never expose to the agent.

## 11. Temporal dimensions

| Timestamp | Meaning | Used for |
|---|---|---|
| `AS_OF` 2026-10-21T13:00Z | simulation "now" | tool visibility, deadlines |
| txn_local_datetime + merchant_timezone | when the cardholder transacted (merchant wall clock) | timezone reasoning, sequence vs security events |
| auth_timestamp_utc | authorization instant | |
| processing_date | clearing | Visa dispute time limits |
| statements.transmitted_at | statement delivery | Reg Z / Reg E 60-day windows |
| disputes.opened_at | notice received | Reg Z 30-day ack / 2-cycle resolution; Reg E business-day clocks |
| dispute_processing_date / response_processing_date | network events | pre-Arb / arbitration deadlines; **CE 3.0 version selection** |
| policy effective_from / effective_to | rule versions | as-of retrieval |
| research captured_at / published_at | what was knowable when | snapshot reasoning |
| memory valid_from / valid_to / created_at / last_accessed_at | belief validity and recency | forgetting, decay |
| available_at (everywhere) | when the record becomes visible | late / out-of-order data |

## 12. Known data-quality issues (deliberate)

| Issue | Where | Why it's there |
|---|---|---|
| Descriptor changes over time; facilitator/marketplace prefixes | merchant_descriptors, C02, C18 | real statements are confusing |
| Same business under two merchant IDs | Quillmark (C19) | entity resolution before consolidation |
| Local times without offsets; merchant vs cardholder time zones | transactions, communications (C14) | deadlines are in someone's local time |
| Processing date ≠ transaction date; weekends | all transactions | time limits count from processing |
| Split clearings that look like duplicates | C04, PRE-0004 contrast | surface rules misfire |
| Credits without original-transaction link, arriving after intake | C18 | refunds rarely reference the ARN |
| Partial delivery address in POD | C12b | Visa requires full address |
| Truncated/hashed IP in merchant evidence | C11 | CE 3.0 format rules |
| Merchant claims that overcount evidence | C09 (device ID + fingerprint), C11 ("CE met") | merchant packets are advocacy |
| Intake miscoding of claim family | C02, C05, C13 | reps pick the nearest code |
| Late and missing packets (`available_at` > AS_OF, `status: not_enrolled`) | C03, C13, C16 | evidence arrives on its own schedule |
| Conflicting statements across contacts | C04, C09, C10, C15 | people misremember and sometimes lie |
| Stale, wrong, duplicate, noisy and prohibited memory notes | memory_seed | memory must be governed |
| Flawed historical decisions | PRE-0031, ~7% of closed background cases | precedent isn't truth |
| Customer attributes that must not be used | birth_year, employer, ZIP | fairness guardrails |
