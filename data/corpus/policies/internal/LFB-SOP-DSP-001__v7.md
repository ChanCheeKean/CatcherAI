---
doc_id: "LFB-SOP-DSP-001@v7"
title: "Dispute intake, classification and routing"
source_type: "internal_sop"
authority: "Lanternfield Bank, N.A. (fictional)"
owner: "Disputes Operations"
version: "7"
effective_from: "2026-03-01"
effective_to: null
status: "active"
supersedes: null
superseded_by: null
applies_to: [all]
jurisdiction: "US"
provenance: "fictional_internal"
---
# SOP-DSP-001 Intake, classification and routing (v7)
1. **Regime.** Credit card accounts → Regulation Z. Debit/prepaid on deposit accounts → Regulation E. Record `regime` at intake.
2. **Is it a dispute?** Before creating a network dispute, rule out: unrecognized **descriptor** (merchant name change, payment facilitator or
   marketplace prefix); pending authorization; **credit already posted** (search credits by merchant, amount and date, including credits posted
   after intake and credits without an original-transaction link); split shipments (same authorization, multiple clearing sequence numbers).
3. **Fraud vs non-fraud.** Network rules treat these as mutually exclusive. If the cardholder's narrative mixes both ("I didn't order it, and I
   cancelled it anyway"), clarify before choosing. Record the claim family the **cardholder** describes and the candidate condition separately.
4. **One network dispute per transaction.** Intake may group transactions; investigation and filing must be per transaction.
5. **Candidate condition map** (candidate only — always check the condition's invalid-dispute list and the version in force):
   | Claim family | Candidates |
   |---|---|
   | unauthorized card-absent | 10.4 |
   | unauthorized card-present | 10.1 / 10.2 / 10.3 |
   | not received / partially received | 13.1 |
   | cancelled subscription | 13.2; if trial/intro offer not clearly disclosed → 13.5 |
   | defective / not as described | 13.3 |
   | cancelled or returned; policy not honored | 13.7 |
   | refund promised, not processed | 13.6 |
   | charged twice | 12.6 |
   | wrong amount (processing error) | 12.5 (not for T&E quoted-vs-actual or price disputes) |
   | price different from what was agreed | usually **no** processing-error condition; consider 13.5, pre-dispute merchant contact, or Reg Z billing error without network recourse |
6. **Secure-channel intake** (secure online banking or secure telephone banking) allows issuer certification in lieu of a signed letter.
7. **Temporary credit (Reg Z).** Post within 2 business days when the notice is timely, the claim describes a billing error type, and no hold
   applies. Holds: descriptor inquiries; novel transaction types without an applicable rule (e.g. agentic transactions); accounts under an
   automated evidence-first control (SOP-DSP-003 §6); claims already resolved by merchant credit.
8. **Automated work queues:** `fraud_cnp`, `fraud_card_present`, `consumer_disputes`, `reg_e_disputes`, `automated_review_panel`.
   Outputs consumed by other systems (no human queues): `fraud_watchlist_feed`, `policy_gap_log`.
