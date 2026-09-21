---
name: network-reason-codes
description: How to choose and validate a card-network reason code and what network actions are eligible per transaction.
---

# Network reason codes

- Decide each transaction separately: a claim can be accepted for one charge and rejected for another.
- Pick the condition that matches the facts you proved, not the one the cardholder named. Look the condition up with `search_knowledge` and check its eligibility: time limits, minimum amounts, whether the transaction was already disputed, and whether a credit already covered part of it.
- A network action (chargeback, no action) is separate from the cardholder outcome. The cardholder can be credited even when no network dispute is filed.
- Never file a second dispute for the same transaction. Where two charges look like a duplicate, check that they are really two clearings of two purchases before treating either as a duplicate.
- Where a merchant credit exists, net it off before computing the disputed amount.
- Use the `python` tool to verify totals: credit + cardholder liability must equal the disputed amount.
