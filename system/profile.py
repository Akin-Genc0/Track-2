"""Workstream 2 - customer profile assembly.
One person's facts from all their records: names, declared and verified DOB, verified legal name, countries
(residence, nationality, approved identity documents, places notes say they lived), each fact with source IDs.
Verified beats declared: the most recent APPROVED identity check (KYC provider or onboarding note) wins."""
import re
from data import as_text
from textutil import parse_date, find_dates, fold, entity_kind, placeholder_dob, approved_result
from countries import norm_country, countries_in_text, countries_in_value

_DOC_RE = re.compile(r"passport|national id|identity card|id card|identity document|driv(?:ing|er'?s?) licen[cs]e|residence permit|registry extract|"
                     r"company registry|registration certificate|certificate of incorporation|document|\bid\b", re.I)
_VERIFY_RE = re.compile(r"verif|validat|confirm|approv|clear|vet|pass|check|screen|match|authenticat|onboard|kyc|identity", re.I)
# 'expired' only: "passport (expires 2031-05-12) ... verified" is an approved check
_NEG_RE = re.compile(r"reject|fail|declin|\bexpired\b|unsuccess|could not|couldn't|unable|not (?:be )?(?:verified|approved|confirmed|validated|accepted)|"
                     r"did not|didn't|mismatch|denied|invalid|fraudulent|forged|suspicious|refused|void|blurr|illegible|not pass|no longer valid|pending|awaiting|incomplete|"
                     r"\bconsider\b|caution|\brefer(?:red)?\b|flagged|manual review|resubmi|\bon hold\b|review required|not clear", re.I)
# an outcome word that survives once the negative phrases are removed: with a negative too, the note is ambiguous
_POS_RE = re.compile(r"\b(?:approved|passed|verified|cleared|successful(?:ly)?|accepted)\b", re.I)
# the note is about someone else on the same email (families share emails): not identity evidence for this person
_REL_RE = re.compile(r"\b(?:spouse|wife|husband|son|daughter|mother|father|partner|child|children|sibling|brother|sister|guardian|"
                     r"dependa?nt|minor|joint (?:account )?holder|on behalf of)\b", re.I)
_LIVED_RE = re.compile(r"\b(?:lived|lives|living|resid\w*|based in|employed|works? in|worked in|relocat\w*|moved to)\b", re.I)
_PARTICLES = {"da", "de", "del", "della", "di", "do", "dos", "das", "du", "van", "von", "der", "den", "ter", "bin", "ibn", "bint",
              "al", "el", "la", "le", "y", "e"}
TITLES = {"mr", "mrs", "ms", "miss", "mx", "dr", "prof", "sir", "dame", "sheikh", "shaikh", "haji", "hajji", "alhaji", "chief", "eng", "hon", "rev"}
_ISSUE_BEFORE = re.compile(r"(?i)\b(?:issued?|issuance|expir\w*|valid\w*|opened|onboard\w*|checked|dated)\W+(?:\w+\W+){0,2}$")


def strip_titles(name):
    """'MR AHMED' -> 'AHMED': a title is not a name part."""
    if not name:
        return name
    toks = name.split()
    while toks and fold(toks[0]).strip(".") in TITLES:
        toks = toks[1:]
    return " ".join(toks) or None
_BIRTH_RE = re.compile(r"born|\bdob\b|d\.o\.b|date of birth|birth ?date|birthday", re.I)
_TITLE_STOP = {"sumsub", "onfido", "veriff", "persona", "jumio", "trulioo", "experian", "equifax", "lexisnexis", "kyc", "dob", "id",
               "customer", "client", "the", "on", "in", "for", "per", "result", "verification", "identity", "passport", "national",
               "driving", "licence", "license", "document", "date", "birth", "born", "check", "checked", "verified", "approved",
               "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
               "december", "mr", "mrs", "ms", "miss", "dr", "onboarding", "team", "companies", "registry", "lookup", "extract"}
_MONTH_WORD = re.compile(r"(?i)(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?")
_ENGLISH_STOP = set("""a an and are as at be been by can completed confirmed confirms cleared did document documents done for from has have
held her his holder identity in into is issued it its id of on or our per performed presented processed provided record records
showing shows successful successfully that the their them they this to under used using utilizing utilising valid validated
validation verified verification vetted via was were which with who whose approved approval passed pass check checked checks screening
screened authenticated authentication established accepted indicating indicates indicated lists listed matches matched matching
birth born date dob licence license driving passport national card permit residence registry extract lookup individual customer
client applicant user account holder team onboarding analyst note added reviewed case queue ref reference no further action informed
email file agent result results provider basis travel""".split())
_CAPS_STOP = {"DOB", "ID", "KYC", "UK", "US", "USA", "EU", "UAE", "AML", "PEP", "SOP", "D.O.B", "N.A", "GB", "OK", "CDD", "EDD", "API", "PDF", "SA", "ISO"}


def parse_id_note(note):
    """Parse a free-text identity-verification note. Returns dict or None if it is not an identity check."""
    t = as_text(note.get("text"))
    ch = as_text(note.get("channel")).strip().lower()
    # 'kyc', 'KYC ', 'identity', 'onboarding', 'id verification': all the identity-check channel
    ch = "kyc" if re.search(r"kyc|identity|onboard|verif|\bidv?\b", ch) else ch
    if not t:
        return None
    is_id = (ch == "kyc" and (_DOC_RE.search(t) or _VERIFY_RE.search(t))) or (_DOC_RE.search(t) and _VERIFY_RE.search(t) and _BIRTH_RE.search(t))
    if not is_id:
        return None
    if _REL_RE.search(t):
        return None
    neg = _NEG_RE.search(t)
    approved = not neg
    ambiguous = bool(neg and _POS_RE.search(_NEG_RE.sub(" ", t)))
    created = parse_date(note.get("created_at"))
    dates = find_dates(t)
    # name: longest run of upper-case tokens
    best, cur, pend = [], [], []
    for m in re.finditer(r"\S+", t):
        tok = re.sub(r"['’]s$", "", m.group(0).strip(",.;:()\""))
        core = re.sub(r"[^\w/'’-]", "", tok)
        letters = [ch2 for ch2 in core if ch2.isalpha()]
        is_caps = (letters and all(c.isupper() for c in letters) and len(letters) >= 2 and core.upper() not in _CAPS_STOP) or core in ("N/A", "NA") or re.fullmatch(r"0+", core or "x")
        if is_caps:
            cur.extend(pend)
            cur.append((m.start(), m.end(), tok))
            pend = []
        elif cur and tok == m.group(0) and tok in _PARTICLES:
            pend.append((m.start(), m.end(), tok))    # 'ANA MARIA da SILVA': a lower-case particle joins two caps runs
            continue
        else:
            if len(cur) > len(best):
                best = cur
            cur, pend = [], []
        if tok != m.group(0).rstrip() and m.group(0).rstrip()[-1:] in ";:)" and cur:
            if len(cur) > len(best):
                best = cur
            cur, pend = [], []
    if len(cur) > len(best):
        best = cur
    name, name_span = None, None
    if best and any(re.search(r"[A-Za-z]{2,}", x[2]) for x in best):
        name = " ".join(x[2] for x in best)
        name_span = (best[0][0], best[-1][1])
    # fallback candidates when the name is not upper-case: runs of consecutive name-like words (no stop words,
    # countries, months or digits). The profile keeps only a run that shares a part with the person's own records.
    title_runs = []
    if not name:
        cur2 = []
        for m in re.finditer(r"[^\s,;:()]+", t):
            raw = m.group(0)
            tok = re.sub(r"['’]s$", "", raw.strip(".\""))
            ok = re.fullmatch(r"[^\W\d_][\w'’-]*", tok) and fold(tok) not in _TITLE_STOP and fold(tok) not in _ENGLISH_STOP \
                and not countries_in_text(tok) and not _MONTH_WORD.fullmatch(tok)
            if ok:
                cur2.append(tok)
            if not ok or raw[-1:] in ",;:)" or raw.endswith("."):
                if len(cur2) >= 2:
                    title_runs.append(" ".join(cur2[:5]))
                cur2 = []
        if len(cur2) >= 2:
            title_runs.append(" ".join(cur2[:5]))
    # DOB: a date that is not the check date, closest to a birth keyword
    cand = []
    births = list(_BIRTH_RE.finditer(t))
    for s, e, d in dates:
        if created and d == created:
            continue
        if created and d[1] is None and d[0] == created[0] and not births:
            continue
        # dates after a birth keyword come first; one before it pays a penalty ("issued 2019-02-03, DOB: March 1968")
        dist = min([s - k.end() for k in births if s >= k.end()] + [k.start() - e + 10 for k in births if e <= k.start()] + [10 ** 6])
        if dist > 12 and _ISSUE_BEFORE.search(t[max(0, s - 30):s]):
            continue          # an issue / expiry / opening / check date, not a birth date
        if not (d[1] and d[2]) and dist > 30:
            continue
        if births and dist > 60:
            continue          # with a birth keyword present, a full date far from it is some other date
        cand.append((dist, -s, d))
    dob = sorted(cand)[0][2] if cand else None
    # check date
    check_date = created
    if not check_date:
        others = [d for s, e, d in dates if d != dob and d[1] and d[2]]
        check_date = others[0] if others else None
    if dob and check_date and check_date[0] - dob[0] < 16:
        dob = None            # a person under 16 at the check: the parse picked some other date
    # document country (outside the name span)
    t2 = t if not name_span else t[:name_span[0]] + " " + t[name_span[1]:]
    ctry = countries_in_text(t2)
    return {"id": as_text(note.get("note_id")), "name": name, "dob": dob, "country": ctry[0] if ctry else None, "countries": ctry,
            "date": check_date, "approved": approved, "ambiguous": ambiguous, "source": "note", "title_runs": title_runs}


class Profile:
    """Facts about one customer person; every fact carries its source record IDs."""

    def __init__(self, idx, person, promote_ambiguous=False):
        self.idx = idx
        C = idx.room.customers
        self.primary = person["primary"]
        self.records = list(person["records"])
        recs = [C[r] for r in self.records]
        prim = C[self.primary]
        self.company = idx.is_company(prim.get("entity_type"))
        self.type_known = entity_kind(as_text(prim.get("entity_type"))) is not None
        self.entity_type = "Company" if self.company else "Individual"
        # names on records
        self.record_names = []          # (name, rid)
        for r in self.records:
            c = C[r]
            for f in ("full_name", "preferred_name"):
                v = as_text(c.get(f))
                if v:
                    self.record_names.append((v, r))
        # declared DOBs
        self.declared_dobs = []
        for r in self.records:
            d = parse_date(C[r].get("dob"))
            if d and not placeholder_dob(d):
                self.declared_dobs.append((d, r))
        # countries with provenance
        self.countries = {}

        def add(c, src):
            if c:
                self.countries.setdefault(c, set()).add(src)
        self.unplaced = []      # residence / nationality values we cannot place: never evidence of a different country
        for r in self.records:
            for f in ("residence_country", "nationality"):
                # 'Russia, Cyprus', 'Russian/Cypriot', 'ru', 'Korea, Republic of': every country the value names
                cs, ok = countries_in_value(C[r].get(f))
                for c in cs:
                    add(c, r)
                if not ok:
                    self.unplaced.append(as_text(C[r].get(f)))
        # identity checks
        checks = []
        for r in self.records:
            for k in idx.kyc_checks_for(r):
                checks.append({"id": as_text(k.get("check_id")), "name": strip_titles(as_text(k.get("verified_name"))) or None,
                               "dob": None if placeholder_dob(parse_date(k.get("verified_dob"))) else parse_date(k.get("verified_dob")), "country": norm_country(k.get("document_country"), codes_any_case=True),
                               "date": parse_date(k.get("checked_at")),
                               "approved": approved_result(as_text(k.get("result"))), "source": "kyc"})
        self.residence_notes = []
        seen_notes = set()
        for r in self.records:
            for n in idx.notes_by_email.get(as_text(C[r].get("email")).lower(), []):
                nid = as_text(n.get("note_id"))
                if nid in seen_notes:
                    continue
                seen_notes.add(nid)
                p = parse_id_note(n)
                if p is not None:
                    p["name"] = strip_titles(p["name"])
                    checks.append(p)
                    continue
                found = countries_in_text(as_text(n.get("text")))
                for c in found:
                    add(c, nid)
                    self.residence_notes.append((c, nid))
                if not found and _LIVED_RE.search(as_text(n.get("text"))) and "address on file" not in as_text(n.get("text")).lower():
                    self.unplaced.append(nid)     # says where they lived or worked, but names no country we know
        # a note with both an approval and a negative word is ambiguous: it never supplies clearing facts, but
        # screen.py re-decides with it counted as approved, and if that stops the clear the hit goes to REVIEW
        self.ambiguous = [c for c in checks if c.get("ambiguous")]
        approved = [c for c in checks if c["approved"] or (promote_ambiguous and c.get("ambiguous"))]
        for c in approved:
            for x in c.get("countries") or [c["country"]]:    # every country an approved note names (places they lived count)
                add(x, c["id"])
        key = lambda c: ((c["date"] or (0, 0, 0))[0], (c["date"] or (0, 0, 0))[1] or 0, (c["date"] or (0, 0, 0))[2] or 0, c["id"])
        approved.sort(key=key, reverse=True)
        self.checks = approved
        self.latest_check = approved[0] if approved else None
        # Guard against free-text parsing errors: a name read from a note must share at least one name part
        # with the person's own records, otherwise we treat the note's name as unreadable (never as a mismatch).
        rec_parts = [idx.m.parts(n, self.company) for n, _ in self.record_names]

        def plausible(c):
            if c["source"] != "note":
                return True
            vp = idx.m.parts(c["name"], self.company)
            return any(idx.m.part_match(a, b) for a in vp for rp in rec_parts for b in rp)
        for c in approved:
            if not c["name"] and c.get("title_runs"):
                for run in c["title_runs"]:
                    cand = dict(c, name=run)
                    if plausible(cand) and len(idx.m.parts(run, self.company)) >= 2:
                        c["name"] = run
                        # read without capitalisation cues (lower-case run): never used to clear on name
                        c["weak_name"] = not all(w[:1].isupper() for w in run.split())
                        break
        self.verified_name = next(((c["name"], c["id"]) for c in approved if c["name"] and plausible(c)), None)
        self.verified_name_weak = bool(next((c.get("weak_name") for c in approved if c["name"] and plausible(c)), False))
        self.verified_dob = next(((c["dob"], c["id"]) for c in approved if c["dob"]), None)

    def best_country_sources(self, c):
        """Minimal citation for a country: the latest approved identity check, else system-of-record records, else notes."""
        srcs = self.countries.get(c, set())
        lc = self.latest_check
        if lc and lc["id"] in srcs:
            return [lc["id"]]
        recs = sorted(s for s in srcs if s in self.records)
        if recs:
            return recs
        chk = sorted(s for s in srcs if any(s == k["id"] for k in self.checks))
        if chk:
            return chk[:1]
        return sorted(srcs)[:1]

    # DOBs used for comparison: verified if present, else the declared ones
    def dobs(self):
        if self.verified_dob:
            return [self.verified_dob]
        out, seen = [], set()
        for d, r in self.declared_dobs:
            if d not in seen:
                seen.add(d)
                out.append((d, r))
        return out

    def names_for_comparison(self):
        """Verified legal name outranks record names."""
        if self.verified_name:
            return [self.verified_name]
        return self.record_names
