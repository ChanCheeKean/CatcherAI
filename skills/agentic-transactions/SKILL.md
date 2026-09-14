---
name: agentic-transactions
description: Handle disputes about purchases made by an AI agent without inventing a network rule.
version: "1"
source: data/corpus/policies/network_visa/VISA-4.1.24-AGENTIC__2026-04-18.md
---

# Agentic transactions

Load this skill when the transaction was initiated by an Agentic Payment Provider (APP).

1. Retrieve Visa §4.1.24 as of the notice date; an APP is not a merchant.
2. Evaluate each candidate dispute condition (10.4, 13.1, 13.5, 13.7) and record why it does or does not fit.
3. Request the cardholder instruction record from the APP (written request under §4.1.24) and wait for it on the virtual clock; never decide before a determinative record that is expected before the latest safe decision time.
4. Separate hard constraints from preferences using the record, not the cardholder's recollection alone.
5. If no condition fits, decide the cardholder outcome under Reg Z directly, take no network action, and write a machine-readable policy-gap record (SOP-DSP-003 §5).
6. Route the decision through the automated review panel.
