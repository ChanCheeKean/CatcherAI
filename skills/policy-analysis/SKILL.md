---
name: policy-analysis
description: How to compare applicable Amex and Merchant clauses. Load for policy questions.
---

# Policy analysis
1. Read `graph_schema` descriptions, then find the Merchant Policy version accepted for this purchase through the graph.
2. Search Clause text with `search_knowledge`, then verify each Clause's applicability in the graph.
3. Find Amex Policies binding the Merchant, account, Offer or program; verify disclosure and acceptance.
4. A recorded acceptance of a specific policy version (a checkbox, signature or booking confirmation) proves that version was disclosed at the point of sale. Do not ask for more proof of disclosure than that record.
5. A Merchant Policy is evidence, not an override. A clear, disclosed, accepted Clause can decide the Dispute even if the Card Member did not read it, or relied on a shorter headline elsewhere that points to it.
6. When a Merchant condition conflicts with Amex terms the Merchant accepted, or terms are ambiguous, read against the drafter. For each such conflict, quote the Card Member-facing Amex Clause on the same point and say whether it covers the condition the Merchant added; if it does not, record that silence too (step 7).
7. Note when an Amex Clause is silent on the point the parties disagree about; that silence is a policy gap to record as `improvement_idea`.
8. Cite exact Clause ids and relevant excerpts. Record conflicts as `conflict` and gaps as `improvement_idea` in the Case Notebook.
