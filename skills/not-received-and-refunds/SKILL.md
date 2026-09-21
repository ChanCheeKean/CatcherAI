---
name: not-received-and-refunds
description: Investigating goods or services not received, delivery evidence and merchant credits or refunds.
---

# Not received and refunds

1. Establish the promised delivery from the order: which items, what date, to which address.
2. Follow the shipment: carrier, tracking events, delivered-to address versus ordered address, signature. A delivery confirmation to a different address than the order does not prove delivery to the cardholder.
3. Look for merchant credits linked through the order, even if they do not reference the original transaction. Net them off; only the remaining amount is in dispute.
4. Check whether the merchant was asked for proof and whether it answered (`missing-evidence-default`).
5. Look at the delivery destination against other claims: several unrelated claims resolving to one drop point or reshipper is a pattern, not coincidence, while a single parcel delivered to the cardholder's own home is different.
6. Each transaction is decided separately. Compute the credit and any remaining cardholder liability with `python`.
