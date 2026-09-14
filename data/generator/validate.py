"""Validate the generated dataset: integrity, leakage, hero invariants, pattern discoverability, and ground-truth references.

Usage: python3 data/generator/validate.py      (exit code 1 on any failure)
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from derived import add_business_days, reg_z_resolution_deadline  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "generated")
CORPUS = os.path.join(ROOT, "corpus")
failures, passes = [], []


def check(name, cond, detail=""):
    (passes if cond else failures).append(f"{name}{' — ' + str(detail) if detail and not cond else ''}")


def load_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    for path in glob.glob(os.path.join(GEN, "structured", "*.csv")) + [os.path.join(GEN, "reference", "ip_intel.csv")]:
        name = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as f:
            rows = list(csv.reader(f))
        cols = rows[0]
        con.execute(f"CREATE TABLE {name} ({', '.join(c + ' TEXT' for c in cols)})")
        con.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(cols))})", rows[1:])
    for name in ("account_events", "dispute_events"):
        rows = [json.loads(line) for line in open(os.path.join(GEN, "events", f"{name}.jsonl"), encoding="utf-8")]
        cols = list(rows[0].keys())
        con.execute(f"CREATE TABLE {name} ({', '.join(c + ' TEXT' for c in cols)})")
        con.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(cols))})",
                        [[json.dumps(r[c]) if isinstance(r[c], (dict, list)) else r[c] for c in cols] for r in rows])
    return con


def q(con, sql, *args):
    return con.execute(sql, args).fetchall()


def main():
    con = load_db()
    # ------------------------------------------------ integrity
    for table, key in (("customers", "customer_id"), ("accounts", "account_id"), ("cards", "card_id"), ("merchants", "merchant_id"),
                       ("transactions", "txn_id"), ("disputes", "case_id"), ("devices", "device_id"), ("addresses", "address_id")):
        dup = q(con, f"SELECT {key}, COUNT(*) FROM {table} GROUP BY {key} HAVING COUNT(*) > 1")
        check(f"unique {table}.{key}", not dup, dup[:3])
    fks = [("transactions", "account_id", "accounts", "account_id"), ("transactions", "card_id", "cards", "card_id"),
           ("cards", "account_id", "accounts", "account_id"), ("customers", "home_address_id", "addresses", "address_id"),
           ("disputes", "customer_id", "customers", "customer_id"), ("disputes", "card_id", "cards", "card_id"),
           ("dispute_transactions", "txn_id", "transactions", "txn_id"), ("dispute_transactions", "case_id", "disputes", "case_id"),
           ("evidence_packets", "case_id", "disputes", "case_id"), ("account_events", "customer_id", "customers", "customer_id"),
           ("dispute_events", "case_id", "disputes", "case_id"), ("account_holders", "customer_id", "customers", "customer_id")]
    for t, c, rt, rc in fks:
        bad = q(con, f"SELECT COUNT(*) FROM {t} WHERE {c} <> '' AND {c} NOT IN (SELECT {rc} FROM {rt})")[0][0]
        check(f"fk {t}.{c} -> {rt}.{rc}", bad == 0, f"{bad} orphans")
    bad = q(con, "SELECT COUNT(*) FROM transactions WHERE merchant_id <> '' AND merchant_id NOT IN (SELECT merchant_id FROM merchants)")[0][0]
    check("fk transactions.merchant_id", bad == 0, bad)
    for path in glob.glob(os.path.join(GEN, "documents", "evidence_packets", "*.json")):
        pk = json.load(open(path))
        if pk["txn_id"]:
            check(f"packet txn exists {pk['packet_id']}", q(con, "SELECT 1 FROM transactions WHERE txn_id=?", pk["txn_id"]) != [])
    # ------------------------------------------------ leakage
    for path in glob.glob(os.path.join(GEN, "structured", "*.csv")) + glob.glob(os.path.join(GEN, "events", "*.jsonl")) + \
            glob.glob(os.path.join(GEN, "documents", "*.jsonl")):
        head = open(path, encoding="utf-8").readline()
        check(f"no is_hero in {os.path.basename(path)}", "is_hero" not in head)
    agent_visible = glob.glob(os.path.join(GEN, "documents", "**", "*"), recursive=True) + glob.glob(os.path.join(GEN, "precedents", "*"))
    leak = [p for p in agent_visible if os.path.isfile(p) and re.search(r"ground_truth|hero_index|\bC(0\d|1\d)\b", open(p, encoding="utf-8").read())]
    check("no ground-truth vocabulary in agent-visible documents", not leak, leak[:3])
    # ------------------------------------------------ identities are obviously fictional
    emails = [r[0] for r in q(con, "SELECT email FROM customers")]
    check("all emails use example domains", all(re.search(r"@example\.(com|net|org)$", e) for e in emails))
    phones = [r[0] for r in q(con, "SELECT phone FROM customers")]
    check("all phones in 555-01xx", all(re.search(r"555-01\d\d$", p) for p in phones))
    dup_ph = [p for p, n in collections.Counter(phones).items() if n > 1]
    check("primary phones unique", not dup_ph, dup_ph[:5])
    ips = [r[0] for r in q(con, "SELECT ip FROM ip_intel")]
    check("IPs in reserved test ranges", all(i.startswith(("198.18.", "198.19.", "203.0.113.")) for i in ips))
    # ------------------------------------------------ hero invariants
    r = q(con, "SELECT auth_code, clearing_seq, clearing_count, billing_amount, auth_amount, processing_date FROM transactions WHERE txn_id IN ('TXN-9000401','TXN-9000402') ORDER BY txn_id")
    check("C04 split clearing same auth", r[0][0] == r[1][0] and (r[0][1], r[1][1]) == ("1", "2") and
          f"{float(r[0][3]) + float(r[1][3]):.2f}" == r[0][4] == "128.36", r)
    r = q(con, "SELECT transmitted_at FROM statements WHERE account_id='ACC-CR-90001' AND cycle_start <= '2026-08-19' AND cycle_end >= '2026-08-19'")
    check("C01 first statement transmitted 2026-08-26", r and r[0][0].startswith("2026-08-26"), r)
    check("C01 Reg Z 60-day deadline", (dt.date(2026, 8, 26) + dt.timedelta(days=60)).isoformat() == "2026-10-25")
    r = q(con, "SELECT cycle_end, transmitted_at FROM statements WHERE account_id='ACC-CR-90022' AND cycle_start <= '2026-02-03' AND cycle_end >= '2026-02-03'")
    check("C17 statement cycle end 2026-02-20", r and r[0][0] == "2026-02-20", r)
    nxt = q(con, "SELECT closing_balance, payments FROM statements WHERE account_id='ACC-CR-90022' ORDER BY cycle_end")
    paid = all(abs(float(nxt[i + 1][1]) - float(nxt[i][0])) < 0.01 for i in range(1, len(nxt) - 1) if float(nxt[i][0]) > 0)
    check("C17 customer pays statement balance in full", paid)
    check("C08 20 business days -> 2026-11-10", add_business_days("2026-10-13", 20) == "2026-11-10")
    check("C08 10 business days -> 2026-10-27", add_business_days("2026-10-13", 10) == "2026-10-27")
    check("C15 Reg Z deadline Sep notice", reg_z_resolution_deadline("2026-09-18", 5) == "2026-12-05")
    check("C15 Reg Z deadline Oct notice", reg_z_resolution_deadline("2026-10-19", 5) == "2027-01-05")
    check("C18 5 business days after 2026-10-21", add_business_days("2026-10-21", 5) == "2026-10-28")
    check("C06 unused portion", f"{119.88 * 360 / 365:.2f}" == "118.24")
    check("C05 folio arithmetic", abs(567 + 180 + 105 + 96 + round((567 + 180 + 105) * 0.1525, 2) + 9.60 - 1087.53) < 0.005)
    r = q(con, "SELECT SUM(CAST(billing_amount AS REAL)) FROM transactions t JOIN dispute_transactions x USING(txn_id) WHERE x.case_id='DSP-2026-90011'")
    check("C10 total 486.77", f"{r[0][0]:.2f}" == "486.77", r)
    # ------------------------------------------------ discoverability (the agent must be able to find these with plain queries)
    cpp = q(con, """
        WITH victims AS (
          SELECT d.card_id, MIN(t.txn_local_datetime) AS first_fraud
          FROM disputes d JOIN dispute_transactions x USING(case_id) JOIN transactions t USING(txn_id)
          WHERE d.claim_family_initial='fraud_cnp' AND d.opened_at >= '2026-09-15' GROUP BY d.card_id)
        SELECT m.dba_name, COUNT(DISTINCT v.card_id) AS n
        FROM victims v JOIN transactions t ON t.card_id = v.card_id AND t.card_present='true'
             AND t.txn_local_datetime < v.first_fraud AND t.txn_local_datetime >= date(v.first_fraud, '-30 day')
        JOIN merchants m USING(merchant_id)
        GROUP BY m.merchant_id ORDER BY n DESC LIMIT 3""")
    check("C08 CPP query ranks Pinegrove Fuel #22 first", cpp and cpp[0][0] == "Pinegrove Fuel #22" and cpp[0][1] >= 8 and
          (len(cpp) < 2 or cpp[1][1] <= cpp[0][1] / 2), cpp)
    shared = q(con, """
        SELECT device_id, GROUP_CONCAT(DISTINCT customer_id) FROM account_events
        WHERE event_type='login_success' AND device_id <> ''
        GROUP BY device_id HAVING COUNT(DISTINCT customer_id) > 1""")
    ring_devs = {dv: set(c.split(",")) for dv, c in shared}
    ring_members = set().union(*[v for k, v in ring_devs.items() if k.startswith("DEV-RING")]) if ring_devs else set()
    check("C12 ring devices connect 4 customers", ring_members == {"CUS-90013", "CUS-90014", "CUS-90015", "CUS-90016"}, ring_members)
    check("C12b innocent not on shared devices", not any("CUS-90017" in v for v in ring_devs.values()))
    alt = q(con, "SELECT alt_phone, GROUP_CONCAT(customer_id) FROM customers WHERE alt_phone<>'' GROUP BY alt_phone")
    check("C12 alt phone shared by 90014 & 90016", ("(614) 555-0188", "CUS-90014,CUS-90016") in alt, alt)
    n14 = q(con, """SELECT COUNT(*) FROM disputes d JOIN dispute_transactions x USING(case_id) JOIN transactions t USING(txn_id)
                   WHERE d.customer_id='CUS-90014' AND t.merchant_id='MER-90014' AND d.claim_family_initial='not_received'
                   AND d.opened_at >= '2026-09-25'""")[0][0]
    check("C12 CUS-90014 three Stridevault claims within 30 days", n14 == 3, n14)
    drop = collections.Counter()
    for path in glob.glob(os.path.join(GEN, "documents", "evidence_packets", "*.json")):
        pk = json.load(open(path))
        if "Wharfside" in (pk.get("shipping_address") or ""):
            drop[pk["case_id"]] += 1
    check("C11 drop address in >= 4 disputes", len(drop) >= 4, dict(drop))
    days = {t: (dt.date(2026, 10, 26) - dt.date.fromisoformat(dd)).days for t, dd in
            (("pr1", "2026-03-20"), ("pr2", "2026-05-15"), ("pr3", "2026-09-10"))}
    check("C09 prior ages", days == {"pr1": 220, "pr2": 164, "pr3": 46}, days)
    qm = q(con, """SELECT COUNT(*) FROM disputes d JOIN dispute_transactions x USING(case_id) JOIN transactions t USING(txn_id)
                  WHERE t.merchant_id IN ('MER-90023','MER-90024') AND d.status='closed'""")[0][0]
    check("C19 eleven historical Quillmark disputes", qm == 11, qm)
    qm_after = q(con, "SELECT COUNT(*) FROM transactions WHERE merchant_id='MER-90023' AND txn_local_datetime >= '2026-08-12' AND txn_id <> 'TXN-9002101'")[0][0]
    check("C19 post-August Quillmark orders exist", qm_after >= 6, qm_after)
    oak = q(con, """SELECT COUNT(*) FROM disputes d JOIN dispute_transactions x USING(case_id) JOIN transactions t USING(txn_id)
                   WHERE t.merchant_id='MER-90001' AND d.status='open' AND d.case_id<>'DSP-2026-90001'""")[0][0]
    check("C01 Oakhollow cluster of 4", oak == 4, oak)
    bf = q(con, "SELECT COUNT(*) FROM transactions WHERE customer_id='CUS-90002' AND merchant_id='MER-90002' AND txn_id<>'TXN-9000201'")[0][0]
    check("C02 prior Bluefern visits", bf == 16, bf)
    # ------------------------------------------------ ground truth references resolve
    policy_ids = set()
    for path in glob.glob(os.path.join(CORPUS, "policies", "**", "*.md"), recursive=True):
        m = re.search(r"^doc_id:\s*\"?([^\"\n]+)", open(path, encoding="utf-8").read(), re.M)
        if m:
            policy_ids.add(m.group(1).strip())
    ids = dict(
        MEP={os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(GEN, "documents", "evidence_packets", "*.json"))},
        WEB={os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(GEN, "documents", "research", "*.md"))},
        PRE={os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(GEN, "precedents", "*.md"))},
        MEM={json.loads(l)["note_id"] for l in open(os.path.join(GEN, "memory_seed", "agent_memory_notes.jsonl"))})
    for path in glob.glob(os.path.join(GEN, "ground_truth", "cases", "*.json")):
        gt = json.load(open(path))
        text = json.dumps(gt)
        for pref, known in ids.items():
            for ref in set(re.findall(rf"\b{pref}-[0-9A-Z]+(?:-[0-9A-Z]+)*\b", text)):
                if pref == "MEM" and ".." in ref:
                    continue
                check(f"{gt['case_id']} ref {ref} exists", ref in known)
        for pid in gt.get("must_cite", []):
            check(f"{gt['case_id']} must_cite {pid} in corpus", pid in policy_ids)
        for dsp in set(re.findall(r"\bDSP-20\d\d-\d{5}\b", text)):
            check(f"{gt['case_id']} case {dsp} exists", q(con, "SELECT 1 FROM disputes WHERE case_id=?", dsp) != [])
        for txn in set(re.findall(r"\bTXN-\d{7}\b", text)):
            check(f"{gt['case_id']} txn {txn} exists", q(con, "SELECT 1 FROM transactions WHERE txn_id=?", txn) != [])
    # ------------------------------------------------ required capabilities: every one is needed by real cases
    cov = json.load(open(os.path.join(GEN, "ground_truth", "capability_coverage.json")))
    required = {"agents", "router", "loop_termination", "agent_graph", "subagents", "tool_calling", "harness", "skills",
                "memory_persistent", "memory_graph", "memory_semantic", "sandbox", "read_paths", "write_paths"}
    check("all required capabilities defined", required <= set(cov), required - set(cov))
    for cap in sorted(required):
        prim = cov.get(cap, {}).get("primary_cases", [])
        check(f"capability {cap} is primary in >= 2 cases", len(prim) >= 2, prim)
    for path in glob.glob(os.path.join(GEN, "ground_truth", "cases", "*.json")):
        gt = json.load(open(path))
        if "see" in gt:
            continue
        caps = gt.get("required_capabilities", [])
        check(f"{gt['case_id']} has a primary capability", any(c["necessity"] == "primary" for c in caps))
    q01 = json.load(open(os.path.join(GEN, "ground_truth", "Q01_queue.json")))
    check("Q01 has required capabilities", bool(q01.get("required_capabilities")))
    # ------------------------------------------------ summary
    print(f"PASS {len(passes)}   FAIL {len(failures)}")
    for f in failures:
        print("  FAIL:", f)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
