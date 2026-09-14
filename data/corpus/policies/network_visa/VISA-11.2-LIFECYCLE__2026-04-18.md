---
doc_id: "VISA-11.2-LIFECYCLE@2026-04-18"
title: "Dispute lifecycle, stages and time limits"
source_type: "network_rule"
authority: "Visa"
section_ref: "11.1–11.3"
rule_ids: "0030207–0030216"
edition: "Visa Core Rules and Visa Product and Service Rules, 18 April 2026"
effective_from: "2026-04-18"
effective_to: null
status: "active"
supersedes: null
superseded_by: null
applies_to: [all_conditions]
jurisdiction: "global (US Region specifics noted)"
provenance: "paraphrase_of_primary"
source_url: "https://usa.visa.com/dam/VCOM/download/about-visa/visa-rules-public.pdf"
---
# Visa dispute lifecycle (Allocation vs Collaboration)

## General requirements (11.2.1)
- Dispute **each transaction separately**. An issuer must **not initiate a dispute for the same transaction more than once** (except 10.5).
- When counting any dispute time limit, the processing date of the preceding event is **not** counted as a day.
- If a member does not respond in Visa Resolve Online (VROL) within the time limit, or accepts responsibility, the cycle closes and
  that member is responsible for the last amount received by the other side.
- Issuers must not process invalid disputes and must conduct adequate due diligence (11.1.2). Issuers must extend cardholders
  all protections under applicable law and customary practices, regardless of Visa card type.
- A member may **reverse** its own action within **31 calendar days** if the other side has not moved to the next stage (11.3.3).
- Arbitration/compliance case may combine **no more than 10 transactions** with the same credential, acquirer, merchant, location and condition.

## Categories 10 (Fraud) and 11 (Authorization) — *Allocation*
| Stage | Who | Time limit |
|---|---|---|
| Dispute | Issuer | per condition |
| Pre-Arbitration attempt | **Acquirer** | 30 days from Dispute processing date |
| Pre-Arbitration response | Issuer | 30 days from pre-Arb processing date |
| Arbitration | **Acquirer** | 10 days from pre-Arb response processing date |

There is **no Dispute Response stage** in Allocation. To decline an acquirer pre-Arb supported by Compelling Evidence, the issuer must
certify either that the contact information in the evidence does not match its cardholder records, **or** that it contacted the
cardholder to review the evidence and records why the cardholder still disputes. If evidence shows delivery to the address with
AVS result Y, the issuer must explain why AVS returned Y. Not applicable if the merchant accepted via Rapid Dispute Resolution.

## Categories 12 (Processing Errors) and 13 (Consumer Disputes) — *Collaboration*
| Stage | Who | Time limit |
|---|---|---|
| Dispute | Issuer | per condition |
| Dispute Response | Acquirer | 30 days from Dispute processing date |
| Pre-Arbitration attempt | **Issuer** | 30 days from Dispute Response processing date |
| Pre-Arbitration response | Acquirer | 30 days from pre-Arb processing date |
| Arbitration | **Issuer** | 10 days from pre-Arb response processing date |

Issuer pre-Arb grounds: new documentation; change of condition (only if the original condition was valid and the acquirer's response
supports the new condition); cardholder still disputes after acquirer claimed otherwise; and where the acquirer's response meets the
condition's response requirements the issuer **must certify it contacted the cardholder to review the evidence** and why they still dispute.

## Credits processed before the dispute (11.2.2 / 11.2.3)
If a credit was processed before the dispute, the issuer must apply it to the disputed transaction or identify it and explain why it
does not resolve the dispute. A credit whose details don't match the sale may only be applied to a transaction not older than 120 days.

## FX loss after dispute
The issuer may pursue pre-Arbitration under the same condition if, **after the dispute was initiated**, the merchant credited the full
amount in the merchant's local currency and the issuer lost money on the exchange-rate difference.
