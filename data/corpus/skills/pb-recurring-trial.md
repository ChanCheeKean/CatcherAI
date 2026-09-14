---
name: "pb-recurring-trial"
description: "Investigate cancelled subscriptions and free-trial conversions (13.2 / 13.5)"
triggers: [cancelled_recurring, free trial, subscription]
uses_policies: [VISA-13.2@2026-04-18, VISA-13.5@2026-04-18, VISA-5-RECURRING-MERCHANT-DUTIES@2026-04-18]
provenance: "fictional_internal"
version: "1"
---
# Playbook: recurring and trials
1. Transaction type: merchant-initiated recurring vs unscheduled COF vs cardholder-initiated (13.2 invalid for the latter two).
2. Cancellation date vs transaction date (13.2 invalid when cancellation is after the transaction — disputes processed on/after 2026-04-18).
3. Trial/intro offer: did the merchant notify **≥7 days before** the recurring charge with amount, date, and cancellation link? Checkout disclosure?
   If not → 13.5 candidate.
4. Usage after cancellation / after charge (merchant logs).
5. Amount: unused portion — compute with the sandbox and state the day-count convention.
