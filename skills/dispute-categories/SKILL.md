---
name: dispute-categories
description: How to classify what a Card Member alleges. Load before selecting a Dispute Category.
---

# Dispute categories
1. Read `graph_schema` descriptions and confirm code meanings with `search_knowledge` in the Amex Dispute Guide.
2. NKN: charge not recognised; inspect the descriptor and Card use. RET: returned or refused without credit; inspect return and refund records.
3. CNC: cancelled order or booking; inspect confirmation. CNR: recurring billing contested; inspect the exact plan, consent and cancellation.
4. DMG: damaged merchandise; inspect condition evidence. DSS: service unsatisfactory or not as described; inspect the agreement and delivery.
5. DUP: multiple charges for one purchase; reconcile charges. NRC: goods or service not received; inspect delivery or use.
6. OVR: amount differs from agreement; compare price and discounts. PDD: paid by other means; reconcile payments with the bill.
7. Choose by the allegation, independent of outcome. NKN is not fraud; if the Card Member denies taking part, use the fraud_referral verdict.
