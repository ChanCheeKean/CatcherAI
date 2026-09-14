---
name: "pb-eligibility-check"
description: "Verify a candidate network condition is valid before arguing merits"
triggers: [any network dispute decision]
uses_policies: [VISA-11.2-LIFECYCLE@2026-04-18]
provenance: "fictional_internal"
version: "1"
---
# Playbook: eligibility before merits
1. Retrieve the candidate condition **as of the date that governs**: dispute processing date (network), notice date (regulation), transaction date only
   where the rule says so. If the projected processing date crosses an effective date, evaluate both versions.
2. Walk the **invalid-dispute list** line by line against the facts. Record each item as `clear`, `triggered`, or `unknown`.
3. Check **time limits and waiting periods** (and their waivers) with the sandbox — never by mental arithmetic.
4. Check **mutual exclusivity** (fraud vs non-fraud) against the cardholder's own words.
5. Check **amount limits** (portion not received, unused portion, value returned).
6. If any item is `triggered`, re-plan: look for another condition, a pre-dispute remedy, or a regulatory remedy without network recourse.
