"""Deterministic text helpers: dates and names (stdlib only)."""
import re, unicodedata

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"])}
for _k, _v in list(MONTHS.items()):
    MONTHS[_k[:3]] = _v
MONTHS["sept"] = 9
_MON = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"

# date patterns, most specific first; each returns (y, m, d)
_DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), lambda g: (g[0], g[1], g[2])),
    (re.compile(r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b"), lambda g: (g[0], g[1], g[2])),
    (re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b"), lambda g: (g[2], g[1], g[0])),  # day-first
    (re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?(?: of)? (" + _MON + r"),? (\d{4})\b", re.I), lambda g: (g[2], g[1], g[0])),
    (re.compile(r"\b(" + _MON + r") (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})\b", re.I), lambda g: (g[2], g[0], g[1])),
    (re.compile(r"\b(" + _MON + r"),? (\d{4})\b", re.I), lambda g: (g[1], g[0], None)),
    (re.compile(r"\b(\d{4})-(\d{1,2})\b(?!-)"), lambda g: (g[0], g[1], None)),
    (re.compile(r"\b(1[89]\d\d|20\d\d)\b"), lambda g: (g[0], None, None)),
]


def _mk(y, m, d):
    try:
        y = int(y)
        if m is not None and not str(m).isdigit():
            m = MONTHS.get(str(m).lower().rstrip(".")[:4].rstrip("t") if str(m).lower().startswith("sept") else str(m).lower().rstrip(".")[:3])
        m = int(m) if m is not None else None
        d = int(d) if d is not None else None
    except (TypeError, ValueError):
        return None
    if not (1800 <= y <= 2100):
        return None
    if m is not None and not 1 <= m <= 12:
        return None
    if d is not None and not 1 <= d <= 31:
        return None
    return (y, m, d)


def find_dates(text, allow_year_only=True):
    """All dates in text as list of (start, end, (y,m,d)), non-overlapping, most specific wins."""
    out = []
    if not text:
        return out
    taken = []
    for i, (rx, fn) in enumerate(_DATE_PATTERNS):
        if i == len(_DATE_PATTERNS) - 1 and not allow_year_only:
            break
        for m in rx.finditer(text):
            s, e = m.span()
            if any(s < te and e > ts for ts, te in taken):
                continue
            v = _mk(*fn(m.groups()))
            if v:
                taken.append((s, e))
                out.append((s, e, v))
    out.sort()
    return out


def parse_date(s):
    """Parse one date value; returns (y, m, d) with None for missing parts, or None."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    ds = find_dates(s)
    return ds[0][2] if ds else None


def fmt_date(d):
    if not d:
        return "unknown"
    y, m, dd = d
    if m is None:
        return f"{y}"
    if dd is None:
        return f"{y}-{m:02d}"
    return f"{y}-{m:02d}-{dd:02d}"


def date_lt(a, b):
    """True if date a is certainly before date b (partial dates handled conservatively)."""
    a_hi = (a[0], a[1] if a[1] else 12, a[2] if a[2] else 31)
    b_lo = (b[0], b[1] if b[1] else 1, b[2] if b[2] else 1)
    return a_hi < b_lo


# ----------------------------------------------------------------------------- names
_TRANS = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "ß": "ss", "đ": "d", "Đ": "D",
                        "ı": "i", "œ": "oe", "Œ": "OE", "þ": "th", "ð": "d"})
PLACEHOLDERS = {"na", "n/a", "test", "unknown", "xxx", "none", "null", "nil", "fnu", "lnu", "tbd", "tba", "nn", "unk", "dummy", "sample", "noname"}


def fold(s):
    s = str(s).translate(_TRANS)
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def name_parts(name, legal_forms=None):
    """Policy principle 8 tokenisation. Returns distinct real parts in order."""
    if not name:
        return []
    s = fold(name)
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]|\{[^}]*\}", " ", s)
    s = re.sub(r"[`'’‘ʼ]", "", s)
    s = re.sub(r"[^\w]+|_", " ", s)
    out = []
    for p in s.split():
        if len(p) < 2:
            continue                      # initials are not parts
        if any(ch.isdigit() for ch in p):
            continue                      # digits are placeholders
        if p in PLACEHOLDERS or re.fullmatch(r"x+", p):
            continue
        if legal_forms and p in legal_forms:
            continue
        if p not in out:
            out.append(p)
    return out


def lev(a, b, cap=3):
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class NameMatcher:
    def __init__(self, groups, legal_forms):
        self.group_of = {}
        for gi, g in enumerate(groups):
            for n in g:
                k = fold(n).strip()
                self.group_of.setdefault(k, set()).add(gi)
        self.legal_forms = {fold(x).strip().replace(".", "") for x in legal_forms}

    def parts(self, name, company=False):
        return name_parts(name, self.legal_forms if company else None)

    def part_match(self, a, b):
        if a == b:
            return True
        ga, gb = self.group_of.get(a), self.group_of.get(b)
        if ga and gb and ga & gb:
            return True
        short = min(len(a), len(b))
        if short < 4:
            return False
        lim = 1 if short <= 6 else 2
        return lev(a, b, lim) <= lim

    def _candidates(self, A, B):
        c = []
        for i, a in enumerate(A):
            for j, b in enumerate(B):
                if self.part_match(a, b):
                    c.append((frozenset([i]), frozenset([j])))
        for i, a in enumerate(A):
            for j in range(len(B) - 1):
                if a == B[j] + B[j + 1] or a == B[j + 1] + B[j]:
                    c.append((frozenset([i]), frozenset([j, j + 1])))
        for j, b in enumerate(B):
            for i in range(len(A) - 1):
                if b == A[i] + A[i + 1] or b == A[i + 1] + A[i]:
                    c.append((frozenset([i, i + 1]), frozenset([j])))
        return c

    def agree_parts(self, A, B):
        """Names agree: >=2 matched parts, or every part of the shorter name matched."""
        if not A or not B:
            return False
        cands = self._candidates(A, B)
        if not cands:
            return False
        best = (0, 0, 0)

        def rec(k, ua, ub, n):
            nonlocal best
            key = (n, len(ua), len(ub))
            if key > best:
                best = key
            for t in range(k, len(cands)):
                ia, ib = cands[t]
                if ia & ua or ib & ub:
                    continue
                rec(t + 1, ua | ia, ub | ib, n + 1)
        if len(cands) > 18:
            cands = cands[:18]
        rec(0, frozenset(), frozenset(), 0)
        n, ca, cb = best
        if n >= 2:
            return True
        if len(A) < len(B):
            return ca == len(A)
        if len(B) < len(A):
            return cb == len(B)
        return ca == len(A) or cb == len(B)

    def agree(self, n1, n2, company=False):
        return self.agree_parts(self.parts(n1, company), self.parts(n2, company))
