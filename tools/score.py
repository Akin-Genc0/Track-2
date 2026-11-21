"""Local scorer: python3 tools/score.py output/dev.jsonl dev/practice_labels.jsonl"""
import json, sys
COST = {("DIFFERENT_ENTITY", "SAME_ENTITY"): 3, ("DIFFERENT_ENTITY", "REVIEW"): 3,
        ("SAME_ENTITY", "DIFFERENT_ENTITY"): 60, ("SAME_ENTITY", "REVIEW"): 2,
        ("REVIEW", "DIFFERENT_ENTITY"): 60, ("REVIEW", "SAME_ENTITY"): 2}
def lst(v): return v if isinstance(v, list) else [x.strip() for x in str(v or "").split(";") if x.strip()]
pred = {json.loads(l)["hit_id"]: json.loads(l) for l in open(sys.argv[1], encoding="utf-8")}
labs = [json.loads(l) for l in open(sys.argv[2], encoding="utf-8")]
cost = base = 0; unsafe = 0; right = 0; code_ok = cust_ok = 0; evj = 0.0; verbose = "-v" in sys.argv
for L in labs:
    p = pred.get(L["hit_id"])
    t = L["decision"]; d = p["decision"] if p else "REVIEW"
    c = COST.get((t, d), 0); cost += c; base += COST.get((t, "REVIEW"), 0)
    if c == 60: unsafe += 1
    if t == d:
        right += 1
        if p["reason_code"] in lst(L["reason_codes"]): code_ok += 1
        cids = lst(L["customer_record_ids"])
        if (p["customer_record_id"] in cids) or (p["customer_record_id"] == "AMBIGUOUS" and "AMBIGUOUS" in cids) or (not cids and p["customer_record_id"] is None): cust_ok += 1
        g, s = set(lst(L["evidence"])), set(p["evidence"])
        evj += len(g & s) / len(g | s) if g | s else 1
    if verbose and (t != d or p["reason_code"] not in lst(L["reason_codes"]) or set(lst(L["evidence"])) != set(p["evidence"])):
        print(f"{L['hit_id']} truth={t} {lst(L['reason_codes'])} cust={lst(L['customer_record_ids'])} ev={sorted(lst(L['evidence']))}\n   pred={d} {p['reason_code']} cust={p['customer_record_id']} ev={sorted(p['evidence'])}\n   {p['reason'][:300]}")
print(f"labels={len(labs)} correct={right} unsafe={unsafe} cost={cost} all-review cost={base} score={max(0, 1 - cost / base) if base else 0:.3f}")
print(f"on correct: code_ok={code_ok}/{right} cust_ok={cust_ok}/{right} evidence_jaccard={evj / max(right, 1):.2f}")
