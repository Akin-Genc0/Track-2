"""Workstream 3 - hit (watchlist profile) fact extraction.
Names/aliases, entity type, countries tied to the hit, possible birth dates (dobs field, first paragraph of
profile notes, else qualifying web search results), earliest dated report, date of death."""
import re
from data import as_text, as_list, as_dict_list
from textutil import parse_date, find_dates, fold, name_parts
from countries import norm_country, countries_in_text

LISTING_PHRASES = [
    ("sanction", "a sanctioned individual"),
    ("pep", "a politically exposed person"),
    ("politically", "a politically exposed person"),
    ("enforcement", "the subject of enforcement action"),
    ("adverse", "named in adverse media"),
    ("soe", "a state-owned enterprise official"),
    ("state owned", "a state-owned enterprise official"),
    ("state-owned", "a state-owned enterprise official"),
]
OTHER_PHRASE = "named on a watchlist"

_AGE_PATTERNS = [
    r"\baged? (\d{1,3})\b", r"\b(\d{1,3})[- ]years?[- ]old\b", r"\bage of (\d{1,3})\b", r"\b(\d{1,3}) years of age\b",
    r"\b(\d{1,3}) years old\b", r"\bage:? ?(\d{1,3})\b", r"\(aged? (\d{1,3})\)", r"\((\d{1,3})\)", r", (\d{1,3}),",
    r"\b(?:was|is|turned|reached|then) (\d{1,3})\b(?! ?(?:%|percent|years? (?:prison|sentence|jail)|months|days))",
]
_AGE_RE = [re.compile(p, re.I) for p in _AGE_PATTERNS]
_BORN_RE = re.compile(r"\bborn\b(?: (?:on|in))?", re.I)
_REPORT_RE = re.compile(r"^\s*According to [^;\n]+;\s*([^:\n]{4,40}?)\s*:", re.M)


def listing_phrase(primary, categories):
    cat = as_text(primary) or (categories[0] if categories else "")
    k = fold(cat)
    for key, ph in LISTING_PHRASES:
        if k.startswith(key) or (key in ("pep",) and k == "pep"):
            return ph
    return OTHER_PHRASE


def ages_in(text):
    """[(start, age)] for age statements in text."""
    out = []
    for rx in _AGE_RE:
        for m in rx.finditer(text):
            a = int(m.group(1))
            if 1 <= a <= 120:
                out.append((m.start(), a))
    out.sort()
    # dedupe by position
    res, last = [], -100
    for s, a in out:
        if s - last > 3:
            res.append((s, a))
            last = s
    return res


def years_from_age(text):
    """Birth-year candidates from an 'age at date' statement: someone aged 45 in March 2019 -> 1973 or 1974."""
    found = []
    ages = ages_in(text)
    if not ages:
        return found
    dates = [(s, d) for s, e, d in find_dates(text) if not (d[1] is None and d[2] is None and re.search(r"\b%d\b" % d[0], text) and False)]
    for pos, age in ages:
        if not dates:
            continue
        # nearest date in the same sentence/text
        s, d = min(dates, key=lambda x: (abs(x[0] - pos), x[0]))
        y = d[0] - age
        found.append(("age", {y - 1, y}, None, None, age, d))
    return found


class HitFacts:
    def __init__(self, hit, matcher, search_index):
        self.hit = hit
        self.id = as_text(hit.get("hit_id"))
        et = as_text(hit.get("entity_type")).lower()
        self.company = et.startswith("compan") or et in ("organisation", "organization", "entity", "vessel", "business")
        self.entity_type = "Company" if self.company else "Individual"
        self.name = as_text(hit.get("name"))
        self.aliases = as_list(hit.get("aliases"))
        self.names = [self.name] + self.aliases if self.name else list(self.aliases)
        self.categories = as_list(hit.get("categories"))
        self.phrase = listing_phrase(hit.get("primary_category"), self.categories)
        # countries tied to the hit
        self.countries = []
        for f in ("countries", "nationality", "citizenship", "addresses", "place_of_birth"):
            for item in as_dict_list(hit.get(f)):
                if isinstance(item, dict):
                    v = item.get("country") or item.get("country_name") or as_text(item)
                else:
                    v = item
                v = re.sub(r"\[.*?\]", "", as_text(v)).strip()
                if not v:
                    continue
                c = norm_country(v.split(",")[-1]) or norm_country(v)
                if not c:
                    cs = countries_in_text(v)
                    c = cs[-1] if cs else None
                if c and c not in self.countries:
                    self.countries.append(c)
        # birth dates the hit gives: list of dicts {years:set, m, d, src, text}
        self.dob_source = None
        self.dobs = []
        if not self.company or True:
            for v in as_list(hit.get("dobs")):
                for part in re.split(r"\s*(?:;|\bor\b|/(?=\d{4}\b))\s*", v):
                    rng = re.fullmatch(r"\s*(\d{4})\s*[-–]\s*(\d{4})\s*", part)
                    if rng:
                        a, b = int(rng.group(1)), int(rng.group(2))
                        if 0 <= b - a <= 15:
                            self.dobs.append({"years": set(range(a, b + 1)), "m": None, "d": None, "src": None, "kind": "field", "text": part})
                        continue
                    d = parse_date(part)
                    if d:
                        self.dobs.append({"years": {d[0]}, "m": d[1], "d": d[2], "src": None, "kind": "field", "text": part})
            if self.dobs:
                self.dob_source = "listed date of birth"
        notes = as_text(hit.get("profile_notes"))
        if not self.company:
            first = re.split(r"\n\s*\n", notes.strip())[0] if notes.strip() else ""
            pdobs = []
            for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z])|\n", first):
                for m in _BORN_RE.finditer(sent):
                    tail = sent[m.end():m.end() + 40]
                    ds = find_dates(tail)
                    if ds and ds[0][0] <= 3:
                        d = ds[0][2]
                        pdobs.append({"years": {d[0]}, "m": d[1], "d": d[2], "src": None, "kind": "notes", "text": tail[:ds[0][1]]})
                if not _BORN_RE.search(sent):
                    for kind, ys, mm, dd, age, ref in years_from_age(sent):
                        pdobs.append({"years": ys, "m": None, "d": None, "src": None, "kind": "notes",
                                      "text": f"aged {age} at {ref}"})
            if pdobs:
                self.dobs.extend(pdobs)
                if not self.dob_source:
                    self.dob_source = "profile notes"
            # web search results, only when neither field nor notes give a DOB
            self.search_hits = []
            if not self.dobs:
                for sr in search_index.get(query_key(self.name), []):
                    snip = as_text(sr.get("snippet")) + " " + as_text(sr.get("title"))
                    if self.phrase not in fold(snip):
                        continue
                    if not (set(countries_in_text(snip)) & set(self.countries)):
                        continue
                    ys = years_from_age(as_text(sr.get("snippet")))
                    born = None
                    for m in _BORN_RE.finditer(snip):
                        ds = find_dates(snip[m.end():m.end() + 30])
                        if ds:
                            born = ds[0][2]
                    rid = as_text(sr.get("result_id"))
                    if born:
                        self.dobs.append({"years": {born[0]}, "m": born[1], "d": born[2], "src": rid, "kind": "search", "text": snip})
                        self.search_hits.append(rid)
                    elif ys:
                        self.dobs.append({"years": ys[0][1], "m": None, "d": None, "src": rid, "kind": "search", "text": snip})
                        self.search_hits.append(rid)
                if self.dobs:
                    self.dob_source = "search results"
        # dated reports: "According to ...; <date>: ..."
        self.reports = []
        for m in _REPORT_RE.finditer(notes):
            d = parse_date(m.group(1))
            if d and re.match(r"^\s*[A-Za-z0-9]", m.group(1)):
                self.reports.append(d)
        self.earliest_report = min(self.reports, key=lambda d: (d[0], d[1] or 1, d[2] or 1)) if self.reports else None
        self.deceased = parse_date(hit.get("deceased_date"))

    def dob_text(self):
        parts = []
        for d in self.dobs:
            ys = sorted(d["years"])
            if d["m"] and len(ys) == 1:
                parts.append(f"{ys[0]}-{d['m']:02d}" + (f"-{d['d']:02d}" if d["d"] else ""))
            else:
                parts.append(" or ".join(str(y) for y in ys))
        out = []
        for p in parts:
            if p not in out:
                out.append(p)
        return ", ".join(out)


def query_key(name):
    return " ".join(sorted(name_parts_raw(name)))


def name_parts_raw(name):
    s = fold(name)
    s = re.sub(r"[`'’‘ʼ]", "", s)
    s = re.sub(r"[^\w]+|_", " ", s)
    return [p for p in s.split() if p]


def build_search_index(rows):
    idx = {}
    for r in rows:
        q = " ".join(sorted(fold(as_text(r.get("query"))).split()))
        idx.setdefault(q, []).append(r)
    for k in idx:
        idx[k].sort(key=lambda r: as_text(r.get("result_id")))
    return idx
