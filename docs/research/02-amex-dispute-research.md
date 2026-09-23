# 02 — American Express Dispute Handling

> **Status:** Research checkpoint, a companion to `01-domain-research.md`. It records how Amex disputes work so the knowledge graph and three demo cases can rest on verified rules.
>
> **Research date:** 23 September 2026.
> **Primary documents read in full text:**
> - Amex, *How to Manage and Help Prevent Disputes — Global Merchant Network Services*, version **2024PROP**, 73 pp. (the "Disputes Reference Guide", DRG): <https://www.americanexpress.com/content/dam/amex/us/merchant/pdf/manage-disputes/US-Disputes-Reference-Guide.pdf>
> - Amex, *Merchant Operating Guide — All Regions*, **April 2026**, 120 pp. (MOG, the OptBlue / Merchant Services Provider rulebook; `americanexpress.com/merchantopguide` redirects here): <https://icm.aexp-static.com/content/dam/gms/en_us/optblue/us-mog.pdf>
> - Amex, *Merchant Reference Guide — U.S.*, **October 2021** (MRG, the direct-acquired "Merchant Regulations" rulebook. This is the newest U.S. edition that is publicly reachable; newer editions need a merchant login): <https://www.americanexpress.com/content/dam/amex/us/merchant/merchant-channel/US-Reference-Guide.pdf>
> - 12 CFR 1026.12 and 1026.13 (Reg Z), CFPB mirror.
> - Amex Offers standard terms, Platinum fact sheet (Sept 2025 refresh), Amex Platinum and Gold Cardmember Agreements.

## Source-quality legend (same as doc 01)

| Tag | Meaning |
|---|---|
| **[P]** | Primary rule text I read directly (Amex rulebook or guide PDF, CFR text, Cardmember Agreement) |
| **[N]** | Amex marketing, educational or help-page text (true about their product, but not a rulebook) |
| **[S]** | Secondary practitioner source (chargeback vendor blogs) |
| **[K]** | My own domain knowledge, not re-verified. Treat as **UNVERIFIED** |
| **[D]** | My **design inference** from the sources above. Not an Amex statement |

---

## 0. TL;DR for the graph designer

1. Amex runs **one case, two notices**. A Cardmember dispute opens a case. Amex either sends the merchant an **Inquiry** (a request for information, identified by a 3-digit code, 20 days to reply) or issues an **Upfront Chargeback** (a lettered reason code). If the merchant replies badly or late, the Inquiry turns into a chargeback coded **R03** (Insufficient Reply) or **R13** (No Reply). Neither step has Visa-style network arbitration. **[P]** DRG p.4, p.12; MRG §11.3–11.9.
2. **Inquiry codes (numeric) are the cardmember-facing complaint taxonomy. Chargeback codes (lettered) are the liability taxonomy.** The user's 3-letter case types (NKN, RET, CNC…) line up one-to-one with Amex *Inquiry* codes, not chargeback codes (§4).
3. **Fraud and non-fraud are separate branches from intake.** Inquiry **193 Fraud** leads to the F-codes. Inquiry **127/176 No Knowledge** is a *non-fraud* "I don't recognise this" claim, and itemization or proof of delivery answers it. Inquiry **691** is not a dispute at all: it is a request for itemization. **[P]** DRG pp.19, 25, 26, 29.
4. **Amex rules favour the Cardmember when a merchant policy is ambiguous.** For Advance Payments the MOG says Amex may charge back "if… the dispute cannot be resolved in the Merchant's favor based upon **unambiguous terms**" to which the Cardmember gave written consent. **[P]** MOG §4.5.1.
5. **A missing Amex Offer or Platinum credit is an Amex benefit issue, not a merchant dispute.** The merchant charged the right price. The credit is Amex's to post under Amex's own terms (§6).

---

## 1. The three-party (closed-loop) model

### 1.1 What "closed loop" means

- Amex's 10-K: *"we have direct access to information at both ends of the card transaction, which distinguishes our integrated payments platform from the bankcard networks."* **[P]** [AXP FY2020 10-K](https://www.sec.gov/Archives/edgar/data/4962/000000496221000013/axp-20201231.htm)
- In the proprietary case, **Amex is the issuer, the network and the acquirer** at once. Amex issued the card, signed the merchant, and settles with the merchant. **[P]** 10-K. The MRG uses "we" for the party that both takes the Cardmember's dispute and charges back the merchant: *"If a Cardmember disputes a Charge, American Express opens a case… we may initiate a Chargeback to you immediately or send you an Inquiry."* **[P]** MRG §11.2.

### 1.2 Flow (proprietary, direct-acquired merchant)

```
Cardmember ──(dispute ≤120 days from txn date*)──► Amex Disputes (issuer role)
   │                                                   │ tries to resolve with info on hand
   │                                                   │ (e.g. substitute/digital receipt)
   │                                        ┌──────────┴───────────┐
   │                                   Inquiry (3-digit code)   Upfront Chargeback (letter code)
   │                                   20 days to reply         20 days to request reversal
   │                                        │                        │
   │                      sufficient & on time?               sufficient & on time?
   │                        yes → Case resolved                 yes → Chargeback Reversal
   │                        no  → Chargeback (R03/R13/…)        no  → Chargeback stands
   │
   └── Re-dispute: Cardmember adds new info → Amex may reinvestigate → merchant must re-support
```
*120-day window with exceptions for not-received, returned/canceled and re-disputes. Cardmembers are "limited to just 2 disputes per charge in most cases." **[P]** DRG p.4. Re-dispute: **[P]** MRG §11.9.

### 1.3 What disappears compared with Visa's four-party model

| Visa four-party layer | Amex proprietary | Source |
|---|---|---|
| Issuer and acquirer are separate banks that exchange disputes through VROL | Both are Amex. The dispute moves between Amex departments, not between two banks | **[P]** 10-K, MRG §11.2 |
| Issuer "dispute" followed by acquirer "representment" | Replaced by **Inquiry → merchant reply** (before any chargeback) and **Chargeback → Chargeback Reversal request** | **[P]** DRG p.4, MRG §11.4 |
| Pre-arbitration and network arbitration run by Visa | **No arbitration stage appears** in the DRG, MRG or MOG. *"All judgments regarding resolution of Disputed Charges are at our sole discretion."* | **[P]** MRG §11.3 |
| Acquirer's own liability and its buffer | The merchant is debited directly: Amex deducts from settlement or debits the bank account. The Discount is not refunded on chargebacks | **[P]** MRG §11.11 |
| Cardholder must first attempt merchant resolution (Visa rule) | Amex *asks* Cardmembers to "first contact the merchant directly". This is a help-page instruction, not a published hard precondition | **[N]** [Amex FAQ](https://www.americanexpress.com/us/customer-service/faq.dispute-a-charge.html) |

UNVERIFIED **[K]**: whether Amex has any internal second-level review for a merchant whose reversal request is denied. No public Amex document describes one.

### 1.4 Exceptions: where Amex is *not* both ends

- **OptBlue (third-party acquirers).** *"through our OptBlue® merchant-acquiring program, third-party acquirers contract directly with small merchants for card acceptance."* **[P]** 10-K. Under OptBlue, **the merchant never talks to Amex about disputes**: *"All interactions with American Express related to disputes will be conducted by your Merchant Services Provider"* and *"Your Merchant Services Provider will let you know applicable time frames for responding to notices."* **[P]** MOG §10.2, §10.3. The merchant's response window therefore depends on the acquirer (usually shorter than 20 days, **[K]**). Amex still acts as issuer and network. The acquirer is now a third party, as in Visa.
- **Global Network Services (GNS, third-party issuers and some acquirers).** GNS partners are *"third-party banks and other institutions in approximately 98 countries and territories"* that issue Amex-branded cards and/or acquire merchants. 43.1M cards in force were issued by third parties at year-end 2020. **[P]** 10-K. The MOG notes Amex *"may also open cases when Issuers or the Network initiates disputes."* **[P]** MOG §10.2. In a GNS case the **issuer is a bank**, so the flow looks four-party: GNS issuer → Amex network → acquirer (Amex or OptBlue MSP) → merchant. UNVERIFIED **[K]**: the GNS issuer-to-network dispute rules and timeframes (in the partner rulebook, not public).
- **Design implication [D]:** model `Issuer`, `Network`, and `Acquirer` as separate roles. Allow one `Organization` (Amex) to fill all three. In OptBlue cases, `Acquirer` = MSP. In GNS cases, `Issuer` = partner bank.

---

## 2. Dispute lifecycle and stages

| Stage | Rule | Source |
|---|---|---|
| Cardmember filing window | Up to **120 days from transaction date** (exceptions: not received, returned/canceled, re-disputes). Max ~2 disputes per charge | **[P]** DRG p.4 |
| Amex pre-work | Amex "will work directly with the Card Member… and try to resolve the case before reaching out to you" (e.g. substitute or digital receipts) | **[P]** DRG p.4; MOG §10.3 |
| **Inquiry** | Sent "if a Card Member disputes a charge… and we cannot resolve it using the information we have available." Merchant must "respond within 20 days" | **[P]** DRG p.12; MRG §11.8 |
| Inquiry outcomes | Reply sufficient and on time → **Case resolved**. Merchant agrees credit is due → **M01** Chargeback Authorization. Reply incomplete → **R03** Insufficient Reply. No reply or late → **R13** No Reply | **[P]** DRG pp.4, 59–61 |
| **Upfront Chargeback** (chargeback without Inquiry) | "If we determine we have sufficient information to pursue a Chargeback, we may debit your account up front" | **[P]** DRG p.4; MRG §11.3 |
| **Chargeback Reversal** (Amex's version of representment) | Merchant must request "no later than twenty (20) days after the date of the Chargeback" with the required support | **[P]** MRG §11.4 |
| Compelling Evidence | For fraud-type claims, if the evidence meets policy, "the Issuer will review the Compelling Evidence with the Cardmember prior to making a decision on the Chargeback Reversal request" | **[P]** MRG §11.6; MOG §10.6 |
| Re-dispute | "We may reinvestigate an Inquiry if a Cardmember provides new or additional information" | **[P]** MRG §11.9 |
| No resubmission | A charge resolved in the Cardmember's favour must not be re-submitted. It will be charged back | **[P]** MRG §11.5 |
| No waivers | Merchant "must not suggest or require Cardmembers to waive their right to dispute" | **[P]** MRG §11.2; MOG §10.2 |

### 2.1 Chargeback programs (full recourse)

In Amex usage, "Chargeback is sometimes called 'full recourse'". **[P]** MRG glossary. Amex can place a merchant in a program "any time during the term of the Agreement". **[P]** MRG §11.12. In each program the only defenses are "you were not in the program at the time" or "you already credited". **[P]** DRG pp.70–72.

| Code | Program | Effect |
|---|---|---|
| **FR2** | Fraud Full Recourse | Any Cardmember fraud denial is charged back. No Inquiry |
| **FR4** | Immediate Chargeback | *Any* dispute is charged back immediately |
| **FR6** | Partial Immediate Chargeback | Immediate chargeback for disputes at or under a threshold ("up to $20, $25, $50, $100 or $250") |

Lodging "no show" disputes that stay disproportionate can put a merchant "in any of American Express' Chargeback programs." **[P]** MOG §11.11.2.

### 2.2 Merchant response channels

- **Online Merchant Account** at `americanexpress.com/merchant`, with the "Disputes" access option, is Amex's "preferred method". It offers email alerts (new Inquiries, new Chargebacks, case updates, urgent), document upload, and live chat. **[P]** DRG pp.8–9; MRG §11.13.
- In the online tool, the merchant picks *"I do not agree with the Card Member or I already issued a refund"* or *"I agree with the Card Member and I would like to provide a full refund"* and must respond by the **"reply-by" date**. **[N]** [Managing a Dispute Case](https://www.americanexpress.com/us/merchant/support-center/disputes/managing-a-disputes-case.html). Merchants can search cases by Case #, Charge Reference #, Card Member Name or Number. **[N]** [Searching for Disputes](https://www.americanexpress.com/us/merchant/support-center/disputes/searching-for-disputes.html).
- **Fax or mail**: non-fraud to PO Box 981532, El Paso TX 79998 / fax 623-444-3000. Fraud to American Express Datamark, 43 Butterfield Circle, El Paso TX 79906 / fax 623-444-3003. Phone 1-800-528-5200. **[P]** DRG p.9.
- "Merchant Services Online" and "Disputes Management" as product names: **UNVERIFIED**. The current guides say "Merchant Account online".
- **OptBlue**: all responses go through the MSP's portal. **[P]** MOG §10.2.

### 2.3 Related clocks a graph should carry

| Clock | Value | Source |
|---|---|---|
| Merchant issues credit once due | within **7 days** of determining a credit is due | **[P]** MOG §4.6.3.1; DRG p.5 |
| Authorization validity | 7 days (exceptions for lodging, cruise, rental). Ship more than 7 days later → re-authorize | **[P]** MRG §5; MOG §4.4 |
| Recurring billing written confirmation | within **24 hours** of the first recurring charge | **[P]** MOG §4.5.6 |
| Advance Payment written confirmation (CNP) | within **24 hours** | **[P]** MOG §4.5.1 |
| Lodging cancellation notice | written notice with cancellation number within **3 Business Days** | **[P]** MOG §11.11.1 |
| Variable recurring amount notice | ≥ **10 days** before each charge (where notice is required) | **[P]** MOG §4.5.6 |
| Record retention | Clearing Records ≥ **24 months**. Recurring consent **2 years** after last charge | **[P]** MOG §4.6.3.1, §4.5.6 |

---

## 3. Chargeback reason codes (DRG 2024PROP, pp.31–72)

The DRG groups codes as Authorization, Card Member Disputes, Fraud, Inquiry/Misc, Processing Errors and Programs. Every code accepts one universal defense: **"proof that a credit, which directly offsets the disputed charge, has already been processed."** The table leaves that defense out. **[P]**

### 3.1 FRAUD codes (Cardmember denies participation)

| Code | Meaning | What defeats it (beyond offsetting credit) |
|---|---|---|
| **F10** Missing Imprint | CM denies participation. Card not swiped or chip-read, or a CNP transaction was not flagged as CNP, or a keyed transaction had no imprint | Proof it was actually a CNP charge |
| **F14** Multiple ROCs | CM admits one valid transaction and denies the additional ones | Proof each transaction is a valid charge |
| **F24** No Card Member Authorization | CM denies participation, and the merchant "failed to provide proof that the Card Member participated" | **Only an offsetting credit** (transit contactless exceptions apply). Participation evidence has to come at Inquiry stage |
| **F29** Card Not Present | CM denies participation in, receiving or benefiting from a CNP charge. *Not applicable to digital-wallet-app-initiated txns* | POD to billing address. Or: valid auth with CID attempted and "no match/unchecked". Or: AVS-validated address shipped to. Or: shipping address matches a prior undisputed txn. **Airline**: boarding pass, manifest, miles credited, passenger name matching a prior undisputed txn. **Digital goods**: description + download date/time + a prior undisputed e-com txn in 12 months on same credential/account with ≥2 of device ID, full IP, email. **Recurring**: written consent to periodic billing, account login, a prior undisputed recurring txn, renewal notification evidence, CM verification (password, 2FA, device/IP history, AAV/CID "Y") |
| **F30** EMV Counterfeit | Counterfeit chip card used at a non-chip or keyed POS | Proof it was CNP, or proof the POS processed it as chip |
| **F31** EMV Lost/Stolen/Non-Received | Chip-and-PIN card lost or stolen, used without PIN validation | Proof it was CNP, or chip+PIN was validated |
| **FR2** Fraud Full Recourse | Merchant is in the program | Proof not enrolled at the time |

Inquiry **193 Fraud** (the fraud intake stage). Card present: Charge Record + imprint. CNP: Charge Record, contracts, POD with full shipping address. **[P]** DRG p.26.

### 3.2 NON-FRAUD: Card Member dispute codes (C / M)

| Code | Meaning | Defense evidence |
|---|---|---|
| **C02** Credit Not Processed | Merchant's Inquiry reply said credit was or would be issued, but it never arrived or was short | Written explanation why credit is not due, with documents |
| **C04** Goods/Services Returned or Refused | Returned or refused, no credit | Refutation that goods came back. **Or**, if returned: the return policy + *"an explanation of your procedures for disclosing it"* + how CM failed to follow it. **Or** Charge Record showing the T&Cs. **Or**, if refused: proof of acceptance (signed delivery slip, screen print of service use). Tip: *"Program your terminals to print your return/refund policy on receipts"* |
| **C05** Goods/Services Canceled / Not Received / Partially Received | CM says canceled | Cancellation policy + *disclosure procedures* + how CM failed to follow it. Or Charge Record with T&Cs |
| **C08** Goods/Services Not Received or Only Partially Received | Non-receipt | POD with date and full address. Or proof services were rendered and when. Or a signed work order. Or refutation of cancellation/return. Or a link between the recipient and the CM (photos, emails). **Airline**: boarding pass, miles, ancillary purchases. **Store pickup**: signature + ID verification. **Digital**: IP match, email match, or post-purchase site access (optional: description, download time). **Installments**: T&Cs + non-compliance |
| **C14** Paid by Other Means | CM proves payment another way | Other payment was unrelated. Or CM consented to use of the Card for this charge |
| **C18** "No Show" or CARDeposit Canceled | Lodging reservation canceled, or CARDeposit credit not received | Documentation supporting the validity of the no-show or CARDeposit charge |
| **C28** Canceled Recurring Billing (title also lists "Goods Not as Described/Defective/Damaged") | CM canceled or tried to cancel a recurring charge, or was billed for an **Introductory Offer** | Cancellation policy + disclosure procedures + non-compliance. Or proof CM **has not canceled and still uses** the service. **Introductory Offer**: clear disclosure incl. a simple cancel-before-first-charge path, express consent, written enrollment confirmation, written reminder before the first recurring charge |
| **C31** Goods/Services Not as Described | Differs from the written description at time of charge | Refutation. Or CM agreed to accept as provided. Or proof it matched the description (photos, emails). If received damaged: attempted repair/replace, or CM failed a "clearly documented" return policy, or CM accepted "as is" |
| **C32** Goods/Services Damaged or Defective | Damaged or defective | Refutation (if goods not returned). Attempted repair or replacement. CM failed a "clearly documented" cancellation/return policy (if returned). CM accepted as delivered. Goods not returned |
| **M10** Vehicle Rental – Capital Damages | Incorrectly billed for damage | Signed acknowledgment of responsibility, and charge ≤ **115%** of agreed amount |
| **M49** Vehicle Rental – Theft or Loss of Use | Same | Signed acknowledgment, and charge ≤ **110%** of agreed amount |
| *Local Regulatory/Legal Disputes* | CM invokes a legal right where no other chargeback right applies | Law doesn't exist, doesn't cover CM or facts, or imposes no acquirer obligation |

Note: C28's title in the 2024 DRG bundles "Not as Described/Defective/Damaged", but its body covers recurring billing only. C31 and C32 are the dedicated codes. **[P]** DRG pp.44–47.

### 3.3 NON-FRAUD: Authorization (A), Processing (P), Inquiry/Misc (R, M01)

| Code | Meaning | Defense |
|---|---|---|
| **A01** Charge exceeds authorization | Lodging/rental >15%, restaurant >30%, cruise >15% over auth without re-auth | Valid approval for full amount |
| **A02** No valid authorization | Declined, expired card, mismatched approval code | Valid approval. Or charge incurred within card validity dates |
| **A08** Authorization approval expired | Submitted after approval expired (7-day rule) | Valid approval per Agreement |
| **P01** Unassigned card number | Invalid or closed account number | Imprint, approval for that number, or terminal-read Charge Record |
| **P03** Credit processed as charge | Should have been a credit | Charge was correct |
| **P04** Charge processed as credit | Inverse | Credit was correct |
| **P05** Incorrect charge amount | Amount ≠ what CM agreed. Includes shipping, taxes, **restocking fee**, delayed charges, or a credit short by a cancel/restocking/fuel fee | Proof CM agreed to the amount. Or CM was advised of and agreed to additional or delayed charges **on this Card**. Or an itemized contract |
| **P07** Late submission | Submitted outside the required time frame | Proof of timely submission |
| **P08** Duplicate charge | Submitted more than once | Each charge valid |
| **P22** Non-matching card number | Submitted card ≠ authorized card | Imprint or terminal-read record |
| **P23** Currency discrepancy | Wrong currency | Only an offsetting credit |
| **R03** Insufficient Reply | Inquiry reply incomplete (e.g. missing the policy, partial credit unexplained) | Only an offsetting credit. Win it at Inquiry stage |
| **R13** No Reply | No or late Inquiry reply | Proof of on-time reply |
| **M01** Chargeback Authorization | Merchant's reply authorized the chargeback | n/a |

---

## 4. Mapping the user's case-type codes to Amex codes

**Do NKN, RET, CNC… appear in Amex material?** I found **no public Amex document using these 3-letter abbreviations** (searched americanexpress.com, the DRG, the MOG and the MRG). **UNVERIFIED.** They are most likely an internal or vendor case-type vocabulary. Their meanings do, however, **match Amex's public numeric Inquiry codes one-to-one**, and the Inquiry code names use the same words ("No Knowledge", "Return", "Canceled", "Damaged", "Dissatisfied", "Duplicate", "Not Received", "Overcharge", "Paid… by Other Means"). **[P]** DRG pp.12–30.

The Inquiry → Chargeback column is **[D]** my mapping by matching descriptions. The DRG does not publish an Inquiry-to-Chargeback crosswalk. Any Inquiry can also end in **R03/R13** (bad or no reply) or **M01** (merchant accepts).

| Case type | Amex Inquiry code(s) [P] | Likely chargeback code(s) [D] | What the Cardmember is saying | Merchant should respond with [P] |
|---|---|---|---|---|
| **NKN** No Knowledge | **127** No Knowledge – Card Present. **176** No Knowledge – Card Not Present. (**691** = CM only wants itemization, "not disputing") | R03/R13 if the reply fails. **F24/F29/F14** only if the CM escalates to denying participation (a fraud claim, reclassified to 193) | "I don't recognise this." Causes Amex lists: auto-renewal, recurring after free trial, **supplementary card or family member**, unfamiliar descriptor | Support and itemization, or credit. POD with full address if shipped (127). "Signed support and itemization" (176) |
| **RET** Returned / Refused | **158** Return. (Refused shipments also sit under **021/154**) | **C04** | "I sent it back (or refused it) and got no credit" | Credit, or return policy + why credit is not due |
| **CNC** Cancelled | **021** Canceled – Expired. **154** Canceled – Expired/Unsuccessful Cancelation | **C05**. Lodging: **C18** | "I canceled (or tried to) and was charged or not refunded" | Discontinue billing and credit, **or** the policy *provided at time of purchase* + how CM didn't follow it |
| **CNC** Continuity / Recurring | **021/154** (their "caused by" lists include auto-renewal) | **C28**. Or **F29** (recurring-billing evidence set) if CM denies authorizing | "I canceled the subscription," "I didn't know it would renew," "free trial converted" | Evidence CM has not canceled and keeps using it. Consent. Cancellation policy. Introductory Offer reminders |
| **DMG** Damaged merchandise | **024** Damaged/Defective – Return Authorization Requested. **059** … – Repair/Replacement Requested | **C32** (C31 damaged clause) | "It arrived broken or defective" | Credit or return instructions. Or return/replacement policy + efforts to resolve |
| **DSS** Dissatisfied with service | **063** Dissatisfied | **C31** | "Not as described" or "quality inferior to what was described" | Proof of repair/replacement/credit, or T&Cs incl. warranty + efforts to resolve |
| **DUP** Duplicate / multiple | **173** Duplicate/Multiple Billing | **P08**. (**F14** if CM denies the extra ones) | "Charged twice." Causes include a failed checkout followed by a retry, and **forgotten recurring charges** | Credit, or support and itemization of *both* charges |
| **NRC** Not received | **004** Not Received – Delivery Requested. **155** Not Received – Credit Requested | **C08** (C05 also covers partial receipt) | "Never got it" or "only part of it" | Ship or perform, credit, or POD / proof of service |
| **OVR** Overcharged | **680** Overcharge | **P05**. (**A01** if the amount exceeded the authorization) | "Amount ≠ what I agreed," incl. tips, fees, taxes, restocking, cancel fees deducted from credit | Credit, or explain why none is due (at CB stage: proof CM agreed to the amount) |
| **PDD** Paid by other means | **684** Paid Direct by Other Means | **C14** | "I paid with cash, another card, or a voucher," or "a third party (insurer) should pay" | Proof the other payment was unrelated, or no record of it |

Other Inquiry codes with no case type in the user's list: **062** Credit Posted as Charge (→P03), **175** Requests Credit (→C02), **193** Fraud (→F-codes), **691** Signed Support/Itemization (not a dispute), **693** Vehicle Rental & Capital Damages (→M10/M49).

### 4.1 NKN is not fraud

- Amex's own taxonomy keeps them apart: **127/176 "No Knowledge"** ("does not recognize the charge") versus **193 "Fraud"** ("claims the referenced charge is fraudulent… compromised… lost/stolen"). **[P]** DRG pp.19, 25, 26.
- The listed causes of No Knowledge are *legitimate charges the CM doesn't recognise*: descriptors, renewals, supplementary cards. The listed fix is **descriptor hygiene** and itemization, not fraud tooling. **[P]** DRG p.19.
- **Graph rule [D]:** `NKN` must not auto-route to fraud handling. It routes to *clarification*: itemization, descriptor lookup, supplementary-card check, recurring-billing check. It becomes `FRAUD` only if the Cardmember, after seeing the itemization, affirmatively denies authorizing it. Reg Z echoes the split: 1026.13(a)(2) and (a)(6) (unidentified charge, request for clarification) are separate billing-error types from (a)(1) (unauthorized). **[P]**
- Secondary sources claim an unresolved 127 "typically converts into F24". **[S]** ([Chargeflow](https://www.chargeflow.io/chargebacks-101/amex-chargebacks)). **UNVERIFIED** against Amex text.

---

## 5. Merchant policy disclosure rules and how merchant policy can conflict with them

### 5.1 The Amex rules (what a merchant policy must satisfy)

| Rule | Text | Source |
|---|---|---|
| Disclose everywhere | "Disclose all terms and conditions of your sale/return/exchange/cancellation policies **at the point of sale, on all Clearing Records and customer receipts, and on your website**." | **[P]** MOG §10.5 (framed as "Tips for Avoiding Chargebacks") |
| Receipt wording | Transaction receipts must include "The words **'No Refund,'** if a no-refund policy is applicable, or other wording that conforms to Applicable Law… and describes the Merchant's return policy." | **[P]** MOG §4.6.2 |
| E-commerce site | Must display the "Return/refund policy", delivery policy, a customer-service email and phone number, and the physical address | **[P]** MOG §11.6 |
| Pre-purchase acceptance | "Before completing the purchase, have Card Member 'accept' your terms/conditions and policies." "Provide written cancelation, return, refund and special terms policies at time of purchase." | **[P]** DRG pp.5, 14 |
| Refund to original card | Credit only to the Card Account used for the original charge, in the original currency, within 7 days. "If the Card is not available, Merchants may implement their in-store refund policy." No cash refunds (limited exceptions) | **[P]** MOG §4.6.3.1 |
| **Advance Payment** | Before authorization: state full cancellation and refund policies, disclose intent, get **written consent** covering price, cancel/refund policy, description and delivery date. CNP: "Advance Payment" on the record + written confirmation within 24h. If the merchant can't deliver, credit the full amount immediately. **Amex may charge back "if… the dispute cannot be resolved in the Merchant's favor based upon unambiguous terms"** | **[P]** MOG §4.5.1 |
| Lodging Advance Payment | ≤ 14 nights + tax. Written confirmation of dates, amount, confirmation #, cancellation policy. Cancellation number within 3 Business Days. Walk the guest if unable to honor | **[P]** MOG §11.11.1 |
| Guaranteed reservation / no-show | Tell CM the one-night rate. Give a confirmation code and **cancellation policy at time of reservation**. Hold the room until check-out time next day. No-show = max 1 night, marked "No Show" | **[P]** MOG §11.11.2 |
| Recurring billing | Disclose all material terms (duration, amount, frequency, continues until canceled). Express consent. Written confirmation incl. cancellation policy within 24h. Tell CM they can cancel any time. A **"simple and expeditious cancellation process"** disclosed at consent. **Material change → written notice + express written consent before the next charge.** Card cancellation = consent withdrawn | **[P]** MOG §4.5.6 |
| Introductory Offer / free trial | Disclose terms incl. a cancel-before-first-charge path. Express consent. Written enrollment confirmation. **Written reminder before the first recurring charge** with reasonable time to cancel | **[P]** MOG §4.5.6.1; DRG C28 |
| Delayed delivery / deposit | Written consent before auth. "deposit" and "balance" records. Balance only after shipment | **[P]** MOG §4.5.5 |
| Vehicle rental damages | Signed acknowledgment of responsibility. Written estimate. New consent if the final bill is >15% over the estimate | **[P]** DRG p.30 |

**How the rules interact with the merchant's own policy [D]:** a merchant's policy is *evidence*, not an override. Amex rules decide (a) whether the policy was **validly disclosed** (when, where, and accepted), and (b) whether the policy can **legally reach** this situation. Examples: a no-refund policy cannot defeat a C08 non-delivery claim, and it cannot keep an Advance Payment the merchant failed to deliver on. The C04/C05/C28 defenses all require *"an explanation of your procedures for disclosing it"*, so undisclosed or unprovable disclosure means the policy counts for nothing. R03 names "missing cancelation/return/refund policy" and "partial credit… not explained (e.g., non-refundable cancelation fee per policy/terms)" as insufficient-reply triggers. **[P]** DRG p.59.

### 5.2 Realistic conflict patterns (for the policy-conflict node type)

1. **Undisclosed restocking fee.** The website T&C page says "15% restocking fee on returns". The POS receipt says nothing, and checkout had no acceptance click. The CM returns an item and receives a credit 15% short, then files **OVR (680)** or **RET (158)**. Amex's 680/P05 text names "credit… included a deduction… for… restocking fee" as a cause. The P05 defense requires proof the CM *agreed* to the amount. The MOG expects terms on receipts *and* site. **Conflict:** policy exists but was not disclosed at the point of sale. Likely outcome: CM wins the fee amount. **[P]** DRG p.27, 65; MOG §10.5.
2. **"Store credit only" / "exchange only" with the card present.** The merchant issues a gift card for a return. Amex requires credits to the original Card, and only allows the in-store policy "if the Card is not available". Receipts must carry "No Refund" or wording that describes the policy. **Conflict:** the merchant's policy may be lawful and posted, but Amex's credit-to-card rule, plus missing receipt wording, weakens a **C04** defense. **Ambiguity:** does "exchange only" count as the "No Refund" wording? Amex doesn't say (**UNVERIFIED**). **[P]** MOG §4.6.2, §4.6.3.1.
3. **Cancellation deadline in an unspecified time zone (lodging / advance deposit).** The confirmation email says "Free cancellation until 48 hours before check-in." It names no check-in time and no time zone. The CM, in another time zone, cancels 47 hours out by property time and 50 hours out by their own clock. The hotel keeps the deposit, and the CM files **CNC → C18/C05**. The MOG Advance Payment clause lets Amex charge back unless the dispute resolves for the merchant "based upon **unambiguous** terms". **Conflict:** the ambiguity resolves against the merchant. **[P]** MOG §4.5.1, §11.11.
4. **Policy on the website but changed after purchase (subscription price or term change).** The merchant raises the monthly price and updates its site T&Cs. It sends no individual notice and gets no fresh consent. The CM files **OVR** or **CNC (recurring)**. Amex requires written notice *and express written consent* before the next charge after a material change, or cancellation of future charges. **Conflict:** "our posted terms allow price changes" does not satisfy Amex. The applicable code is C28/P05. **[P]** MOG §4.5.6.
5. **Free trial converts; cancel path buried.** The T&Cs say "cancel any time in Settings". No reminder email was sent before the first charge. The CM files **CNC (recurring)** or **NKN** ("don't recognise this"; DRG 127 lists "recurring billings that begin after free trial"). **Conflict:** the Introductory Offer rules require a written reminder before the first charge, so a disclosed policy alone loses **C28**. **[P]** MOG §4.5.6.1; DRG p.19, p.44.
6. **Digital goods "all sales final".** The CM claims a download never arrived (**NRC → C08**). The no-refund policy is irrelevant. C08 digital defenses need IP match, email match, or post-purchase access logs. **Conflict:** the merchant relies on policy when Amex requires delivery evidence. **[P]** DRG p.41.

---

## 6. Amex Offers and Platinum credits: the "wrong card" complaint

### 6.1 Amex Offers terms

- Enrollment is card-specific: "Card Members must first enroll in the Offer on the **specific eligible Card** intended for redemption" and "that same Card must be used." "If the Offer is not added to the Card before the transaction, the Card Member will not be eligible." **[P]** [Amex Offers standard terms](https://www.americanexpress.com/en-us/benefits/offers/partner-terms/)
- Purchase must be direct with the merchant. Purchases via "resellers, third-party payment processors, delivery services, or other intermediaries, may not be recognized." **[P]** same. Mobile or digital wallet and third-party payment accounts may not earn the credit. **[N]** search snippet of the same Amex terms (not fetched verbatim).
- Timing: credit "generally… within 30 days from the date of the Qualifying Purchase," up to **90 days**. **[P]** same.
- Exclusions: gift cards, reloadables, cash equivalents, cash advances, traveler's cheques. **[P]** same.
- Returns: refunded or cancelled purchases don't count toward minimum spend, and "any reward… may be reversed." **[P]** same.
- Support: Amex Live Chat or the number on the card, **not the merchant**. **[P]** same.
- FAQ: if the offer was added to one card and a different card was used, "you will not get the statement credit." **[N]** Amex offers FAQ (JS-rendered page, content seen via search index only, [link](https://global.americanexpress.com/card-offers/faqs.html?locale=en-US)). **Partially UNVERIFIED** (not fetched verbatim).

### 6.2 Platinum statement credits (Sept 18, 2025 refresh, annual fee $895)

**[N]** [U.S. Consumer Platinum Fact Sheet](https://www.americanexpress.com/content/dam/amex/en-us/company/press-kits/platinum-refresh/U-S-Consumer-Platinum-Card-Fact-Sheet.pdf):

| Credit | Amount / cadence | Conditions stated |
|---|---|---|
| Hotel (FHR / The Hotel Collection) | up to $300 semi-annually | Prepaid booking via Amex Travel with the Platinum Card. THC 2-night minimum |
| Digital Entertainment | $25/month (≤$300/yr) | Select partners (Disney+, ESPN+, Hulu, NYT, Peacock, WSJ, Paramount+, YouTube Premium/TV). Enrollment required |
| Resy | $100/quarter | Eligible Resy purchases. Enrollment required |
| lululemon | $75/quarter | U.S. stores (no outlets) or lululemon.com. Enrollment required |
| Saks Fifth Avenue | $50 semi-annually | Enrollment required |
| Airline Fee | ≤$200/calendar year | Select **one** airline. Incidentals only. Enrollment required |
| Uber Cash / Uber One | $15/mo (+$20 Dec) / ≤$120/yr | Card added to Uber account |
| Oura, Equinox, Walmart+, CLEAR+, Global Entry/TSA | various | See sheet |

Detailed terms:
- **Resy**: eligible = partnering U.S. restaurants booked through Resy, plus Resy Pay. Excludes Resy software, Resy gift cards and restaurant gift cards. "It could take up to **8 weeks**" to post. **[N]** [Amex Credit Intel – Resy](https://www.americanexpress.com/en-us/credit-cards/credit-intel/resy-credit/)
- **Airline fee**: incidentals "charged to your Platinum Card **separately from your ticket**". Excludes tickets, upgrades, miles, gift cards, duty free and award tickets. Amex relies on the airline's transaction coding. "If you do not see a credit… after **eight weeks**, simply call the number on the back of your Card." Airline can change each January. **[N]** [Amex Credit Intel – Airline credit](https://www.americanexpress.com/en-us/credit-cards/credit-intel/using-your-american-express-platinum-airline-credit/)
- The full benefit-terms page (`global.americanexpress.com/card-benefits/terms/platinum`) is JS-rendered and could not be fetched. Basic vs Additional Card eligibility, the exact reversal-on-refund wording, and per-credit merchant-coding caveats are **UNVERIFIED**.
- Cardmember Agreement: "We have the right to add, modify or delete any benefit or service of your Account at our discretion." **[P]** Platinum CMA (03/31/2023), "Changing benefits".

### 6.3 Merchant dispute or Amex benefit issue? (analysis [D], grounded in the terms above)

**Scenario:** the CM enrolled a $50-off-$250 Amex Offer (or has the Saks credit) on their Platinum Card but paid with their Gold Card. No credit arrives. The CM files a dispute, most likely under **OVR (Overcharge)** ("I was supposed to pay $200, not $250"), or possibly **DSS**.

- **It is not a merchant billing error.** The merchant charged the price shown at checkout. Inquiry 680 covers amounts that differ "from the amount the Card Member agreed to pay". The CM agreed to $250. The Offer credit is posted by Amex under Amex's Offer terms, and the terms route questions to Amex, not the merchant. Sending an Inquiry to the merchant would produce a correct "credit not due" reply and waste the 20-day cycle.
- **It is a benefit-eligibility question, and the terms decide it against the CM**: the offer was not on the card used, so it is ineligible.
- **Reg Z angle:** 1026.13(a)(4) covers failure to credit properly "a payment or other credit". A statement credit that the terms say was *never owed* is arguably not a billing error. Whether a misposted *owed* credit (right card, correct merchant, merchant miscoded) is a 1026.13(a)(4) billing error is **UNVERIFIED legal interpretation**.
- **Correct resolution path:** (1) classify as `BENEFIT_INQUIRY`, not `DISPUTE`. (2) Check the enrollment card against the transaction card, the purchase channel (direct vs third-party/wallet), the timing window (30–90 days), and exclusions. (3) If ineligible, explain the terms to the CM, with no merchant contact. Any goodwill credit is an Amex discretionary servicing decision (**UNVERIFIED** policy). (4) If eligible but the credit is late, wait out the window or escalate internally. (5) Close the OVR dispute as "no merchant error".
- **Look-alike that *is* a merchant OVR:** a *merchant's own* discount (promo code, advertised sale price, price match) not applied at checkout. That is a genuine 680/P05 case. The merchant must prove the CM agreed to the charged amount. The graph needs a `discount.funding_source ∈ {merchant, amex_offer, card_benefit}` attribute to tell the two apart.

---

## 7. Cardmember billing rights: Reg Z vs Amex timelines

| Rule | Content | Source |
|---|---|---|
| Billing-error types | (1) unauthorized. (2) not properly identified. (3) goods/services not accepted or not delivered as agreed. (4) failure to credit a payment or other credit. (5) computational error. (6) request for clarification/documentation. (7) statement not delivered | **[P]** 12 CFR 1026.13(a) |
| Notice window | Written notice within **60 days** after the creditor transmitted the first statement showing the error | **[P]** 1026.13(b) |
| Creditor clocks | Acknowledge within **30 days**. Resolve within **2 complete billing cycles, max 90 days** | **[P]** 1026.13(c) |
| While pending | CM may withhold the disputed amount. No collection, no adverse credit reporting, no closing the account solely for the dispute | **[P]** 1026.13(d) |
| Claims & defenses ("$50 / 100-mile rule") | CM may assert merchant claims against the issuer if: a good-faith attempt to resolve with the merchant, amount **> $50**, and purchase in the **same state or within 100 miles** of the billing address. The limits do not apply when the merchant is the issuer or controlled by it, or the sale came from an issuer mail solicitation. Capped at credit outstanding | **[P]** 1026.12(c) |
| Unauthorized-use cap | Lesser of **$50** or the amount obtained | **[P]** 1026.12(b) |
| Amex CMA "Assigning claims" | "If you dispute a charge with a merchant, we may credit the Account for all or part of the disputed charge. If we do so, you assign and transfer to us all rights and claims (excluding tort claims) against the merchant." | **[P]** Platinum CMA 03/31/2023 ([pdf](https://www.americanexpress.com/content/dam/amex/en-us/company/legal/cardmember-agreements/public-site-2023-q1-pdf-cmas/cps-charge/platinum-card-03-31-2023.pdf)) |
| Amex CMA "Your Billing Rights" section | **Not found** in the extracted text of the Platinum (2023) or Gold (2019) CMA PDFs. It is probably printed on statements or in a separate notice (Reg Z requires a billing-rights statement). Exact Amex wording is **UNVERIFIED** | — |
| Amex dispute window | Merchant-facing: CMs have **up to 120 days from transaction date** (with exceptions) | **[P]** DRG p.4 |
| Temporary credit | Amex may show a "suspended amount/credit" and not request payment while the case is open. It becomes permanent or is reversed on outcome | **[N]** Amex help pages (Canada FAQ + US search snippets). U.S. wording **UNVERIFIED** |

**Design note [D]:** carry two clocks per case. `reg_z_notice_deadline` = first statement date + 60d, which decides whether *legal* billing-error protections attach. `amex_filing_deadline` = txn date + 120d (with exceptions), which decides whether Amex will *pursue* the merchant. Amex's operational window is more generous than the legal one. A late claim can still be worked, but without 1026.13 obligations.

---

## 8. Evidence catalog (graph `EvidenceType` nodes)

All items are **[P]** from the DRG sections cited in §3–4 unless marked otherwise.

| Evidence type | Defends | Notes |
|---|---|---|
| Offsetting credit proof (credit record) | **every** code | Universal defense |
| Charge Record / substitute Charge Record, itemization | 127, 176, 691, 173, 062, 193, P03, P05 | Substitute records allowed for CNP (MRG §11.7) |
| Proof of delivery (date + full address, signature) | 004/155/C08, 127, 193, F29 | F29: to *billing* address, or AVS-validated, or matching a prior undisputed ship-to |
| Proof services rendered / signed work order / service-use screenshots | C08, C04 (refused) | |
| Cancellation / return / refund policy **+ disclosure procedure + non-compliance explanation** | 021/154/C05, 158/C04, C18, C28, C32 | "explanation of your procedures for disclosing it" is required |
| Charge Record showing T&Cs | C04, C05 | Policy printed on receipt |
| Recurring consent + usage after claimed cancel | C28, F29 | Consent kept 2 years (MOG §4.5.6) |
| Introductory Offer disclosure, consent, enrollment confirmation, pre-charge reminder | C28 | All four required |
| Proof CM agreed to amount / additional charges on this Card | 680/P05, A01 | |
| Authorization approval proof | A01, A02, A08, P01 | |
| Imprint / chip read / terminal record | F10, F30, F31, P01, P22 | |
| Descriptions matching goods (photos, emails), "as is" acceptance, repair/replace attempts | 063/C31, 024/059/C32 | |
| Other-payment-unrelated proof / consent to use Card | 684/C14 | |
| No-show validity (reservation, confirmation, cancellation policy given) | C18 | + cancellation-number log (MOG §11.11.2) |
| Signed damage acknowledgment, estimate, ≤115%/110% | 693/M10/M49 | |
| Digital: IP match, email match, access logs, device ID, prior undisputed txn (12 mo) | C08, F29 | F29 digital needs ≥2 identifiers matched |
| Airline: boarding pass, manifest, miles credited, ancillary purchases | C08, F29 | |
| Proof of timely Inquiry reply | R13 | |
| Proof merchant not in program at time | FR2/FR4/FR6 | |

---

## 9. Three demo cases (design sketches [D])

**Case A — NKN that is not fraud.** A Platinum CM sees "PLTFM*STRMCO 800-555…" at $14.99 and files *No Knowledge* (CNP → Inquiry **176**). The graph checks for supplementary cards (Amex lists supplementary or family use as a 127 cause), recurring-billing history, and descriptor-to-DBA resolution. The merchant replies within 20 days with itemization: a subscription started on the supplementary card holder's login, a prior undisputed charge 30 days earlier, and the same device ID. **Expected:** case resolved at Inquiry, no chargeback. Branch: if the CM then states "I never authorized it", reclassify to **193 Fraud**. The **F29 recurring** evidence set (consent, login, prior undisputed recurring txn, renewal notice) becomes the test. Shows: NKN ≠ fraud, the 691/176/193 distinction, and the 2-disputes-per-charge limit.

**Case B — CNC with policy ambiguity (hotel advance deposit).** A CM pays a $600 advance deposit online. The confirmation says "Cancel free up to 48 hours before arrival". It gives no time or time zone. The CM cancels by email, the hotel says the request was 2 hours late, keeps the deposit, and never sends a cancellation number. CM files *Cancelled* → Inquiry **154** → **C05/C18**. Rule nodes: MOG §4.5.1 (written consent to *unambiguous* terms; otherwise Amex may charge back), §11.11.1 (cancellation number within 3 Business Days), and DRG C18 defenses. **Expected:** chargeback stands for the CM. The merchant's policy exists but is ambiguous and the process was not followed. Shows: the merchant policy vs network rule conflict, and "policy = evidence, not override".

**Case C — OVR that is really an Amex Offer / wrong-card issue.** A CM enrolls "Spend $250, get $50 back" on their Platinum Card, pays with their Gold Card, sees no credit after 30 days, and files *Overcharged* (Inquiry **680** candidate). The graph finds that the transaction amount equals the checkout amount (no merchant error), `discount.funding_source = amex_offer`, and enrolled card ≠ transaction card. Offers terms: the same enrolled card is required, and support goes through Amex. **Expected:** no Inquiry sent to the merchant. Reclassified to a benefit inquiry. The CM is told the credit is ineligible under the terms. Any goodwill is an Amex decision (UNVERIFIED policy). Contrast node: the merchant's own promo code not applied → true **680/P05**. Shows: separating merchant disputes from issuer benefit servicing, and Reg Z (a)(4) not triggered when no credit was owed.

---

## 10. Open items / UNVERIFIED

- The 3-letter case-type codes (NKN, RET, CNC, DMG, DSS, DUP, NRC, OVR, PDD) do not appear in any public Amex source. Their mapping to Inquiry codes is by name and description only.
- There is no official Inquiry→Chargeback code crosswalk. §4's chargeback column is inference.
- No public Amex source describes a second-level review or arbitration after a denied reversal request.
- OptBlue MSP response windows and GNS issuer/network dispute rules are not public.
- Current (2026) U.S. direct-merchant "Merchant Regulations" edition requires login. The MRG Oct 2021 and the MOG April 2026 (OptBlue) were used. Chapter-10 dispute text is consistent between them.
- Exact Amex "Your Billing Rights" wording. Platinum credit terms for additional cards and reversal-on-refund.
- The Amex Offers FAQ wrong-card statement was seen via search index only.

## Sources

- Amex Disputes Reference Guide 2024PROP — https://www.americanexpress.com/content/dam/amex/us/merchant/pdf/manage-disputes/US-Disputes-Reference-Guide.pdf
- Amex Merchant Operating Guide, April 2026 — https://icm.aexp-static.com/content/dam/gms/en_us/optblue/us-mog.pdf
- Amex Merchant Reference Guide U.S., Oct 2021 — https://www.americanexpress.com/content/dam/amex/us/merchant/merchant-channel/US-Reference-Guide.pdf
- Amex Merchant Regulations landing page — https://www.americanexpress.com/us/merchant/merchant-regulations.html
- Amex Recurring Billing factsheet — https://www.americanexpress.com/content/dam/amex/us/merchant/pdf/manage-disputes/Amex_Recur_Billing_Factsheet.pdf
- Amex Managing a Dispute Case — https://www.americanexpress.com/us/merchant/support-center/disputes/managing-a-disputes-case.html
- Amex TPP Managing Disputes — https://www.americanexpress.com/us/merchant/tpp/manage-disputes.html
- Amex Cardmember dispute FAQ — https://www.americanexpress.com/us/customer-service/faq.dispute-a-charge.html
- American Express FY2020 Form 10-K — https://www.sec.gov/Archives/edgar/data/4962/000000496221000013/axp-20201231.htm
- Platinum Cardmember Agreement (03/31/2023) — https://www.americanexpress.com/content/dam/amex/en-us/company/legal/cardmember-agreements/public-site-2023-q1-pdf-cmas/cps-charge/platinum-card-03-31-2023.pdf
- Amex Offers standard terms — https://www.americanexpress.com/en-us/benefits/offers/partner-terms/
- U.S. Consumer Platinum Fact Sheet (2025 refresh) — https://www.americanexpress.com/content/dam/amex/en-us/company/press-kits/platinum-refresh/U-S-Consumer-Platinum-Card-Fact-Sheet.pdf
- Amex Credit Intel: Resy credit — https://www.americanexpress.com/en-us/credit-cards/credit-intel/resy-credit/
- Amex Credit Intel: Airline fee credit — https://www.americanexpress.com/en-us/credit-cards/credit-intel/using-your-american-express-platinum-airline-credit/
- 12 CFR 1026.13 — https://www.consumerfinance.gov/rules-policy/regulations/1026/13/
- 12 CFR 1026.12 — https://www.consumerfinance.gov/rules-policy/regulations/1026/12/
- [S] Chargeflow, Amex chargebacks — https://www.chargeflow.io/chargebacks-101/amex-chargebacks
