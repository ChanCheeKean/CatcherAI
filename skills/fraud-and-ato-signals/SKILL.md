---
name: fraud-and-ato-signals
description: Signals that separate account takeover, third-party fraud and compromise points from genuine or household use.
---

# Fraud and account-takeover signals

- **Sequence matters more than credentials.** Contact-detail change, password reset, new device or token provisioning followed by high-value purchases is a takeover pattern even if the card details were entered correctly.
- **Novelty.** A device, IP, shipping address or token the customer has never used before, appearing together with a change of contact details, is strong. Any one of them alone is weak.
- **Fan-in.** Many unrelated accounts converging on one address, device or reshipper within a short window is the strongest ring signal. Check that the convergence is not a benign block (office, building, carrier-grade network).
- **Common compromise point.** When several cardholders report card-present fraud, look for the one terminal or merchant they all touched before the fraud and that other, unaffected customers did not. Sharing a popular merchant alone is not a compromise.
- **Compelling evidence.** Earlier undisputed use of the same device, address or token supports cardholder involvement. Verify the earlier use really is the same entity and the same period.
- **Household and authorized users** are handled by `household-authority`; do not call it fraud until that has been tested.
- **Write confidence honestly.** State which single fact would flip the conclusion.
