# 01 — Domain Research: Card Dispute Investigation

> **Status:** Research checkpoint. No design has been committed yet. This document records what the domain actually looks like so the use case, data ecosystem, and memory design can be built on verified ground.
>
> **Research date:** 13 September 2026. Rule editions referenced: *Visa Core Rules and Visa Product and Service Rules, 18 April 2026* (read in full-text for chapter 11 and section 4.1.24); *12 CFR 1026 (Reg Z)* and *12 CFR 1005 (Reg E)* from the CFPB eCFR mirror.

## Source-quality legend

Every claim below is tagged with how much it should be trusted.

| Tag | Meaning |
|---|---|
| **[P]** | Primary rule text I read directly (Visa Rules PDF, CFR text, CFPB official interpretation) |
| **[R]** | Regulator publication (CFPB supervisory highlights, withdrawn-guidance notices) |
| **[N]** | Network press release / network-sponsored research (true statements about *their* product, but promotional) |
| **[V]** | Vendor marketing (treat numbers as claims, not facts) |
| **[S]** | Secondary practitioner source (chargeback-industry blogs, acquirer docs) — usually right on structure, sometimes stale on details |
| **[A]** | Academic / open-source |
| **[K]** | My own domain knowledge, not re-verified in this pass — **flagged for verification** |

---

## 1. Corrections to the brief

The brief is directionally right but several details would produce an unrealistic system if taken literally.

1. **"cardholder claim → issuer investigation → provisional credit → representment → pre-arbitration → arbitration" is not one flow — it is at least two, and the stages differ by dispute category.**
   - Visa splits disputes into **Allocation** (categories 10 Fraud, 11 Authorization) and **Collaboration** (12 Processing Errors, 13 Consumer Disputes). In Allocation there is **no Dispute Response (representment) stage**: the acquirer's only move is a *pre-Arbitration attempt* within 30 days, which the issuer answers within 30 days, and the **acquirer** files arbitration within 10 days. In Collaboration the acquirer makes a Dispute Response within 30 days, the **issuer** makes the pre-Arbitration attempt, and the **issuer** files arbitration. **[P]** Visa Rules §11.2.2 (ID 0030212), §11.2.3 (ID 0030213).
   - There is also a **pre-dispute stage** that the brief omits and that the industry now considers the main battleground: merchant contact, Visa Order Insight / Rapid Dispute Resolution, Ethoca Consumer Clarity/Alerts, Mastercard First-Party Trust. **[N][S]**
   - And an **issuer-internal fraud-reporting step** that must precede a fraud dispute: *"Before initiating a Dispute, an Issuer must report the Fraud Activity to Visa."* **[P]** §11.7.5.2.

2. **Provisional credit is not a legal requirement for credit cards.** Reg Z §1026.13(d) says the consumer *need not pay* the disputed amount and the creditor *may not collect or report it delinquent* while the dispute is pending. **[P]** Issuers commonly post a temporary credit anyway as practice. Mandatory provisional credit (within 10 business days if the investigation runs longer) is a **Reg E / debit** rule, §1005.11(c)(2). **[P]** This matters for the data model: "provisional credit" is a policy choice on credit and a legal clock on debit.

3. **The customer does not have to contact the merchant first under Reg Z — but the network rules require it for most consumer disputes.** Official interpretation to §1026.13: *"a consumer is not required to first notify the merchant… before providing a billing-error notice."* **[P]** Visa 13.1, 13.3, 13.5, 13.7 and 12.6 (paid by other means) all require that *"the Cardholder must attempt to resolve the dispute with the Merchant"* and impose 15-day waiting periods. **[P]** So the issuer has a live legal obligation to investigate *before* it has a valid chargeback right. That gap is load-bearing for the design (see §3).

4. **"Charged a price that doesn't match what was agreed" has no obvious reason code — and the obvious ones are explicitly invalid.** Visa 13.3 lists *"A Dispute regarding a price discrepancy"* as invalid; Visa 12.5 (Incorrect Amount) is invalid for *"A T&E Transaction in which there is a difference between the quoted price and the actual charges"* and where *"the Merchant has the right to alter the Transaction amount without the Cardholder's consent."* **[P]** 12.5 is really for addition/transposition errors. Price disputes route to 13.5 Misrepresentation, to the delayed/amended-charge rules, or to *no network right at all* — while Reg Z may still treat it as a billing error ("not delivered as agreed"). This is exactly the "multiple policies appear to apply" case the brief wants, and it's real.

5. **Friendly-fraud share figures disagree by a factor of three to four, depending on who publishes them.** Visa: first-party misuse is *~20% of fraud disputes globally, up to 30% for high-volume online merchants.* **[N]** Mastercard-cited figures: *"75% of fraud experienced by online businesses is first-party"* and chargeback growth *"nearly 80% driven by friendly fraud."* **[N][S]** Ethoca marketing: *"up to 80% of all credit card fraud."* **[V]** These measure different denominators (fraud disputes vs merchant-experienced fraud vs all chargebacks) and come from parties with different incentives. **The POC should not hard-code a "most disputes are fraud" prior**; background data should use a moderate, stated rate and the doc should explain why.

6. **"Discover" and "Amex" are not the same shape as Visa/Mastercard.** Amex and Discover historically operate as both issuer and network (Amex is closed-loop; Discover also issues), so the issuer-vs-acquirer evidence exchange is internal. **[S]** Capital One completed its acquisition of Discover in 2025 **[K — verify date/network-migration status]**. For an issuer-side POC, Amex/Discover reason codes are mostly relevant as *merchant-descriptor/mapping* data, not as a separate dispute workflow the agent drives. Recommendation: model Visa deeply, Mastercard as a second rulebook, and Amex/Discover as reference mappings only.

---

## 2. The real dispute lifecycle (issuer view)

### 2.1 Stages

```
 Cardholder contact (app/phone/chat/letter)
   │
   ├─ Intake: identify txn(s), capture narrative, authenticate cardholder (secure channel
   │          matters: Visa lets issuer "certify" instead of a signed letter only if intake
   │          was via secure online/telephone banking — §11.7.1, §11.10.1 [P])
   │
   ├─ Triage / classification
   │     • Is it actually a dispute? (descriptor confusion, pending auth, already refunded)
   │     • Regulatory regime: Reg Z (credit) / Reg E (debit, prepaid) / non-US
   │     • Fraud vs non-fraud (mutually exclusive in network rules — see §4.3)
   │     • Write-off below threshold? (common practice; see §7.3)
   │
   ├─ Pre-dispute resolution (optional but increasingly standard)
   │     • Visa Order Insight lookup / RDR auto-accept / Ethoca Consumer Clarity [N][S]
   │     • Ask cardholder to contact merchant (required for most 13.x)
   │
   ├─ Regulatory clock starts (Reg Z: ack ≤30 days, resolve ≤2 billing cycles/≤90 days) [P]
   │
   ├─ Fraud reporting (TC40 to Visa / SAFE to Mastercard) — before a fraud dispute [P for Visa]
   │
   ├─ Dispute (first chargeback) filed via VROL / Mastercom
   │     ── Visa Allocation (cat 10/11) ─────────────── Visa Collaboration (cat 12/13) ──
   │     acquirer pre-Arb attempt ≤30d                   acquirer Dispute Response ≤30d
   │     issuer pre-Arb response ≤30d                    issuer pre-Arb attempt ≤30d
   │       (must certify cardholder was shown             (must certify cardholder reviewed
   │        compelling evidence and still disputes)        merchant evidence — new Apr 2026 for 13.1)
   │     acquirer files Arbitration ≤10d                 acquirer pre-Arb response ≤30d
   │                                                     issuer files Arbitration ≤10d
   │
   ├─ Final cardholder resolution
   │     • Reg Z: if no error / different error → written explanation, documents on request,
   │       re-bill with grace period [P §1026.13(f),(g)]
   │     • Issuer can lose the chargeback but still owe the cardholder (and eat the loss)
   │
   └─ QA / audit sampling, complaint handling, regulator exam trail
```

### 2.2 Visa timelines (primary text, April 2026 edition)

| Item | Rule | Source |
|---|---|---|
| Most dispute time limits | 120 calendar days from Transaction Processing Date | [P] per condition |
| 13.1 / 13.3 / 13.7 alternate start | 120 days from expected/actual receipt date, capped at 540 days from processing | [P] §11.10.2.4, .4.4, .8.4 |
| 13.3 alternate | 60 days from issuer's first cardholder notice **if** there's evidence of ongoing merchant negotiation within 120 days | [P] §11.10.4.4 |
| 13.6 Credit Not Processed | wait 15 days from credit receipt date; ≤120 days from that date | [P] §11.10.7.4 |
| Waiting periods | 15 days after return/cancel (13.1, 13.3, 13.7); **30 days** for MCC 4722 travel agencies & third-party ticket agencies (13.1); 60 days after a bonding-authority claim (Europe) | [P] |
| Dispute Response / pre-Arb / pre-Arb response | 30 / 30 / 30 days | [P] §11.2.2–11.2.3 |
| Arbitration filing | 10 days from pre-Arb response | [P] |
| Reversal of own action | ≤31 days, if opponent hasn't moved on | [P] §11.3.3 |
| One dispute per transaction | *"An Issuer must not initiate a Dispute for the same Transaction more than once"* (except 10.5) | [P] §11.2.1 |
| Arbitration case bundling | max 10 transactions; same credential, acquirer, merchant, location, condition | [P] §11.3.1 fn 2 |
| Missed deadline | *"the Dispute cycle will be considered closed and that Member will be responsible for last amount received"* | [P] §11.2.1 |
| Minimum dispute (T&E) | USD 25 for most conditions; from 18 Apr 2026 either txn amount or partial amount must be ≥ USD 25 | [P] §11.4.3 |
| Partial disputes | allowed; surcharge pro-rated | [P] §11.4.1 |
| FX difference | liable party bears conversion-rate difference; issuer may pre-arb if merchant refunded full amount in merchant currency and issuer lost on FX | [P] §11.4.2, §11.2.2 |
| Prior credit | if merchant credited before the dispute, issuer must apply it or explain why it doesn't resolve the dispute; credits that don't match can only be applied to txns ≤120 days old | [P] §11.2.2 fn 1 |

### 2.3 Mastercard (secondary sources — official guide was 403-blocked)

The Mastercard *Chargeback Guide – Merchant Edition* is dated **19 May 2026** but could not be fetched. Secondary sources agree on: first chargeback 120 days (some 90-day categories); second presentment 45 days; pre-arbitration 45 days; response 30 days; arbitration after. **[S — verify]** Reason codes are consolidated into four families: Authorization (4808), Fraud (4837, 4840, 4849, 4863, 4870, 4871), Cardholder Dispute (4853 absorbing legacy 4855/4859/4860 and — per some sources — 4841), Point-of-Interaction Error (4831, 4834, 4842, 4846, 4850, 4999). **[S]** Sources disagree on whether 4841 is still standalone. Fee schedules published by vendors (e.g. arbitration $150 + $250 admin) are **unverified**.

**Mastercard First-Party Trust** (US 2024, expanded 2025): merchant shares device/delivery/identity data matched against ≥2 prior undisputed transactions; liability shifts to issuer; delivered via Ethoca Consumer Clarity and 3DS Identity Check Insights. **[N][S]** Functionally Mastercard's analogue of Visa CE 3.0.

### 2.4 Amex / Discover

Amex: 34 codes in categories A (authorization), C (cardmember dispute: C02, C04, C05, C08, C14, C18, C28, C31, C32), F (fraud: F10, F14, F24, F29, F30, F31), FR (programs: FR2, FR4, FR6), M, P (processing: P01, P03, P04, P05, P07, P08, P22, P23), R (inquiry: R03, R13). Inquiry precedes chargeback; merchant response 20 days. **[S]**
Discover: alphabetic codes — UA01/UA02/UA05/UA06/UA10/UA11 fraud; AA (does not recognize), AP, AW, CD, DP, IC, NF, PM, RG (non-receipt), RM (quality), RN2; AT/DA/EX/NA authorization; IN/LP processing. **[S]**

---

## 3. Two clocks: regulation vs network rules

This is the single most under-appreciated source of complexity, and it is invisible to anyone who models disputes as "just reason codes."

### 3.1 US Regulation Z (credit cards) **[P]**

| Provision | Rule |
|---|---|
| §1026.13(a) billing errors | (1) credit not to consumer or person with actual/implied/apparent authority; (2) not identified properly; (3) goods/services **not accepted or not delivered as agreed**; (4) payment/credit not posted; (5) computational error; (6) request for clarification/documentation; (7) statement not delivered |
| §1026.13(b) notice | received ≤ **60 days after the first statement** reflecting the error was transmitted |
| §1026.13(c) | written acknowledgment ≤ **30 days**; resolution ≤ **2 complete billing cycles, max 90 days** |
| §1026.13(d) pending | no collection of disputed amount; no adverse credit report; no closing/restricting account *solely* for exercising rights |
| §1026.13(f) no error found | written explanation of reasons; copies of documentary evidence on request |
| §1026.13(f)(3)(ii) non-delivery | *"shall not deny… unless it conducts a reasonable investigation and determines that the property or services were actually delivered… as agreed"* |
| §1026.13(f)(3)(i) unauthorized | may review purchase pattern, delivery location vs residence, where purchases were made vs normal shopping, signatures, request documentation / written statement / police report, ask about the consumer's knowledge of the person |
| Interpretation to 13(f)(3) | **may not require an affidavit or statement under penalty of perjury**; **may not automatically deny solely because the consumer fails to comply with a request** — but *if the creditor otherwise has no knowledge of facts confirming the error*, non-cooperation may justify ending the investigation |
| Forfeiture | non-compliance → forfeiture under 15 U.S.C. 1666(e) (statute: up to $50 per error) |
| §1026.12(b) unauthorized use | liability ≤ lesser of **$50** or amount before notice. "Unauthorized" = by someone **without actual, implied, or apparent authority** *and from which the cardholder receives no benefit* |
| Comment 12(b)(1)(ii)-3 | if the cardholder gave the card to someone (family member, coworker) who **exceeds** the authority, the cardholder is liable **until they notify the issuer** that use is no longer authorized |
| §1026.12(c) claims & defenses | cardholder may assert merchant claims against the issuer if: good-faith attempt to resolve with merchant, amount > $50, and same state or within 100 miles (limits waived if issuer controls/affiliated with merchant or mailed the solicitation) |
| Independence | *"rights under §1026.13 are independent of §1026.12(b) and (c)"* |

### 3.2 US Regulation E (debit/prepaid) **[P]** (liability tiers **[K]**)

Notice ≤60 days after statement; investigate in **10 business days** (20 for new accounts), or provisionally credit within 10 business days and extend to **45 days** (**90** for POS debit, foreign-initiated, new accounts); report results in 3 business days; if reversing provisional credit, notify and honor checks for 5 business days. Consumer liability tiers under §1005.6: $50 if reported within 2 business days of learning of loss/theft; up to $500 after; unlimited for transfers on a statement not reported within 60 days. **[K — tiers not re-fetched this pass]**

### 3.3 Regulatory posture (context, not rule changes)

The CFPB withdrew **67 guidance documents** on 12 May 2025 and rescinded its enforcement/supervision priority documents in April 2025. **[R][S]** The *regulations* themselves (Reg Z, Reg E) are unchanged. For the POC this means: encode the regulation text as binding; treat supervisory guidance as versioned, possibly-withdrawn interpretive material. Earlier CFPB supervisory findings remain instructive about real failure modes — issuers using third parties *"failing to acknowledge billing error notices in writing; not properly limiting cardholder liability… furnishing adverse credit report information… failing to timely investigate."* **[R]**

### 3.4 Non-US

- **EU PSD2 Art. 73**: refund unauthorized payment **by end of next business day**, unless the PSP has reasonable grounds to suspect fraud and notifies the national authority in writing. **Art. 74(2)**: if SCA was not required, the payer bears no loss unless they acted fraudulently. PSD3/PSR provisional agreement keeps next-business-day refund with *"objectively justified reasons to suspect fraud or gross negligence."* **[S]** (Article text via EBA single rulebook — structure verified; PSR final text status as of Sep 2026 **[verify]**).
- **UK Consumer Credit Act s.75**: statutory joint-and-several liability of the credit card issuer for supplier breach/misrepresentation, **£100–£30,000** item price; doesn't apply to debit, charge cards, BNPL. Chargeback in the UK is scheme rule, not statute. **[S]**
- **Visa Europe 13.7**: off-premises/distance-selling contracts carry a **14-day cancellation right** in the network rules themselves, with carve-outs (made-to-measure, perishables, sealed hygiene goods, digital downloads, T&E, merchants in Israel/Switzerland/Türkiye). **[P]**
- **Singapore MAS E-Payments User Protection Guidelines** (revised, effective 16 Dec 2024): account-holder liability capped at **S$100** unless recklessness; **S$1,000** protection for third-party-caused losses. **[S]** Reporting and investigation timelines could not be verified (MAS site unavailable). **[verify]**

### 3.5 Where the clocks collide (design-critical)

| Collision | Consequence |
|---|---|
| Reg Z investigation (≤90 days) runs in parallel with Visa's 120-day dispute window **and** the 15-day merchant-contact wait | An issuer that waits for the cardholder to contact the merchant can blow the Reg Z deadline; an issuer that files early files an **invalid** dispute (and can only dispute once). The agent has to schedule around both clocks. |
| A missed **network** deadline doesn't discharge the **regulatory** obligation | Issuer still owes a Reg Z resolution; the loss moves from merchant to issuer. Data must distinguish "cardholder outcome" from "chargeback outcome". |
| Reg Z "unauthorized" excludes use by someone with *apparent authority*; Visa Compelling Evidence item 11 lets the merchant win with *"evidence that the Transaction was completed by a member of the Cardholder's household or family."* | Household-member cases can be unauthorized under Reg Z (card taken without permission) and still lost at pre-Arb — issuer absorbs. Or authorized under Reg Z (card previously shared) and correctly denied. The facts that decide it live in intake statements, prior-use history, and device data. |
| Cardholder notice > 60 days after statement (Reg Z untimely) but < 120 days after processing (network-valid) | Issuer has no Reg Z obligation but may still charge back voluntarily. Policy choice, not rule. |
| §1026.12(c) claims & defenses has no 60-day-from-statement clock | A quality dispute raised "late" can still be a valid claim against the issuer if balance remains outstanding. |

---

## 4. Network rules in detail (Visa, primary text)

### 4.1 Condition map and the invalidators that matter

| Cond. | Name | Invalid when (selected) | Key rights/limits |
|---|---|---|---|
| 10.1–10.3 | EMV counterfeit / non-counterfeit / other card-present fraud | — | card-present; chip liability shift |
| **10.4** | Other Fraud – Card-Absent | ECI 5 + CAVV (3DS authenticated); ECI 6 attempt with CAVV (non-prepaid); **CVV2 result N but issuer approved anyway**; issuer already reported fraud on the credential before approval; **>35 disputes on the account in 120 days**; fraud type 3/C/D; **CE 3.0 match** (below); crypto "deceived into sending" (that's scam, not fraud) | issuer must report fraud first; certification of non-participation |
| 10.5 | Visa Fraud Monitoring Program | — | only condition allowing a second dispute |
| 11.1–11.3 | Card recovery bulletin / declined auth / no auth or late presentment | — | allocation flow |
| 12.2 | Incorrect transaction code | — | amount can exceed txn (debit↔credit) |
| 12.3 | Incorrect currency | — | DCC-related |
| 12.4 | Incorrect account number | — | |
| **12.5** | Incorrect amount | T&E quoted vs actual; no-show; advance payment; merchant has right to alter amount | limited to the difference |
| **12.6** | Duplicate / paid by other means | payments to **different merchants** (unless passed through, e.g. travel agent → hotel) | "same credential, same date, same amount"; if different acquirers and issuer can't tell which is invalid, **second** acquirer is liable; txns with Multiple Clearing Sequence Numbers from one auth count as one |
| 12.7 | Invalid data | — | |
| **13.1** | Merchandise/services not received | cardholder cancelled before expected delivery (buyer's remorse); held by cardholder-country customs; **cardholder says it's fraud**; quality dispute; partial advance payment when merchant still willing | limited to portion not received; late delivery → must return/attempt; **cardholder letter required if ≥3 non-receipt disputes at same merchant on same card within 30 days**; from 18 Apr 2026 issuer's pre-Arb must certify it reviewed merchant's delivery evidence with the cardholder and addresses signature/photo |
| **13.2** | Cancelled recurring | installment; **unscheduled credential-on-file**; **cardholder-initiated txn**; cardholder says fraud; **from 18 Apr 2026: cancellation after the txn date** | limited to unused portion; merchant rebuttal: cardholder used service after cancellation, or cancellation date was later (e.g. end of paid period) |
| **13.3** | Not as described / defective | VAT; returned goods held by non-merchant-country customs; cardholder says fraud; restaurant food quality; **price discrepancy** | must return or *attempt* to return — "attempt" only counts if merchant refused return/RMA, told cardholder not to return, disappeared, or gave no return instructions; limited to returned value / unused portion |
| 13.4 | Counterfeit merchandise | — | |
| **13.5** | Misrepresentation | quality-only disputes; VAT | covers **trial/intro offer where cardholder wasn't clearly told of further transactions**; timeshare resellers; debt relief; tech-support scams; business opportunities; fund-recovery scams; outbound telemarketing; investment platforms blocking withdrawals |
| **13.6** | Credit not processed | cardholder says fraud; AFD; cash-back portion | requires a credit/void receipt; 15-day wait |
| **13.7** | Cancelled merchandise/services | quality disputes unless a credit receipt exists; cardholder says fraud | merchant didn't disclose — **or disclosed but didn't apply** — its limited return/cancel policy; guaranteed reservation cancelled per policy but billed no-show; no-show billed for >1 night; cancelled within 24h of reservation confirmation; timeshare within 14 days |
| 13.8 / 13.9 | OCT not accepted / ATM cash not received | — | |

### 4.2 Compelling Evidence 3.0 — exact mechanics, and a live version change

**Through 23 October 2026** (Disputes *processed* on or before that date) — a 10.4 dispute is invalid if **the same Payment Credential** was used in **2 previous transactions not reported as fraud**, processed **more than 120 days** earlier (and **no more than 365 days** before the dispute processing date), with a detailed description of goods for all three (or a purchase order number for Visa Secure ECI 7 + CAVV transactions), and **device ID, device fingerprint, or IP address plus at least one more** of: customer account/login ID, full delivery address, device ID/fingerprint, IP address matching. **[P]** §11.7.5.3, ID 0030254.

Data-quality requirements baked into the rule **[P]**:
- login ID: unique, clear text, not hashed, recognizable by the cardholder
- delivery address: **full** address incl. street, city, state, postal code, country; clear text
- device ID: ≥15 characters (e.g. IMEI), clear text, not hashed
- device fingerprint: derived from ≥2 hardware/software properties, ≥20 characters, **may** be hashed
- IP: cardholder's **public** IPv4/IPv6, clear text

**From 24 October 2026** (Disputes processed on or after) **[P]** Summary of Changes + §11.7.5.3/§11.7.5.6:
- the prior transactions may be **at one or more merchants** (multi-merchant) — previously same merchant
- "same Card **or a Payment Credential associated with that Card (e.g. a Token)**" — token/PAN linkage counts
- 120 days measured from **when the Dispute was submitted**
- login IDs **include those of an Agentic Payment Provider**
- **device ID and device fingerprint count as one element** — can't be used as two matches
- acquirer may only submit transaction data **it** accepted and processed
- purchase-order-number path extended to Visa Token Service (TAVV) and Visa IDX match key

> **Why this matters:** today (13 Sep 2026) is six weeks before a real scheme change. A dispute on the same facts can be valid or invalid depending on *when it is processed*, not when the transaction happened, and not when the pre-Arb arrives. That is policy versioning with an effective-date rule most engineers would key to the wrong date.

Allowable Compelling Evidence for pre-Arbitration (Table 11-6, abridged) **[P]**: photo/email linking recipient to cardholder or showing cardholder uses the goods; in-store pickup signature/ID; delivery to the AVS-Y/M address (no signature needed); digital goods: description + download date + ≥2 of {IP, device ID, name+email on merchant profile, verified profile accessed before txn, site accessed by cardholder on/after txn date, same device+credential used undisputed}; delivery to a business address where cardholder worked; signed mail/phone order form; passenger transport: boarding pass scan / miles / add-on purchases; T&E loyalty or undisputed related purchases; **≥3 of {login ID, delivery address, device ID, email, IP, phone} used in an undisputed transaction**; **household or family member completed the transaction**; non-disputed payments for the same item; recurring: contract + usage + prior undisputed payment; crypto: wallet address / tx hash.

And the issuer's counter-obligation **[P]** §11.2.2: to decline a pre-Arb backed by compelling evidence the issuer must certify either that the contact info in the evidence **doesn't match** the cardholder's records, or that it **contacted the cardholder to review the evidence** and records why they still dispute. If evidence shows delivery to the AVS-Y address, the issuer must **explain why AVS returned Y**.

### 4.3 Fraud and non-fraud are mutually exclusive

13.1, 13.2, 13.3, 13.6, 13.7 all list *"A Transaction that the Cardholder states is fraudulent"* as invalid. **[P]** A cardholder narrative like *"I never ordered this, and anyway I cancelled it"* forces a decision. The issuer may change the condition only at pre-Arb, only if the original condition was valid, and only based on new information from the acquirer's response. **[P]** §11.2.3. Choosing wrong at intake is expensive and often unrecoverable.

### 4.4 Merchant obligations that become issuer evidence

- **Recurring:** simple cancellation (online if signed up online); disclose fixed dates/intervals; **notify ≥7 days before a trial/intro/promo period ends**, with amount, date, and a cancellation link. **[P]** §5 Table 5-21.
- **Advance payments:** only T&E, custom goods, partially-available face-to-face orders, and tourism activities; T&Cs must state shipping date. **[P]**
- **Limited return/cancel policy:** must be disclosed at time of transaction (§5.4.2.5) — 13.7 turns on it. **[P]**

### 4.5 Agentic commerce — a real rule set with no matching dispute condition

Visa's April 2026 rules define **Agentic Payment Providers** (apps that *"search, discover, and purchase products and services"* on a cardholder's payment instruction) and **Agentic Transactions**. **[P]** §4.1.24, glossary IDs 0031164–0031165. Requirements include:
- before transacting: cardholder consent to tokenize and to the *cardholder-defined payment instruction*; a stated **expiration date** for that instruction; **"Cardholder acknowledgement that they are responsible for actions taken by the Agentic Payment Provider"**; identity verification
- during: *"Use only the Cardholder-defined criteria for purchasing"*; can't aggregate transactions; no card-present
- policy acceptance on the cardholder's behalf (limited refund policies, guaranteed reservation cancel-by dates, estimated auths, DCC) either at checkout or pre-consented at instruction time
- after: order confirmation available **≥120 days** with description, merchant contact, price, currency, cancellation policy; for repeated agentic transactions, a statement that they continue until cancelled
- initiators of agentic transactions *"are not considered Merchants."*

The dispute chapter contains **no condition** for "the agent bought something outside my instructions." The only chapter-11 reference is login IDs for Agentic Payment Providers counting as CE 3.0 evidence from 24 Oct 2026. **[P]** So a cardholder who says *"my AI agent booked a non-refundable flight I didn't ask for"* has: acknowledged responsibility for the agent (weighs against 10.4), a possible 13.3/13.5 argument if the instruction record shows the purchase violated criteria, and Reg Z's "apparent authority" question. **This is a genuinely open policy question in September 2026 — an honest escalation case, not a manufactured one.**

---

## 5. First-party misuse: how it's actually detected and rebutted

### 5.1 Signals issuers can see (their own data)

- Prior disputes by the cardholder; outcomes; how many are within the 35-in-120-day and 3-in-30-day thresholds **[P thresholds]**
- Undisputed history at the same merchant / same device / same delivery address **[P CE3.0 elements]**
- Authentication at the time: 3DS result (ECI/CAVV), CVV2 result, AVS result **[P for invalidators]**
- Card-present vs absent, token vs PAN, wallet
- Purchase pattern vs history; delivery location vs residence; purchase location vs normal shopping — the Reg Z-sanctioned factors **[P]**
- Cardholder online-banking session data: login from new device, password reset, email/phone change shortly before the transaction — the account-takeover tell **[S]**
- Card status history: card reported lost/stolen, reissued, authorized users added
- Intake behavior: narrative changes across contacts, claim type switching, speed of claim after delivery

### 5.2 Signals only the merchant holds (arrive late, via Order Insight/RDR/pre-Arb)

Order detail, account login ID, device ID/fingerprint, IP, shipping address, carrier tracking and proof of delivery (full address required for 13.1 — *"tracking with partial address is not permitted"* **[P]**), digital usage logs, T&C acceptance, cancellation records, chat/email transcripts, refund records.

### 5.3 What the rules forbid the issuer from doing with suspicion

- Can't require an affidavit or statement under penalty of perjury; can't auto-deny for non-cooperation **[P]**
- Can't close/restrict the account solely for exercising dispute rights **[P]**
- Must extend the same protections regardless of Visa card type **[P]** §11.1.2
- ECOA/Reg B and UDAAP apply to how "suspicion" is operationalized **[K — fairness constraints on using protected-class proxies such as neighborhood, language, age in fraud scoring; verify specific guidance]**

### 5.4 Account takeover vs friendly fraud

The discriminating evidence is **sequence**, not presence: ATO shows credential/contact changes (password reset → email change → new device → shipping-address change) clustered shortly before the purchase, often from a new geography; friendly fraud shows continuity (same device, same address, prior undisputed use, consumption of the goods). **[S]** No single indicator suffices. **Crucially, CE 3.0 can be satisfied by an ATO**: an attacker operating inside the cardholder's own merchant account inherits the login ID and delivery address and may share a residential/carrier-grade-NAT IP. A rules engine that treats "CE 3.0 match" as "cardholder did it" will deny a true fraud victim.

---

## 6. The evidence ecosystem

### 6.1 Who holds what, and how reliably it arrives

| Evidence | Holder | Typically available? | Notes |
|---|---|---|---|
| Authorization record (amount, MCC, POS entry mode, ECI, CAVV presence, CVV2 result, AVS result, token flag, COF/recurring indicator, auth code) | Issuer | Always | System of record; Visa arbitration uses V.I.P. auth records [P §11.13.2] |
| Clearing record (processing date, ARN, merchant descriptor, city, amount, currency, enhanced data) | Issuer | Always | Descriptor often ≠ brand name; processing date ≠ txn date |
| Statement cycle dates | Issuer | Always | Reg Z 60-day clock anchor |
| Cardholder profile, tenure, authorized users, addresses, contact changes | Issuer | Always | Address history needed for AVS explanation |
| Online-banking/app session & security events | Issuer | Usually | Different system; timestamp zone often differs |
| Prior disputes & outcomes | Issuer | Usually | 1 in 5 FIs don't track disputes by cardholder [N Javelin/Mastercard 2026] |
| Card-status events (lost/stolen, reissue, freeze) | Issuer | Always | |
| Intake narrative, call summaries, chat logs | Issuer | Always, messy | Free text; claim type often mis-selected by agents |
| Fraud reports (TC40/SAFE) for the credential | Issuer/network | Always | Timing relative to auth matters for invalidators |
| Order details, item description | Merchant | Via Order Insight / response | Often missing for small merchants |
| Login ID, device ID/fingerprint, IP | Merchant | Large e-com: yes; small: rarely | Must meet CE3.0 format rules |
| Tracking & proof of delivery | Merchant/carrier | Physical goods: usually | Partial addresses, "delivered to mailbox", GPS scans, split shipments |
| Digital usage/download logs | Merchant | Digital: sometimes | Stripe: usage logs +10pp win rate [V/N] |
| T&C, cancellation policy, trial notice emails | Merchant | Sometimes | 7-day trial-end notice is a checkable obligation |
| Refund/credit records | Merchant + issuer clearing | Credits in clearing: always; off-network refunds: rarely verifiable | Stripe: processor refunds +63pp, off-network refunds +6pp *"likely because issuing banks cannot independently verify non-network refunds"* [V] |
| Merchant dispute rate / monitoring status | Network/acquirer | Partial | VAMP merchant threshold 1.5% from 1 Apr 2026 [S] |
| Agent payment instruction & order confirmation | Agentic Payment Provider | Upon written request [P] | New in 2026 |

### 6.2 Authentication/verification codes **[K — standard values; verify against network specs before generating data]**

- **AVS (Visa US):** Y street+ZIP match; A street match only; Z ZIP match only; N no match; U unavailable; R retry; S not supported; G global non-participant; international variants B/C/D/I/M/P.
- **CVV2 result:** M match; N no match; P not processed; S merchant indicated not present; U issuer not certified / unable to verify (Visa redefined U handling 18 Apr 2026 [P]).
- **ECI:** Visa 05 authenticated, 06 attempted, 07 non-authenticated e-com; Mastercard 02 authenticated, 01 attempted, 00 non-authenticated.
- **EMV 3DS transStatus:** Y authenticated (frictionless or challenge), N not authenticated, U couldn't perform, A attempts, C challenge required, R rejected, I informational only. **[S]**

### 6.3 Evidence *weight* is rule-relative

The same artifact means different things under different conditions: proof of delivery wins 13.1 but is irrelevant to 13.3; a CE 3.0 match defeats 10.4 but not 13.1; a household-member photo defeats 10.4 and is meaningless for 13.2. Evidence must be stored neutrally and weighed at decision time against the condition in play.

---

## 7. How the industry solves it

### 7.1 Two sides, opposite incentives

| | Issuer-side (this POC) | Merchant-side |
|---|---|---|
| Goal | Correct outcome for cardholder within Reg Z/E; recover loss from merchant where valid; control ops cost; avoid regulatory findings | Win representment; prevent disputes; stay under VAMP/ECM thresholds |
| Wins when | Decision is right and defensible | Dispute is reversed or prevented |
| Tools | VROL, Mastercom, Visa Dispute Intelligence / Doc Analyzer / Case Manager [N]; Quavo QFD + ARIA [V]; Pega Smart Dispute for Issuers [V]; Fiserv/FIS platforms [K] | Verifi Order Insight & RDR, Ethoca Alerts & Consumer Clarity, Mastercard First-Party Trust [N]; Stripe Smart Disputes [V]; Adyen Disputes API [S]; Chargebacks911, Chargeflow, Justt, Chargeback Gurus [V] |
| Failure mode | Rubber-stamping claims (writes off merchant-recoverable losses) or over-denying (regulatory + customer harm) | Auto-fighting everything; submitting templated evidence that doesn't match the condition |

A useful skeptical framing **[S]**: *"If merchant-side AI gets better at preventing and winning disputes at roughly the same rate issuer-side AI gets better at filing and processing them cheaply, the fight doesn't end. It just moves faster."* The same source reports banks under backlog would *"simply accept every claim under 15 euros rather than investigate it."* That's the write-off-threshold practice made explicit.

### 7.2 What product pages reveal about decision logic

- **Pega Smart Dispute for Issuers** **[V]**: a *Reason Code Advisor* — context-based questionnaire whose answers drive rule-based selection of network reason code/condition; *Process AI* predicts probability a dispute passes network validation, used to route high-probability cases to automation and low-probability to humans. → Industry already treats **classification as a decision tree over intake answers** and **routing as a predicted-win problem**.
- **Quavo ARIA ("Automated Reasonable Investigation Agent")** **[V]**: decisions in three buckets — **AutoPay, AutoDeny, refer** — driven by *"likelihood of true fraud, likelihood of friendly fraud, and confidence of the investigation."* 2020 launch claimed no metrics; 2026 messaging claims *"automate up to 90% of casework."* Separately, Quavo states auto-resolution on eligible types *"typically reach 20–25%"*, mostly *"low-complexity Reg E claims."* **The gap between "90%" and "20–25% on eligible low-complexity claims" is the marketing-vs-practice gap in one company's own copy.**
- **Visa (2 Apr 2026)** **[N]**: *Dispute Intelligence* (predictive models over network-wide dispute data), *Dispute Doc Analyzer* (structures merchant documents for issuer analysts), *Visa Dispute Case Manager* (multi-network case platform, NA GA 2026). → The network itself is productizing "summarize merchant evidence into structured fields" — which tells us document-to-structure extraction is a recognized bottleneck.
- **Stripe Smart Disputes** **[V]**: compiles evidence by reason code from data already in Stripe; strong on fraud/duplicate (data lives in the processor), weak where evidence lives outside (per a competitor's critique **[V]**). Stripe's 1M-dispute analysis: delivery confirmation +27pp; with GPS + signature +44pp; tracking submitted *before* delivery only +2pp. **[V, but quantitative and specific]**

### 7.3 Human investigation operations

Verified numbers are scarce. What exists:
- Issuer cost **$9.08–$10.32 per disputed transaction**; **one FTE per ~$13–14K of disputes annually**; typical US FI **>200 back-office staff**. **[N — Mastercard/Datos Insights 2026; figures as reported secondhand, definitions unclear]**
- **~90%** of disputes resolved in consumers' favor; **75%** of consumers go straight to the issuer; merchants resolve **75%** of disputes when contacted first. **[N — Javelin/Mastercard Jan 2026]**
- **91%** of issuers say shipping/delivery data would help. **[N]**
- Visa processed **106M disputes in 2025**, +35% vs 2019. **[N]**
- Job descriptions show the actual task mix **[S]**: intake questioning to pick the right reason, provisional credit, letters, chargeback processing, adjustments; separate **QA analysts** reviewing *"all stages of a dispute with a primary focus on decision accuracy."*

What I could **not** verify and am inferring **[K]**: tiering (Tier 1 intake/simple auto-eligible; Tier 2 investigation; Tier 3 pre-arb/arbitration and complex fraud); handle times of ~15–45 min per non-trivial case; common analyst errors (wrong condition at intake, missed waiting periods, missed pre-arb deadlines, not applying merchant credits, not reviewing merchant evidence with the cardholder, inconsistent treatment of similar cases). These should be presented in the README as practitioner-informed assumptions, not facts.

---

## 8. Academic and open-source work that informs the design

| Work | Relevance |
|---|---|
| **τ-bench** (Sierra, arXiv 2406.12045) + τ²-bench | Agents with DB + tools + **policy documents**; tasks crafted to have **one correct outcome under policy**; **pass^k** reliability metric. Direct template for evaluating a policy-bound investigation agent (consistency across runs matters more than single-run accuracy). **[A]** |
| **RIRAG / ObliQA** (arXiv 2409.05677; RegNLP 2025) | 27,869 questions over ADGM regulation; metric (RePASs) scores whether answers capture **all relevant obligations without contradiction**. Retrieval over rules must be multi-passage and obligation-complete — a single top-k chunk is wrong by construction. **[A]** |
| **FIA framework** (arXiv 2506.11635) | LLM + code execution + vision for card-fraud alert investigation on Sparkov/CCTD; value concentrated on **borderline** cases. Supports sandboxed computation as a first-class tool. **[A]** |
| **Synthetic tabular generators fail on behavioral fraud** (arXiv 2604.13125) | CTGAN/TVAE/GaussianCopula/TabularARGN degrade temporal/velocity patterns 24–39×; **row-independent generators provably cannot reproduce multi-account graph motifs**. → Our generator must be **entity- and event-sequence-based with explicit relationship seeding**, not a tabular GAN. **[A]** |
| **ClaimPilot** (MDPI Future Internet 18(9):465, 2026) | Multi-agent claims adjudication with **deterministic policy evaluation**, immutable audit log, mandatory human review; 150 synthetic claims with independently computed ground truth; failure modes: tool-protocol mismatch, **plan-only execution**, **unreliable numerical reasoning**. (Abstract only; full text 403.) **[A]** |
| Sparkov (1.85M txns/999 customers/2 yrs), PaySim, IBM TabFormer (24M txns), amazon-science fraud-dataset-benchmark | Background-transaction realism references; none contain disputes, orders, deliveries, or policy — confirms we must build the dispute layer ourselves. **[A]** |

---

## 9. Non-obvious insights worth building the demo around

1. **The regulatory clock and the network clock are different races, and losing one doesn't forfeit the other.** "Cardholder outcome" and "chargeback outcome" are separate facts with separate owners.
2. **The obvious reason code is often invalid by rule.** Price discrepancies, fraud-plus-cancellation narratives, post-transaction subscription cancellations — the agent has to prove *eligibility* before arguing *merit*.
3. **Policy effective dates key off the dispute processing date, not the transaction date.** CE 3.0 changes on 24 Oct 2026; 13.2 and CVV2-U changes took effect 18 Apr 2026.
4. **CE 3.0 is a liability rule, not a truth rule.** It says who pays, not who did it. An ATO inside the cardholder's merchant account can satisfy it.
5. **Household-member purchases split Reg Z from the network.** Liability can land on the issuer even when the issuer is right.
6. **Evidence weight is condition-relative**; store evidence neutrally, weigh at decision time.
7. **Cross-cardholder patterns are invisible per case** (shared device/drop address across "unrelated" customers; merchant-level non-delivery clusters) — and 1 in 5 FIs don't even track disputes per cardholder.
8. **Merchant evidence arrives late, in documents**, and the network is building AI just to structure it. Mid-investigation plan revision is a normal consequence of the Dispute Response, not an edge case.
9. **Agentic commerce is live in the rules but not in the dispute framework.** Escalation there is the correct answer, and the reason is verifiable.
10. **"Similar cases resolved differently" is usually explained by one field**: ECI 5 vs 6, AVS Y vs Z, cancellation before vs after the transaction date, return attempted vs merchant refused RMA, 3 vs 2 non-receipt disputes in 30 days, dispute processed 23 vs 24 October.

---

## 10. Preview of design implications (not yet committed)

Candidate hero-scenario seeds, each tied to a verified rule:

| Seed | Rule hook | What breaks a rules engine | What breaks a single prompt |
|---|---|---|---|
| Hotel billed above quoted rate | 12.5 & 13.3 invalid for price; 13.5 / amended-charge rules; Reg Z "not as agreed" | No valid code → auto-deny, ignoring Reg Z duty | Picks 12.5 confidently |
| Digital-goods fraud claim straddling 24 Oct 2026 | CE 3.0 old vs new; device ID + fingerprint no longer double-count; multi-merchant priors | Needs versioned rule + cross-merchant history join | Doesn't know the new rule or applies it to the wrong date |
| "Unauthorized" gaming purchases by a teenager | Reg Z apparent authority; CE item 11 | Can't read intake statements or prior-authorization history | Moralizes; can't traverse device↔household graph |
| CE 3.0 match that is actually ATO | security-event sequence before txn | CE match → deny | Can't see session events it wasn't given |
| Non-receipt ring across unrelated cardholders | 13.1 + graph of addresses/devices | Per-case rules see nothing | No cross-case memory |
| Trial converted to subscription, cancelled after charge | 13.2 invalid post-Apr-2026; merchant's 7-day notice duty → 13.5 | Picks 13.2 → invalid dispute (one shot only) | Misses the version change |
| AI shopping agent bought outside instructions | §4.1.24 duties; no dispute condition | No rule exists | Invents a rule |
| Two identical charges same day | 12.6 vs split shipment with multiple clearing sequence numbers | Flags as duplicate | Flags as duplicate |
| Merchant already refunded in merchant currency | apply credit first; FX-loss pre-Arb | Double recovery or missed FX loss | Arithmetic errors across currencies |
| Serial disputer near 35-in-120 / 3-in-30 thresholds | 10.4 invalidator; 13.1 letter requirement | Blunt threshold denial (unfair to true victims) | No history |
| Late Reg Z notice, still inside network window | 60-day statement clock vs 120-day network clock | One clock only | Doesn't compute statement cycles |

---

## 11. Unverified or conflicting items (to resolve before data generation)

- Mastercard lifecycle timelines, fee schedule, 4841 status, "digital goods ≤ $25" rule — **secondary only**.
- AVS/CVV2/ECI/3DS code tables — **from knowledge**; cross-check against a processor spec before encoding.
- Reg E §1005.6 liability tiers — **from knowledge**; re-fetch.
- MAS EUPG reporting/investigation timelines — **unverified**.
- Capital One–Discover network migration status in 2026 — **not verified**.
- Human ops tiering and handle times — **practitioner inference**.
- Friendly-fraud prevalence — **sources conflict by 3–4×**; choose and justify a background rate.
- ClaimPilot details — **abstract only**.

---

## Sources

**Primary**
- [Visa Core Rules and Visa Product and Service Rules, 18 April 2026 (PDF)](https://usa.visa.com/dam/VCOM/download/about-visa/visa-rules-public.pdf) — §11 Dispute Resolution; §4.1.24 Agentic Platform Requirements; Summary of Changes
- [12 CFR §1026.13 Billing error resolution](https://www.consumerfinance.gov/rules-policy/regulations/1026/13/)
- [12 CFR §1026.13 Official Interpretation](https://www.consumerfinance.gov/rules-policy/regulations/1026/Interp-13)
- [12 CFR §1026.12 Special credit card provisions](https://www.consumerfinance.gov/rules-policy/regulations/1026/12/)
- [12 CFR §1005.11 Error resolution (Reg E)](https://www.consumerfinance.gov/rules-policy/regulations/1005/11/)
- [Visa Compelling Evidence 3.0 Merchant Readiness (Mar 2023)](https://usa.visa.com/content/dam/VCOM/regional/na/us/support-legal/documents/compelling-evidence-3.0-merchant-readiness-mar2023.pdf)
- [EBA Single Rulebook — PSD2 Article 73](https://eba.europa.eu/regulation-and-policy/single-rulebook/interactive-single-rulebook/14600)

**Regulator / legal commentary**
- [CFPB Supervisory Highlights Issue 37 (Winter 2024)](https://files.consumerfinance.gov/f/documents/cfpb_Supervisory-Highlights-Issue-37_Winter-2024.pdf)
- [DWT — CFPB supervisory findings on credit cards](https://www.dwt.com/blogs/financial-services-law-advisor/2017/10/cfpb-highlights-supervisory-findings-related-to-cr)
- [Morgan Lewis — CFPB revokes guidance (2025)](https://www.morganlewis.com/pubs/2025/06/cfpb-revokes-guidance-in-sweeping-rollback-of-agency-policies-and-priorities)
- [Consumer Finance Monitor — CFPB rescinds priorities (Apr 2025)](https://www.consumerfinancemonitor.com/2025/04/17/cfpb-rescinds-enforcement-supervisory-priority-documents-outlines-new-priorities-for-2025/)
- [Norton Rose Fulbright — PSD3 and PSR](https://www.nortonrosefulbright.com/en/knowledge/publications/cedd39c6/psd3-and-psr-from-provisional-agreement-to-2026-readiness)
- [CMS — AG opinion C-70/25 on immediate refunds](https://cms.law/en/aut/legal-updates/CJEU-opinion-of-Advocate-General-victims-of-online-fraud-must-receive-immediate-refunds-from-service-providers)
- [TLT — Connected lender liability (s.75)](https://www.tlt.com/insights-and-events/insight/connected-lender-liability-a-narrower-construction-of-arrangements-under-the-consumer-credit-act)
- [MAS E-Payments User Protection Guidelines](https://www.mas.gov.sg/regulation/guidelines/e-payments-user-protection-guidelines)

**Network announcements / network-sponsored research**
- [Visa — Unveils New Services to Modernize Dispute Resolution (Apr 2026)](https://usa.visa.com/about-visa/newsroom/press-releases.releaseId.22261.html)
- [CU Today — Visa disputes surge 35%](https://www.cutoday.info/Fresh-Today/Visa-Sounds-Alarm-As-Card-Disputes-Surge-35-New-Tools-Target-Rising-Fraud)
- [Visa — Friendly fraud insights](https://corporate.visa.com/en/solutions/visa-protect/insights/friendly-fraud.html)
- [Mastercard — First-Party Trust (Jun 2025)](https://www.mastercard.com/us/en/news-and-trends/press/2025/june/first-party-trust-countering-friendly-fraud.html)
- [Mastercard/Javelin — Chargebacks: The Case for Coordination (Jan 2026)](https://www.mastercard.com/content/dam/mccom/shared/news-and-trends/insights/2026/2026-javelin-chargebacks-white/2026%20Chargebacks%20Javelin%20White%20Paper.pdf) (via [Chargeback Gurus summary](https://www.chargebackgurus.com/blog/mastercard-case-for-coordination))
- [Mastercard Chargeback Guide – Merchant Edition, 19 May 2026](https://www.mastercard.com/content/dam/mccom/shared/business/support/rules-pdfs/chargeback-guide.pdf) (access blocked; cited for existence/date only)

**Vendors / secondary**
- [Quavo — ARIA launch](https://www.quavo.com/news/quavo-inc-launches-ai-that-automatically-processes-fraud-disputes-for-financial-institutions/) · [Quavo QFD](https://www.quavo.com/qfd/)
- [Pega Smart Dispute](https://www.pega.com/industries/financial-services/smart-dispute) · [Pega — AI in Smart Dispute](https://www.pega.com/about/news/press-releases/pega-infuses-ai-pega-smart-dispute-streamline-chargeback-processes)
- [Stripe — Evidence that wins product-not-received disputes](https://stripe.com/blog/analyzing-the-evidence-that-helps-businesses-win-product-not-received-disputes) · [Stripe Smart Disputes](https://stripe.com/payments/dispute-management)
- [Fraudbeat — Chargeback AI: the issuer side](https://www.fraudbeat.com/chargeback-ai-issuer-side/)
- [Chargeflow — Mastercard chargeback rules](https://www.chargeflow.io/blog/mastercard-chargeback-survival-guide) · [Chargeflow — Discover codes](https://www.chargeflow.io/blog/discover-chargeback-reason-codes) · [Chargeflow — CE 3.0](https://www.chargeflow.io/blog/visa-compelling-evidence-3-0-explained)
- [Chargeback Gurus — Amex reason codes](https://www.chargebackgurus.com/chargeback-reason-codes/american-express)
- [Chargebacks911 — Mastercard reason codes](https://chargebacks911.com/chargeback-reason-codes/mastercard/)
- [MRC — Stricter VAMP thresholds in effect (2026)](https://merchantriskcouncil.org/learning/resource-center/member-news/blog/2026/stricter-vamp-ratio-thresholds-are-now-in-effect-heres-how-to-stay-compliant)
- [Adyen — Dispute flow](https://docs.adyen.com/risk-management/understanding-disputes/dispute-process-and-flow)
- [Sift — Dispute analyst role](https://sift.com/blog/dispute-analyst-job-description-role/) · [BuiltIn — Dispute Investigative QA Analyst](https://builtin.com/job/dispute-investigative-quality-assurance-analyst/6979176)
- [Adyen — 3DS trans status](https://help.adyen.com/knowledge/3d-secure/understand-3ds/what-does-trans-status-on-the-3ds-section-of-the-payment-details-page-mean)
- [Adaptive Security — account takeover signals](https://www.adaptivesecurity.com/blog/email-account-takeover-examples)

**Academic / open source**
- [τ-bench (arXiv 2406.12045)](https://arxiv.org/abs/2406.12045) · [τ²-bench repo](https://github.com/sierra-research/tau2-bench)
- [RIRAG / ObliQA (arXiv 2409.05677)](https://arxiv.org/abs/2409.05677)
- [FIA — LLM framework for credit card fraud investigations (arXiv 2506.11635)](https://arxiv.org/abs/2506.11635)
- [Synthetic tabular generators fail to preserve behavioral fraud patterns (arXiv 2604.13125)](https://arxiv.org/abs/2604.13125)
- [ClaimPilot (MDPI Future Internet 18(9):465)](https://www.mdpi.com/1999-5903/18/9/465)
- [amazon-science/fraud-dataset-benchmark](https://github.com/amazon-science/fraud-dataset-benchmark)
