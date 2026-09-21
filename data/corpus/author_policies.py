"""Authoring source for the policy corpus (network rules, regulation, internal SOPs, bulletins).

Writes one markdown file per document with YAML front matter to data/corpus/policies/.
Run: python3 data/corpus/author_policies.py

Provenance conventions (front matter `provenance`):
  paraphrase_of_primary  — paraphrased from the Visa Core Rules and Visa Product and Service Rules, 18 April 2026 edition
                           (public PDF). Section and rule IDs cited. Not a substitute for the rulebook.
  verbatim_regulation    — US federal regulation text (public domain), lightly abridged.
  fictional_internal     — invented Lanternfield Bank internal document for the POC.
"""
from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
VISA_URL = "https://usa.visa.com/dam/VCOM/download/about-visa/visa-rules-public.pdf"


def fm(**k):
    lines = ["---"]
    for key, val in k.items():
        if isinstance(val, list):
            lines.append(f"{key}: [{', '.join(val)}]")
        else:
            lines.append(f"{key}: \"{val}\"" if val is not None else f"{key}: null")
    return "\n".join(lines + ["---", ""])


DOCS = []


def doc(folder, fname, body, **meta):
    DOCS.append((folder, fname, fm(**meta) + body.strip() + "\n"))


def visa(doc_id, title, section, effective_from, effective_to, status, applies_to, body, supersedes=None, superseded_by=None, rule_ids=""):
    doc("policies/network_visa", doc_id.replace("@", "__") + ".md", body, doc_id=doc_id, title=title, source_type="network_rule",
        authority="Visa", section_ref=section, rule_ids=rule_ids, edition="Visa Core Rules and Visa Product and Service Rules, 18 April 2026",
        effective_from=effective_from, effective_to=effective_to, status=status, supersedes=supersedes, superseded_by=superseded_by,
        applies_to=applies_to, jurisdiction="global (US Region specifics noted)", provenance="paraphrase_of_primary", source_url=VISA_URL)


# =============================================================================================== VISA
visa("VISA-11.2-LIFECYCLE@2026-04-18", "Dispute lifecycle, stages and time limits", "11.1–11.3", "2026-04-18", None, "active",
     ["all_conditions"], """
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
""", rule_ids="0030207–0030216")

visa("VISA-11.4-AMOUNTS-CREDITS-FX@2026-04-18", "Dispute amounts, minimums, currency conversion", "11.4", "2026-04-18", None, "active",
     ["all_conditions"], """
# Dispute amounts
- Dispute amount (billing currency) is the billed amount or a **partial amount equal to the disputed portion**; it must not exceed the
  transaction amount (except 12.2). Partial disputes pro-rate any surcharge.
- Acquirer response / pre-Arb amounts: same amount in transaction currency, a partial amount, or the corrected settlement amount.
- **Currency conversion difference (11.4.2):** the party assigned or accepting final liability bears the difference between the original
  transaction amount and the final dispute amount caused by a change in the conversion rate.
- **Minimum dispute amounts (11.4.3):** T&E transactions — USD 25 for most conditions (not for 10.1–10.5, 13.3 in stated cases, 13.8, 13.9).
  Effective 18 April 2026 either the transaction amount or the partial dispute amount must be at least USD 25. No general minimum applies
  to non-T&E transactions under Visa rules (issuers may set internal thresholds).
""", rule_ids="0030217–0030219")

visa("VISA-11.5.1-COMPELLING-EVIDENCE@2026-04-18", "Allowable Compelling Evidence (pre-Arbitration, conditions 10.1/10.3/10.4)", "11.5.1",
     "2026-04-18", None, "active", ["10.1", "10.3", "10.4"], """
# Allowable Compelling Evidence (acquirer pre-Arbitration)
Selected items (10.4 unless noted):
1. Photo/email linking the recipient to the cardholder, or proving the cardholder possesses/uses the goods or services.
2. In-store pickup: cardholder signature on pickup form, or ID presented.
3. Delivery to the same physical address for which the merchant received **AVS Y or M** (no signature required).
4. **Digital goods:** description + download date + **2 or more** of: IP address; device ID; purchaser name and email linked to merchant
   profile; profile accessed and verified before the transaction; site/app accessed by the cardholder on or after the transaction date;
   same device and payment credential used in an undisputed transaction.
5. Delivery to a business address where the cardholder worked at the time.
6. Mail/phone order: signed order form.
7. Passenger transport: services provided plus ticket to billing address / boarding pass scanned / miles earned or redeemed / add-on purchases.
8. T&E: services provided plus loyalty activity or undisputed related transactions.
10. Card-absent: **3 or more** of {customer account/login ID, delivery address, device ID/fingerprint, email, IP, telephone} used in an
    undisputed transaction.
11. **Evidence the transaction was completed by a member of the cardholder's household or family.**
12. Evidence of one or more non-disputed payments for the same merchandise or service.
13. Recurring: contract with cardholder + cardholder using the goods/services + a previous undisputed transaction.
15. US domestic key-entered card-present (10.1/10.3): same card used in undisputed transactions, or ID + linked receipt.
16. Crypto/NFT: destination wallet, traceable transaction hash, prior undisputed transactions.

Merchants must not require positive identification as a condition of card acceptance unless required by law.
Issuer certification duties when declining such a pre-Arb: see VISA-11.2-LIFECYCLE@2026-04-18.
""", rule_ids="Table 11-6")

visa("VISA-CARDHOLDER-LETTER-CERTIFICATION@2026-04-18", "Cardholder letter vs issuer certification", "11.7.1, 11.10.1", "2026-04-18", None,
     "active", ["10.x", "13.x"], """
# Cardholder letter or issuer certification
- Where a dispute requires certification on behalf of the cardholder, the issuer may certify **only** if it obtained the dispute
  information through a secure method that is a valid representation of the cardholder signature, e.g. **secure online banking**
  (unique identity via password/login) or **secure telephone banking** (same security level as a funds transfer to another institution).
- Otherwise a **signed cardholder letter** including the complete or partial payment credential, merchant name(s) and amount(s).
- Category 10: letter must deny authorization of or participation in the transaction.
""", rule_ids="0030223, 0030224")

visa("VISA-10.4@2026-04-18", "10.4 Other Fraud – Card-Absent Environment (in force 18 Apr – 23 Oct 2026)", "11.7.5", "2026-04-18",
     "2026-10-23", "active", ["10.4"], """
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
""", superseded_by="VISA-10.4@2026-10-24", rule_ids="0030252–0030257")

visa("VISA-10.4@2026-10-24", "10.4 Other Fraud – Card-Absent Environment (effective 24 Oct 2026)", "11.7.5", "2026-10-24", None,
     "scheduled", ["10.4"], """
# 10.4 Other Fraud – Card-Absent Environment
*Version applies to disputes **processed on or after 24 October 2026**. Published in the 18 April 2026 edition's Summary of Changes
("Global Updates to Compelling Evidence 3.0 for Dispute Condition 10.4").*

Reason, rights, time limit (120 days), processing requirements and other invalid-dispute items: unchanged from VISA-10.4@2026-04-18.

## Compelling Evidence 3.0 (this version)
A dispute is invalid if:
- the **same Card or a Payment Credential associated with that Card (e.g. a Token)** was used **at one or more merchants** in **2 previous
  transactions** not reported as fraud, processed **more than 120 calendar days before the Dispute was submitted** (and not more than 365 days
  before the dispute processing date), **and**
- a detailed description (or purchase order number for ECI 7 transactions using Visa Secure with CAVV, Visa Token Service with TAVV,
  or Visa Intelligent Data Exchange match key) is provided for the disputed and both prior transactions, **and**
- the **device ID/fingerprint or IP address** plus one or more of the following match:
  - customer account or login ID used to authenticate at the time of the transaction — **including login IDs for an Agentic Payment
    Provider** and the merchant's site/app; clear text, recognizable by the cardholder
  - full delivery address (clear text)
  - either device ID (≥15 chars, clear text) **or** device fingerprint (≥20 chars, may be hashed)
  - IP address (public, clear text)

**Footnotes that change evidence counting:**
- Device ID and device fingerprint are **considered similar data elements**; an acquirer **may not supply both** as two matches and must
  select another element instead.
- For pre-Arbitration, an acquirer **must only submit transaction data accepted and processed by that acquirer** (prior transactions at
  other merchants count only if processed by the same acquirer).
""", supersedes="VISA-10.4@2026-04-18", rule_ids="0030254, 0030257")

visa("VISA-12.5@2026-04-18", "12.5 Incorrect Amount", "11.9.4", "2026-04-18", None, "active", ["12.5"], """
# 12.5 Incorrect Amount
**Reason:** transaction amount is incorrect or an addition/transposition error occurred (ATM deposit adjustment amount incorrect).
**Rights:** dispute limited to the difference; for handwritten vs imprinted differences, handwritten amount governs.
**Invalid:** ATM cash disbursement; mobile push payment; straight-through processing; **a T&E transaction where there is a difference between
the quoted price and the actual charges made by the merchant**; **no-show transaction**; **advance payment**; **a transaction for which the
merchant has the right to alter the amount without the cardholder's consent after completion**.
**Time limit:** 120 days from transaction processing date.
""", rule_ids="0030296–0030299")

visa("VISA-12.6@2026-04-18", "12.6 Duplicate Processing / Paid by Other Means", "11.9.5", "2026-04-18", None, "active", ["12.6"], """
# 12.6 Duplicate Processing / Paid by Other Means
**Reason:** a single transaction was processed more than once using the same credential **on the same transaction date and for the same
amount**; or the cardholder paid for the same goods/services by other means; or an ATM deposit adjustment processed more than once.
The cardholder must have participated in one of the transactions.
**Rights:** if processed by different acquirers, the acquirer of the invalid transaction is liable; if the issuer cannot tell which,
the acquirer of the **second** transaction. Paid by other means: applies where the merchant accepted a third-party voucher then billed the
cardholder; cardholder must attempt to resolve with the merchant.
**Invalid:** payments to **different merchants** unless payment passed from one to the other (e.g. travel agent → hotel).
**Related rule:** individual clearings with a **Multiple Clearing Sequence Number resulting from the same authorization are treated as one
transaction** (see 10.4 / 13.1 counting footnotes) — a split shipment is not duplicate processing.
**Time limit:** 120 days from processing date.
""", rule_ids="0030302–0030306")

visa("VISA-13.1@2026-04-18", "13.1 Merchandise/Services Not Received", "11.10.2", "2026-04-18", None, "active", ["13.1"], """
# 13.1 Merchandise/Services Not Received
**Reason:** cardholder participated but did not receive the goods/services because the merchant was unwilling or unable to provide them.

## Rights
- Amount limited to the **portion not received**.
- Cardholder must **attempt to resolve with the merchant** (or its liquidator) first.
- Merchant is responsible for goods held in customs in the merchant's country.
- **Late delivery:** cardholder must return or attempt to return the merchandise.
- Europe: insolvent bonded travel providers — claim the bond/insurance scheme first.

## Invalid
ATM cash; STP; **cardholder cancelled before the expected delivery/service date** (buyer's remorse); goods held by the cardholder's country's
customs; **transaction the cardholder states is fraudulent**; **disputes about quality**; partial advance payment when merchant still willing
and able; cash-back portion; automated fuel dispensers; crypto delivered but later inaccessible.

## Time limits
- **Wait 15 calendar days** from: the transaction date if no expected date was specified; the date the cardholder returned/attempted to return
  late merchandise; or the date the merchant cancelled. **MCC 4722 travel agencies and third-party ticket agencies: wait 30 days** from the
  service provider's cancellation.
- Waiting periods do **not** apply if they would push the dispute past the time limit, **or if the merchant is insolvent or bankrupt**.
- Dispute must be processed within **120 days of the transaction processing date** or **120 days from the last date the cardholder expected
  to receive** the goods/services, **not to exceed 540 days** from processing.

## Issuer processing requirements
Certification (as applicable): not received by expected date/time or at agreed location; attempted to resolve; late-delivery return date;
merchant cancellation date. **Detailed description** of goods/services beyond clearing data. Explanation if disputed before the expected
delivery date. **Cardholder letter required if the cardholder has disputed 3 or more transactions for non-receipt at the same merchant on the
same card within the same 30-day period.**

## Acquirer Dispute Response
Credit not addressed; dispute invalid; cardholder no longer disputes; services received at agreed place/time; for merchandise, receipt at
agreed location/time including **proof of delivery containing the full delivery address — tracking with partial address is not permitted**;
pickup acknowledgment; card-present certification; airline flight departed; future services available and not cancelled.

## Issuer pre-Arbitration
Evidence of the promised delivery date; return attempts; agreed later delivery for face-to-face sales; merchant cancellation notice; agreed
address. **Effective for Dispute Responses processed on/after 18 April 2026:** where the merchant provided delivery evidence (full address or
pickup), the issuer must certify it reviewed the information with the cardholder and **address** it (acknowledge photos; address signatures).
""", rule_ids="0030313–0030318, 0031084")

visa("VISA-13.2@PRIOR", "13.2 Cancelled Recurring Transaction (prior edition, through 17 Apr 2026)", "11.10.3", "unknown (prior edition)",
     "2026-04-17", "superseded", ["13.2"], """
# 13.2 Cancelled Recurring Transaction — prior edition
*Applies to disputes processed **through 17 April 2026**. The effective start date of this text is not recorded in the corpus.*

Same as VISA-13.2@2026-04-18 **except** the invalid-dispute list did **not** include "a transaction in which the cardholder's cancellation
was after the date of the transaction."
""", superseded_by="VISA-13.2@2026-04-18", rule_ids="0030321 (prior)")

visa("VISA-13.2@2026-04-18", "13.2 Cancelled Recurring Transaction", "11.10.3", "2026-04-18", None, "active", ["13.2"], """
# 13.2 Cancelled Recurring Transaction
**Reason:** cardholder withdrew permission to charge the credential for a **recurring** transaction (Europe: or installment); or the
acquirer/merchant was notified before processing that the account was closed.
**Rights:** amount limited to the **unused portion** of the service or merchandise.
**Invalid:** mobile push payment; STP; installment (outside Europe); **unscheduled credential-on-file transaction**; **cardholder-initiated
transaction**; transaction the cardholder states is fraudulent; **effective for disputes processed on or after 18 April 2026: a transaction in
which the cardholder's cancellation was after the date of the transaction.**
**Time limit:** 120 days from processing date.
**Issuer certification:** date permission withdrawn; contact details used to reach merchant; other form of payment provided (if any); or date
merchant was notified the credential was closed.
**Acquirer response:** credit not addressed; invalid; no longer disputes; cancellation requested for a **different date** and services provided
until then; merchant bills after services provided and services were received until cancellation; account-closure claim invalid; **cardholder
used services after withdrawing permission and before the dispute processing date** (cancellation date = last date the cardholder may use the service).
**Issuer pre-Arb:** evidence of the actual withdrawal notice date; evidence that post-cancellation use related to a previous transaction.
""", supersedes="VISA-13.2@PRIOR", rule_ids="0030319–0030324")

visa("VISA-13.3@2026-04-18", "13.3 Not as Described or Defective Merchandise/Services", "11.10.4", "2026-04-18", None, "active", ["13.3"], """
# 13.3 Not as Described or Defective
**Reason:** goods/services did not match the transaction receipt or other record at time of purchase; damaged or defective; **cardholder
disputes the quality**. (US/Canada domestic: merchant's verbal description or documentation did not match what was received.)
## Rights
- Amount limited to the unused portion of a cancelled service or the value of merchandise returned / attempted to return.
- Cardholder must attempt to resolve with the merchant (**the cardholder cancellation is considered the attempt to resolve**).
- Cardholder must **return or attempt to return** the merchandise or cancel the services before the dispute. **An attempt to return is valid only
  when the merchant** refused the return; refused to provide a return authorization/label; told the cardholder not to return; no longer exists
  or is not responding; or gave no clear return instructions.
- For services already rendered, the cardholder must request a credit.
## Invalid
ATM cash; STP; VAT disputes; returned goods held by customs outside the merchant's country; **cardholder states fraud**; cash-back; AFD;
**quality of food at restaurants**; crypto not increasing in value; **a dispute regarding a price discrepancy**.
## Time limits
Wait **15 days** from the return/attempted return/cancellation date (not if it would exceed the time limit **or if the merchant refuses the
cancellation or return**). Process within 120 days of processing date or of the date the cardholder received the goods/services, or 60 days
from first cardholder notice if there's evidence of negotiations within 120 days of processing; max 540 days.
""", rule_ids="0030325–0030328")

visa("VISA-13.5@2026-04-18", "13.5 Misrepresentation", "11.10.6", "2026-04-18", None, "active", ["13.5"], """
# 13.5 Misrepresentation
**Reason:** cardholder claims the terms of sale were misrepresented by the merchant.
## Rights
- Amount limited to the **unused portion of the cancelled service** or value of merchandise returned / attempted to return.
- Cardholder must attempt to resolve with the merchant (or liquidator). Merchant responsible for goods in its own country's customs.
- Applies to (selected): **card-absent purchases of merchandise or digital goods through a trial period, promotional period or introductory offer
  (or as a one-off purchase) where the cardholder was not clearly advised of further transactions after the purchase date**; timeshare resellers;
  card-absent debt/credit repair and similar services; tech support/software sold with inaccurate ads or malware; business opportunities
  promising income; fund-recovery scams; outbound telemarketing; investment platforms refusing withdrawals.
## Invalid
STP; VAT; **disputes related solely to quality**; cash-back.
""", rule_ids="0030337–0030339")

visa("VISA-13.6@2026-04-18", "13.6 Credit Not Processed", "11.10.7", "2026-04-18", None, "active", ["13.6"], """
# 13.6 Credit Not Processed
**Reason:** cardholder received a credit or voided transaction receipt that was not processed (ATM: disputes validity of an adjustment).
**Rights:** applies if a "void" or "cancelled" notation appears on the receipt.
**Invalid:** mobile push; STP; cash-back portion; AFD; **cardholder states fraud**.
**Time limit:** wait 15 days from the date on the credit receipt (not if undated or if it would exceed the limit); process within 120 days of the
credit receipt date (undated: date cardholder cancelled/returned), max 540 days from processing.
*Note:* a credit that **was** processed — even if its USD value differs because of exchange-rate movement — is not "credit not processed".
""", rule_ids="0030343–0030346")

visa("VISA-13.7@2026-04-18", "13.7 Cancelled Merchandise/Services", "11.10.8", "2026-04-18", None, "active", ["13.7"], """
# 13.7 Cancelled Merchandise/Services
**Reason (all of):** cardholder cancelled or returned merchandise, cancelled services, cancelled a timeshare, or **cancelled a Guaranteed
Reservation**; merchant did not process a credit or voided receipt; and the merchant **did not properly disclose, or disclosed but did not apply,
a limited return or cancellation policy** at the time of the transaction (Europe: 14-day distance-selling cancellation right).
## Rights
- If shipped before cancellation, cardholder must return the goods if received. Amount limited to unused portion / value of returned goods.
- Applies if returned merchandise is refused by the merchant.
- Timeshare: incorrect MCC; or cancelled within 14 days of contract/document receipt.
- **Guaranteed Reservation:** applies if the cardholder cancelled per the cancellation policy but was billed a **No-Show**; if the merchant billed a
  No-Show for **more than one day's accommodation or rental** (plus taxes) when a Guaranteed Reservation was cancelled or unclaimed; if the
  cardholder attempted to cancel within 24 hours of delivery of the reservation confirmation but was billed a No-Show.
- Cardholder must attempt to resolve with the merchant (cancellation counts as the attempt).
## Invalid
ATM; STP; quality disputes (unless a credit receipt is provided); VAT (unless credit receipt); returned goods held in non-merchant-country
customs; cash-back; **cardholder states fraud**; AFD.
## Time limits
Wait **15 days** from return/cancellation (not if it exceeds the limit or merchant refuses cancellation/return). Process within 120 days of
processing date or of expected/actual receipt date (max 540 days).
## Issuer certification — Guaranteed Reservation
Merchant processed a No-Show; date of expected services; and one of: date the cardholder properly cancelled; date of cancellation attempt within
24h of confirmation; or merchant billed more than one day. For goods: description; expected/received date; cancel/return date; shipping details;
for attempted returns, certification the merchant refused or said not to return, plus disposition of the merchandise.
## Acquirer response
Credit not addressed; invalid; no longer disputes; receipt/record proving the limited policy was properly disclosed at the time of the transaction;
cardholder received the policy and did not cancel according to it.
""", rule_ids="0030349–0030355")

visa("VISA-5-RECURRING-MERCHANT-DUTIES@2026-04-18", "Merchant duties for recurring transactions and trials", "5.8.11.1 (Table 5-21)",
     "2026-04-18", None, "active", ["13.2", "13.5"], """
# Recurring transactions — merchant requirements (selected)
The merchant must:
- provide a **simple cancellation procedure**, and **at least an online cancellation procedure** if the order was accepted online;
- include the fixed dates or intervals on which recurring transactions will be processed;
- **at least 7 days before a recurring transaction, notify the cardholder** (email or other agreed method) if **a trial period, introductory
  offer or promotional period is going to end**, including the **transaction amount and transaction date** of subsequent recurring transactions
  and **a link or other simple mechanism to cancel online or by SMS**.
- Europe: also notify if more than 6 months have elapsed or the agreement changed; display merchant name, description, trial length and amounts
  on the credential-entry page and checkout.

Advance payments (entire amount before delivery) are allowed only for T&E, custom goods/services, face-to-face partial availability, and
tourism/travel activities; T&Cs must specify the shipping date.
""")

visa("VISA-4.1.24-AGENTIC@2026-04-18", "Agentic Payment Providers and Agentic Transactions", "4.1.24; Glossary", "2026-04-18", None, "active",
     ["agentic_transactions"], """
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
""", rule_ids="0031163–0031174, 0031236")

# =============================================================================================== REGULATION
def reg(doc_id, title, cite, body, url, applies):
    doc("policies/regulation", doc_id + ".md", body, doc_id=doc_id, title=title, source_type="regulation", authority="CFPB (US federal)",
        section_ref=cite, effective_from="in force", effective_to=None, status="active", applies_to=applies, jurisdiction="US",
        provenance="verbatim_regulation", source_url=url)


reg("REGZ-1026.13", "Regulation Z §1026.13 Billing error resolution", "12 CFR 1026.13", """
# §1026.13 Billing error resolution (abridged)
**(a) Billing error** means: (1) a reflection on a periodic statement of an extension of credit that is **not made to the consumer or to a
person who has actual, implied, or apparent authority** to use the card; (2) credit not identified as required; (3) credit for property or
services **not accepted by the consumer or not delivered to the consumer as agreed**; (4) failure to credit properly a payment or other credit;
(5) computational or similar error of an accounting nature; (6) credit for which the consumer requests clarification including documentary
evidence; (7) failure to mail or deliver a periodic statement to the last known address (if change of address received ≥20 days before cycle end).

**(b) Billing error notice** is a written notice that is received at the address disclosed for that purpose **no later than 60 days after the
creditor transmitted the first periodic statement that reflects the alleged billing error**; enables identification of the name and account
number; and indicates the belief and reasons that a billing error exists, and the type, date and amount.

**(c) Time for resolution:** mail or deliver **written acknowledgment within 30 days** of receiving a notice (unless resolved sooner); comply with
the resolution procedures **within 2 complete billing cycles (but in no event later than 90 days)** after receiving the notice.

**(d) Rules pending resolution:** the consumer need not pay, and the creditor may not collect, the disputed amount and related finance charges;
the creditor may not make or threaten an **adverse credit report** because of non-payment of the disputed amount; the creditor **may not accelerate
the debt or restrict or close the account solely** because the consumer exercised these rights.

**(e) Error occurred as asserted:** correct the error and credit related finance charges, and notify the consumer.

**(f) No error / different error:** after a reasonable investigation, mail or deliver an **explanation of the reasons** for the belief the error
is incorrect (in whole or part), and **furnish copies of documentary evidence on request**; if a different error occurred, correct it.
(f)(3) **Reasonable investigation:** (i) *unauthorized use* — see interpretation; (ii) *non-delivery* — the creditor **shall not deny** the assertion
**unless it conducts a reasonable investigation and determines that the property or services were actually delivered, mailed, or sent as agreed**;
(iii) incorrect information from a merchant — reasonable investigation required.

**(g) Creditor's rights after resolution:** notify the consumer of the amount owed and time to pay (including any grace period disclosed);
may report delinquency only after the grace period; if the consumer re-disputes within that time, may not report as delinquent without also
reporting the amount is in dispute.
**Forfeiture:** failure to comply may result in forfeiture under 15 U.S.C. 1666(e) (up to $50 per error).
""", "https://www.consumerfinance.gov/rules-policy/regulations/1026/13/", ["REG_Z", "credit"])

reg("REGZ-1026.13-INTERP", "Regulation Z official interpretation to §1026.13 (selected)", "12 CFR 1026 Supp. I, 13", """
# Official interpretation — §1026.13 (selected)
- **13(a)(3):** covers property or services delivered in the wrong quantity, late, or to the wrong location. A consumer is **not required to
  first notify the merchant** before providing a billing-error notice.
- **13(b)(1):** if statements are held for the consumer, a statement is "transmitted" when first made available.
- **13(f)(3) Reasonable investigation — unauthorized use.** Steps a creditor may take include: reviewing the types or amounts of purchases in
  relation to the consumer's previous purchasing pattern; reviewing where purchases were delivered in relation to the consumer's residence or
  place of business; reviewing where purchases were made in relation to where the consumer resides or normally shops; comparing signatures;
  requesting documentation to assist verification; requesting a written, signed statement; requesting a copy of a police report if one was filed;
  requesting information regarding the consumer's knowledge of the person who allegedly used the card.
- The creditor **may not require the consumer to provide an affidavit or signed statement under penalty of perjury**, and **may not automatically
  deny a claim based solely on the consumer's failure or refusal to comply** with a particular request. However, if the creditor otherwise has
  **no knowledge of facts confirming the billing error**, the lack of information resulting from non-cooperation may be the basis for concluding
  the investigation.
- The consumer's rights under §1026.13 are independent of §1026.12(b) and (c).
""", "https://www.consumerfinance.gov/rules-policy/regulations/1026/Interp-13", ["REG_Z", "credit"])

reg("REGZ-1026.12", "Regulation Z §1026.12(b)-(c) Unauthorized use liability; claims and defenses", "12 CFR 1026.12(b),(c) + Supp. I", """
# §1026.12(b) Liability of cardholder for unauthorized use
- **Unauthorized use** means use of a credit card by a person, other than the cardholder, **who does not have actual, implied, or apparent
  authority** for such use, **and from which the cardholder receives no benefit**.
- Liability shall not exceed the **lesser of $50** or the amount obtained before notification to the issuer (and only if conditions are met:
  accepted card, adequate notice of liability, means of identifying the cardholder/authorized user).
- **Comment 12(b)(1)(ii)-3:** where a cardholder **furnishes a card to another person** (e.g. family member, coworker) **and that person exceeds the
  authority given**, the cardholder is liable for the use **unless the cardholder has notified the issuer that use by that person is no longer
  authorized**.
- **Comment 12(b)-3 (reasonable investigation):** same investigative steps as §1026.13(f)(3) interpretation; no affidavit under penalty of perjury.

# §1026.12(c) Right of cardholder to assert claims or defenses against card issuer
- When a person who honors the card fails to resolve a dispute about property or services purchased with the card, the cardholder may assert
  against the issuer **all claims (other than tort claims) and defenses** arising out of the transaction, and **withhold payment up to the amount of
  credit outstanding for the property or services that gave rise to the dispute** and related finance charges, if:
  (i) the cardholder made a **good-faith attempt** to resolve with the merchant; (ii) the amount of credit extended exceeds **$50**; and (iii) the
  first card transaction occurred **in the same state as the cardholder's address or within 100 miles** of it. Limits (ii)-(iii) do not apply if
  the merchant is the issuer, is controlled by or under common control with the issuer, is a franchised dealer in the issuer's products, or obtained
  the order through a mail solicitation in which the issuer participated.
- Disputed amount shall not be reported as delinquent until the dispute is settled or judgment is rendered.
- **Comment 12(c)-4 (amount outstanding):** payments and other credits must be applied first to amounts other than the disputed transaction; for
  non-home-secured accounts, alternatively to late charges, then finance charges, then other debits in the order entered (excluding the disputed
  transaction). **If the disputed purchase has been paid, there is no credit outstanding to withhold.**
- **Location of mail, telephone or internet transactions** is determined under state or other applicable law.
- Good-faith attempt requires no special procedure; a matter of fact in each case.
""", "https://www.consumerfinance.gov/rules-policy/regulations/1026/12/", ["REG_Z", "credit"])

reg("REGE-1005.11", "Regulation E §1005.11 Procedures for resolving errors", "12 CFR 1005.11", """
# §1005.11 Error resolution (abridged)
**(a) Error** includes an **unauthorized electronic fund transfer**; incorrect transfer; omission from a statement; computational error; receipt of
incorrect cash; consumer's request for documentation or clarification.

**(b) Notice of error:** received **no later than 60 days after the institution sends the periodic statement** on which the error is first
reflected. The institution **may require written confirmation within 10 business days of an oral notice** (if it informs the consumer and
provides the address).

**(c) Time limits:**
1. Investigate and determine whether an error occurred within **10 business days** of receiving notice; report results within **3 business days**
   after completing; correct within 1 business day after determining an error occurred.
2. Alternatively, take up to **45 calendar days** if the institution **provisionally credits** the consumer's account **within 10 business days**
   of receiving notice (may withhold up to $50 if it has a reasonable basis to believe an unauthorized transfer occurred and §1005.6(a) applies);
   informs the consumer within 2 business days of the provisional credit; gives full use of the funds. If written confirmation was required and
   not received within 10 business days, provisional credit is not required.
3. **Extended periods:** (i) **20 business days** replace 10 business days if the notice involves an EFT to or from an account **within 30 days
   after the first deposit to the account was made**; (ii) **90 calendar days** replace 45 days if the transfer **was not initiated within a state,
   resulted from a point-of-sale debit card transaction, or occurred within 30 days after the first deposit to the account**.

**(d) Procedures if no error or a different error:** written explanation within 3 business days after concluding; notify of right to request
documents. **Debiting provisional credit:** notify the consumer of the date and amount of the debit and that the institution **will honor checks,
drafts, or similar instruments payable to third parties and preauthorized transfers for five business days after the notification**
(to the extent they would have been paid if the provisional credit had not been debited).

**(e) Reassertion:** an institution that has fully complied has no further responsibilities if the consumer later reasserts the same error
(except requests for documentation).
""", "https://www.consumerfinance.gov/rules-policy/regulations/1005/11/", ["REG_E", "debit"])

reg("REGE-1005.6", "Regulation E §1005.6(b) Limitations on liability", "12 CFR 1005.6(b)", """
# §1005.6(b) Consumer liability for unauthorized EFTs
1. **Timely notice given.** If the consumer notifies the institution **within two business days after learning of the loss or theft of the access
   device**, liability shall not exceed the lesser of **$50** or the amount of unauthorized transfers before notice.
2. **Timely notice not given.** If the consumer fails to notify within two business days **after learning of the loss or theft of the access device**,
   liability shall not exceed the lesser of **$500** or the sum of (i) $50 or the amount of unauthorized transfers within the two business days,
   whichever is less, and (ii) the amount of unauthorized transfers after the two business days and before notice (if the institution establishes
   they would not have occurred had notice been given).
3. **Periodic statement; timely notice not given.** The consumer must report an unauthorized EFT **that appears on a periodic statement within 60
   days of the statement's transmittal** to avoid liability for **subsequent** transfers. If not, liability for transfers after the 60 days and before
   notice (that would not have occurred with timely notice) — in addition to any liability under (1) or (2) if an access device was involved.
4. **Extension of time limits** for extenuating circumstances (e.g. extended travel, hospitalization).

*Interpretive note:* tiers (1) and (2) are triggered by **loss or theft of an access device**. Where the card remains in the consumer's
possession (e.g. skimmed card data, card-not-present misuse), only (3) can impose liability, and only for transfers after the 60-day period.
""", "https://www.consumerfinance.gov/rules-policy/regulations/1005/6/", ["REG_E", "debit"])

# =============================================================================================== INTERNAL (fictional)
def internal(doc_id, title, version, effective_from, effective_to, status, body, supersedes=None, superseded_by=None, owner="Disputes Operations",
             applies=("all",), folder="policies/internal"):
    doc(folder, doc_id.replace("@", "__") + ".md", body, doc_id=doc_id, title=title, source_type="internal_sop" if "SOP" in doc_id else
        ("internal_bulletin" if "CB-" in doc_id else "cardholder_agreement"), authority="Lanternfield Bank, N.A. (fictional)", owner=owner,
        version=version, effective_from=effective_from, effective_to=effective_to, status=status, supersedes=supersedes,
        superseded_by=superseded_by, applies_to=list(applies), jurisdiction="US", provenance="fictional_internal")


internal("LFB-SOP-DSP-001@v7", "Dispute intake, classification and routing", "7", "2026-03-01", None, "active", """
# SOP-DSP-001 Intake, classification and routing (v7)
1. **Regime.** Credit card accounts → Regulation Z. Debit/prepaid on deposit accounts → Regulation E. Record `regime` at intake.
2. **Is it a dispute?** Before creating a network dispute, rule out: unrecognized **descriptor** (merchant name change, payment facilitator or
   marketplace prefix); pending authorization; **credit already posted** (search credits by merchant, amount and date, including credits posted
   after intake and credits without an original-transaction link); split shipments (same authorization, multiple clearing sequence numbers).
3. **Fraud vs non-fraud.** Network rules treat these as mutually exclusive. If the cardholder's narrative mixes both ("I didn't order it, and I
   cancelled it anyway"), clarify before choosing. Record the claim family the **cardholder** describes and the candidate condition separately.
4. **One network dispute per transaction.** Intake may group transactions; investigation and filing must be per transaction.
5. **Candidate condition map** (candidate only — always check the condition's invalid-dispute list and the version in force):
   | Claim family | Candidates |
   |---|---|
   | unauthorized card-absent | 10.4 |
   | unauthorized card-present | 10.1 / 10.2 / 10.3 |
   | not received / partially received | 13.1 |
   | cancelled subscription | 13.2; if trial/intro offer not clearly disclosed → 13.5 |
   | defective / not as described | 13.3 |
   | cancelled or returned; policy not honored | 13.7 |
   | refund promised, not processed | 13.6 |
   | charged twice | 12.6 |
   | wrong amount (processing error) | 12.5 (not for T&E quoted-vs-actual or price disputes) |
   | price different from what was agreed | usually **no** processing-error condition; consider 13.5, pre-dispute merchant contact, or Reg Z billing error without network recourse |
6. **Secure-channel intake** (secure online banking or secure telephone banking) allows issuer certification in lieu of a signed letter.
7. **Temporary credit (Reg Z).** Post within 2 business days when the notice is timely, the claim describes a billing error type, and no hold
   applies. Holds: descriptor inquiries; novel transaction types without an applicable rule (e.g. agentic transactions); accounts under an
   automated evidence-first control (SOP-DSP-003 §6); claims already resolved by merchant credit.
8. **Automated work queues:** `fraud_cnp`, `fraud_card_present`, `consumer_disputes`, `reg_e_disputes`, `automated_review_panel`.
   Outputs consumed by other systems (no human queues): `fraud_watchlist_feed`, `policy_gap_log`.
""")

internal("LFB-SOP-DSP-002@v3", "Goodwill write-off threshold (superseded)", "3", "2025-01-01", "2026-06-30", "superseded", """
# SOP-DSP-002 Low-value dispute write-off (v3) — SUPERSEDED by v4 on 2026-07-01
Non-fraud consumer disputes of **$25.00 or less** may be resolved by goodwill credit **without a network dispute** if the customer has had no other
dispute in the prior 12 months and the account is not more than 30 days delinquent.
""", superseded_by="LFB-SOP-DSP-002@v4")

internal("LFB-SOP-DSP-002@v4", "Goodwill write-off threshold", "4", "2026-07-01", None, "active", """
# SOP-DSP-002 Low-value dispute write-off (v4)
Effective **2026-07-01**. Replaces v3.

A **non-fraud** consumer dispute may be resolved by goodwill credit **without investigation or network dispute** when **all** apply:
1. Disputed amount **≤ $15.00** (per transaction).
2. No other dispute (excluding goodwill write-offs) **opened** by the customer in the **12 months before the current intake date**. The current
   claim and other transactions in the same intake do not count.
3. Account not more than 30 days delinquent.
4. The merchant is not subject to an open merchant-level cluster flag.

Rationale for the change: quarterly QA found write-offs between $15 and $25 at merchants with recoverable chargebacks; network recovery rate
for those cases exceeded handling cost.
""", supersedes="LFB-SOP-DSP-002@v3")

internal("LFB-SOP-DSP-003@v5", "Escalation and human review (superseded)", "5", "2026-05-15", "2026-09-30", "superseded", """
# SOP-DSP-003 Escalation and human review (v5) — SUPERSEDED by v6 on 2026-10-01
Historical version. Required human approval before finalizing high-impact decisions (large unauthorized-use denials, reopening closed cases,
organized abuse, policy gaps, authority determinations, low confidence). Retained for audit of decisions made before 2026-10-01.
**Do not apply to current cases.**
""", superseded_by="LFB-SOP-DSP-003@v6")

internal("LFB-SOP-DSP-003@v6", "Automated decision governance (no human in the loop)", "6", "2026-10-01", None, "active", """
# SOP-DSP-003 Automated decision governance (v6)
Effective **2026-10-01**. Replaces v5 (human review). All dispute decisions are made **and executed** by the automated dispute system.
**No case waits for human input.**

## 1. Suspension is only for external events
A run may suspend only while waiting for an **external event with a known or expected arrival**: merchant or provider evidence, a cardholder reply,
a clearing record, or a scheduled follow-up. Before suspending, compute the latest safe decision time = earliest regulatory or network deadline
minus 2 business days. If the event hasn't arrived by then, **decide on the evidence available**, applying §3.

## 2. Automated review panel for high-impact decisions
Run the review panel before recording any of:
1. Denial (in whole or part) of an **unauthorized-use** claim of **$500 or more**, or of any claim where the cardholder contests the issuer's evidence.
2. **Reopening or amending a closed case**.
3. **Authority / household determinations** under Reg Z §1026.12(b).
4. **No applicable network rule** or a **novel transaction type** (e.g. agentic transactions).
5. **Cross-customer abuse findings** (rings, drop addresses, compromise points).

The panel is: a **cardholder advocate** (strongest case for the cardholder), an **issuer/merchant advocate** (strongest case against), an **independent
adjudicator** that decides from the case file, and **verifier checks** (eligibility and invalid-dispute lists, policy versions as of the governing
date, arithmetic via sandbox, citations resolve to evidence, SOP-DSP-004 fairness). Record each position, the decision, the confidence on the
determinative issue, and **the single fact that would flip the decision**.

## 3. Confidence threshold and conservative default
- Required confidence on the determinative issue: **0.75**.
- If confidence remains below 0.75 after the panel: apply the **conservative default** — resolve the **cardholder outcome in the cardholder's favor**
  (credit, or maintain temporary credit as final), **do not file a network dispute unless eligibility is certain**, and set
  `conservative_default_applied = true` with the reason. The issuer absorbs the loss; the customer is never disadvantaged by uncertainty.

## 4. Reopening closed cases
Reopen a closed case automatically when new evidence **contradicts the basis** of the prior decision (e.g. account-takeover indicators, a shared drop
address) **and** the corrected outcome favors the cardholder. Record both decisions and the new evidence. Credit the cardholder (plus related finance
charges). Never initiate a second network dispute for a transaction already disputed; check network time limits before any recovery attempt.

## 5. No applicable rule / novel transaction types
Evaluate Regulation Z / Regulation E billing-error and liability rules directly and decide the cardholder outcome. Network action is `no_dispute`
unless a condition's requirements are fully met. Write a machine-readable `policy_gap` record listing the conditions considered and why each fails.

## 6. Cross-customer abuse: bounded automated controls
Allowed automatically: record the finding in the graph with evidence edges (`status = active`); set an **enhanced-monitoring** flag on linked accounts;
require a **signed cardholder letter and evidence review before temporary credit** on future non-receipt claims from linked accounts; add shared
identifiers (ship-to address, device, compromise-point merchant) to **watchlists** used by real-time fraud rules; enqueue linked open cases for
automated re-review. **Never** close or restrict an account, reverse credits, or deny a claim **on linkage alone** — each case is decided on its own evidence.

## 7. Account security
When takeover indicators are present (unverified contact changes, VPN/hosting-IP logins, password resets preceding the disputed transaction):
lock digital banking pending step-up verification, revert unverified contact changes, reissue the card, and record the actions.

## 8. Decision record
Every decision includes an `adjudication` block (`review_panel_used`, positions, confidence, threshold, `conservative_default_applied`, `flip_fact`)
and the list of `automated_actions` executed.
""", supersedes="LFB-SOP-DSP-003@v5")

internal("LFB-SOP-DSP-004@v2", "Fair and consistent treatment in dispute investigations", "2", "2025-11-01", None, "active", """
# SOP-DSP-004 Fair treatment (v2)
1. **Prohibited bases.** Do not use, or record, race, color, religion, national origin, sex, marital status, **age**, receipt of public assistance, or
   exercise of consumer-protection rights as signals — nor proxies such as neighborhood or ZIP code as a risk signal, name, language, accent, or
   perceived demeanor. Age of a minor may be recorded only as a fact relevant to authority (e.g. "13-year-old child").
2. **Evidence, not character.** Notes and letters describe **facts and evidence** ("merchant evidence shows 37.5 hours of play from the device on
   file"), never labels ("fraudster", "abuser", "liar", "scammer").
3. **Same standard for everyone.** The same evidence standard applies regardless of card product, tenure, or segment.
4. **Non-cooperation.** Do not deny solely because a customer did not respond or declined a request (Reg Z interpretation). Denial requires facts
   confirming no error.
5. **Association is not evidence.** Linkage to other customers requires a **specific shared identifier** (device, phone, address, account) — not
   geography, employer, or merchant alone.
6. **Explanations** are in plain language, state what was reviewed, and tell the customer what they can do next.
""")

internal("LFB-SOP-DSP-005@v1", "Agent memory governance", "1", "2026-08-01", None, "active", """
# SOP-DSP-005 Agent memory governance (v1)
Applies to all long-term notes written by dispute assistants or analysts into shared memory.

## What may be written
- **Factual** observations with `source_refs` (case, packet, document IDs) and `valid_from`/`valid_to`.
- **Merchant patterns** derived from **three or more** independent cases; must list the cases.
- **Procedural lessons** from QA findings or resolved cases.
- **Never:** SOP-DSP-004 prohibited bases or labels; free-text speculation about intent; copies of full card numbers.

## Lifecycle operations
| Operation | When | How |
|---|---|---|
| **supersede** | the source (policy, SOP, bulletin) changed, or a newer note replaces it | set `status=superseded`, `superseded_by`, `valid_to`; keep text for audit |
| **retract** | note is shown to be **wrong** | set `status=retracted` with reason; write a **correction** note linking evidence; never silently delete |
| **consolidate** | ≥3 raw observations describe one pattern | write one note with validity window and `source_refs`; mark raw notes `archived` with pointer; merge near-duplicate entities (e.g. old and new merchant IDs) |
| **time-bound** | a pattern stops being true (merchant change, rule change) | set `valid_to`; do **not** delete history |
| **dedupe** | same fact recorded twice | keep the earliest, archive the rest |
| **expire** | operational/tooling notes | TTL 30 days |
| **purge** | prohibited content under SOP-DSP-004 | remove content, retain tombstone with reason |

## Reading memory
Memory is a lead, not evidence. A decision must rest on case evidence and current policy. When memory conflicts with a current source of truth
(policy corpus, case data), the source of truth wins and the memory note must be updated.
Merchant pattern notes older than 90 days, or predating a known merchant change, must be revalidated before use.
""")

internal("LFB-SOP-DSP-006@v4", "Regulation E debit dispute procedures", "4", "2025-09-02", None, "active", """
# SOP-DSP-006 Regulation E procedures (v4)
- **Business day** = Monday–Friday excluding Lanternfield Bank holidays (`reference/bank_holidays_2026.csv`). Count starts the day **after** notice.
- **Provisional credit:** if the investigation will not finish within 10 business days of notice (**20 business days** when the transfer occurred
  within 30 days after the account's first deposit), post provisional credit by that deadline. Bank practice: post immediately for card-not-present
  claims with no confirming evidence of participation.
- **Investigation limit:** 45 calendar days; **90 calendar days** for POS debit card transactions, foreign-initiated transfers, and new-account transfers.
- **Written confirmation:** the bank may require written confirmation of an oral notice within 10 business days; if not received, provisional credit
  is not required, but the investigation continues.
- **Liability:** apply §1005.6(b)(1)/(2) tiers **only** when the access device (card) was lost or stolen. Card in possession → §1005.6(b)(3) only.
- **Reversing provisional credit:** send notice with date and amount; honor third-party checks/drafts and preauthorized transfers for **5 business
  days** after the notice. Also applies when the error was resolved by a merchant credit that makes the provisional credit a duplicate.
- **Network disputes** for debit follow Visa rules (same conditions as credit).
""")

internal("LFB-SOP-DSP-007@v2", "Foreign transaction fee reversal on refunds", "2", "2025-06-01", None, "active", """
# SOP-DSP-007 Foreign transaction fee reversal (v2)
- When a merchant credits the **full original transaction-currency amount** of a purchase within **180 days** of the purchase, reverse the
  **foreign transaction fee** charged on that purchase. Partial credits: reverse the fee pro rata.
- Lanternfield does **not** charge a foreign transaction fee on credits.
- **Exchange-rate differences** between the purchase and the credit are **not reimbursed**; they are disclosed in the Cardholder Agreement §9 and are
  not a billing error.
- This is a goodwill adjustment, not a network dispute.
""")

internal("LFB-SOP-DSP-008@v3", "Fraud chargeback recovery thresholds", "3", "2026-01-01", None, "active", """
# SOP-DSP-008 Fraud recovery thresholds (v3)
- **Always** report confirmed fraud activity to the network (TC40) for every fraudulent transaction, regardless of amount, before any fraud dispute.
- **Cardholder outcome is independent of recovery:** a customer with a valid unauthorized-use claim is credited in full (less any legal liability).
- File a network fraud dispute when the transaction amount is **≥ $100.00**, or when multiple fraudulent transactions at the **same merchant** on the
  same card within 30 days total ≥ $100.00. Below threshold: write off (no chargeback).
""")

internal("LFB-CB-2025-03", "Compliance bulletin: Reg E provisional credit timing (superseded)", "1", "2025-03-15", "2025-09-01", "superseded", """
# Compliance Bulletin CB-2025-03 — SUPERSEDED by CB-2025-09
For debit card disputes, post provisional credit **within 10 calendar days** of the customer's notice if the investigation is not complete.
""", superseded_by="LFB-CB-2025-09", owner="Compliance")

internal("LFB-CB-2025-09", "Compliance bulletin: Reg E timing uses business days; new-account extension", "1", "2025-09-02", None, "active", """
# Compliance Bulletin CB-2025-09
Supersedes CB-2025-03, which incorrectly described Regulation E provisional-credit timing in **calendar** days.
- Regulation E §1005.11(c) deadlines for investigation/provisional credit are **business days** (10, or **20** for transfers within 30 days after the
  account's first deposit). The 45/90-day extended investigation periods are calendar days.
- Use the bank holiday calendar. The day notice is received is not counted.
- QA found 14 cases in Q2 2025 where provisional credit was posted on calendar-day timing; no customer harm (all early), but deadline tracking
  must be corrected.
""", supersedes="LFB-CB-2025-03", owner="Compliance")

internal("LFB-CARDHOLDER-AGREEMENT@2025-01", "Lanternfield Visa Signature Cardholder Agreement (excerpts)", "2025-01", "2025-01-01", None, "active", """
# Cardholder Agreement — excerpts
**§4 Authorized users and others.** You are responsible for all charges made by authorized users and by anyone you allow to use your card or
account, including charges they make beyond the scope of permission you gave, until you tell us that person is no longer permitted to use it.

**§9 Foreign transactions.** Transactions in a foreign currency are converted to U.S. dollars using the rate selected by Visa for the processing date.
Credits are converted on the date the credit is processed, so a credit may differ from the original U.S. dollar amount. We charge a **foreign
transaction fee of 3%** of the U.S. dollar amount of each purchase made in a foreign currency or processed outside the U.S. We do not charge this fee on credits.

**§12 Your billing rights.** (Summary of the Regulation Z model notice.) If you think there is an error on your statement, contact us within 60 days
after the error appeared on your statement. While we investigate, you do not have to pay the amount in question. If you have a problem with the
quality of property or services you purchased, you may have the right not to pay the remaining amount due if you tried in good faith to correct the
problem with the merchant, the purchase was more than $50, and it was made in your home state or within 100 miles of your mailing address.
""")

if __name__ == "__main__":
    root = os.path.join(HERE, "policies")
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.endswith(".md"):
                os.remove(os.path.join(dirpath, f))
    for folder, fname, text in DOCS:
        path = os.path.join(HERE, folder, fname)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(f"wrote {len(DOCS)} documents")
