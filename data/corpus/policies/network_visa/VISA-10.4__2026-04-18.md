---
doc_id: "VISA-10.4@2026-04-18"
title: "10.4 Other Fraud – Card-Absent Environment (in force 18 Apr – 23 Oct 2026)"
source_type: "network_rule"
authority: "Visa"
section_ref: "11.7.5"
rule_ids: "0030252–0030257"
edition: "Visa Core Rules and Visa Product and Service Rules, 18 April 2026"
effective_from: "2026-04-18"
effective_to: "2026-10-23"
status: "active"
supersedes: null
superseded_by: "VISA-10.4@2026-10-24"
applies_to: [10.4]
jurisdiction: "global (US Region specifics noted)"
provenance: "paraphrase_of_primary"
source_url: "https://usa.visa.com/dam/VCOM/download/about-visa/visa-rules-public.pdf"
---
# 10.4 Other Fraud – Card-Absent Environment
*Version applies to disputes **processed** on or before **23 October 2026**.*

**Reason:** cardholder denies authorization of or participation in a card-absent transaction.
**Rights:** issuer must **report the fraud activity to Visa before initiating** the dispute. (US domestic: applies regardless of ECI for MCCs 4829, 5967, 6051, 6540, 7801, 7802, 7995.)
**Time limit:** 120 calendar days from the transaction processing date.
**Processing:** certification that the cardholder denies authorization or participation.

## Invalid disputes (selected)
- Transaction approved using a credential the issuer had **already reported as fraud** (except fraud types C, D or declines).
- Account with **more than 35 disputes in the previous 120 days** (MCSN clearings from one authorization count as one).
- CVV2 result **U** with CVV2 presence indicator **1** (effective for disputes processed on/after 18 April 2026).
- Secure e-commerce with **ECI 5**, issuer authentication confirmation via Visa Secure (EMV 3DS) and **CAVV** in the authorization.
- Tokenized (TAVV) transaction with ECI 5 and approved cardholder verification.
- **ECI 6** attempt with CAVV, where the issuer/Visa returned an attempt response (not non-reloadable prepaid).
- Fraud reported with type 3 (fraudulent application), C (merchant misrepresentation) or D (manipulation of account holder).
- Crypto/NFT where the cardholder participated but claims they were deceived into sending to a fraudulent recipient.
- **CVV2 presence 1, CVV2 result N, and the issuer approved** the authorization.
- **Compelling Evidence 3.0 (this version):** the **same Payment Credential** was used in **2 previous transactions** not reported as fraud,
  processed **more than 120 days** before and **not more than 365 days** before the dispute processing date, **and**
  - a detailed description of goods/services for the disputed and both prior transactions is provided (or a purchase order number for
    Visa Secure ECI 7 + CAVV transactions), **and**
  - the **device ID, device fingerprint, or IP address** *plus one or more* of the following match between the prior and disputed transactions:
    - customer account/login ID — unique, recognizable by the cardholder, **clear text, not hashed**
    - **full** delivery address — street, city, state, postal code, country; clear text
    - device ID — cardholder-verifiable unique ID (e.g. IMEI), **≥15 characters**, clear text
    - device fingerprint — derived from ≥2 hardware/software properties, **≥20 characters**, may be hashed
    - IP address — the cardholder's **public** IPv4/IPv6 address, **clear text, not hashed**, industry format
- US domestic: airline/rail with AVS Y and tickets mailed to billing address; AVS result U after acquirer attempted AVS (conditions apply).

*Operational note (Lanternfield Dispute Policy Desk):* Visa's October 2026 change summary describes the next version as extending CE 3.0 to
**multi-merchant** prior transactions; the prior-transaction test in this version is applied as **same merchant**.
