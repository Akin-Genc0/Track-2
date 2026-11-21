#!/usr/bin/env python3
"""
Web terminal for the Track 2 screening engine.

    python3 app.py                 # then open http://localhost:8000
    python3 app.py --port 9000 --data dev

No extra packages needed (standard library only). All decisions come from screen.py.
"""
import argparse, json, os, random, sys, time, threading
from datetime import date
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import screen  # noqa: E402

STATE = {"engine": None, "preds": None, "by_hit": {}, "eval": None, "ready": False,
         "error": None, "load_secs": None}


def load(data_dir):
    t0 = time.time()
    try:
        eng = screen.Engine(data_dir)
        preds = eng.run()
        STATE.update(engine=eng, preds=preds, by_hit={p["hit_id"]: p for p in preds})
        STATE["eval"] = evaluate(preds, screen.find_file(data_dir, "practice_labels"))
        STATE["ready"] = True
    except Exception as e:  # pragma: no cover
        STATE["error"] = f"{type(e).__name__}: {e}"
    STATE["load_secs"] = round(time.time() - t0, 1)


def evaluate(preds, path):
    labels = screen.load_jsonl(path)
    if not labels:
        return None
    P = {p["hit_id"]: p for p in preds}
    rows, d_ok, c_ok, r_ok, worst = [], 0, 0, 0, 0
    for l in labels:
        p = P.get(l["hit_id"])
        if not p:
            continue
        codes = [c.strip() for c in (l.get("reason_codes") or "").split(";") if c.strip()]
        lc = [c.strip() for c in (l.get("customer_record_ids") or "").split(";") if c.strip()]
        dk = p["decision"] == l["decision"]
        ck = dk and p["reason_code"] in codes
        rk = (p["customer_record_id"] == "AMBIGUOUS") if lc == ["AMBIGUOUS"] else \
             (p["customer_record_id"] is None if not lc else p["customer_record_id"] in lc)
        d_ok += dk; c_ok += ck; r_ok += rk
        worst += l["decision"] == "SAME_ENTITY" and p["decision"] == "DIFFERENT_ENTITY"
        rows.append({"hit_id": l["hit_id"], "gold": l["decision"], "pred": p["decision"], "ok": dk and ck and rk})
    return {"n": len(rows), "decision": d_ok, "reason": c_ok, "customer": r_ok, "worst": worst, "rows": rows}


def counts(preds):
    out = {"SAME_ENTITY": 0, "DIFFERENT_ENTITY": 0, "REVIEW": 0}
    reasons = {}
    for p in preds:
        out[p["decision"]] = out.get(p["decision"], 0) + 1
        reasons[p["reason_code"]] = reasons.get(p["reason_code"], 0) + 1
    return out, dict(sorted(reasons.items(), key=lambda kv: -kv[1]))


def alert_of(eng, alert_id):
    return next((a for a in eng.alerts if a["alert_id"] == alert_id), None)


def row(eng, p):
    al = alert_of(eng, p["alert_id"])
    h = eng.hits[p["hit_id"]]
    return {"hit_id": p["hit_id"], "alert_id": p["alert_id"], "decision": p["decision"],
            "reason_code": p["reason_code"], "customer": screen.s(al.get("customer_name")),
            "flagged": screen.s(h.get("name")), "category": screen.s(h.get("primary_category")) or
            (screen.split_list(h.get("categories")) or [None])[0], "explanation": p["explanation"]}


def picture_json(P):
    return {"records": P["records"], "names": P["names"], "verified_name": P["verified_name"],
            "verified_src": P["verified_src"], "dob": screen.fmt_date(P["dob"]) if P["dob"] else None,
            "dob_src": P["dob_src"],
            "countries": [{"name": screen.country_name(c), "src": v} for c, v in P["countries"].items()]}


def case(key):
    eng = STATE["engine"]
    key = key.strip().upper()
    if key.startswith("H-"):
        al = next((a for a in eng.alerts if key in screen.split_list(a.get("hit_ids"))), None)
        hit_ids = [key]
    else:
        al = alert_of(eng, key)
        hit_ids = screen.split_list(al.get("hit_ids")) if al else []
    if not al:
        return {"error": f"no alert or hit with id {key}"}
    persons, path = eng.resolve(al)
    pics = [eng.picture(p) for p in persons]
    hits = []
    for hid in hit_ids:
        h = eng.hits[hid]
        hds, hsrc, sr = eng.hit_dobs(h)
        p = STATE["by_hit"][hid]
        hits.append({"hit_id": hid, "name": screen.s(h.get("name")), "aliases": screen.split_list(h.get("aliases")),
                     "entity_type": screen.s(h.get("entity_type")),
                     "category": screen.s(h.get("primary_category")) or screen.s(h.get("categories")),
                     "match_score": h.get("match_score"), "gender": screen.s(h.get("gender")),
                     "born": [screen.fmt_date(d) for d in hds], "born_src": hsrc,
                     "countries": [screen.country_name(c) for c in eng.hit_countries(h)],
                     "position": screen.s(h.get("position_or_allegation")),
                     "deceased": screen.s(h.get("deceased_date")),
                     "decision": p["decision"], "reason_code": p["reason_code"],
                     "explanation": p["explanation"], "evidence": p["evidence"],
                     "customer_record_id": p["customer_record_id"]})
    return {"alert": {"alert_id": al["alert_id"], "screened_at": screen.s(al.get("screened_at")),
                      "customer_name": screen.s(al.get("customer_name")), "entity_type": screen.s(al.get("entity_type")),
                      "dob": screen.s(al.get("dob")), "country": screen.s(al.get("country")), "city": screen.s(al.get("city"))},
            "path": path, "customers": [picture_json(P) for P in pics], "hits": hits}


def check(body):
    eng = STATE["engine"]
    c, h = body.get("customer", {}), body.get("hit", {})
    al = {"alert_id": "A-LIVE", "screened_at": date.today().isoformat(), "customer_name": c.get("name"),
          "entity_type": c.get("type") or "Individual", "dob": c.get("dob"), "country": c.get("country")}
    hit = {"hit_id": "H-LIVE", "name": h.get("name"), "entity_type": h.get("type") or al["entity_type"],
           "aliases": h.get("aliases"), "dobs": h.get("dobs"), "countries": h.get("countries"),
           "profile_notes": h.get("profile"), "deceased_date": h.get("deceased"), "primary_category": "Sanctions"}
    r = eng.decide_one(eng.screened_picture(al), hit, al)
    return {"decision": r["decision"], "reason_code": r["reason_code"], "explanation": r["why"]}


def demo(n=None):
    eng = STATE["engine"]
    out = []
    for i, (title, c, hh) in enumerate(screen.DEMOS, 1):
        if n and i != n:
            continue
        r = check({"customer": {"name": c[0], "type": c[1], "dob": c[2], "country": c[3]},
                   "hit": {"name": hh[0], "type": hh[1], "aliases": hh[2], "dobs": hh[3], "countries": hh[4],
                           "profile": hh[5], "deceased": hh[6]}})
        out.append({"n": i, "title": title,
                    "customer": {"name": c[0], "type": c[1], "dob": c[2], "country": c[3]},
                    "hit": {"name": hh[0], "type": hh[1], "dobs": hh[3], "countries": hh[4], "profile": hh[5],
                            "deceased": hh[6]}, **r})
    return out


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, obj, code=200, ctype="application/json"):
        data = obj if isinstance(obj, (bytes, bytearray)) else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "json" in ctype or "html" in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "web", "index.html"), "rb") as f:
                return self.send(f.read(), ctype="text/html")
        if u.path == "/api/status":
            return self.send({"ready": STATE["ready"], "error": STATE["error"], "load_secs": STATE["load_secs"]})
        if not STATE["ready"]:
            return self.send({"error": "engine still loading", "loading": True}, 503)
        eng = STATE["engine"]
        if u.path == "/api/stats":
            c, r = counts(STATE["preds"])
            ev = STATE["eval"]
            return self.send({"alerts": len(eng.alerts), "hits": len(STATE["preds"]), "customers": len(eng.cust),
                              "counts": c, "reasons": r, "eval": ev, "load_secs": STATE["load_secs"]})
        if u.path == "/api/list":
            f = [x for x in (q.get("filter") or "").upper().split(",") if x]
            alias = {"SAME": "SAME_ENTITY", "MATCH": "SAME_ENTITY", "DIFFERENT": "DIFFERENT_ENTITY",
                     "DIFF": "DIFFERENT_ENTITY", "CLEARED": "DIFFERENT_ENTITY", "HUMAN": "REVIEW"}
            f = [alias.get(x, x) for x in f]
            rows = [p for p in STATE["preds"] if all(x in (p["decision"], p["reason_code"]) for x in f)]
            total = len(rows)
            if q.get("random"):
                rows = random.sample(rows, len(rows))
            n = int(q.get("n") or 15)
            return self.send({"total": total, "rows": [row(eng, p) for p in rows[:n]]})
        if u.path == "/api/case":
            return self.send(case(q.get("id", "")))
        if u.path == "/api/demo":
            return self.send(demo(int(q["n"]) if q.get("n") else None))
        return self.send({"error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if not STATE["ready"]:
            return self.send({"error": "engine still loading"}, 503)
        if u.path == "/api/check":
            return self.send(check(body))
        return self.send({"error": "not found"}, 404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(HERE, "dev"))
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    if not os.path.exists(screen.find_file(a.data, "alerts")):
        print(f"No data in {a.data}. Build it first:\n  python3 xlsx_to_jsonl.py \"Screening Dev Set - browse.xlsx\" dev")
        sys.exit(1)
    threading.Thread(target=load, args=(a.data,), daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    print(f"SENTINEL terminal on  http://localhost:{a.port}   (engine loading in background, ~30s)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")


if __name__ == "__main__":
    main()
