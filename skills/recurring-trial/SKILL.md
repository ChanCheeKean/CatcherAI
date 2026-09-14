---
name: recurring-trial
description: Verify 13.2 eligibility and re-plan trial conversions to 13.5 when required.
version: "1"
source: data/corpus/skills/pb-recurring-trial.md
---

# Recurring trial

Load this skill for cancelled subscriptions and trial conversions.

1. Retrieve 13.2, 13.5, and recurring-merchant duties for the intended dispute-processing date.
2. Test cancellation date against transaction date before selecting 13.2.
3. If 13.2 is invalid, record the failed verifier check, update the plan, and evaluate trial disclosures under 13.5.
4. Treat precedents and memory as leads. Distinguish any decision made under a prior rule version.
5. Compute the unused service portion in the sandbox with the explicit day-count convention.
6. Keep cardholder credit and network recovery separate.
