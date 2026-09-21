---
name: agentic-transactions
description: Transactions initiated by an AI agent or agent provider under a cardholder mandate.
---

# Agentic transactions

- Follow the graph from the transaction to the token, the agent provider and the mandate that authorized it.
- The mandate defines what the agent may do: limit per transaction, total budget, merchant categories, validity period. Compare each disputed transaction with it separately.
- A purchase inside the mandate is authorized even if the cardholder is surprised. A purchase outside it (over the cap, wrong category, expired mandate) exceeded authority; the excess or the whole purchase is unauthorized.
- An agent provider is not a merchant. Check the current network rule for agent-initiated transactions with `search_knowledge` before selecting a network action.
- Consider whether the agent acted on the cardholder's behalf at all: the token must have been provisioned to that provider under that mandate.
