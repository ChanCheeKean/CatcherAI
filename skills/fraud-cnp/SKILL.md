---
name: fraud-cnp
description: Investigate card-not-present unauthorized-use claims without treating network liability evidence as truth.
version: "1"
source: data/corpus/skills/pb-fraud-cnp.md
---

# Card-not-present fraud

1. Determine Reg Z or Reg E before applying liability rules.
2. Validate authorization and compelling-evidence fields, including exact IP/address formats.
3. Compare issuer security events with merchant account and device events.
4. Keep first-party, household-authority, third-party fraud and account-takeover hypotheses open until separated by evidence.
5. Select CE 3.0 by projected processing date and treat it only as a network-liability rule.
6. Report fraud before filing 10.4. Apply recovery thresholds separately from cardholder protection.
7. Use graph analysis for compromise points or shared delivery destinations, with evidence-linked and bounded writes only.
