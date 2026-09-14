---
name: "pb-automated-adjudication"
description: "Decide high-impact or uncertain cases without human review"
triggers: [review_panel, high_impact, policy_gap]
uses_policies: [LFB-SOP-DSP-003@v6, LFB-SOP-DSP-004@v2]
provenance: "fictional_internal"
version: "1"
---
# Playbook: automated adjudication
1. Check whether SOP-DSP-003 §2 requires the review panel.
2. Write the case file summary: facts with source IDs, hypotheses, rules with versions, computed amounts/deadlines.
3. Run the cardholder advocate and the issuer/merchant advocate independently on the same case file (no shared reasoning).
4. Adjudicator decides; verifier checks eligibility, versions, arithmetic, citations and fairness. Any verifier failure → back to planning.
5. Record confidence on the determinative issue and the single fact that would flip the decision.
6. Confidence < 0.75 → apply the conservative default (cardholder-favorable outcome, no uncertain network dispute) and say why.
7. Execute the bounded automated actions (SOP-DSP-003 §4–§7) and record each one. Never wait for a human.
