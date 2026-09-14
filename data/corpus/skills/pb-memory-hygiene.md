---
name: "pb-memory-hygiene"
description: "Read, correct, consolidate and expire long-term memory"
triggers: [memory]
uses_policies: [LFB-SOP-DSP-005@v1, LFB-SOP-DSP-004@v2]
provenance: "fictional_internal"
version: "1"
---
# Playbook: memory hygiene
- Treat retrieved notes as leads. Verify against current case evidence and the policy corpus before relying on them.
- Conflict with a source of truth → supersede (policy changed) or retract (note was wrong) and write a correction with sources.
- Three or more raw observations of one pattern → consolidate with a validity window; archive raw notes; merge duplicate entities.
- Pattern stopped being true → set `valid_to`, don't delete.
- Never store prohibited content (SOP-DSP-004); purge with tombstone if found.
