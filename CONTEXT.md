# DisputeAI (Amex)

An investigation assistant for American Express's own disputes team. Amex issues the Card and signs the Merchant, so one team hears both sides and decides the outcome.

## Language

### Parties

**Amex**:
The single company acting as card issuer, network and merchant acquirer. The disputes team works on its behalf.
_Avoid_: issuer, acquirer, bank, network (as separate parties)

**Card Member**:
A person who holds an Amex Card, either as the Basic Card Member or as an Additional Card Member on someone else's account.
_Avoid_: cardholder, customer, user

**Additional Card Member**:
A person given their own Card on a Basic Card Member's account; their charges bill to that account.
_Avoid_: authorized user, supplementary cardholder

**Card Product**:
The kind of Card (for example Platinum, Gold, Green, Blue Cash), which decides which benefits and Offers a Card is eligible for.
_Avoid_: card type, tier

**Merchant**:
A business that accepts Amex under a direct agreement with Amex.
_Avoid_: seller, acquirer, SE (unless quoting Amex text)

### Terms

**Amex Policy**:
A rule Amex sets for Card Members or Merchants (Merchant Regulations, Card Member Agreement, Offer and benefit terms).
_Avoid_: network rules, scheme rules

**Merchant Policy**:
A rule a Merchant sets for its own customers (return, cancellation, pricing, promotion terms), in the version the Card Member saw.
_Avoid_: T&Cs (unqualified), store policy

**Clause**:
One numbered or headed provision within an Amex Policy or Merchant Policy, the unit agents cite and compare.
_Avoid_: section, rule (when meaning one provision)

**Amex Offer**:
An Amex-funded statement credit a Card Member adds to one specific Card before purchasing at a named Merchant.
_Avoid_: discount, promo, cashback

### Case

**Dispute**:
A Card Member's challenge to a specific charge as billed wrongly by a Merchant; never a fraud claim and never a general complaint.
_Avoid_: chargeback, claim, complaint, case (when meaning the challenge itself)

**Dispute Category**:
The one code from the fixed list (NKN No Knowledge, RET Returned/Refused, CNC Cancelled, CNR Continuity/Recurring Billing, DMG Damaged Merchandise, DSS Dissatisfied with Service, DUP Duplicate/Multiple, NRC Not Received, OVR Overcharged, PDD Paid by Other Means) that describes what the Card Member alleges.
_Avoid_: reason code, case type, claim family

**Fraud Referral**:
The outcome when investigation shows the Card Member denies taking part in the charge; the Dispute is handed off, not decided.
_Avoid_: fraud dispute

**Verdict**:
The outcome of a Dispute: accepted, partially accepted, rejected (the Merchant's position is upheld), goodwill credit, not a dispute (a misunderstanding or unrelated matter resolved by explanation) or fraud referral.
_Avoid_: decision, resolution

**Not a Dispute**:
A Verdict for a charge that was never a Merchant error, where the Card Member misunderstood what or who was charged.
_Avoid_: complaint, withdrawn

**Goodwill Credit**:
A credit Amex funds at its own discretion when the Dispute is not upheld against the Merchant.
_Avoid_: courtesy credit, chargeback

**Merchant Submission**:
Evidence and Merchant Policies a Merchant provides for a Dispute.
_Avoid_: merchant response, representment

**Case Notebook**:
The per-run log where investigating agents record findings, each citing graph and policy ids; it is separate from the evidence graph.
_Avoid_: findings graph, scratchpad, memory

**Memory Note**:
A durable, cross-case lesson kept outside the evidence graph and retrieved by search.
_Avoid_: finding, note (unqualified)

**System Improvement**:
A report item proposing a change to a policy, process or data that would have prevented or clarified the Dispute.
_Avoid_: recommendation, feedback
