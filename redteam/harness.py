"""Red-team harness: build a tiny synthetic data room, run the real system on it, return one row per hit.

    w = World()
    c = w.customer(full_name="Ivan Petrov", dob="1970-05-01", nationality="Russia")
    h = w.hit(c, name="Petrov, Ivan", dobs=["1970"], countries=["Russia"])
    row = w.run()[h]

Every customer gets an account, an onboarding row and a KYC applicant; alerts link through account_ref unless
link=None is passed (then the system has to search by screened name/DOB/country/city). Stdlib only."""
import io, json, os, shutil, sys, tempfile
from contextlib import redirect_stderr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))
import screen  # noqa: E402

UNSAFE = "DIFFERENT_ENTITY"


class World:
    def __init__(self):
        self.customers, self.accounts, self.onboarding, self.kyc = [], [], [], []
        self.notes, self.search, self.alerts, self.hits = [], [], [], []
        self._n = 0

    def _id(self, prefix):
        self._n += 1
        return f"{prefix}-{self._n:06X}"

    # ------------------------------------------------------------------ customer side
    def customer(self, full_name, dob="", nationality="", residence_country="", entity_type="Individual", **kw):
        rid = kw.pop("record_id", None) or "CUS-%06d" % (100000 + len(self.customers))
        email = kw.pop("email", None) or f"{rid.lower()}@test.example"
        rec = {"record_id": rid, "entity_type": entity_type, "full_name": full_name, "preferred_name": "", "login_name": "",
               "dob": dob, "nationality": nationality, "residence_country": residence_country, "city": "", "address": "",
               "email": email, "phone": kw.pop("phone", "+44 7700 %06d" % len(self.customers)), "occupation": "", "employer": "",
               "registration_number": "", "onboarded_at": "2022-01-01", "status": "active", "last_kyc_refresh": "2024-01-01"}
        rec.update(kw)
        self.customers.append(rec)
        acc = self._id("ACC")
        app = self._id("APP")
        self.accounts.append({"account_id": acc, "customer_id": rid, "login_handle": rid.lower().replace("-", ""),
                              "phone": rec["phone"], "opened_at": "2022-01-01", "status": "active"})
        self.onboarding.append({"account_id": acc, "customer_id": rid, "kyc_applicant_id": app, "onboarded_at": "2022-01-01"})
        rec["_acc"], rec["_app"] = acc, app
        return rec

    def kyc_check(self, cust, verified_name="", verified_dob="", document_country="", result="approved",
                  checked_at="2024-01-01", document_number=None, **kw):
        cid = kw.pop("check_id", None) or self._id("KYC")
        self.kyc.append({"check_id": cid, "applicant_id": cust["_app"], "provider": kw.pop("provider", "Onfido"),
                         "verified_name": verified_name, "verified_dob": verified_dob, "document_type": "passport",
                         "document_number": document_number or ("P" + cid[-6:]), "document_country": document_country,
                         "result": result, "checked_at": checked_at})
        return cid

    def note(self, cust, text, channel="kyc", created_at="2024-01-01"):
        nid = self._id("NOTE")
        self.notes.append({"note_id": nid, "requester_email": cust["email"], "created_at": created_at, "channel": channel, "text": text})
        return nid

    def search_result(self, query, snippet, title=""):
        sid = self._id("SR")
        q = " ".join(sorted(query.lower().split()))
        self.search.append({"result_id": sid, "query": q, "title": title or query, "snippet": snippet, "source": "news.example"})
        return sid

    # ------------------------------------------------------------------ hit side
    def hit(self, cust, link="account", alert=None, **hit_fields):
        """One alert with one hit. cust = the customer the alert was raised on (or None)."""
        aid, hid = self._id("A"), self._id("H")
        a = {"alert_id": aid, "screened_at": "2026-11-01", "customer_name": cust["full_name"] if cust else "",
             "entity_type": cust["entity_type"] if cust else "Individual", "dob": "", "country": "", "city": "",
             "account_ref": "", "login_handle": "", "email": "", "hit_count": 1, "hit_ids": [hid]}
        if cust and link == "account":
            a["account_ref"] = cust["_acc"]
        a.update(alert or {})
        self.alerts.append(a)
        h = {"hit_id": hid, "alert_id": aid, "match_score": 90.0, "entity_type": "Individual", "name": "", "aliases": [],
             "gender": "", "dobs": [], "place_of_birth": [], "life_status": "", "deceased_date": "", "nationality": [],
             "citizenship": [], "countries": [], "addresses": [], "identifiers": [], "categories": ["Sanctions"],
             "primary_category": "Sanctions", "position_or_allegation": "", "details": "", "relationships": [],
             "profile_notes": "", "sources": [], "source_urls": []}
        h.update(hit_fields)
        self.hits.append(h)
        return hid

    # ------------------------------------------------------------------ run
    def run(self):
        d = tempfile.mkdtemp(prefix="redteam-")
        try:
            strip = lambda r: {k: v for k, v in r.items() if not k.startswith("_")}
            for name, rows in [("customers", self.customers), ("accounts", self.accounts), ("onboarding", self.onboarding),
                               ("kyc_checks", self.kyc), ("notes", self.notes), ("search_results", self.search),
                               ("alerts", self.alerts), ("hits", self.hits)]:
                with open(os.path.join(d, name + ".jsonl"), "w", encoding="utf-8") as f:
                    for r in rows:
                        f.write(json.dumps(strip(r), ensure_ascii=False) + "\n")
            shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), "name_variants.json"), d)
            with redirect_stderr(io.StringIO()):
                rows = screen.run(d, os.path.join(d, "out.jsonl"))
            return {r["hit_id"]: r for r in rows}
        finally:
            shutil.rmtree(d, ignore_errors=True)


def one(build):
    """build(world) -> hit_id; returns that hit's output row."""
    w = World()
    hid = build(w)
    return w.run()[hid]
