---
name: unrecognized-charges
description: Separating "I don't recognize this charge" from genuine unauthorized use, and when the right outcome is an explanation rather than a credit.
---

# Unrecognized charges

Not recognizing a charge is a statement about a name, not proof that nobody authorized it. The claim only becomes fraud when something in the graph points to someone other than the cardholder or an authorized user.

1. **Resolve the descriptor.** Follow the transaction's descriptor to the merchant it describes, including payment-facilitator or sub-merchant links to a parent merchant. A prefix such as a facilitator code can make a familiar storefront look foreign.
2. **Check the card's own history.** Look for earlier transactions on the same card at that merchant (directly or through its descriptors) that pre-date the disputed one, are not themselves disputed and are not explained by any fraud signal. Repeat use by the cardholder is strong evidence that they know the merchant.
3. **Look for fraud signals before deciding.** New device, changed contact details, shared compromise point or delivery ring (`fraud-and-ato-signals`). If none connect this charge to anything unusual, an unfamiliar name alone is not fraud.
4. **Choose the outcome by what the graph proves.** If the charge resolves to a merchant the cardholder has used before and nothing contradicts that, the charge is genuine: use verdict `not_a_dispute`, credit nothing, keep the cardholder liable for the amount, take no network action, and explain in the letter which merchant the name belongs to and which earlier purchases show it. Reserve `accepted` for claims the evidence supports.
5. **Do not confuse gaps with silence.** Data that is simply absent from the graph (no authorization or terminal record for a transaction) is not an unanswered evidence request, so `missing-evidence-default` does not apply. Lack of data on one point does not outweigh a resolved merchant relationship on another.
6. **Similar-looking names are decoys.** A merchant or descriptor with a similar name but no link to this card's transactions or history does not matter; say why it is unconnected.
