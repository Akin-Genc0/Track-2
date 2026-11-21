"""Workstream 1 - customer resolution.
Follow the alert's link (account_ref / login_handle / email), or search the system of record by the screened
name, DOB, country and city; then group records into people (principle 3: shared phone + same full DOB, or same
document number on approved KYC checks, transitively)."""
import re
from collections import defaultdict
from data import as_text
from textutil import parse_date, fold, entity_kind, placeholder_dob, approved_result
from countries import norm_country


def norm_phone(p):
    d = re.sub(r"\D", "", as_text(p))
    return d if len(d) >= 6 else ""


_DOC_PLACEHOLDERS = re.compile(r"UNKNOWN|PENDING|NONE|NULL|NA|TBC|TBD|TEST|XXX|SAMPLE|DUMMY|NOTPROVIDED|REDACTED|MISSING")


def norm_doc(n):
    """A document number that can link records: 5+ characters, at least one digit, not one repeated character or
    sequence, not a placeholder ('UNKNOWN', 'NONE00', '000000', '123456')."""
    d = re.sub(r"[^A-Z0-9]", "", as_text(n).upper())
    if len(d) < 5 or not re.search(r"\d", d) or len(set(d)) == 1 or d in "01234567890" or d in "98765432109":
        return ""
    if _DOC_PLACEHOLDERS.match(d):
        return ""
    return d


class UnionFind:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # deterministic root: smallest id
            if rb < ra:
                ra, rb = rb, ra
            self.p[rb] = ra


def dob_compatible(a, b):
    """Equal in every part both give (unknown stays unknown)."""
    if not a or not b:
        return True
    for x, y in zip(a, b):
        if x is not None and y is not None and x != y:
            return False
    return True


class CustomerIndex:
    def __init__(self, room, matcher):
        self.room = room
        self.m = matcher
        C = room.customers
        self.by_email = defaultdict(list)
        self.by_part = defaultdict(set)
        for rid in sorted(C):
            c = C[rid]
            e = as_text(c.get("email")).lower()
            if e:
                self.by_email[e].append(rid)
            comp = self.is_company(c.get("entity_type"))
            for f in ("full_name", "preferred_name", "login_name"):
                for p in self.m.parts(as_text(c.get(f)), comp):
                    self.by_part[self.block_key(p)].add(rid)
        self.acc_by_id = defaultdict(list)
        self.acc_by_login = defaultdict(list)
        self.acc_by_cust = defaultdict(list)
        for a in room.accounts:
            aid, cid = as_text(a.get("account_id")), as_text(a.get("customer_id"))
            self.acc_by_id[aid].append(cid)
            lh = as_text(a.get("login_handle")).lower()
            if lh:
                self.acc_by_login[lh].append((aid, cid))
            self.acc_by_cust[cid].append(aid)
        self.applicants = defaultdict(list)   # customer_id -> [applicant ids] (account+customer must both match)
        for o in room.onboarding:
            cid, aid, app = as_text(o.get("customer_id")), as_text(o.get("account_id")), as_text(o.get("kyc_applicant_id"))
            if not (app and cid):
                continue
            if aid in self.acc_by_id:
                # the row names a known account: attach only to a customer who holds it (a shared account's other
                # holder's check must never become this customer's verified identity)
                if aid in self.acc_by_cust.get(cid, ()):
                    self.applicants[cid].append(app)
            elif all(len(set(self.acc_by_id[a])) == 1 for a in self.acc_by_cust.get(cid, ())):
                # no usable account on the row: trust its customer_id only when that customer holds no shared account
                self.applicants[cid].append(app)
        self.kyc_by_app = defaultdict(list)
        for k in room.kyc:
            self.kyc_by_app[as_text(k.get("applicant_id"))].append(k)
        self.notes_by_email = defaultdict(list)
        for n in room.notes:
            self.notes_by_email[as_text(n.get("requester_email")).lower()].append(n)
        self._cluster()

    @staticmethod
    def is_company(t):
        return entity_kind(as_text(t)) == "company"

    def block_key(self, p):
        g = self.m.group_of.get(p)
        return "G%d" % min(g) if g else p

    def kyc_checks_for(self, cid):
        out = []
        for app in sorted(set(self.applicants.get(cid, []))):
            out.extend(self.kyc_by_app.get(app, []))
        return out

    def _cluster(self):
        uf = UnionFind()
        C = self.room.customers
        by_phone_dob = defaultdict(list)
        for rid in sorted(C):
            c = C[rid]
            ph = norm_phone(c.get("phone"))
            d = parse_date(c.get("dob"))
            if ph and d and d[1] and d[2] and not placeholder_dob(d):
                by_phone_dob[(ph, d)].append(rid)
        by_doc = defaultdict(set)
        for rid in sorted(C):
            for k in self.kyc_checks_for(rid):
                if approved_result(as_text(k.get("result"))):
                    dn = norm_doc(k.get("document_number"))
                    if dn:
                        by_doc[dn].add(rid)
        for grp in list(by_phone_dob.values()) + [sorted(s) for s in by_doc.values()]:
            for r in grp[1:]:
                uf.union(grp[0], r)
        self.uf = uf
        self.members = defaultdict(list)
        for rid in sorted(C):
            self.members[uf.find(rid)].append(rid)

    def person_of(self, rid):
        return self.members[self.uf.find(rid)]

    # ------------------------------------------------------------------ fit checks
    def name_fits(self, screened, c):
        comp = self.is_company(c.get("entity_type"))
        sp = self.m.parts(screened, comp)
        for f in ("full_name", "preferred_name", "login_name"):
            v = as_text(c.get(f))
            if v and self.m.agree_parts(sp, self.m.parts(v, comp)):
                return True
        return False

    def fits(self, alert, c, need_name=True, need_city=True):
        name = as_text(alert.get("customer_name"))
        if need_name and name and not self.name_fits(name, c):
            return False
        if not dob_compatible(parse_date(alert.get("dob")), parse_date(c.get("dob"))):
            return False
        ctry = norm_country(alert.get("country"))
        if ctry:
            rc = {norm_country(c.get("residence_country")), norm_country(c.get("nationality"))} - {None}
            if rc and ctry not in rc:
                return False
        city = fold(as_text(alert.get("city"))).strip()
        if city and need_city:
            hay = fold(as_text(c.get("city")) + " " + as_text(c.get("address")))
            if hay.strip() and city not in hay:
                return False
        return True

    # ------------------------------------------------------------------ resolution
    def resolve(self, alert):
        """Returns (persons, path) where persons is a list of sorted record-id lists (one per person)."""
        persons, path, _ = self.resolve_with_near(alert)
        return persons, path

    def near(self, alert):
        """People the screened city alone excluded (see resolve_with_near)."""
        return self.resolve_with_near(alert)[2]

    def resolve_with_near(self, alert):
        """Like resolve, plus `near`: people found by the name search who fail only the screened city (an exonym or
        transliteration, 'Munich' vs 'München'). They never decide anything, but a clear must also hold for them."""
        C = self.room.customers
        linked, path = [], ""
        acc = as_text(alert.get("account_ref"))
        lh = as_text(alert.get("login_handle")).lower()
        em = as_text(alert.get("email")).lower()
        # follow each link the alert carries, in order, until one resolves
        tried = []
        for kind, val, look in (("account_ref", acc, lambda: list(self.acc_by_id.get(acc, []))),
                                ("login_handle", lh, lambda: [cid for _, cid in self.acc_by_login.get(lh, [])]),
                                ("email", em, lambda: list(self.by_email.get(em, [])))):
            if not val:
                continue
            linked = sorted({r for r in look() if r in C})
            tried.append(f"{kind} {val} -> {'customers' if kind == 'email' else 'accounts'}")
            if linked:
                break
        path = (" (link not found); ".join(tried[:-1]) + " (link not found); " if len(tried) > 1 else "") + (tried[-1] if tried else "")
        near_records = []
        if linked:
            if len({self.uf.find(r) for r in linked}) > 1:
                fit = [r for r in linked if self.fits(alert, C[r])]
                if not fit:
                    fit = [r for r in linked if self.fits(alert, C[r], need_name=False)]
                if fit:
                    linked = fit
            records = linked
        elif acc or lh or em:
            records = []
            path += " (link not found)"
        else:
            path = "screened name, date of birth, country and city -> customers"
            comp = self.is_company(alert.get("entity_type"))
            cand = set()
            for p in self.m.parts(as_text(alert.get("customer_name")), comp):
                cand |= self.by_part.get(self.block_key(p), set())
            records = sorted(r for r in cand if self.fits(alert, C[r]))
            near_records = sorted(r for r in cand if r not in records and self.fits(alert, C[r], need_city=False))
            et = as_text(alert.get("entity_type"))
            if et and records:
                same_type = [r for r in records if self.is_company(C[r].get("entity_type")) == comp]
                records = same_type or records
        persons = {}
        for r in records:
            root = self.uf.find(r)
            persons.setdefault(root, {"primary": r, "records": self.members[root]})
        out = [persons[k] for k in sorted(persons, key=lambda k: persons[k]["primary"])]
        near = {}
        for r in near_records:
            root = self.uf.find(r)
            if root not in persons:
                near.setdefault(root, {"primary": r, "records": self.members[root]})
        return out, path, [near[k] for k in sorted(near, key=lambda k: near[k]["primary"])]
