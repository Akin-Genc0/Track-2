"""Workstream 3 - hit (watchlist profile) fact extraction.
Names/aliases, entity type, countries tied to the hit, possible birth dates (dobs field, first paragraph of
profile notes, else qualifying web search results), earliest dated report, date of death."""
import re
from data import as_text, as_list, as_dict_list
from textutil import parse_date, find_dates, fold, name_parts, entity_kind
from countries import norm_country, countries_in_text, _key, SUBNATIONAL, SUBNATIONAL_AMBIG, NOT_COUNTRIES

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

# Strong cues: an explicit age word. Used everywhere (profile notes are real-world prose).
_STRONG = [
    r"(?i)\baged? (\d{1,3})\b", r"(?i)\b(\d{1,3})[- ]years?[- ]old\b", r"(?i)\bage of (\d{1,3})\b", r"(?i)\b(\d{1,3}) years of age\b",
    r"(?i)\b(\d{1,3}) years old\b", r"(?i)\bage:? ?(\d{1,3})\b", r"(?i)\(aged? (\d{1,3})\)", r"(?i)\b(\d{1,3}) yrs? old\b",
    r"(?i)\b(\d{1,3})-year-old\b",
    # a bare verb + number is an age only when the clause ends there or an age word follows ("was 45.", "was 45 when",
    # "turned 45 in 2019"); "were 40 apartments" / "turned 3 companies" / "at 3 banks" are counts, not ages
    r"(?i)\b(?:was|is|turned|reached|then|now|aged)\s+(\d{1,3})(?=\s*(?:[.,;:)!?]|$|\(|-|yrs?\b|years?\b|when\b|at the time\b|in (?:\w+ )?\d{4}\b|on \d|during\b))(?!\s*years? (?:in|prison|sentence|jail|imprisonment))",
    r"(?i)\bat (?:the age of |age )?(\d{1,3})(?=\s*(?:years? old|yrs? old)\b|,|\s*[.;!?)]|\s*$|\s+(?:he|she|they)\b)",
    # "John Smith, 45, was arrested" / "John Smith (45)" / "a man of 45" / "Age at the time of listing: 45"
    r"(?<=[A-Za-z]), (\d{2}), (?=(?:was|is|who|had|has|said|appeared|pleaded|faces|faced|a|an|the|of|from)\b)",
    r"\b[A-Z][a-z'’-]+ \((?:age |aged )?(\d{2})\)",
    r"(?i)\ba (?:man|woman|person|boy|girl) of (\d{2})\b",
    r"(?i)\bage at the time\b[^:\n]{0,40}:\s*(\d{2})\b",
]
# Weak cues: a bare number next to a name ("Mark Mueller, 48, a sanctioned ..."). Only used for short search-result
# snippets, and never when the number is part of a date.
_WEAK = [
    r"\((\d{1,3})\)", r", (\d{1,3}),",
    r", (\d{1,3})\.\s", r"\b[Aa] (\d{1,3}) (?:a|an|the)\b", r"(?<![\d,] )\b(\d{1,3}), (?=[A-Z][a-z])", r", (\d{1,3})\.?\s*$",
    r"\b(\d{1,3}) and (?:named|was|is|a|the|working|served)", r"\b[Aa] (\d{1,3}),", r"\b(\d{1,3}), (?:a|an|the)\b",
    r"\b[Aa] (\d{1,3}) (?!(?:percent|per|years?|months?|days?|weeks?|hours?|million|billion|thousand|times|counts?|charges?|people|men|women|units?)\b)(?=[a-z])",
]
_STRONG_RE = [re.compile(p) for p in _STRONG]
_WEAK_RE = [re.compile(p) for p in _WEAK]
_MONTH_BEFORE = re.compile(r"(?i)\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s*$")
_BORN_RE = re.compile(r"\b(?:born|birth ?date|date of birth|d\.?o\.?b\.?|birthday)\b(?:\s+(?:is|was|of|on|in|during|around|circa|c\.|:|as|recorded as|listed as|given as))*:?", re.I)
_REPORT_RE = re.compile(r"^\s*According to [^;\n]+;\s*([^:\n]{4,40}?)\s*:", re.M)


def years_span(text):
    """Every birth year one dobs item or 'born ...' clause names ('circa 1960-1965', '1960 to 1965', '1960, 1965',
    '1960/61', '1974 or 1976'). Two or more distinct years -> the whole span min..max (no month/day), else None."""
    ys = {d[0] for _, _, d in find_dates(text)}
    for a, b in re.findall(r"\b(1[89]\d\d|20\d\d)/(\d{2})\b(?![/.-]\d)", text):
        ys |= {int(a), int(a[:2] + b)}
    if len(ys) < 2 or max(ys) - min(ys) > 15:
        return None
    return set(range(min(ys), max(ys) + 1))


def listing_phrase(primary, categories):
    cat = as_text(primary) or (categories[0] if categories else "")
    k = fold(cat)
    for key, ph in LISTING_PHRASES:
        if k.startswith(key) or (key in ("pep",) and k == "pep"):
            return ph
    return OTHER_PHRASE


def ages_in(text, weak=False):
    """[(start, age)] for age statements in text. Numbers that belong to a date are never ages."""
    spans = [(a, b) for a, b, _ in find_dates(text)]
    out = []
    for rx in _STRONG_RE + (_WEAK_RE if weak else []):
        for m in rx.finditer(text):
            s0, e0 = m.span(1)
            if any(s0 < b and e0 > a for a, b in spans):
                continue
            if _MONTH_BEFORE.search(text[max(0, s0 - 12):s0]) or re.search(r"(?:[/:]|\d[-.])$", text[max(0, s0 - 2):s0]):
                continue
            if re.match(r",? ?\d{4}\b|[/:]|[-.]\d", text[e0:e0 + 6]):
                continue
            a = int(m.group(1))
            if 16 <= a <= 100:     # no adult watchlist profile states an age outside this; dropping only removes a clearing fact
                out.append((m.start(), a))
    out.sort()
    res, last = [], -100
    for s1, a in out:
        if s1 - last > 3:
            res.append((s1, a))
            last = s1
    return res


_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                                      "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
_NUMWORD_RE = re.compile(r"(?i)\b(" + "|".join(_TENS) + r")(?:[- ](" + "|".join(list(_UNITS)[1:10]) + r"))?\b|\b(" +
                         "|".join(list(_UNITS)[16:]) + r")\b")


def number_words(text):
    """'aged forty-two' -> 'aged 42' (16-99 only), so the age cues read written-out ages."""
    def sub(m):
        if m.group(3):
            return str(_UNITS[m.group(3).lower()])
        return str(_TENS[m.group(1).lower()] + (_UNITS[m.group(2).lower()] if m.group(2) else 0))
    return _NUMWORD_RE.sub(sub, text)


def years_from_age(text, weak=False):
    """Birth-year candidates from an 'age at date' statement: someone aged 45 in March 2019 -> 1973 or 1974."""
    text = number_words(text)
    found = []
    ages = ages_in(text, weak)
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
        kind = entity_kind(as_text(hit.get("entity_type")))
        self.company = kind == "company"
        self.type_known = kind is not None
        self.entity_type = "Company" if self.company else "Individual"
        self.name = as_text(hit.get("name"))
        self.aliases = as_list(hit.get("aliases"))
        self.names = [self.name] + self.aliases if self.name else list(self.aliases)
        # Official hits also have first/middle/last_name and best_matching_name (often "Last, First").
        # Add them as extra names; they are not used as country/DOB/death evidence.
        extras = [as_text(hit.get("best_matching_name"))]
        constructed = " ".join(as_text(hit.get(k)) for k in ("first_name", "middle_name", "last_name") if as_text(hit.get(k)))
        extras.append(constructed)
        for extra in extras:
            if extra and extra not in self.names:
                self.names.append(extra)
        self.categories = as_list(hit.get("categories"))
        self.phrase = listing_phrase(hit.get("primary_category"), self.categories or as_list(hit.get("subcategories")))
        # countries tied to the hit (structured fields only — never the flattened `details` text)
        self.countries = []
        self.unplaced = []      # place values we cannot tie to any country: never evidence of a different country
        for f in ("countries", "nationality", "citizenship", "addresses", "place_of_birth"):
            for item in as_dict_list(hit.get(f)):
                if isinstance(item, dict):
                    v = item.get("country") or item.get("country_name") or as_text(item)
                else:
                    v = item
                v = re.sub(r"\[.*?\]", "", as_text(v)).strip()
                if not v:
                    continue
                last = _key(v.split(",")[-1])
                if f in ("addresses", "place_of_birth") and (last in SUBNATIONAL or last in SUBNATIONAL_AMBIG):
                    # 'Atlanta, Georgia' / 'Newark, New Jersey': a US state or Canadian province (Georgia: state or country)
                    cs = list(SUBNATIONAL_AMBIG.get(last) or [SUBNATIONAL[last]])
                else:
                    c = norm_country(v.split(",")[-1]) or norm_country(v)
                    # the last part decides (policy); if it names no country, every country the value mentions counts
                    # ('Kenyan/British', 'Lagos Nigeria'), never just the last one found
                    cs = [c] if c else list(countries_in_text(v))
                if not cs and _key(v) not in NOT_COUNTRIES:
                    self.unplaced.append(v)
                for c in cs:
                    if c not in self.countries:
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
                    span = years_span(part)
                    if span:
                        self.dobs.append({"years": span, "m": None, "d": None, "src": None, "kind": "field", "text": part})
                        continue
                    d = parse_date(part)
                    if d:
                        amb = re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.]\d{2,4}\b", part)
                        if amb and int(amb.group(1)) <= 12 and int(amb.group(2)) <= 12 and amb.group(1) != amb.group(2):
                            d = (d[0], None, None)   # provider-written D/M vs M/D is ambiguous: keep the year only
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
                    if ds and ds[0][0] <= 3 and not re.search(r"(?i)\b(?:not|unknown|unverified)\b", tail[:ds[0][0]]):
                        d = ds[0][2]
                        amb = re.match(r"\s*(?:on |in )?(\d{1,2})[/.](\d{1,2})[/.]\d{2,4}", tail)
                        if amb and int(amb.group(1)) <= 12 and int(amb.group(2)) <= 12 and amb.group(1) != amb.group(2):
                            d = (d[0], None, None)
                        # 'born 1974 or 1976' / 'born 1960-65': every year the clause chains with or/and/to/-
                        end = ds[0][1]
                        for s2, e2, _ in ds[1:]:
                            if re.fullmatch(r"\s*(?:,|or|and|to|/|-|–)\s*(?:(?:about|around|circa|c\.)\s*)?", tail[end:s2]):
                                end = e2
                            else:
                                break
                        span = years_span(tail[:end]) if end != ds[0][1] else None
                        if span:
                            pdobs.append({"years": span, "m": None, "d": None, "src": None, "kind": "notes", "text": tail[:end]})
                            continue
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
                    ys = years_from_age(as_text(sr.get("snippet")), weak=True)
                    born = None
                    for m in _BORN_RE.finditer(snip):
                        tail = snip[m.end():m.end() + 30]
                        ds = find_dates(tail)
                        # same rule as profile notes: the date must follow 'born' directly ('born in Kano; listed 2012' is not a birth year)
                        if ds and ds[0][0] <= 3 or (ds and re.fullmatch(r"\s*(?:on|in)\s*", tail[:ds[0][0]])):
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
        # dated reports: "According to ...; <date>: ..." -- the policy's form is a full date ("September 10, 2025");
        # month-only or year-only lines ("According to ...; January 1997:") are other wordings and never clear a hit.
        self.reports = []
        for m in _REPORT_RE.finditer(notes):
            d = parse_date(m.group(1))
            if d and d[1] and d[2] and re.match(r"^\s*[A-Za-z0-9]", m.group(1)):
                self.reports.append(d)
        self.earliest_report = min(self.reports, key=lambda d: (d[0], d[1] or 1, d[2] or 1)) if self.reports else None
        # Date of death is the structured deceased_date only, never dates inside details/profile prose
        # other than the exact "According to …; <date>:" report form used above.
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
