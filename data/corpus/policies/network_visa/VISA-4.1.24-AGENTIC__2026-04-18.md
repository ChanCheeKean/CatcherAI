---
doc_id: "VISA-4.1.24-AGENTIC@2026-04-18"
title: "Agentic Payment Providers and Agentic Transactions"
source_type: "network_rule"
authority: "Visa"
section_ref: "4.1.24; Glossary"
rule_ids: "0031163–0031174, 0031236"
edition: "Visa Core Rules and Visa Product and Service Rules, 18 April 2026"
effective_from: "2026-04-18"
effective_to: null
status: "active"
supersedes: null
superseded_by: null
applies_to: [agentic_transactions]
jurisdiction: "global (US Region specifics noted)"
provenance: "paraphrase_of_primary"
source_url: "https://usa.visa.com/dam/VCOM/download/about-visa/visa-rules-public.pdf"
---
# Agentic platform requirements (selected)
**Agentic Payment Provider (APP):** an application used by a cardholder to carry out tasks electronically on their behalf that can search,
discover and purchase goods/services upon a cardholder's payment instruction and cardholder verification; can be used at more than one
merchant; stores/transmits a Token; transfers the token to the merchant to complete the transaction; is not involved in authorization,
clearing or settlement. **Initiators of agentic transactions are not considered Merchants** for the purposes of the Visa Rules.
Neither an Agentic Payment Enabler nor an APP is classified as a Visa "Agent".

## APP obligations
- Enroll in the **Visa Intelligent Commerce** program; use a Visa token for stored credentials; not aggregate multiple agentic transactions;
  no card-present agentic transactions; only transact where the cardholder selected a Visa credential.
- **Before transacting:** obtain cardholder consent to tokenize and to use the **cardholder-defined payment instruction**; clearly state the
  instruction's **expiration date**; **obtain cardholder acknowledgement that they are responsible for actions taken by the APP**; verify the
  cardholder's identity before storing the credential and before acting on the instruction. For stored credentials, express informed consent
  to terms (last 4 digits, how notified of changes, how used, expiration, trial length). **Retain this information for the duration of the
  agreement and provide it to the cardholder or Issuer upon written request.**
- **When transacting:** **use only the cardholder-defined criteria** for purchasing; pass cardholder name, billing/shipping address, email.
- **Accepting merchant policies on the cardholder's behalf (4.1.24.6):** obtain consent/acknowledgement for limited cancellation/refund policies,
  advance-payment cancellation dates, guaranteed-reservation cancel-by dates, delayed/amended charges, estimated authorizations, upsells —
  **either at final checkout** (clear disclosure, consent before initiating) **or at the time the instruction is captured** (consent to complete
  without further acknowledgement).
- **After transacting (4.1.24.8):** make an order confirmation available **for at least 120 days** from processing, including description,
  merchant contact details, total price, currency, cancellation/refund policies; for repeated agentic transactions, that they continue until
  the cardholder cancels or changes instructions.

## Disputes
The dispute chapter (section 11) contains **no dispute condition specific to agentic transactions**. The only agentic reference in chapter 11 is
that, from 24 October 2026, **login IDs for an Agentic Payment Provider** may be used as a CE 3.0 data element (see VISA-10.4@2026-10-24).
