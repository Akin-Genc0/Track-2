"""Workstream 4 - decisioning per POLICY.md.
Clear (DIFFERENT_ENTITY) only on a contradiction; confirm (SAME_ENTITY) only on agreement; otherwise REVIEW.
Every decision carries one reason code, the deciding record IDs and a factual 2-4 sentence reason."""
import re
from textutil import fmt_date, date_lt, fold

CLEAR_PRIORITY = ["ENTITY_TYPE_MISMATCH", "DECEASED", "TEMPORAL_IMPOSSIBILITY", "DOB_MISMATCH", "NAME_MISMATCH_VERIFIED", "LOCATION_MISMATCH"]


def dob_contradicted(cd, hd):
    """Customer DOB cd=(y,m,d) contradicts hit birth date hd? (more than 1 year outside, or same year and month/day differ)"""
    ys = sorted(hd["years"])
    y = cd[0]
    if y < ys[0] - 1 or y > ys[-1] + 1:
        return True
    if len(ys) == 1 and y == ys[0]:
        if cd[1] and hd["m"] and cd[1] != hd["m"]:
            return True
        if cd[1] and hd["m"] and cd[1] == hd["m"] and cd[2] and hd["d"] and cd[2] != hd["d"]:
            return True
    return False


def dob_agrees(cd, hd):
    if cd[0] not in hd["years"]:
        return False
    if len(hd["years"]) == 1:
        if cd[1] and hd["m"] and cd[1] != hd["m"]:
            return False
        if cd[2] and hd["d"] and cd[2] != hd["d"]:
            return False
    return True


def max_age_at(dob, when):
    """Largest age the person can have had at date `when`."""
    y = when[0] - dob[0]
    if dob[1] and when[1]:
        if when[1] < dob[1]:
            y -= 1
        elif when[1] == dob[1] and dob[2] and when[2] and when[2] < dob[2]:
            y -= 1
    return y


def latin(name):
    """At least two Latin letters once accents are folded."""
    return len(re.findall(r"[a-z]", fold(name or ""))) >= 2


def sentence_join(parts):
    return " ".join(p.strip() for p in parts if p and p.strip())


class Decider:
    def __init__(self, matcher):
        self.m = matcher

    def name_status(self, prof, hit):
        """Returns (agrees:bool, usable:bool, matched_hit_name, cust_name, cust_src_ids)."""
        comp = prof.company
        hit_parts = [(n, self.m.parts(n, hit.company or comp)) for n in hit.names]
        hit_parts = [(n, p) for n, p in hit_parts if p]
        cands = prof.names_for_comparison()
        usable = False
        for cname, src in cands:
            cp = self.m.parts(cname, comp)
            if comp or len(cp) >= 2:
                usable = True
            for hn, hp in hit_parts:
                # an individual whose name has fewer than two real parts can be neither confirmed nor cleared on name
                if (comp or len(cp) >= 2) and self.m.agree_parts(cp, hp):
                    return True, True, hn, cname, [src]
        return False, usable, None, None, []

    def decide_person(self, prof, hit, alert):
        screened = alert.get("screened_at")
        from textutil import parse_date
        screened = parse_date(screened)
        contra = {}      # code -> (sentence, evidence list)
        hit_c = set(hit.countries)
        cust_c = set(prof.countries)

        # type
        if prof.company != hit.company and prof.type_known and hit.type_known:
            contra["ENTITY_TYPE_MISMATCH"] = (
                f"The customer is {'a company' if prof.company else 'an individual'} but the hit is {'a company' if hit.company else 'an individual'}.",
                [prof.primary])
        # deceased
        if hit.deceased and screened and date_lt(hit.deceased, screened):
            contra["DECEASED"] = (f"The hit's profile gives a date of death of {fmt_date(hit.deceased)}, before the customer was screened on {fmt_date(screened)}.", [])
        dobs = prof.dobs()
        # temporal
        if hit.earliest_report and dobs:
            r = hit.earliest_report
            if prof.company:
                if all(date_lt(r, d) for d, _ in dobs):
                    d, src = dobs[0]
                    contra["TEMPORAL_IMPOSSIBILITY"] = (
                        f"The customer was incorporated {'in' if d[1] is None else 'on'} {fmt_date(d)} ({src}), after the hit's earliest dated report on {fmt_date(r)}.", [src])
            else:
                ages = [(max_age_at(d, r), d, src) for d, src in dobs]
                if all(a < 16 for a, _, _ in ages):
                    a, d, src = max(ages, key=lambda x: x[0])
                    contra["TEMPORAL_IMPOSSIBILITY"] = (
                        f"The customer was born {'in' if d[1] is None else 'on'} {fmt_date(d)} ({src}), so they were at most {max(a, 0)} when the hit's profile reports activity on {fmt_date(r)}.",
                        [src])
        # dob
        hit_dobs = [d for d in hit.dobs if not prof.company or d["kind"] == "field"]
        dob_agree = False
        dob_agree_src = []
        if hit_dobs and dobs:
            if all(all(dob_contradicted(cd, hd) for hd in hit_dobs) for cd, _ in dobs):
                d, src = dobs[0]
                ev = [s for _, s in dobs] + sorted({hd["src"] for hd in hit_dobs if hd["src"]})
                exact = all(hd["m"] and len(hd["years"]) == 1 for hd in hit_dobs)
                what = {"listed date of birth": "listed date of birth is",
                        "profile notes": "profile notes give its date of birth as" if exact else "profile notes put its birth year at",
                        "search results": "search results give its date of birth as" if exact else "search results put its birth year at"}.get(hit.dob_source, "birth date is")
                lbl = "incorporation date" if prof.company else "date of birth"
                contra["DOB_MISMATCH"] = (f"The customer's {lbl} is {fmt_date(d)} ({src}) but the hit's {what} {hit.dob_text()}.", ev)
            else:
                for cd, src in dobs:
                    agreeing = [hd for hd in hit_dobs if dob_agrees(cd, hd)]
                    if agreeing:
                        dob_agree = True
                        dob_agree_src = [src] + sorted({hd["src"] for hd in agreeing if hd["src"]})
                        dob_agree_txt = f"The customer's date of birth {fmt_date(cd)} ({src}) agrees with the hit's {hit.dob_text()}."
                        break
                if dob_agree and not all(any(dob_agrees(cd, hd) for hd in hit_dobs) for cd, _ in dobs):
                    dob_agree = False     # declared DOBs disagree among themselves
        # name
        n_agree, n_usable, hn, cname, nsrc = self.name_status(prof, hit)
        if prof.verified_name:
            vname, vsrc = prof.verified_name
            vparts = self.m.parts(vname, prof.company)
            # names in different scripts cannot be compared: 'ИВАН ПЕТРОВ' vs 'Petrov, Ivan' is no evidence either way
            comparable = latin(vname) and any(latin(n) for n in hit.names)
            if (prof.company or len(vparts) >= 2) and not n_agree and comparable and not getattr(prof, "verified_name_weak", False):
                contra["NAME_MISMATCH_VERIFIED"] = (
                    f"The customer's verified name is {vname} ({vsrc}), which does not match the hit's name {hit.name}.", [vsrc])
        # location
        shared = sorted(cust_c & hit_c)
        if cust_c and hit_c and not shared and not hit.unplaced and not prof.unplaced:
            if not (n_agree and dob_agree):
                ev = sorted({s for c in cust_c for s in prof.countries[c]})
                contra["LOCATION_MISMATCH"] = (
                    f"The customer is linked only to {', '.join(sorted(cust_c))} but the hit is linked only to {', '.join(sorted(hit_c))}.", ev)

        if contra:
            codes = [c for c in CLEAR_PRIORITY if c in contra]
            ev = []
            for c in codes:
                for e in contra[c][1]:
                    if e and e not in ev:
                        ev.append(e)
            reason = sentence_join([contra[c][0] for c in codes[:3]])
            return {"decision": "DIFFERENT_ENTITY", "reason_code": codes[0], "reason": reason, "evidence": ev}

        loc_src = sorted({s for c in shared for s in prof.countries[c]})
        loc_txt = f"Both the customer and the hit are linked to {', '.join(shared)}." if shared else ""
        name_txt = f"The customer's name agrees with the hit's name {hn}." if n_agree else ""
        loc_conflict = bool(cust_c and hit_c and not shared)
        if loc_conflict and n_agree and dob_agree:
            ev = []
            for e in dob_agree_src + sorted({s for c in cust_c for s in prof.countries[c]}):
                if e not in ev:
                    ev.append(e)
            return {"decision": "REVIEW", "reason_code": "INSUFFICIENT_DATA", "evidence": ev,
                    "reason": sentence_join([dob_agree_txt, name_txt,
                                             f"However the customer is linked only to {', '.join(sorted(cust_c))} while the hit is linked only to {', '.join(sorted(hit_c))}; "
                                             "a country difference cannot clear a hit whose name and date of birth agree, so a person must review it."])}
        if not prof.company and n_agree and dob_agree:
            ev = []
            for e in dob_agree_src + loc_src:
                if e not in ev:
                    ev.append(e)
            code = "NAME_DOB_LOCATION_MATCH" if shared else "NAME_DOB_MATCH"
            return {"decision": "SAME_ENTITY", "reason_code": code, "reason": sentence_join([dob_agree_txt, loc_txt, name_txt]), "evidence": ev}
        if prof.company and n_agree and shared:
            ev = []
            for e in loc_src:
                if e not in ev:
                    ev.append(e)
            return {"decision": "SAME_ENTITY", "reason_code": "NAME_LOCATION_MATCH", "reason": sentence_join([loc_txt, name_txt]), "evidence": ev}
        # review
        missing = []
        if not n_agree:
            missing.append("the names cannot be confirmed to agree" if n_usable else "the customer's name has too few real parts to compare")
        if not prof.company and not dob_agree:
            missing.append("the date of birth cannot be compared with it" if not (hit_dobs and dobs) else "the dates of birth do not clearly agree")
        if prof.company and not shared:
            missing.append("no country is shared")
        ev = []
        for e in loc_src + (dob_agree_src if dob_agree else []):
            if e not in ev:
                ev.append(e)
        if not ev:
            ev = list(nsrc) or [prof.primary]
        tail = "Nothing in the customer's records contradicts the hit, and " + " and ".join(missing) + ", so the hit can be neither cleared nor confirmed."
        return {"decision": "REVIEW", "reason_code": "INSUFFICIENT_DATA",
                "reason": sentence_join([loc_txt, name_txt, tail]), "evidence": ev}

    def decide_unresolved(self, hit, alert, path):
        """No customer record found: never clear on unverified screened data."""
        return {"decision": "REVIEW", "reason_code": "INSUFFICIENT_DATA", "customer_record_id": None,
                "reason": (f"No customer record in the system of record could be resolved for the screened customer "
                           f"{alert.get('customer_name')} ({path}). Without the customer's records nothing contradicts or confirms "
                           f"the hit {hit.name}, so it is left for review."),
                "evidence": []}
