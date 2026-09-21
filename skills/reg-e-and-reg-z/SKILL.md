---
name: reg-e-and-reg-z
description: Regulation E (debit) and Regulation Z (credit) essentials for liability, notice periods and provisional credit.
---

# Reg E and Reg Z essentials

Look up the exact text with `search_knowledge` and cite the document ID; the points below are a guide only.

- **Which regulation?** Debit cards and electronic fund transfers fall under Reg E; credit cards under Reg Z. Decide from the account type in the graph.
- **Notice.** Reg Z billing-error notice is within 60 days of the statement showing the charge. Reg E error notice is generally within 60 days of the statement, with liability tiers that depend on when the consumer told the institution.
- **Liability tiers** (Reg E $50 / $500) apply to a lost or stolen access device. Where credentials rather than a device were misused, the general rule applies instead. Credit-card unauthorized-use liability is capped at $50 and often waived.
- **Unauthorized use.** Use by a person the cardholder gave authority to is authorized; use by anyone else is unauthorized.
- **Provisional credit** and investigation deadlines exist for debit disputes; compute dates with the `python` tool, counting business days explicitly.
- **Internal policy may be stricter than regulation.** Prefer the version of a policy valid on the dispute date (`as_of`); superseded documents are history, not current rules.
