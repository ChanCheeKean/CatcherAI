---
name: "pb-lodging-te"
description: "Investigate hotel and T&E disputes (folios, no-shows, fees)"
triggers: [hotel, lodging, no-show, folio]
uses_policies: [VISA-13.7@2026-04-18, VISA-12.5@2026-04-18, VISA-13.3@2026-04-18, VISA-13.1@2026-04-18, VISA-11.4-AMOUNTS-CREDITS-FX@2026-04-18]
provenance: "fictional_internal"
version: "1"
---
# Playbook: lodging / T&E
1. Decompose the folio into lines; classify each: disclosed, acknowledged (initials/signature), or unsupported.
2. 12.5 is invalid for quoted-vs-actual T&E differences; 13.3 is invalid for price discrepancies — route line items to the condition that actually fits
   (e.g. 13.1 portion not provided) or to pre-dispute merchant contact.
3. No-shows: cancellation deadline in **hotel local time**; convert cardholder-reported times; billing more than one night is independently improper.
4. Corroborate with the cardholder's own card activity (ride-hail, parking, airline) — never with assumptions.
5. Minimum dispute amount for T&E: USD 25.
