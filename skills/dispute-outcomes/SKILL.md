---
name: dispute-outcomes
description: How to choose verdicts and report improvements. Load for adjudication.
---

# Dispute outcomes
1. Read `graph_schema` descriptions and the Amex Dispute Guide Clauses; choose a verdict for every disputed charge.
2. The evidence graph is the complete case file. Decide on the records it holds; never withhold a verdict for artefacts it cannot hold (screenshots, processor logs, timestamps, signed statements). Amex disputes here have no time component: never require, or propose, validity dates, deadlines, posting windows or effective dates.
3. `accepted` means the Merchant owes the full disputed amount (the amount on the Dispute, not the whole charge); `partially_accepted` means the Merchant owes only a proven part of it. When every charge has the same verdict, the report verdict is that verdict.
4. Ask first whether the Card Member identified the charge correctly. If the charge is for a different plan, Card, Card Member or purchase than the one they believe, and the Merchant billed it correctly, it is `not_a_dispute`.
5. `rejected` applies only when the Card Member correctly identifies the charge, contests the Merchant's conduct, and that conduct was proper under the terms they accepted.
6. When the Merchant is not at fault but the Card Member lost a promised Amex benefit, search the Amex Dispute Guide goodwill Clauses and test every condition in the graph, including the Card Member's own past Disputes. If all hold, the verdict is `goodwill_credit`; otherwise no credit. "May" in a goodwill Clause is the discretion this team exercises by applying the Clause: when every stated condition holds, grant it, and never add conditions the Clause does not state.
7. `fraud_referral` hands off a denial of participation without deciding the Dispute.
8. Reconcile each charge: credit amount plus Card Member liability equals the disputed amount, not the full charge. Cite evidence for each decision and hypothesis.
9. Add a System Improvement only for a gap that caused or prolonged this Dispute: start from the fact that decided the verdict and ask what change would have stopped this Card Member from filing it. Details a Clause or record omits that nobody disagreed about are not gaps. Give evidence for each:
   - `amex_policy`: an Amex Clause is silent or ambiguous on the point the parties disagreed about. A Clause that is clear on that point is not an `amex_policy` gap, even if the Card Member did not follow it. Amex terms that are merely general, or that do not explain how records work, are not gaps.
   - `merchant_policy`: a Merchant Clause conflicts with Amex terms or misled the Card Member. Report it even when Amex terms override the Clause in this Dispute, because the Clause remains in force for other customers. Then check the Amex side of the same conflict: if the Card Member-facing Amex Clause for that benefit or rule does not itself say what the Merchant Clause disputes, also report `amex_policy`.
   - `process`: an Amex or Merchant step would have prevented the Dispute, such as a warning at checkout, booking or enrolment when the Card Member was about to act against a clear Clause. When the Card Member lost value by acting against a clear Clause, this is the target.
   - `product`: a Card feature invited the confusion. `data`: a graph record is wrong or inconsistent; a wish for more fields or records is not a `data` gap.
   Report or explicitly dismiss every `conflict` and `improvement_idea` entry in the Case Notebook; one Dispute can need several items. Evidence the case file does not hold is not an improvement. Dismissing wish-lists is not the end of the check: leave the list empty only when the policies were clear, were followed, and no step could have caught the mistake. When Amex funds a credit because the Card Member acted against a clear Amex Clause, report the Amex `process` step that would have caught it.
10. Explain the outcome to the Card Member in plain words, consistent with the verdict.
