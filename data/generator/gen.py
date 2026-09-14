"""Generate the synthetic card-dispute dataset.

Usage:  python3 data/generator/gen.py        (writes to data/generated/)
Deterministic: same SEED -> byte-identical output.
"""
from __future__ import annotations

import csv
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import background as bg  # noqa: E402
import capabilities  # noqa: E402
import derived  # noqa: E402
import memory_seed  # noqa: E402
import precedents  # noqa: E402
from common import AS_OF, OUT_DIR, SCHEMAS, SEED, Ctx, write_json, write_jsonl, write_text  # noqa: E402
from heroes import cases_a, cases_b, cases_c, cases_d, personas_extra  # noqa: E402
from world import (BANK_HOLIDAYS_2026, CITIES, FX_EUR_USD, MCC, REF_3DS_STATUS, REF_AUTH_RESPONSE, REF_AVS, REF_COF,  # noqa: E402
                   REF_CVV2_PRESENCE, REF_CVV2_RESULT, REF_ECI, REF_POS_ENTRY, VISA_CONDITIONS)

HIDDEN_COLUMNS = {"is_hero"}  # ground-truth-only; never shipped to agent-visible files


def build() -> Ctx:
    ctx = Ctx(SEED)
    bg.build_merchants(ctx)
    bg.build_background_people(ctx)
    bg.build_background_activity(ctx)
    for mod in (cases_a, cases_b, cases_c, cases_d, personas_extra):
        mod.build(ctx)
    hero_customers = {r["customer_id"] for r in ctx.t["customers"] if r["is_hero"]}
    bg.build_background_disputes(ctx, exclude_customers=frozenset(hero_customers))
    precedents.build_hand_precedents(ctx)
    bg.build_statements_and_payments(ctx)
    precedents.build_templated_precedents(ctx)
    memory_seed.build(ctx)
    derived.build_queue(ctx)
    derived.build_graph(ctx)
    for gt in ctx.ground_truth.values():
        if "see" in gt:
            continue
        gt["required_capabilities"] = capabilities.required_capabilities(gt["code"])
        if gt["code"] in capabilities.MUST_NOT_WRITE:
            gt.setdefault("memory_ops", {})["must_not_write"] = capabilities.MUST_NOT_WRITE[gt["code"]]
    ctx.queue_truth["required_capabilities"] = capabilities.required_capabilities("Q01")
    return ctx


def _write_table(path, table, rows):
    cols = [c for c in SCHEMAS[table] if c not in HIDDEN_COLUMNS]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            out = []
            for c in cols:
                v = r[c]
                if isinstance(v, bool):
                    v = "true" if v else "false"
                elif v is None:
                    v = ""
                out.append(v)
            w.writerow(out)


def _write_ref(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def write(ctx: Ctx):
    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    S = lambda *p: os.path.join(OUT_DIR, *p)
    sort_keys = {"transactions": "txn_id", "disputes": "case_id", "account_events": "event_id", "dispute_events": "event_id",
                 "communications": "comm_id", "statements": "statement_id"}
    for table in ("customers", "addresses", "accounts", "account_holders", "cards", "tokens", "merchants", "merchant_descriptors",
                  "devices", "transactions", "statements", "disputes", "dispute_transactions", "evidence_packets"):
        rows = ctx.t[table]
        if table in sort_keys:
            rows = sorted(rows, key=lambda r: r[sort_keys[table]])
        _write_table(S("structured", f"{table}.csv"), table, rows)
    strip = lambda rows: [{k: v for k, v in r.items() if k not in HIDDEN_COLUMNS} for r in rows]
    write_jsonl(S("events", "account_events.jsonl"), strip(sorted(ctx.t["account_events"], key=lambda r: (r["timestamp_utc"], r["event_id"]))))
    write_jsonl(S("events", "dispute_events.jsonl"), strip(sorted(ctx.t["dispute_events"], key=lambda r: (r["timestamp_utc"], r["event_id"]))))
    write_jsonl(S("documents", "communications.jsonl"), strip(sorted(ctx.t["communications"], key=lambda r: (r["timestamp_utc"], r["comm_id"]))))
    for pid, pk in sorted(ctx.packets.items()):
        write_json(S("documents", "evidence_packets", f"{pid}.json"), pk)
    for doc_id, r in sorted(ctx.research.items()):
        front = "\n".join(["---"] + [f"{k}: \"{r[k]}\"" for k in ("doc_id", "title", "url", "publisher", "published_at", "captured_at",
                                                                   "doc_type", "related_merchant_id")] + ["---", ""])
        write_text(S("documents", "research", f"{doc_id}.md"), front + f"# {r['title']}\n\n{r['body']}")
    for pid, text in sorted(ctx.precedents.items()):
        write_text(S("precedents", f"{pid}.md"), text)
    write_jsonl(S("memory_seed", "agent_memory_notes.jsonl"), ctx.memory_notes)
    for tid, steps in ctx.run_traces.items():
        write_jsonl(S("memory_seed", "run_traces", f"{tid}.jsonl"), steps)
    write_json(S("simulation", "cardholder_personas.json"), ctx.personas)
    # reference
    _write_ref(S("reference", "avs_result_codes.csv"), ["code", "meaning"], REF_AVS)
    _write_ref(S("reference", "cvv2_result_codes.csv"), ["code", "meaning"], REF_CVV2_RESULT)
    _write_ref(S("reference", "cvv2_presence_indicators.csv"), ["code", "meaning"], REF_CVV2_PRESENCE)
    _write_ref(S("reference", "eci_values.csv"), ["value", "meaning"], REF_ECI)
    _write_ref(S("reference", "three_ds_trans_status.csv"), ["code", "meaning"], REF_3DS_STATUS)
    _write_ref(S("reference", "pos_entry_modes.csv"), ["code", "meaning"], REF_POS_ENTRY)
    _write_ref(S("reference", "cof_types.csv"), ["code", "meaning"], REF_COF)
    _write_ref(S("reference", "auth_response_codes.csv"), ["code", "meaning"], REF_AUTH_RESPONSE)
    _write_ref(S("reference", "mcc_codes.csv"), ["mcc", "description"], sorted(MCC.items()))
    _write_ref(S("reference", "visa_dispute_conditions.csv"), ["condition", "name", "category", "flow"], VISA_CONDITIONS)
    _write_ref(S("reference", "bank_holidays_2026.csv"), ["date", "holiday"], BANK_HOLIDAYS_2026)
    _write_ref(S("reference", "fx_rates_eur_usd.csv"), ["date", "eur_usd"], sorted(FX_EUR_USD.items()))
    _write_ref(S("reference", "cities.csv"), ["city", "state", "timezone", "lat", "lon"],
               [(c, v["state"], v["tz"], v["lat"], v["lon"]) for c, v in CITIES.items()])
    _write_table(S("reference", "ip_intel.csv"), "ip_intel", ctx.t["ip_intel"])
    # graph
    nodes, edges = ctx.graph
    write_jsonl(S("graph", "nodes.jsonl"), nodes)
    write_jsonl(S("graph", "edges.jsonl"), edges)
    # ground truth (never loaded into agent memory)
    for cid, gt in sorted(ctx.ground_truth.items()):
        write_json(S("ground_truth", "cases", f"{cid}.json"), gt)
    write_json(S("ground_truth", "Q01_queue.json"), ctx.queue_truth)
    write_json(S("ground_truth", "capability_coverage.json"), capabilities.coverage())
    write_jsonl(S("ground_truth", "background_labels.jsonl"), sorted(ctx.bg_labels, key=lambda r: r["case_id"]))
    hero_index = {t: sorted(r[SCHEMAS[t][0]] for r in ctx.t[t] if r.get("is_hero")) for t in
                  ("customers", "accounts", "merchants", "transactions", "account_events", "disputes")}
    write_json(S("ground_truth", "hero_index.json"), hero_index)
    manifest = dict(
        dataset="Synthetic card-dispute ecosystem",
        seed=SEED,
        as_of=AS_OF.isoformat(),
                    counts={**{k: len(v) for k, v in sorted(ctx.t.items())}, "evidence_packets_json": len(ctx.packets),
                            "research_docs": len(ctx.research), "precedents": len(ctx.precedents), "memory_notes": len(ctx.memory_notes),
                            "graph_nodes": len(nodes), "graph_edges": len(edges), "hero_cases": len(ctx.ground_truth)},
                    hero_cases={cid: dict(code=g.get("code"), title=g.get("title"), depth=g.get("depth"))
                                for cid, g in sorted(ctx.ground_truth.items())})
    write_json(S("manifest.json"), manifest)
    return manifest


if __name__ == "__main__":
    c = build()
    man = write(c)
    for k, v in man["counts"].items():
        print(f"{k:28s} {v}")
