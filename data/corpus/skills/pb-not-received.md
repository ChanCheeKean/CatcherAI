---
name: "pb-not-received"
description: "Investigate goods/services not received (Visa 13.1; Reg Z 13(a)(3))"
triggers: [not_received, partial delivery, late delivery]
uses_policies: [VISA-13.1@2026-04-18, REGZ-1026.13, LFB-SOP-DSP-004@v2]
provenance: "fictional_internal"
version: "1"
---
# Playbook: not received
1. Expected delivery/service date from order evidence; has it passed? If disputed before it, record why.
2. Attempt to resolve with merchant — evidence and dates. Merchant insolvent? (research; waives waiting period).
3. Credits posted since purchase (including unlinked credits after intake).
4. Merchant/carrier evidence: **full** delivery address? photo, GPS, signature? Compare house number / unit to the cardholder's address on file.
5. Same merchant disputes on the same card in 30 days (≥3 → cardholder letter).
6. Graph: is the delivery address, device, or phone shared with other disputing customers? Linkage needs a specific shared identifier.
7. Partial delivery or portion of services → dispute amount = portion not received.
