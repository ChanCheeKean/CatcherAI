---
name: graph-investigation
description: How to explore the evidence graph, pivot on shared identifiers, use temporal edges and rule out decoys. Load first for any investigation.
---

# Graph investigation

The evidence lives in a temporal property graph. The story a cardholder tells is a lead, not a fact.

1. **Start from the schema.** Call `graph_schema` once, then anchor on the dispute: its transactions, customer, account, card and the evidence items already attached.
2. **Expand one hop at a time** with `graph_neighbors`; move to `graph_query` (Cypher, variable-length paths) when you need a specific multi-hop question such as "which other accounts touch this address, device or token".
3. **Pivot on shared identifiers** (device, IP, phone, email, address, terminal, token, merchant account). A pivot is only interesting if it separates this case from the background, so always count how many other entities sit behind the identifier.
4. **Respect time.** Edges carry `valid_from`/`valid_to`. Ownership, residence and device use are only evidence for the period in which the edge was valid. Pass `since`/`until` around the transaction date, and check that intervals overlap before linking two entities.
5. **Hold competing hypotheses** (e.g. genuine purchase, household use, third-party fraud, merchant error, coordinated abuse). For each, write down which graph fact would confirm it and which would refute it, then query for exactly those facts.
6. **Rule out decoys.** Shared addresses, office or carrier-grade IPs, recycled phone numbers, marketplaces and family devices often look suspicious but are benign. Show the fact that separates the decoy (non-overlapping dates, different unit, thousands of unrelated users) before dismissing it.
7. **Record what you find** with `graph_write_finding`, citing the node and edge IDs that support it. Never cite an ID you did not see in a tool result.
8. **Use `python`** for arithmetic, date differences and aggregation instead of computing in your head.
