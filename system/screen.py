"""Entry point: python3 screen.py <data folder> <output file>.  Deterministic, stdlib only, no network."""
import json, os, sys
from data import DataRoom, as_text, as_list
from textutil import NameMatcher
from resolve import CustomerIndex
from profile import Profile
from hitfacts import HitFacts, build_search_index
from decide import Decider


def run(folder, out_path):
    room = DataRoom(folder)
    matcher = NameMatcher(room.groups, room.legal_forms)
    idx = CustomerIndex(room, matcher)
    sidx = build_search_index(room.search)
    decider = Decider(matcher)
    alerts = {as_text(a.get("alert_id")): a for a in room.alerts}
    hits_by_alert = {}
    for h in room.hits:
        hits_by_alert.setdefault(as_text(h.get("alert_id")), []).append(h)
    # hits referenced only by alerts.hit_ids
    hit_by_id = {as_text(h.get("hit_id")): h for h in room.hits}
    resolved_cache, profile_cache = {}, {}
    rows = []
    for h in sorted(room.hits, key=lambda h: (as_text(h.get("alert_id")), as_text(h.get("hit_id")))):
        aid = as_text(h.get("alert_id"))
        alert = alerts.get(aid)
        if alert is None:
            alert = next((a for a in room.alerts if as_text(h.get("hit_id")) in as_list(a.get("hit_ids"))), {"alert_id": aid})
            aid = as_text(alert.get("alert_id")) or aid
        hf = HitFacts(h, matcher, sidx)
        if aid not in resolved_cache:
            resolved_cache[aid] = idx.resolve_with_near(alert)
        persons, path, near = resolved_cache[aid]
        try:
            if not persons:
                res = decider.decide_unresolved(hf, alert, path)
            else:
                results = []
                for p in persons:
                    key = p["primary"]
                    if key not in profile_cache:
                        profile_cache[key] = Profile(idx, p)
                    prof = profile_cache[key]
                    r = decider.decide_person(prof, hf, alert)
                    if r["decision"] == "DIFFERENT_ENTITY" and prof.ambiguous:
                        # a note that both approves and rejects must not let a clear stand if its facts would stop it
                        r2 = decider.decide_person(Profile(idx, p, promote_ambiguous=True), hf, alert)
                        if r2["decision"] != "DIFFERENT_ENTITY":
                            ids = [c["id"] for c in prof.ambiguous]
                            r = {"decision": "REVIEW", "reason_code": "INSUFFICIENT_DATA", "evidence": ids + [e for e in r["evidence"] if e not in ids],
                                 "reason": f"{r['reason']} However the identity note {', '.join(ids)} both approves and rejects a check, and if it "
                                           f"counts as approved the hit is no longer contradicted, so a person must review it."}
                    results.append((p, r))
                if len(results) == 1:
                    p, r = results[0]
                    res = dict(r, customer_record_id=p["primary"])
                else:
                    decs = {r["decision"] for _, r in results}
                    ev = []
                    for _, r in results:
                        for e in r["evidence"]:
                            if e not in ev:
                                ev.append(e)
                    ids = ", ".join(p["primary"] for p, _ in results)
                    if len(decs) == 1:
                        r0 = results[0][1]
                        res = dict(r0, customer_record_id="AMBIGUOUS", evidence=ev,
                                   reason=f"{len(results)} different people in the system of record fit the alert ({ids}); each leads to {r0['decision']}. " + r0["reason"])
                    else:
                        summary = "; ".join(f"{p['primary']}: {r['decision']} ({r['reason_code']})" for p, r in results)
                        res = {"decision": "REVIEW", "reason_code": "AMBIGUOUS_CUSTOMER_RECORD", "customer_record_id": "AMBIGUOUS",
                               "evidence": ev,
                               "reason": f"{len(results)} different people in the system of record fit the alert ({ids}) and they lead to different decisions: {summary}. A person must decide which customer was screened."}
            if res["decision"] == "DIFFERENT_ENTITY" and near:
                # a clear must also hold for anyone the screened city alone excluded ('Munich' vs 'München')
                held = []
                for p in near:
                    if p["primary"] not in profile_cache:
                        profile_cache[p["primary"]] = Profile(idx, p)
                    r = decider.decide_person(profile_cache[p["primary"]], hf, alert)
                    if r["decision"] != "DIFFERENT_ENTITY":
                        held.append((p, r))
                if held:
                    ids = ", ".join(p["primary"] for p, _ in held)
                    summary = "; ".join(f"{p['primary']}: {r['decision']} ({r['reason_code']})" for p, r in held)
                    res = {"decision": "REVIEW", "reason_code": "AMBIGUOUS_CUSTOMER_RECORD", "customer_record_id": "AMBIGUOUS",
                           "evidence": list(res["evidence"]) + [e for _, r in held for e in r["evidence"] if e not in res["evidence"]],
                           "reason": f"The customer who fits the alert is cleared ({res['reason_code']}), but {ids} fits the screened name and "
                                     f"details except the city spelling and leads to {summary}. A person must decide which customer was screened."}
        except Exception as e:  # never crash a run; fail safe to REVIEW
            res = {"decision": "REVIEW", "reason_code": "INSUFFICIENT_DATA", "customer_record_id": None,
                   "reason": f"The hit could not be evaluated automatically ({type(e).__name__}), so it is left for review.", "evidence": []}
        rows.append({"hit_id": as_text(h.get("hit_id")), "alert_id": aid, "decision": res["decision"],
                     "reason_code": res["reason_code"], "customer_record_id": res.get("customer_record_id"),
                     "reason": res["reason"], "evidence": list(res["evidence"])})
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n")
    return rows


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: system/run <data folder> <output file>", file=sys.stderr)
        sys.exit(2)
    rows = run(sys.argv[1], sys.argv[2])
    from collections import Counter
    print(json.dumps(dict(Counter(r["decision"] for r in rows))), file=sys.stderr)
