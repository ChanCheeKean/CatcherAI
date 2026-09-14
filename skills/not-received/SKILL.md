---
name: not-received
description: Investigate non-receipt at transaction granularity, including immediate digital delivery.
version: "1"
source: data/corpus/skills/pb-not-received.md
---

# Not received

Load this skill for a `not_received` route.

1. Treat each transaction as a separate eligibility and network-action decision.
2. Establish the promised delivery date or immediate-delivery term from sourced evidence.
3. Check merchant-contact attempts and credits.
4. For low-value claims, retrieve the internal write-off SOP as of intake and apply it per transaction.
5. Use merchant evidence for claims that remain material; never investigate a claim already terminated by the current write-off rule.
6. Cite the current policy version and record why any memory lead was accepted or rejected.
