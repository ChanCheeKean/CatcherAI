---
name: "pb-reg-e-clocks"
description: "Compute Regulation E deadlines and liability for debit disputes"
triggers: [REG_E]
uses_policies: [REGE-1005.11, REGE-1005.6, LFB-SOP-DSP-006@v4, LFB-CB-2025-09]
provenance: "fictional_internal"
version: "1"
---
# Playbook: Reg E clocks
1. Notice date and channel (oral → optional written confirmation within 10 business days).
2. First deposit date → new-account test (transfer within 30 days after first deposit).
3. POS debit / foreign-initiated → 90-day investigation.
4. Business days from bank calendar; day of notice not counted. Use the sandbox.
5. Liability: card lost/stolen? Only then the $50/$500 tiers; otherwise 60-day statement rule.
6. Reversal of provisional credit → notice + 5 business days honoring.
