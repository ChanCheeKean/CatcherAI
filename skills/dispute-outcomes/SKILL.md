---
name: dispute-outcomes
description: How to choose verdicts and report improvements. Load for adjudication.
---

# Dispute outcomes
1. Read `graph_schema` descriptions and the Amex Dispute Guide Clauses; choose a verdict for every disputed charge.
2. The evidence graph is the complete case file. Decide on the records it holds; never withhold a verdict for artefacts it cannot hold (screenshots, processor logs, timestamps, signed statements).
3. `accepted` means the Merchant owes the full disputed credit; `partially_accepted` means the Merchant owes only the proven part.
4. Ask first whether the Card Member identified the charge correctly. If the charge is for a different plan, Card, Card Member or purchase than the one they believe, and the Merchant billed it correctly, it is `not_a_dispute`.
5. `rejected` applies only when the Card Member correctly identifies the charge, contests the Merchant's conduct, and that conduct was proper under the terms they accepted.
6. When the Merchant is not at fault but the Card Member lost a promised Amex benefit, search the Amex Dispute Guide goodwill Clauses and test every condition in the graph, including the Card Member's own past Disputes. If all hold, the verdict is `goodwill_credit`; otherwise no credit.
7. `fraud_referral` hands off a denial of participation without deciding the Dispute.
8. Reconcile each charge: credit amount plus Card Member liability equals the disputed amount, not the full charge. Cite evidence for each decision and hypothesis.
9. Add a System Improvement only for a gap that caused or prolonged this Dispute: ask what change would have stopped this Card Member from filing it. Details a Clause or record omits that nobody disagreed about are not gaps. Give evidence for each:
   - `amex_policy`: an Amex Clause is silent or ambiguous on the point the parties disagreed about. A Clause that is clear on that point is not an `amex_policy` gap, even if the Card Member did not follow it.
   - `merchant_policy`: a Merchant Clause conflicts with Amex terms or misled the Card Member. Report it even when Amex terms override the Clause in this Dispute, because the Clause remains in force for other customers.
   - `process`: an Amex or Merchant step would have prevented the Dispute, such as a warning at checkout, booking or enrolment when the Card Member was about to act against a clear Clause.
   - `product`: a Card feature invited the confusion. `data`: a graph record is wrong or inconsistent.
   Report or explicitly dismiss every `conflict` and `improvement_idea` entry in the Case Notebook; one Dispute can need several items. Evidence the case file does not hold is not an improvement. When the policies were clear and followed, leave the list empty.
10. Explain the outcome to the Card Member in plain words, consistent with the verdict.
