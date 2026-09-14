---
doc_id: "LFB-SOP-DSP-005@v1"
title: "Agent memory governance"
source_type: "internal_sop"
authority: "Lanternfield Bank, N.A. (fictional)"
owner: "Disputes Operations"
version: "1"
effective_from: "2026-08-01"
effective_to: null
status: "active"
supersedes: null
superseded_by: null
applies_to: [all]
jurisdiction: "US"
provenance: "fictional_internal"
---
# SOP-DSP-005 Agent memory governance (v1)
Applies to all long-term notes written by dispute assistants or analysts into shared memory.

## What may be written
- **Factual** observations with `source_refs` (case, packet, document IDs) and `valid_from`/`valid_to`.
- **Merchant patterns** derived from **three or more** independent cases; must list the cases.
- **Procedural lessons** from QA findings or resolved cases.
- **Never:** SOP-DSP-004 prohibited bases or labels; free-text speculation about intent; copies of full card numbers.

## Lifecycle operations
| Operation | When | How |
|---|---|---|
| **supersede** | the source (policy, SOP, bulletin) changed, or a newer note replaces it | set `status=superseded`, `superseded_by`, `valid_to`; keep text for audit |
| **retract** | note is shown to be **wrong** | set `status=retracted` with reason; write a **correction** note linking evidence; never silently delete |
| **consolidate** | ≥3 raw observations describe one pattern | write one note with validity window and `source_refs`; mark raw notes `archived` with pointer; merge near-duplicate entities (e.g. old and new merchant IDs) |
| **time-bound** | a pattern stops being true (merchant change, rule change) | set `valid_to`; do **not** delete history |
| **dedupe** | same fact recorded twice | keep the earliest, archive the rest |
| **expire** | operational/tooling notes | TTL 30 days |
| **purge** | prohibited content under SOP-DSP-004 | remove content, retain tombstone with reason |

## Reading memory
Memory is a lead, not evidence. A decision must rest on case evidence and current policy. When memory conflicts with a current source of truth
(policy corpus, case data), the source of truth wins and the memory note must be updated.
Merchant pattern notes older than 90 days, or predating a known merchant change, must be revalidated before use.
