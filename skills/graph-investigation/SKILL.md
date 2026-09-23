---
name: graph-investigation
description: How to explore a Dispute through schema descriptions and connected evidence. Load for graph investigations.
---

# Graph investigation
1. Call `graph_schema` first; read descriptions to learn how this graph represents people, Cards, purchases, terms and evidence.
2. Anchor on the Dispute and expand one hop with `graph_neighbors`; use `graph_query` for specific multi-hop questions.
3. Use `graph_find` to locate records by text, then verify their paths to this Dispute.
4. Never match people by name alone. Namesakes and similar records are relevant only when connecting records prove it.
5. Count how common a pivot is before treating it as meaningful; test at least one plausible look-alike.
6. Cite only ids returned by tools. Record facts and ruled-out paths in the Case Notebook.
7. Use `python` for arithmetic and aggregations.
