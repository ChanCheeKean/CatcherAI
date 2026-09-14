---
name: dispute-lifecycle
description: Join disputes already in the network lifecycle and keep each charge on its own stage and clocks.
version: "1"
source: data/corpus/policies/network_visa/VISA-11.2-LIFECYCLE__2026-04-18.md
---

# Dispute lifecycle

1. Load lifecycle events for every related case before planning; never merge charges into one dispute.
2. Compute each track's clocks in the sandbox: pre-arbitration (30 days from the Dispute Response processing date), Visa time limit (120 days), and the Reg Z resolution deadline.
3. Treat a late Dispute Response as new evidence: detect contradictions with the intake statement and re-plan.
4. Before accepting a response or attempting pre-arbitration, contact the cardholder to review the evidence and record that certification.
5. Decide each track independently; a later charge can remain disputable when an earlier one is not.
