---
doc_id: "VISA-10.4@2026-10-24"
title: "10.4 Other Fraud – Card-Absent Environment (effective 24 Oct 2026)"
source_type: "network_rule"
authority: "Visa"
section_ref: "11.7.5"
rule_ids: "0030254, 0030257"
edition: "Visa Core Rules and Visa Product and Service Rules, 18 April 2026"
effective_from: "2026-10-24"
effective_to: null
status: "scheduled"
supersedes: "VISA-10.4@2026-04-18"
superseded_by: null
applies_to: [10.4]
jurisdiction: "global (US Region specifics noted)"
provenance: "paraphrase_of_primary"
source_url: "https://usa.visa.com/dam/VCOM/download/about-visa/visa-rules-public.pdf"
---
# 10.4 Other Fraud – Card-Absent Environment
*Version applies to disputes **processed on or after 24 October 2026**. Published in the 18 April 2026 edition's Summary of Changes
("Global Updates to Compelling Evidence 3.0 for Dispute Condition 10.4").*

Reason, rights, time limit (120 days), processing requirements and other invalid-dispute items: unchanged from VISA-10.4@2026-04-18.

## Compelling Evidence 3.0 (this version)
A dispute is invalid if:
- the **same Card or a Payment Credential associated with that Card (e.g. a Token)** was used **at one or more merchants** in **2 previous
  transactions** not reported as fraud, processed **more than 120 calendar days before the Dispute was submitted** (and not more than 365 days
  before the dispute processing date), **and**
- a detailed description (or purchase order number for ECI 7 transactions using Visa Secure with CAVV, Visa Token Service with TAVV,
  or Visa Intelligent Data Exchange match key) is provided for the disputed and both prior transactions, **and**
- the **device ID/fingerprint or IP address** plus one or more of the following match:
  - customer account or login ID used to authenticate at the time of the transaction — **including login IDs for an Agentic Payment
    Provider** and the merchant's site/app; clear text, recognizable by the cardholder
  - full delivery address (clear text)
  - either device ID (≥15 chars, clear text) **or** device fingerprint (≥20 chars, may be hashed)
  - IP address (public, clear text)

**Footnotes that change evidence counting:**
- Device ID and device fingerprint are **considered similar data elements**; an acquirer **may not supply both** as two matches and must
  select another element instead.
- For pre-Arbitration, an acquirer **must only submit transaction data accepted and processed by that acquirer** (prior transactions at
  other merchants count only if processed by the same acquirer).
