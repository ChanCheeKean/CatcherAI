"""Load the agent-visible generated data into a single SQLite file (the POC's persistent store).

Usage: python3 data/generator/load_sqlite.py [output_path]   (default: data/generated/catcher.sqlite)
Ground truth and simulation files are deliberately NOT loaded.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sqlite3
import sys

GEN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated")
CORPUS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "corpus")


def _table_from_rows(con, name, cols, rows):
    con.execute(f'DROP TABLE IF EXISTS "{name}"')
    con.execute(f'CREATE TABLE "{name}" ({", ".join(f"{c} TEXT" for c in cols)})')
    con.executemany(f'INSERT INTO "{name}" VALUES ({", ".join("?" * len(cols))})', rows)


def _front_matter(text):
    meta, body = {}, text
    if text.startswith("---"):
        head, body = text[3:].split("\n---", 1)
        for line in head.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
    return meta, body.lstrip("\n")


def main(out):
    if os.path.exists(out):
        os.remove(out)
    con = sqlite3.connect(out)
    for path in sorted(glob.glob(os.path.join(GEN, "structured", "*.csv")) + glob.glob(os.path.join(GEN, "reference", "*.csv"))):
        with open(path, encoding="utf-8") as f:
            rows = list(csv.reader(f))
        name = os.path.splitext(os.path.basename(path))[0]
        name = name if "structured" in path else f"ref_{name}"
        _table_from_rows(con, name, rows[0], rows[1:])
    for path in [os.path.join(GEN, "events", "account_events.jsonl"), os.path.join(GEN, "events", "dispute_events.jsonl"),
                 os.path.join(GEN, "documents", "communications.jsonl"), os.path.join(GEN, "memory_seed", "agent_memory_notes.jsonl")]:
        recs = [json.loads(line) for line in open(path, encoding="utf-8")]
        cols = list(recs[0].keys())
        _table_from_rows(con, os.path.splitext(os.path.basename(path))[0], cols,
                         [[json.dumps(r[c]) if isinstance(r[c], (dict, list)) else r[c] for c in cols] for r in recs])
    packets = [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(os.path.join(GEN, "documents", "evidence_packets", "*.json")))]
    _table_from_rows(con, "evidence_packet_documents", ["packet_id", "case_id", "txn_id", "available_at", "json"],
                     [[p["packet_id"], p["case_id"], p["txn_id"], p["available_at"], json.dumps(p)] for p in packets])
    docs = []
    for kind, pattern in (("research", os.path.join(GEN, "documents", "research", "*.md")), ("precedent", os.path.join(GEN, "precedents", "*.md")),
                          ("policy", os.path.join(CORPUS, "policies", "**", "*.md")), ("skill", os.path.join(CORPUS, "skills", "*.md"))):
        for p in sorted(glob.glob(pattern, recursive=True)):
            meta, body = _front_matter(open(p, encoding="utf-8").read())
            doc_id = meta.get("doc_id") or meta.get("precedent_id") or meta.get("name")
            docs.append([doc_id, kind, meta.get("title", ""), meta.get("effective_from", meta.get("captured_at", meta.get("decided_at", ""))),
                         meta.get("effective_to", ""), meta.get("status", ""), json.dumps(meta), body])
    _table_from_rows(con, "documents", ["doc_id", "kind", "title", "valid_from", "valid_to", "status", "meta_json", "body"], docs)
    con.execute("CREATE VIRTUAL TABLE documents_fts USING fts5(doc_id, kind, title, body)")
    con.executemany("INSERT INTO documents_fts VALUES (?,?,?,?)", [[d[0], d[1], d[2], d[7]] for d in docs])
    for stmt in ("CREATE INDEX ix_txn_card ON transactions(card_id)", "CREATE INDEX ix_txn_merchant ON transactions(merchant_id)",
                 "CREATE INDEX ix_evt_customer ON account_events(customer_id)", "CREATE INDEX ix_devt_case ON dispute_events(case_id)"):
        con.execute(stmt)
    con.commit()
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(GEN, "catcher.sqlite"))
