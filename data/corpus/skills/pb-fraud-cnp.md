---
name: "pb-fraud-cnp"
description: "Investigate card-absent unauthorized-use claims (Visa 10.4; Reg Z 12(b)/13; Reg E 6/11)"
triggers: [fraud_cnp, unauthorized online]
uses_policies: [VISA-10.4@2026-04-18, VISA-10.4@2026-10-24, REGZ-1026.12, REGE-1005.6, LFB-SOP-DSP-008@v3]
provenance: "fictional_internal"
version: "1"
---
# Playbook: card-not-present fraud
1. Regime and liability rules (Reg Z $50 cap / Reg E tiers only if card lost or stolen).
2. Authentication at authorization: ECI, CAVV, 3DS status, CVV2 presence/result, AVS → any **invalid-dispute** triggers (ECI 5 + CAVV; CVV2 N approved).
3. Issuer security events in the 72 hours before the transaction: phone/email changes, password resets, new devices, VPN/hosting IPs → ATO hypothesis.
4. Merchant evidence: login, IP, device, ship-to, account changes before order. Validate **format** (full clear-text IP, full address, device ID length).
5. CE 3.0: select the version by projected dispute processing date; count prior transactions (>120 days, ≤365 days; same merchant vs multi-merchant
   same acquirer); count elements (device ID and fingerprint are one element in the new version).
6. Keep **H1 first-party / household** and **H2 third-party / ATO** open until evidence separates them. Write both down.
7. Fraud report (TC40) before dispute; recovery threshold per SOP-DSP-008; cardholder outcome is independent of recovery.
8. Compromise point: common card-present merchants among recent fraud victims (graph/SQL).
