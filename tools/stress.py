"""Unseen-robustness stress test: perturb an official-format data room into /tmp copies, re-run, and report
crashes, missing hits, run time and every move towards DIFFERENT_ENTITY that the perturbation cannot justify.

Each variant rewrites the data in a way the policy treats as the same evidence (name order, case, accents,
date formats, country synonyms, legal-form spellings, extra/missing optional fields, ...) or as LESS evidence
(empty notes, partial dates, extra candidate customers). Neither may turn a SAME_ENTITY/REVIEW hit into a clear.

  python3 tools/stress.py <dev folder> [variant ...]     (default: every variant; data copies go to /tmp)
Exit code 1 if any variant crashes, drops hits, or moves a hit to DIFFERENT_ENTITY."""
import collections, json, os, random, re, shutil, subprocess, sys, tempfile, time, unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MON = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
YM = re.compile(r"^(\d{4})-(\d{2})$")
SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
LONG = re.compile(r"^(" + "|".join(MON) + r") (\d{1,2}), (\d{4})$")
COUNTRY_SYN = {
    "United Kingdom": ["UK", "GB", "Great Britain", "U.K.", "British"], "United States": ["USA", "US", "U.S.", "United States of America", "American"],
    "Germany": ["Deutschland", "DE", "German", "Federal Republic of Germany"], "Spain": ["España", "ES", "Spanish"],
    "France": ["FR", "French", "République française"], "Italy": ["Italia", "IT", "Italian"], "Nigeria": ["NG", "Nigerian", "Federal Republic of Nigeria"],
    "Brazil": ["Brasil", "BR", "Brazilian"], "Mexico": ["México", "MX", "Mexican"], "Russia": ["Russian Federation", "RU", "Russian"],
    "Netherlands": ["The Netherlands", "Holland", "NL", "Dutch"], "Switzerland": ["Schweiz", "CH", "Swiss"], "Austria": ["Österreich", "AT", "Austrian"],
    "Canada": ["CA", "Canadian"], "India": ["IN", "Indian", "Bharat"], "Turkey": ["Türkiye", "TR", "Turkish"], "China": ["PRC", "CN", "Chinese", "People's Republic of China"],
    "Iran": ["Islamic Republic of Iran", "IR", "Iranian"], "United Arab Emirates": ["UAE", "AE", "Emirati"], "South Korea": ["Republic of Korea", "KR", "Korea, Republic of"],
    "Portugal": ["PT", "Portuguese"], "Poland": ["Polska", "PL", "Polish"], "Sweden": ["Sverige", "SE", "Swedish"], "Denmark": ["Danmark", "DK", "Danish"],
    "Belgium": ["België", "BE", "Belgian"], "Ireland": ["Éire", "IE", "Irish"], "Pakistan": ["PK", "Pakistani"], "Kenya": ["KE", "Kenyan"],
    "Ghana": ["GH", "Ghanaian"], "Egypt": ["EG", "Egyptian"], "South Africa": ["ZA", "South African"], "Australia": ["AU", "Australian"],
    "Japan": ["JP", "Japanese", "Nippon"], "Greece": ["Hellas", "GR", "Greek"], "Czech Republic": ["Czechia", "CZ", "Czech"],
    "Ukraine": ["UA", "Ukrainian"], "Philippines": ["PH", "Filipino"], "Indonesia": ["ID", "Indonesian"], "Colombia": ["CO", "Colombian"],
    "Argentina": ["AR", "Argentine"], "Singapore": ["SG", "Singaporean"], "Finland": ["Suomi", "FI", "Finnish"], "Norway": ["Norge", "NO", "Norwegian"],
}
LEGAL = [(r"\bLtd\b\.?", "Limited"), (r"\bLimited\b", "Ltd."), (r"\bGmbH\b", "G.m.b.H."), (r"\bS\.A\.", "SA"), (r"\bSA\b", "S.A."),
         (r"\bLLC\b", "L.L.C."), (r"\bInc\b\.?", "Incorporated"), (r"\bCorp\b\.?", "Corporation"), (r"\bPLC\b", "Public Limited Company"),
         (r"\bplc\b", "P.L.C."), (r"\bAG\b", "A.G."), (r"\bAB\b", "Aktiebolag"), (r"\bS\.p\.A\.", "SpA"), (r"\bB\.V\.", "BV"), (r"\bN\.V\.", "NV")]
ACCENT = str.maketrans({"a": "á", "e": "é", "i": "í", "o": "ö", "u": "ü", "c": "ç", "n": "ñ", "A": "Á", "E": "É", "O": "Ö", "U": "Ü"})


def strip_acc(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def ymd(s):
    """Parse the unambiguous date shapes found in the dev files -> (y, m, d) with m/d possibly None."""
    if not isinstance(s, str):
        return None
    s = s.strip()
    if m := ISO.match(s): return int(m[1]), int(m[2]), int(m[3])
    if m := YM.match(s): return int(m[1]), int(m[2]), None
    if re.fullmatch(r"\d{4}", s): return int(s), None, None
    if m := LONG.match(s): return int(m[3]), MON.index(m[1]) + 1, int(m[2])
    if (m := SLASH.match(s)) and int(m[1]) > 12: return int(m[3]), int(m[2]), int(m[1])   # only clearly D/M/Y
    return None


def fmt(dt, rnd):
    y, m, d = dt
    if m is None: return rnd.choice([str(y), f"{y}", f"c. {y}" if False else str(y)])
    if d is None: return rnd.choice([f"{MON[m-1]} {y}", f"{MON[m-1][:3]} {y}", f"{y}/{m:02d}", f"{m:02d}/{y}"])
    return rnd.choice([f"{d} {MON[m-1]} {y}", f"{MON[m-1]} {d}, {y}", f"{d:02d}-{MON[m-1][:3]}-{y}", f"{y}/{m:02d}/{d:02d}",
                       f"{d}. {MON[m-1]} {y}", f"{y}{m:02d}{d:02d}" if False else f"{y}-{m:02d}-{d:02d}T00:00:00",
                       f"{MON[m-1][:3].upper()} {d:02d} {y}", f"{d:02d}.{m:02d}.{y}" if d > 12 else f"{d} {MON[m-1][:3]} {y}"])


def redate(v, rnd):
    if isinstance(v, list): return [redate(x, rnd) for x in v]
    dt = ymd(v)
    return fmt(dt, rnd) if dt else v


def swap_order(name):
    if not isinstance(name, str) or not name.strip(): return name
    if "," in name:
        last, first = name.split(",", 1)
        return f"{first.strip()} {last.strip()}"
    parts = name.split()
    return f"{parts[-1]}, {' '.join(parts[:-1])}" if len(parts) >= 2 else name


def country_syn(v, rnd):
    if isinstance(v, list): return [country_syn(x, rnd) for x in v]
    if not isinstance(v, str): return v
    for canon, syns in COUNTRY_SYN.items():
        if v.strip().lower() == canon.lower():
            return rnd.choice(syns)
    return v


def addr_syn(v, rnd):
    if isinstance(v, list): return [addr_syn(x, rnd) for x in v]
    if not isinstance(v, str): return v
    for canon, syns in COUNTRY_SYN.items():
        if re.search(r"\b" + re.escape(canon) + r"\b", v):
            return re.sub(r"\b" + re.escape(canon) + r"\b", rnd.choice([s for s in syns if len(s) > 3] or syns), v)
    return v


def legal(v, rnd):
    if not isinstance(v, str): return v
    for rx, rep in LEGAL:
        if re.search(rx, v):
            return re.sub(rx, rep, v, count=1)
    return v


def acc(v, rnd):
    if not isinstance(v, str): return v
    return "".join(c.translate(ACCENT) if rnd.random() < 0.3 else c for c in v)


def cust(a):
    """The screened customer dict inside an alert (official: nested under alert.customer)."""
    return a["customer"] if isinstance(a.get("customer"), dict) else a


# ------------------------------------------------------------------- variants: fn(tables, rnd, ctx) mutates tables
def v_hit_name_order(t, rnd, ctx):
    for h in t["hits"]:
        h["name"] = swap_order(h["name"])
        h["aliases"] = [swap_order(a) for a in h.get("aliases") or []]


def v_cust_name_order(t, rnd, ctx):
    for a in t["alerts"]:
        c = cust(a)
        if c.get("entity_type") != "Company": c["name"] = swap_order(c.get("name"))


def v_case(t, rnd, ctx):
    for a in t["alerts"]:
        c = cust(a); c["name"] = (c.get("name") or "").swapcase()
    for h in t["hits"]:
        h["name"] = h["name"].upper() if rnd.random() < .5 else h["name"].lower()
    for r in t["customers"]:
        if r.get("full_name"): r["full_name"] = r["full_name"].upper()
    for k in t["kyc_checks"]:
        if k.get("verified_name"): k["verified_name"] = k["verified_name"].lower()


def v_diacritics(t, rnd, ctx):
    for h in t["hits"]:
        h["name"] = strip_acc(h["name"]) if rnd.random() < .5 else acc(h["name"], rnd)
        h["aliases"] = [strip_acc(a) for a in h.get("aliases") or []]
    for a in t["alerts"]:
        c = cust(a); c["name"] = acc(c.get("name"), rnd)
    for k in t["kyc_checks"]:
        if k.get("verified_name"): k["verified_name"] = acc(k["verified_name"], rnd)


def v_cust_dob_fmt(t, rnd, ctx):
    for a in t["alerts"]:
        c = cust(a); c["dob"] = redate(c.get("dob"), rnd)
    for r in t["customers"]: r["dob"] = redate(r.get("dob"), rnd)
    for k in t["kyc_checks"]: k["verified_dob"] = redate(k.get("verified_dob"), rnd)


def v_hit_dob_fmt(t, rnd, ctx):
    for h in t["hits"]:
        h["dobs"] = redate(h.get("dobs") or [], rnd)
        if h.get("deceased_date"): h["deceased_date"] = redate(h["deceased_date"], rnd)


def v_screened_fmt(t, rnd, ctx):
    for a in t["alerts"]:
        dt = ymd(a.get("screened_at"))
        if dt: a["screened_at"] = rnd.choice([f"{a['screened_at']}T09:30:00Z", f"{dt[2]} {MON[dt[1]-1]} {dt[0]}", f"{a['screened_at']} 14:02:11"])


def v_partial_dob(t, rnd, ctx):
    """Less precise screened DOB (year or year-month only): less evidence, never a new clear."""
    for a in t["alerts"]:
        c = cust(a); dt = ymd(c.get("dob"))
        if dt and dt[1]: c["dob"] = str(dt[0]) if rnd.random() < .5 else f"{dt[0]}-{dt[1]:02d}"


def v_hit_partial_dob(t, rnd, ctx):
    for h in t["hits"]:
        out = []
        for d in h.get("dobs") or []:
            dt = ymd(d)
            out.append(f"{dt[0]}-{dt[1]:02d}" if dt and dt[2] and rnd.random() < .5 else (str(dt[0]) if dt else d))
        h["dobs"] = out


def v_country_syn(t, rnd, ctx):
    for a in t["alerts"]:
        c = cust(a); c["country"] = country_syn(c.get("country"), rnd)
    for r in t["customers"]:
        r["nationality"] = country_syn(r.get("nationality"), rnd); r["residence_country"] = country_syn(r.get("residence_country"), rnd)
    for k in t["kyc_checks"]: k["document_country"] = country_syn(k.get("document_country"), rnd)
    for h in t["hits"]:
        for f in ("countries", "nationality", "citizenship"): h[f] = country_syn(h.get(f) or [], rnd)
        h["addresses"] = addr_syn(h.get("addresses") or [], rnd)
        h["place_of_birth"] = addr_syn(h.get("place_of_birth"), rnd)


def v_drop_optional(t, rnd, ctx):
    for h in t["hits"]:
        for f in ("gender", "place_of_birth", "sources", "source_urls", "details", "relationships", "identifiers", "subcategories",
                  "best_matching_name", "first_name", "middle_name", "last_name", "match_score", "position_or_allegation", "life_status"):
            h.pop(f, None)
    for r in t["customers"]:
        for f in ("occupation", "employer", "address", "status", "last_kyc_refresh", "onboarded_at", "registration_number"): r.pop(f, None)
    for a in t["alerts"]:
        c = cust(a)
        for f in ("city",): c.pop(f, None)


def v_null_optional(t, rnd, ctx):
    for h in t["hits"]:
        for f in ("gender", "place_of_birth", "details", "best_matching_name", "primary_category", "life_status", "position_or_allegation"): h[f] = None
        for f in ("aliases", "identifiers", "relationships", "sources", "subcategories"):
            if not h.get(f): h[f] = None
    for r in t["customers"]:
        for f in ("preferred_name", "login_name", "city", "address", "occupation"):
            if not r.get(f): r[f] = None


def v_extra_fields(t, rnd, ctx):
    for name, rows in t.items():
        for r in rows:
            r["x_unknown_" + name] = {"id": "CUS-000000", "note": "ignore me", "dob": "1900-01-01", "country": "Atlantis"}
            r["risk_rating"] = rnd.choice(["low", "high", None])
    for a in t["alerts"]:
        c = cust(a); c["middle_name"] = None; c["gender"] = None; c["x_source_system"] = "core-banking"


def v_empty_notes(t, rnd, ctx):
    for h in t["hits"]:
        if h.get("profile_notes") is not None: h["profile_notes"] = ""
    for n in t["notes"]: n["text"] = ""


def v_drop_search(t, rnd, ctx):
    t["search_results"].clear()


def v_legal_form(t, rnd, ctx):
    for a in t["alerts"]:
        c = cust(a)
        if c.get("entity_type") == "Company": c["name"] = legal(c.get("name"), rnd)
    for h in t["hits"]:
        if h.get("entity_type") == "Company": h["name"] = legal(h["name"], rnd)
    for r in t["customers"]:
        if r.get("entity_type") == "Company": r["full_name"] = legal(r.get("full_name"), rnd)


def v_deceased_phrase(t, rnd, ctx):
    for h in t["hits"]:
        ls = h.get("life_status")
        if ls == "Deceased": h["life_status"] = rnd.choice(["deceased", "DECEASED", "Dead", "Deceased (confirmed)"])
        elif ls == "Alive": h["life_status"] = rnd.choice(["alive", "Living", "ALIVE", "Not deceased"])
        if h.get("deceased_date"): h["deceased_date"] = redate(h["deceased_date"], rnd)


def v_type_spelling(t, rnd, ctx):
    syn = {"Individual": ["individual", "INDIVIDUAL", "Person", "person", "Natural Person"],
           "Company": ["company", "COMPANY", "Organisation", "Organization", "Entity", "Business", "Legal Entity"]}
    for a in t["alerts"]:
        c = cust(a)
        if c.get("entity_type") in syn: c["entity_type"] = rnd.choice(syn[c["entity_type"]])
    for rows in (t["hits"], t["customers"]):
        for r in rows:
            if r.get("entity_type") in syn: r["entity_type"] = rnd.choice(syn[r["entity_type"]])


def v_multi_candidate(t, rnd, ctx):
    """Clone each resolved customer as a second, unlinked person with the same name/DOB/country but no KYC or notes."""
    by_id = {r["record_id"]: r for r in t["customers"]}
    for i, rid in enumerate(sorted(ctx["resolved"])):
        r = by_id.get(rid)
        if not r: continue
        c = dict(r, record_id=f"CUS-Z{i:05d}", phone=f"+44 7000{i:06d}", email=f"clone{i}@clone.example", login_name=None)
        t["customers"].append(c)


def v_alias_bracket(t, rnd, ctx):
    for h in t["hits"]:
        if h.get("entity_type") == "Individual" and rnd.random() < .5:
            h["name"] = f"{h['name']} (a.k.a. {rnd.choice(['the Engineer', 'Junior', 'Doc'])})"


def v_lists_as_strings(t, rnd, ctx):
    for h in t["hits"]:
        for f in ("dobs", "countries", "nationality", "citizenship", "aliases", "categories"):
            v = h.get(f)
            if isinstance(v, list) and len(v) == 1: h[f] = v[0]


def v_whitespace(t, rnd, ctx):
    for a in t["alerts"]:
        c = cust(a)
        if c.get("name"): c["name"] = "  " + c["name"].replace(" ", "  ") + " "
    for h in t["hits"]:
        h["name"] = " " + h["name"] + "\t"


TEXT_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b(?:" + "|".join(MON) + r") \d{1,2}, \d{4}\b|\b(?:[1-3]?\d) (?:" + "|".join(MON) + r") \d{4}\b")


def text_redate(s, rnd):
    def sub(m):
        v = m.group(0)
        dt = ymd(v) or (lambda p: p and (p[2], MON.index(p[1]) + 1, int(p[0])))(re.fullmatch(r"(\d{1,2}) (\w+) (\d{4})", v) and re.fullmatch(r"(\d{1,2}) (\w+) (\d{4})", v).groups())
        if not dt: return v
        y, mo, d = dt
        return rnd.choice([f"{d} {MON[mo-1]} {y}", f"{MON[mo-1]} {d}, {y}", f"{d:02d}-{MON[mo-1][:3]}-{y}", f"{y}/{mo:02d}/{d:02d}", f"{d}. {MON[mo-1]} {y}"])
    return TEXT_DATE.sub(sub, s)


def v_notes_dates(t, rnd, ctx):
    for n in t["notes"]:
        n["text"] = text_redate(n.get("text") or "", rnd)


def v_notes_titlecase(t, rnd, ctx):
    """Customer names written in Title Case in notes instead of CAPS."""
    for n in t["notes"]:
        n["text"] = re.sub(r"\b[A-Z][A-Z'\-]{1,}(?: [A-Z][A-Z'\-]{1,})+\b",
                           lambda m: m.group(0) if m.group(0) in ("DOB", "KYC", "ID") else m.group(0).title(), n.get("text") or "")


def v_notes_channel(t, rnd, ctx):
    for n in t["notes"]:
        ch = n.get("channel")
        if ch == "kyc": n["channel"] = rnd.choice(["KYC", "Kyc", "kyc ", "identity"])


def v_notes_country_syn(t, rnd, ctx):
    for n in t["notes"]:
        n["text"] = addr_syn(n.get("text") or "", rnd)


def v_hit_notes_dates(t, rnd, ctx):
    """Reformat dates in hit profile notes except the fixed 'According to ...; <Month d, yyyy>:' dated-report form."""
    for h in t["hits"]:
        pn = h.get("profile_notes")
        if pn:
            h["profile_notes"] = re.sub(r"(?m)^(?!According to).*$", lambda m: text_redate(m.group(0), rnd), pn)


def _variant_word(w, rnd, ctx):
    g = ctx["groups"].get(strip_acc(w).lower())
    if not g: return w
    alt = rnd.choice(sorted(g))
    return alt.upper() if w.isupper() else alt.capitalize()


def v_translit(t, rnd, ctx):
    """Swap name parts for other spellings listed together in name_variants.json; join/split 'Abdul X'."""
    def tr(name):
        if not isinstance(name, str): return name
        name = re.sub(r"\b[^\W\d_]+\b", lambda m: _variant_word(m.group(0), rnd, ctx), name)
        name = re.sub(r"\b(Abdul|Abdel|ABDUL) (\w+)", lambda m: m[1] + m[2].lower() if rnd.random() < .5 else m[0], name)
        return name
    for h in t["hits"]:
        h["name"] = tr(h["name"]); h["aliases"] = [tr(a) for a in h.get("aliases") or []]


def v_hit_name_typo(t, rnd, ctx):
    """One substituted letter inside a name part of 5+ letters (within the policy's 1-edit tolerance)."""
    def typo(name):
        def sub(m):
            w = m.group(0)
            if len(w) < 5 or rnd.random() > .3: return w
            i = rnd.randrange(1, len(w) - 1)
            c = "x" if w[i].lower() != "x" else "z"
            return w[:i] + (c.upper() if w[i].isupper() else c) + w[i+1:]
        return re.sub(r"[^\W\d_]+", sub, name) if isinstance(name, str) else name
    for h in t["hits"]:
        if h.get("entity_type") == "Individual": h["name"] = typo(h["name"])


def v_malformed_alerts(t, rnd, ctx):
    """Duplicate hit IDs, a dangling hit ID, a null customer block on alerts without hits we score, a hit whose alert is gone."""
    for i, a in enumerate(t["alerts"]):
        if a.get("hit_ids"): a["hit_ids"] = a["hit_ids"] + [a["hit_ids"][0], "H-DOESNOTEXIST"]
    t["alerts"].append({"alert_id": "A-EMPTY", "screened_at": None, "customer": None, "account_ref": None, "hit_ids": []})
    t["alerts"].append({"alert_id": "A-NOCUST", "screened_at": "2026-11-01", "hit_ids": ["H-ORPHAN2"]})
    t["hits"].append({"hit_id": "H-ORPHAN", "alert_id": "A-MISSING", "entity_type": "Individual", "name": "Nobody Atall", "dobs": []})
    t["hits"].append({"hit_id": "H-ORPHAN2", "alert_id": "A-NOCUST", "entity_type": "Individual", "name": "Nobody Else", "dobs": None})


def v_kyc_result(t, rnd, ctx):
    syn = {"approved": ["Approved", "APPROVED", "approved ", "passed", "Pass", "clear", "verified", "Approved - clear"],
           "rejected": ["Rejected", "REJECTED", "declined", "failed"], "expired": ["Expired", "EXPIRED", "expired - resubmit"]}
    for k in t["kyc_checks"]:
        if k.get("result") in syn: k["result"] = rnd.choice(syn[k["result"]])
        k["checked_at"] = redate(k.get("checked_at"), rnd)


def v_all(t, rnd, ctx):
    for f in (v_cust_dob_fmt, v_hit_dob_fmt, v_country_syn, v_extra_fields, v_legal_form, v_deceased_phrase, v_case, v_drop_optional):
        f(t, rnd, ctx)


VARIANTS = {k[2:]: v for k, v in globals().items() if k.startswith("v_")}
FILES = ["alerts", "hits", "customers", "accounts", "kyc_checks", "notes", "onboarding", "search_results"]


def load(folder):
    return {n: [json.loads(l) for l in open(folder / f"{n}.jsonl", encoding="utf-8") if l.strip()] for n in FILES}


def run(folder, out):
    t0 = time.time()
    p = subprocess.run([str(ROOT / "system/run"), str(folder), str(out)], capture_output=True, text=True)
    dt = time.time() - t0
    if p.returncode:
        return None, dt, p.stderr[-1500:]
    return {r["hit_id"]: r for r in map(json.loads, open(out))}, dt, None


def make_variant(src, tables, name, tmp, ctx):
    dest = tmp / name
    dest.mkdir()
    for f in os.listdir(src):
        if not f.endswith(".jsonl") or f[:-6] not in FILES:
            shutil.copy(src / f, dest / f)
    t = json.loads(json.dumps(tables))
    VARIANTS[name](t, random.Random(f"stress-{name}"), ctx)
    for n, rows in t.items():
        with open(dest / f"{n}.jsonl", "w", encoding="utf-8") as fh:
            fh.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    return dest


def main():
    src = Path(sys.argv[1]).expanduser().resolve()
    names = sys.argv[2:] or list(VARIANTS)
    tmp = Path(tempfile.mkdtemp(prefix="clearsight-stress-", dir="/tmp"))
    base, dt, err = run(src, tmp / "base.jsonl")
    if err: print(err); return 1
    print(f"baseline: {len(base)} hits in {dt:.1f}s  {dict(collections.Counter(r['decision'] for r in base.values()))}")
    labels = {}
    if (src / "practice_labels.jsonl").exists():
        labels = {r["hit_id"]: r["decision"] for r in map(json.loads, open(src / "practice_labels.jsonl"))}
    ctx = {"resolved": {r.get("customer_record_id") for r in base.values() if r.get("customer_record_id") not in (None, "AMBIGUOUS")}}
    tables = load(src)
    ctx["groups"] = {}
    if (src / "name_variants.json").exists():
        for g in json.load(open(src / "name_variants.json")).get("groups", []):
            for w in g:
                ctx["groups"][w] = set(g) - {w} or {w}
    bad = 0

    def one(name):
        d = make_variant(src, tables, name, tmp, ctx)
        return name, run(d, tmp / f"{name}.jsonl")
    with ThreadPoolExecutor(max_workers=min(6, os.cpu_count() or 2)) as ex:
        results = list(ex.map(one, names))
    for name, (out, dt, err) in results:
        if err:
            bad += 1; print(f"\n[{name}] CRASH ({dt:.1f}s)\n{err}"); continue
        missing = set(base) - set(out)
        flips = collections.Counter()
        unsafe = []
        for hid, r in base.items():
            o = out.get(hid)
            if not o or o["decision"] == r["decision"]: continue
            flips[f"{r['decision'][:4]}->{o['decision'][:4]}"] += 1
            if o["decision"] == "DIFFERENT_ENTITY":
                unsafe.append((hid, r, o))
        lab_unsafe = sum(1 for hid, o in out.items() if labels.get(hid) in ("SAME_ENTITY", "REVIEW") and o["decision"] == "DIFFERENT_ENTITY")
        bad += bool(missing or unsafe)
        print(f"\n[{name}] {dt:.1f}s  flips={dict(flips)}  ->DIFF={len(unsafe)}  missing={len(missing)}  practice_unsafe={lab_unsafe}")
        for hid, r, o in unsafe[:8]:
            print(f"   {hid}: {r['decision']}/{r['reason_code']} -> {o['decision']}/{o['reason_code']}: {o['reason'][:260]}")
    print(f"\ndata copies in {tmp}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
