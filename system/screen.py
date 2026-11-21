"""Entry point: python3 screen.py <data folder> <output file>.  Deterministic, stdlib only, no network."""
import json, os, sys
from data import DataRoom, as_text, as_list, normalize
MODULE_ERROR = None
try:
    from textutil import NameMatcher
    from resolve import CustomerIndex
    from profile import Profile
    from hitfacts import HitFacts, build_search_index
    from decide import Decider
except Exception as exc:
    MODULE_ERROR = type(exc).__name__



CORE = ("customers", "accounts", "onboarding", "kyc_checks", "notes")


def recover_rows(folder, name):
    """Best-effort inventory plus explicit loss signal; never silently trust partial sources."""
    rows, damaged = [], False
    try:
        with open(os.path.join(folder, name + ".jsonl"), encoding="utf-8-sig") as source:
            for line in source:
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError("not a record")
                    rows.append(normalize(value, name))
                except Exception:
                    damaged = True
    except Exception:
        damaged = True
    return rows, damaged


def fallback(detail, customer_id=None):
    return {"decision": "REVIEW", "reason_code": "INSUFFICIENT_DATA",
            "customer_record_id": customer_id, "evidence": [],
            "reason": detail + ". An analyst must review this hit before a decision can be made."}


def run(folder, out_path):
    # Recover the work queue independently of decision-module initialization.
    hits, _ = recover_rows(folder, "hits")
    alert_rows, _ = recover_rows(folder, "alerts")
    alerts = {as_text(a.get("alert_id")): a for a in alert_rows}
    by_id = {as_text(h.get("hit_id")): h for h in hits if as_text(h.get("hit_id"))}
    missing_hits = set()
    for alert in alert_rows:
        for hid in as_list(alert.get("hit_ids")):
            if hid not in by_id:
                by_id[hid] = {"hit_id": hid, "alert_id": as_text(alert.get("alert_id"))}
                missing_hits.add(hid)
            elif not by_id[hid].get("alert_id"):
                by_id[hid]["alert_id"] = as_text(alert.get("alert_id"))
    unavailable = [name + ".jsonl" for name in CORE if recover_rows(folder, name)[1]]
    setup_error = None
    try:
        if MODULE_ERROR:
            raise RuntimeError("decision module import failed: " + MODULE_ERROR)
        room = DataRoom(folder)
        matcher = NameMatcher(room.groups, room.legal_forms)
        idx = CustomerIndex(room, matcher)
        sidx = build_search_index(room.search)
        decider = Decider(matcher)
    except Exception as exc:
        setup_error = type(exc).__name__
    resolved_cache, profile_cache = {}, {}
    rows = []
    for h in sorted(by_id.values(), key=lambda h: (as_text(h.get("alert_id")), as_text(h.get("hit_id")))):
        aid = as_text(h.get("alert_id"))
        customer_id = None
        try:
            if setup_error:
                raise RuntimeError("initialization failed: " + setup_error)
            if as_text(h.get("hit_id")) in missing_hits:
                raise ValueError("hit record unavailable")
            alert = alerts.get(aid, {"alert_id": aid})
            hf = HitFacts(h, matcher, sidx)
            if aid not in resolved_cache:
                resolved_cache[aid] = idx.resolve(alert)
            persons, path = resolved_cache[aid]
            if len(persons) == 1:
                customer_id = persons[0]["primary"]
            if not persons:
                res = decider.decide_unresolved(hf, alert, path)
            else:
                results = []
                for p in persons:
                    key = p["primary"]
                    if key not in profile_cache:
                        profile_cache[key] = Profile(idx, p)
                    r = decider.decide_person(profile_cache[key], hf, alert)
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
            if unavailable and res["decision"] == "DIFFERENT_ENTITY":
                res = fallback("Required sources were unavailable or partly unreadable: " + ", ".join(unavailable),
                               res.get("customer_record_id"))
            row = {"hit_id": as_text(h.get("hit_id")), "alert_id": aid, "decision": res["decision"],
                   "reason_code": res["reason_code"], "customer_record_id": res.get("customer_record_id"),
                   "reason": res["reason"], "evidence": list(res["evidence"])}
            json.dumps(row, allow_nan=False)
        except Exception as e:
            detail = "The automated check could not complete (" + (setup_error or type(e).__name__) + ")"
            if unavailable:
                detail += "; unavailable or partly unreadable sources: " + ", ".join(unavailable)
            row = dict(hit_id=as_text(h.get("hit_id")), alert_id=aid, **fallback(detail, customer_id))
        rows.append(row)
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
