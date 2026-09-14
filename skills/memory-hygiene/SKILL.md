---
name: memory-hygiene
description: Read memory as leads, then correct, consolidate, time-bound and expire notes under SOP-DSP-005.
version: "1"
source: data/corpus/skills/pb-memory-hygiene.md
---

# Playbook: memory hygiene
- Treat retrieved notes as leads. Verify against current case evidence and the policy corpus before relying on them.
- Conflict with a source of truth → supersede (policy changed) or retract (note was wrong) and write a correction with sources.
- Three or more raw observations of one pattern → consolidate with a validity window; archive raw notes; merge duplicate entities.
- Pattern stopped being true → set `valid_to`, don't delete.
- Never store prohibited content (SOP-DSP-004); purge with tombstone if found.
- Merchant pattern notes older than 90 days, or predating a known merchant change, must be revalidated against current evidence before use.
