---
doc_id: "LFB-SOP-DSP-003@v6"
title: "Automated decision governance (no human in the loop)"
source_type: "internal_sop"
authority: "Lanternfield Bank, N.A. (fictional)"
owner: "Disputes Operations"
version: "6"
effective_from: "2026-10-01"
effective_to: null
status: "active"
supersedes: "LFB-SOP-DSP-003@v5"
superseded_by: null
applies_to: [all]
jurisdiction: "US"
provenance: "fictional_internal"
---
# SOP-DSP-003 Automated decision governance (v6)
Effective **2026-10-01**. Replaces v5 (human review). All dispute decisions are made **and executed** by the automated dispute system.
**No case waits for human input.**

## 1. Suspension is only for external events
A run may suspend only while waiting for an **external event with a known or expected arrival**: merchant or provider evidence, a cardholder reply,
a clearing record, or a scheduled follow-up. Before suspending, compute the latest safe decision time = earliest regulatory or network deadline
minus 2 business days. If the event hasn't arrived by then, **decide on the evidence available**, applying §3.

## 2. Automated review panel for high-impact decisions
Run the review panel before recording any of:
1. Denial (in whole or part) of an **unauthorized-use** claim of **$500 or more**, or of any claim where the cardholder contests the issuer's evidence.
2. **Reopening or amending a closed case**.
3. **Authority / household determinations** under Reg Z §1026.12(b).
4. **No applicable network rule** or a **novel transaction type** (e.g. agentic transactions).
5. **Cross-customer abuse findings** (rings, drop addresses, compromise points).

The panel is: a **cardholder advocate** (strongest case for the cardholder), an **issuer/merchant advocate** (strongest case against), an **independent
adjudicator** that decides from the case file, and **verifier checks** (eligibility and invalid-dispute lists, policy versions as of the governing
date, arithmetic via sandbox, citations resolve to evidence, SOP-DSP-004 fairness). Record each position, the decision, the confidence on the
determinative issue, and **the single fact that would flip the decision**.

## 3. Confidence threshold and conservative default
- Required confidence on the determinative issue: **0.75**.
- If confidence remains below 0.75 after the panel: apply the **conservative default** — resolve the **cardholder outcome in the cardholder's favor**
  (credit, or maintain temporary credit as final), **do not file a network dispute unless eligibility is certain**, and set
  `conservative_default_applied = true` with the reason. The issuer absorbs the loss; the customer is never disadvantaged by uncertainty.

## 4. Reopening closed cases
Reopen a closed case automatically when new evidence **contradicts the basis** of the prior decision (e.g. account-takeover indicators, a shared drop
address) **and** the corrected outcome favors the cardholder. Record both decisions and the new evidence. Credit the cardholder (plus related finance
charges). Never initiate a second network dispute for a transaction already disputed; check network time limits before any recovery attempt.

## 5. No applicable rule / novel transaction types
Evaluate Regulation Z / Regulation E billing-error and liability rules directly and decide the cardholder outcome. Network action is `no_dispute`
unless a condition's requirements are fully met. Write a machine-readable `policy_gap` record listing the conditions considered and why each fails.

## 6. Cross-customer abuse: bounded automated controls
Allowed automatically: record the finding in the graph with evidence edges (`status = active`); set an **enhanced-monitoring** flag on linked accounts;
require a **signed cardholder letter and evidence review before temporary credit** on future non-receipt claims from linked accounts; add shared
identifiers (ship-to address, device, compromise-point merchant) to **watchlists** used by real-time fraud rules; enqueue linked open cases for
automated re-review. **Never** close or restrict an account, reverse credits, or deny a claim **on linkage alone** — each case is decided on its own evidence.

## 7. Account security
When takeover indicators are present (unverified contact changes, VPN/hosting-IP logins, password resets preceding the disputed transaction):
lock digital banking pending step-up verification, revert unverified contact changes, reissue the card, and record the actions.

## 8. Decision record
Every decision includes an `adjudication` block (`review_panel_used`, positions, confidence, threshold, `conservative_default_applied`, `flip_fact`)
and the list of `automated_actions` executed.
