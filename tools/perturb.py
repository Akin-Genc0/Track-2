"""Perturbation test: reword free text / reformat dates in a copy of the data room, re-run, measure decision flips.
Usage: python3 tools/perturb.py dev  [variant ...]"""
import json, os, random, re, shutil, subprocess, sys, collections

SRC = sys.argv[1]
VARIANTS = sys.argv[2:] or ["kyc_case", "kyc_order", "kyc_dates", "kyc_synonyms", "kyc_noise", "hit_ages", "hit_dates",
                            "hit_dobfield", "sr_ages", "sr_dates", "cust_dates", "all", "kyc_lower", "hit_codes", "resid_reword", "hit_reword", "sr_reword", "all2"]
MON = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
ORD = lambda d: f"{d}{'th' if 11 <= d % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th')}"


def reformat_full(y, m, d, rnd):
    f = rnd.choice(["ord", "mdy", "dmy_short", "abbr", "dots", "dash_abbr", "us_ord"])
    if f == "ord": return f"{ORD(d)} {MON[m-1]} {y}"
    if f == "mdy": return f"{MON[m-1]} {d}, {y}"
    if f == "dmy_short": return f"{d:02d}/{m:02d}/{str(y)[2:]}"
    if f == "abbr": return f"{d} {MON[m-1][:3]}. {y}"
    if f == "dots": return f"{d:02d}.{m:02d}.{y}"
    if f == "dash_abbr": return f"{d:02d}-{MON[m-1][:3]}-{y}"
    return f"{MON[m-1]} {ORD(d)}, {y}"


DATE_RX = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{1,2}) (" + "|".join(MON) + r") (\d{4})\b|\b(" + "|".join(MON) + r") (\d{1,2}), (\d{4})\b|\b(\d{2})/(\d{2})/(\d{4})\b")


def redate(text, rnd, skip=None):
    def sub(m):
        if skip and m.group(0) == skip:
            return m.group(0)
        g = m.groups()
        if g[0]: y, mo, d = int(g[0]), int(g[1]), int(g[2])
        elif g[3]: y, mo, d = int(g[5]), MON.index(g[4]) + 1, int(g[3])
        elif g[6]: y, mo, d = int(g[8]), MON.index(g[6]) + 1, int(g[7])
        else: y, mo, d = int(g[11]), int(g[10]), int(g[9])
        if not (1 <= mo <= 12 and 1 <= d <= 31):
            return m.group(0)
        return reformat_full(y, mo, d, rnd)
    return DATE_RX.sub(sub, text)


SYN = [("verified", "authenticated"), ("validated", "checked and accepted"), ("confirmed", "established"), ("successfully", ""),
       ("passport", "travel passport"), ("born", "born"), ("DOB", "date of birth"), ("using", "on the basis of")]


def caps_runs(text):
    return list(re.finditer(r"\b[A-ZÀ-Þ][A-ZÀ-Þ'’\-]+(?: [A-ZÀ-Þ][A-ZÀ-Þ'’\-/0]+)+\b", text))


AGE_FORMS = ["aged {a}", "{a} years old", "at {a} years of age", "a {a}-year-old", "({a})", "then {a}", "age {a}"]


def perturb(dst, variant, seed=0):
    rnd = random.Random(seed)
    R2 = {"kyc_lower", "hit_codes", "resid_reword", "hit_reword", "sr_reword"}
    want = lambda v: variant == v or (variant == "all" and v not in R2) or (variant == "all2")
    def rw(name, fn):
        p = os.path.join(dst, name)
        rows = [json.loads(l) for l in open(p)]
        rows = [fn(r) for r in rows]
        with open(p, "w") as f:
            for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def notes(n):
        t = n["text"]
        if n["channel"] == "kyc":
            if want("kyc_case"):
                t = re.sub(r"\b([A-ZÀ-Þ][A-ZÀ-Þ'’\-]+)\b", lambda m: m.group(1) if m.group(1) in ("ID", "DOB") else m.group(1).title(), t)
            if want("kyc_order"):
                for m in reversed(caps_runs(t)):
                    parts = m.group(0).split()
                    t = t[:m.start()] + parts[-1] + ", " + " ".join(parts[:-1]) + t[m.end():]
            if want("kyc_dates"):
                t = redate(t, rnd, skip=n.get("created_at"))
            if want("kyc_synonyms"):
                for a, b in SYN:
                    if rnd.random() < 0.5: t = t.replace(a, b)
                t = re.sub(r"\s+", " ", t)
            if want("kyc_noise"):
                t = rnd.choice(["Ref 4471. ", "Note added by onboarding analyst. ", "Case reviewed in queue B. "]) + t + rnd.choice(["", " No further action.", " Customer informed by email on file."])
            if want("kyc_lower"):
                t = re.sub(r"\b([A-ZÀ-Þ][A-ZÀ-Þ'’\-]+)\b", lambda m: m.group(1) if m.group(1) in ("ID", "DOB") else m.group(1).lower(), t)
        else:
            if want("resid_reword"):
                mm = re.search(r"(\d{4})\D+(\d{4})", t)
                from_c = None
                for c in ["United States", "United Kingdom", "South Africa", "Cote D'Ivoire", "Bangladesh", "Nigeria", "Germany", "France", "Spain", "Italy", "Kenya", "India", "Brazil", "Portugal", "Poland", "Sweden", "Ireland", "Canada", "Finland", "Ghana", "Norway", "Romania", "Serbia", "Australia", "Netherlands", "Denmark", "Pakistan"]:
                    if c in t: from_c = c; break
                if from_c and mm:
                    t = rnd.choice([f"Previously based in {from_c} ({mm.group(1)}-{mm.group(2)}) per customer call.",
                                    f"Customer mentioned an earlier stay in {from_c}, roughly {mm.group(1)} to {mm.group(2)}, for work.",
                                    f"Former address on file: {from_c}, {mm.group(1)}\u2013{mm.group(2)}."])
            if want("kyc_noise") and rnd.random() < 0.3:
                t = t + " Agent: Sam."
        n["text"] = t
        return n

    def hits(h):
        pn = h.get("profile_notes") or ""
        if pn:
            parts = re.split(r"(\n\s*\n)", pn, maxsplit=1)
            first = parts[0]
            if want("hit_ages"):
                first = re.sub(r"\baged (\d{1,3})\b|\b(\d{1,3})-year-old\b|\bage of (\d{1,3})\b|\b(\d{1,3}) years of age\b",
                               lambda m: rnd.choice(AGE_FORMS).format(a=next(x for x in m.groups() if x)), first)
            if want("hit_dates"):
                first = redate(first, rnd)
            h["profile_notes"] = first + "".join(parts[1:])
        if want("hit_codes"):
            CODES = {"United States": "US", "United Kingdom": "GB", "Nigeria": "NG", "Germany": "DE", "France": "FR", "Spain": "ES", "Italy": "IT", "Bangladesh": "BD", "Pakistan": "PK", "India": "IN"}
            for f in ("countries", "citizenship"):
                h[f] = [CODES.get(x, x) for x in (h.get(f) or [])]
            h["nationality"] = [{"United States": "American", "Nigeria": "Nigerian", "Germany": "German", "France": "French"}.get(x, x) for x in (h.get("nationality") or [])]
        if want("hit_reword") and pn:
            first = h["profile_notes"].split("\n\n")[0]
            mm = re.search(r"([A-Z][\w'’\-]+(?: [A-Z][\w'’\-]+)+),? (?:was |aged |, )?(\d{1,3})\b", first)
            for rx, rep in [(r"was born in (\d{4})", r"was born during \1"), (r"was born on ", "has a recorded birth date of "),
                            (r"\bwhen\b", "at the time"), (r"\binvestigators\b", "the authorities"), (r"\bquestioned\b", "interviewed")]:
                first = re.sub(rx, rep, first)
            h["profile_notes"] = first + h["profile_notes"][len(h["profile_notes"].split("\n\n")[0]):]
        if want("hit_dobfield"):
            out = []
            for d in h.get("dobs") or []:
                m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", d)
                out.append(rnd.choice([f"{int(m.group(3))} {MON[int(m.group(2))-1][:3]} {m.group(1)}", f"{MON[int(m.group(2))-1]} {int(m.group(3))}, {m.group(1)}"]) if m else d)
            h["dobs"] = out
        return h

    def sr(s):
        t = s.get("snippet") or ""
        if want("sr_ages"):
            t = re.sub(r", (\d{1,3}),", lambda m: rnd.choice([" (aged {a}),", ", then {a},", ", a {a}-year-old,", ", age {a},"]).format(a=m.group(1)), t)
        if want("sr_dates"):
            t = re.sub(r"\b(" + "|".join(MON) + r") (\d{4})\b", lambda m: rnd.choice([f"{m.group(1)[:3]}. {m.group(2)}", f"{m.group(1)}, {m.group(2)}", f"{m.group(1)} of {m.group(2)}"]), t)
        if want("sr_reword"):
            parts = re.split(r"(?<=[.]) ", t)
            t = " ".join(reversed(parts)) if len(parts) > 1 else t
            t = t.replace("was named in a public report", "featured in reporting").replace("appeared on a published list", "was listed")
        s["snippet"] = t
        return s

    def cust(c):
        if want("cust_dates") and c.get("dob"):
            c["dob"] = redate(c["dob"], rnd)
        return c

    rw("notes.jsonl", notes)
    rw("hits.jsonl", hits)
    rw("search_results.jsonl", sr)
    if want("cust_dates"):
        rw("customers.jsonl", cust)
        rw("kyc_checks.jsonl", lambda k: dict(k, verified_dob=redate(k["verified_dob"] or "", rnd) or k["verified_dob"]))


def load(p):
    return {json.loads(l)["hit_id"]: json.loads(l) for l in open(p)}


here = os.path.dirname(os.path.abspath(__file__))
run = os.path.join(here, "..", "system", "run")
base_out = "/tmp/perturb_base.jsonl"
subprocess.run([run, SRC, base_out], check=True, stderr=subprocess.DEVNULL)
base = load(base_out)
total = collections.Counter()
for v in VARIANTS:
    dst = f"/tmp/perturb_{v}"
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(SRC, dst)
    perturb(dst, v)
    out = f"/tmp/perturb_{v}.jsonl"
    subprocess.run([run, dst, out], check=True, stderr=subprocess.DEVNULL)
    new = load(out)
    flips = collections.Counter((base[h]["decision"][:4], new[h]["decision"][:4]) for h in base if base[h]["decision"] != new[h]["decision"])
    to_diff = [h for h in base if base[h]["decision"] != "DIFFERENT_ENTITY" and new[h]["decision"] == "DIFFERENT_ENTITY"]
    n = sum(flips.values())
    print(f"{v:14s} flips={n:3d} ({n / len(base):.1%})  toward_DIFFERENT={len(to_diff)}  {dict(flips)}  e.g. {to_diff[:4]}")
