#!/usr/bin/env python3
"""
Compare teammates' solutions fairly.

Each solution just needs to produce a predictions file (JSONL or CSV) with one row per hit:
    hit_id, decision, reason_code (optional), customer_record_id (optional)
Field names are matched loosely (decision/label/verdict, reason_code/reason_codes/reason, ...).

    python compare.py dev/practice_labels.jsonl yianni.jsonl alex.jsonl sam.csv

Prints:
  1. Score on the 50 practice labels (decision, decision+reason, customer, worst mistakes)
  2. Where the solutions DISAGREE on the other ~770 unlabelled hits - check a sample of
     those by hand against the policy; that is the real test of who generalises.
"""
import csv, json, os, sys, random
from collections import Counter

DEC_KEYS = ["decision", "label", "verdict", "prediction", "result"]
CODE_KEYS = ["reason_code", "reason_codes", "reason", "code"]
CUST_KEYS = ["customer_record_id", "customer_record_ids", "customer_id", "customer", "record_id"]
NORM = {"SAME": "SAME_ENTITY", "MATCH": "SAME_ENTITY", "TRUE_MATCH": "SAME_ENTITY",
        "DIFFERENT": "DIFFERENT_ENTITY", "NO_MATCH": "DIFFERENT_ENTITY", "FALSE_POSITIVE": "DIFFERENT_ENTITY",
        "CLEAR": "DIFFERENT_ENTITY", "ESCALATE": "REVIEW", "HUMAN_REVIEW": "REVIEW"}


def load(path):
    rows = []
    if path.endswith(".csv"):
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    else:
        with open(path, encoding="utf-8") as f:
            txt = f.read().strip()
        if txt.startswith("["):
            rows = json.loads(txt)
        else:
            rows = [json.loads(l) for l in txt.splitlines() if l.strip()]
    out = {}
    for r in rows:
        r = {k.lower().strip(): v for k, v in r.items()}
        hid = r.get("hit_id") or r.get("hit")
        if not hid:
            continue
        get = lambda keys: next((r[k] for k in keys if k in r and r[k] not in (None, "")), None)
        dec = str(get(DEC_KEYS) or "").upper().strip().replace(" ", "_")
        dec = NORM.get(dec, dec)
        code = get(CODE_KEYS)
        codes = code if isinstance(code, list) else [c.strip() for c in str(code or "").split(";") if c.strip()]
        cust = get(CUST_KEYS)
        if isinstance(cust, list):
            cust = cust[0] if cust else None
        cust = str(cust).split(";")[0].strip() if cust else None
        if cust in ("None", "null", ""):
            cust = None
        out[hid] = {"decision": dec, "codes": [c.upper() for c in codes], "cust": cust}
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    gold = load(sys.argv[1])
    gold_raw = {}
    with open(sys.argv[1], encoding="utf-8") as f:
        for l in f:
            if l.strip():
                j = json.loads(l)
                gold_raw[j["hit_id"]] = j
    sols = {os.path.splitext(os.path.basename(p))[0]: load(p) for p in sys.argv[2:]}

    print("=" * 90)
    print(f"1) PRACTICE LABELS ({len(gold)} hits)")
    print("=" * 90)
    print(f"{'solution':<20}{'coverage':>10}{'decision':>10}{'+reason':>10}{'customer':>10}{'WORST*':>9}")
    for name, P in sols.items():
        cov = sum(h in P for h in gold)
        d = dr = c = worst = 0
        for hid, g in gold.items():
            p = P.get(hid)
            if not p:
                continue
            if p["decision"] == g["decision"]:
                d += 1
                if set(p["codes"]) & set(g["codes"]):
                    dr += 1
            gc = [x.strip() for x in (gold_raw[hid].get("customer_record_ids") or "").split(";") if x.strip()]
            if (not gc and p["cust"] is None) or (p["cust"] in gc):
                c += 1
            if g["decision"] == "SAME_ENTITY" and p["decision"] == "DIFFERENT_ENTITY":
                worst += 1
        print(f"{name:<20}{cov:>10}{d:>10}{dr:>10}{c:>10}{worst:>9}")
    print("* WORST = cleared a hit that IS the customer (the policy's worst mistake). Must be 0.")

    names = list(sols)
    if len(names) < 2:
        return
    all_hits = sorted(set().union(*[set(P) for P in sols.values()]) - set(gold))
    print()
    print("=" * 90)
    print(f"2) DISAGREEMENTS ON THE {len(all_hits)} UNLABELLED HITS")
    print("=" * 90)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            A, B = sols[names[i]], sols[names[j]]
            both = [h for h in all_hits if h in A and h in B]
            diff = [h for h in both if A[h]["decision"] != B[h]["decision"]]
            pat = Counter((A[h]["decision"], B[h]["decision"]) for h in diff)
            print(f"\n{names[i]} vs {names[j]}: agree on {len(both) - len(diff)}/{len(both)}, disagree on {len(diff)}")
            for (a, b), n in pat.most_common():
                print(f"   {names[i]}={a:<17} {names[j]}={b:<17} x{n}")
            random.seed(0)
            sample = random.sample(diff, min(8, len(diff)))
            if sample:
                print("   hand-check these against the policy (python screen.py --case <hit_id> shows the evidence):")
                print("   " + "  ".join(sample))
    print("\nDistribution per solution:")
    for name, P in sols.items():
        print(f"   {name:<20}", dict(Counter(p["decision"] for p in P.values())))


if __name__ == "__main__":
    main()
