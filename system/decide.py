"""Workstream 4 - decisioning per POLICY.md.
Clear (DIFFERENT_ENTITY) only on a contradiction; confirm (SAME_ENTITY) only on agreement; otherwise REVIEW.
Every decision carries one reason code, the deciding record IDs and a factual 2-4 sentence reason."""
import re
from textutil import fmt_date, date_lt, fold
from explain import explain

DECIDES = {"ENTITY_TYPE_MISMATCH": "the type difference", "DECEASED": "the date of death", "TEMPORAL_IMPOSSIBILITY": "the timing",
           "DOB_MISMATCH": "the date-of-birth contradiction", "NAME_MISMATCH_VERIFIED": "the verified legal name",
           "LOCATION_MISMATCH": "the country difference"}
# Team call, off by default: when the customer's own record name agrees with the hit and the approved check's verified
# name shares only a part (a surname) with that record, the check may be a relative's on a shared account. On, such a hit
# is not cleared on the verified name (or on facts from that check alone) and goes to REVIEW. The practice labels clear
# this pattern (H-2808BE, H-EDBB79, H-380854), so turning it on costs 3 practice decisions.
DOUBTFUL_LINK_REVIEW = False
CLEAR_PRIORITY = ["ENTITY_TYPE_MISMATCH", "DECEASED", "TEMPORAL_IMPOSSIBILITY", "DOB_MISMATCH", "NAME_MISMATCH_VERIFIED", "LOCATION_MISMATCH"]


def dob_swapped(cd, hd):
    """Same year with day and month swapped (03/04 vs 04/03): the classic data-entry error, never a contradiction."""
    return (len(hd["years"]) == 1 and cd[0] in hd["years"] and bool(cd[1] and cd[2] and hd["m"] and hd["d"])
            and cd[1] != cd[2] and cd[1] == hd["d"] and cd[2] == hd["m"])


def dob_contradicted(cd, hd):
    """Customer DOB cd=(y,m,d) contradicts hit birth date hd? (more than 1 year outside, or same year and month/day differ)"""
    if dob_swapped(cd, hd):
        return False
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


def names_list(names):
    """'A' or 'A; B; C' (names hold commas: 'Petrov, Ivan'); more than five names end with how many others were compared."""
    # an abbreviation's full stop ('Pte. Ltd.') would read as a sentence end inside the reason
    names = list(dict.fromkeys(re.sub(r"\.(?=\s|$)", "", n) for n in names if n))
    return "; ".join(names[:5] + ([f"{len(names) - 5} other listed names"] if len(names) > 5 else []))


def and_join(xs):
    xs = [x for x in xs if x]
    if not xs:
        return "nothing else could be compared"
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


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

    def doubtful_link(self, prof, hit):
        """The record name agrees with the hit, and the verified name agrees with no record name but shares a part with one."""
        comp = prof.company
        vp = self.m.parts(prof.verified_name[0], comp)
        recs = [self.m.parts(n, comp) for n, _ in prof.record_names]
        hits = [self.m.parts(n, hit.company or comp) for n in hit.names]
        if not any(self.m.agree_parts(rp, hp) for rp in recs for hp in hits if rp and hp):
            return False
        if any(self.m.agree_parts(vp, rp) for rp in recs if rp):
            return False
        return any(self.m.part_match(a, b) for rp in recs for a in vp for b in rp)

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
            contra["DECEASED"] = (f"The hit's profile gives a date of death of {fmt_date(hit.deceased)}, before the customer was screened on {fmt_date(screened)}.",
                                  [prof.primary])     # the death date is the hit's own fact; cite the screened customer record
        dobs = prof.dobs()
        # a support note says the record date of birth is wrong (no verified DOB replaces it): it may not clear the hit
        dob_disputed = [] if prof.verified_dob else list(prof.dob_disputed)
        dob_blocked = []     # clearing codes a disputed record DOB would have given
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
                if all(a < 16 for a, _, _ in ages) and dob_disputed:
                    dob_blocked.append("TEMPORAL_IMPOSSIBILITY")
                elif all(a < 16 for a, _, _ in ages):
                    a, d, src = max(ages, key=lambda x: x[0])
                    contra["TEMPORAL_IMPOSSIBILITY"] = (
                        f"The customer was born {'in' if d[1] is None else 'on'} {fmt_date(d)} ({src}), so they "
                        + (f"were at most {a}" if a >= 0 else "were not yet born") + f" when the hit's profile reports activity on {fmt_date(r)}.",
                        [src])
        # dob
        hit_dobs = [d for d in hit.dobs if not prof.company or d["kind"] == "field"]
        dob_agree = False
        dob_agree_src = []
        swapped = [(cd, src, hd) for cd, src in dobs for hd in hit_dobs if dob_swapped(cd, hd)]

        def search_basis(hds):
            """Why a search result's birth date counts: its query, listing phrase and a hit country all matched."""
            hds = [hd for hd in hds if hd.get("kind") == "search"]
            if not hds:
                return ""
            ids = sorted({hd["src"] for hd in hds if hd["src"]})
            cs = sorted({c for hd in hds for c in hd.get("ctry", ())})
            return (f" (from {and_join(ids)}, used only because the search query, the listing phrase '{hit.phrase}' and "
                    f"the hit's country {and_join(cs)} all matched)")
        if hit_dobs and dobs and dob_disputed and all(all(dob_contradicted(cd, hd) for hd in hit_dobs) for cd, _ in dobs):
            dob_blocked.append("DOB_MISMATCH")
        elif hit_dobs and dobs:
            if all(all(dob_contradicted(cd, hd) for hd in hit_dobs) for cd, _ in dobs):
                d, src = dobs[0]
                ev = [s for _, s in dobs] + sorted({hd["src"] for hd in hit_dobs if hd["src"]})
                exact = all(hd["m"] and len(hd["years"]) == 1 for hd in hit_dobs)
                what = {"listed date of birth": "listed date of birth is",
                        "profile notes": "profile notes give its date of birth as" if exact else "profile notes put its birth year at",
                        "search results": "search results give its date of birth as" if exact else "search results put its birth year at"}.get(hit.dob_source, "birth date is")
                lbl = "incorporation date" if prof.company else "date of birth"
                contra["DOB_MISMATCH"] = (f"The customer's {lbl} is {fmt_date(d)} ({src}) but the hit's {what} {hit.dob_text()}{search_basis(hit_dobs)}.", ev)
                # after the timing sentence, which already gives the customer's date: say only what the hit's date adds
                hit_src = {"profile notes": "date of birth in its profile notes",
                           "search results": "date of birth in search results"}.get(hit.dob_source, "listed " + lbl)
                dob_also = f"The customer's {lbl} also contradicts the hit's {hit_src}, {hit.dob_text()}{search_basis(hit_dobs)}."
            else:
                for cd, src in dobs:
                    agreeing = [hd for hd in hit_dobs if dob_agrees(cd, hd)]
                    if agreeing:
                        dob_agree = True
                        dob_agree_src = [src] + sorted({hd["src"] for hd in agreeing if hd["src"]})
                        dob_agree_txt = f"The customer's date of birth {fmt_date(cd)} ({src}) agrees with the hit's {hit.dob_text()}{search_basis(agreeing)}."
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
            # without name_variants.json short forms ('Mide' / 'Olumide') look like different names: never clear a person on name then
            comparable = comparable and (prof.company or bool(self.m.group_of))
            # one spelling step away from agreeing through a listed variant is doubt, not a contradiction
            comparable = comparable and not any(self.m.agree_parts_loose(vparts, self.m.parts(n, hit.company or prof.company)) for n in hit.names)
            if vparts and (prof.company or len(vparts) >= 2) and not n_agree and comparable and not getattr(prof, "verified_name_weak", False):
                compared_names = f"the hit's name {hit.names[0]}" if len(set(hit.names)) == 1 else f"any of the hit's names ({names_list(hit.names)})"
                contra["NAME_MISMATCH_VERIFIED"] = (
                    f"The customer's verified name is {vname} ({vsrc}), which does not match {compared_names}.", [vsrc])
        # location
        shared = sorted(cust_c & hit_c)
        loc_unplaced = bool(cust_c and hit_c and not shared and (hit.unplaced or prof.unplaced) and not (n_agree and dob_agree))
        if cust_c and hit_c and not shared and not hit.unplaced and not prof.unplaced:
            if not (n_agree and (dob_agree or swapped)):
                ev = sorted({s for c in cust_c for s in prof.countries[c]})
                contra["LOCATION_MISMATCH"] = (
                    f"The customer is linked only to {', '.join(sorted(cust_c))} but the hit is linked only to {', '.join(sorted(hit_c))}.", ev)

        if DOUBTFUL_LINK_REVIEW and "NAME_MISMATCH_VERIFIED" in contra and self.doubtful_link(prof, hit):
            vname, vsrc = prof.verified_name
            for c in [c for c, (_, ev) in contra.items() if c == "NAME_MISMATCH_VERIFIED" or (ev and set(ev) <= {vsrc})]:
                del contra[c]
            if not contra:
                return dict(explain({"sentences": [
                    f"The approved check {vsrc} gives the verified name {vname}, which shares only part of the name with the customer's own record, while the record name agrees with the hit's name {hit.name}.",
                    "The check may belong to a relative on a shared account, so it is not used to clear the hit and a person must confirm whose check it is."],
                    "evidence": [vsrc, prof.primary]}), decision="REVIEW", reason_code="INSUFFICIENT_DATA")

        def compared(code):
            """What else was compared, for a reason whose deciding fact fits in one sentence."""
            out, tail = [], ""
            if code == "NAME_MISMATCH_VERIFIED":
                if any(self.m.agree_parts(self.m.parts(rn, prof.company), self.m.parts(n, hit.company or prof.company))
                       for rn, _ in prof.record_names for n in hit.names):
                    tail = "the customer's own record name agrees with the hit, but the verified legal name outranks it and is enough to clear the hit under the policy."
                else:
                    them = "any of them" if len(set(hit.names)) > 1 else "the hit's name"
                    tail = f"the customer's record names do not agree with {them} either, and the verified legal name is enough to clear the hit under the policy."
            elif n_agree:
                out.append(f"the customer's name agrees with the hit's name {hn}")
            else:
                out.append(f"the customer's name does not clearly agree with the hit's name {hit.name}")
            if not prof.company and code not in ("DOB_MISMATCH", "TEMPORAL_IMPOSSIBILITY", "ENTITY_TYPE_MISMATCH"):
                if dob_agree:
                    out.append(f"the dates of birth agree ({fmt_date(dobs[0][0])} against {hit.dob_text()})")
                elif not hit_dobs:
                    out.append("the hit gives no date of birth to compare")
                elif not dobs:
                    out.append("the customer has no date of birth on file")
                elif swapped:
                    out.append(f"the customer's date of birth {fmt_date(swapped[0][0])} has the same year as the hit's {hit.dob_text()} with the day and month swapped")
                else:
                    out.append(f"the customer's date of birth {fmt_date(dobs[0][0])} does not contradict the hit's {hit.dob_text()}")
            if code != "LOCATION_MISMATCH":
                if shared:
                    out.append(f"both are linked to {', '.join(shared)}")
                elif not cust_c:
                    out.append("the customer has no country on file")
                elif not hit_c:
                    out.append("the hit lists no country")
                else:
                    out.append(f"the customer is linked to {', '.join(sorted(cust_c))} and the hit to {', '.join(sorted(hit_c))}")
            if code is None:
                return f"Compared: {and_join(out)}."
            if tail:
                return f"{tail[0].upper()}{tail[1:-1]}; for context, {and_join(out)}."
            lead = f"{DECIDES[code][0].upper()}{DECIDES[code][1:]} alone clears the hit under the policy"
            if code == "LOCATION_MISMATCH" and not prof.company:
                # why a country difference is enough: the name and date of birth do not both agree (principle 6)
                return f"{lead}, because the name and date of birth do not both agree: {and_join(out)}."
            return f"{lead}; the other facts do not change that: {and_join(out)}." 

        if contra:
            codes = [c for c in CLEAR_PRIORITY if c in contra]
            ev = []
            for c in codes:
                for e in contra[c][1]:
                    if e and e not in ev:
                        ev.append(e)
            shown = [dob_also if c == "DOB_MISMATCH" and "TEMPORAL_IMPOSSIBILITY" in codes[:3] else contra[c][0] for c in codes[:3]]
            return dict(explain({"sentences": shown, "context": [compared(codes[0])], "evidence": ev}),
                        decision="DIFFERENT_ENTITY", reason_code=codes[0])

        loc_src = sorted({s for c in shared for s in prof.countries[c]})
        loc_txt = f"Both the customer and the hit are linked to {', '.join(shared)}." if shared else ""
        name_txt = f"The customer's name agrees with the hit's name {hn}." if n_agree else ""
        loc_conflict = bool(cust_c and hit_c and not shared)
        if loc_conflict and n_agree and dob_agree:
            ev = []
            for e in dob_agree_src + sorted({s for c in cust_c for s in prof.countries[c]}):
                if e not in ev:
                    ev.append(e)
            return dict(explain({"sentences": [dob_agree_txt, name_txt,
                                               f"However the customer is linked only to {', '.join(sorted(cust_c))} while the hit is linked only to {', '.join(sorted(hit_c))}; "
                                               "a country difference cannot clear a hit whose name and date of birth agree, so a person must review it."],
                                 "evidence": ev}), decision="REVIEW", reason_code="INSUFFICIENT_DATA")
        if not prof.company and n_agree and dob_agree:
            ev = []
            for e in dob_agree_src + loc_src:
                if e not in ev:
                    ev.append(e)
            code = "NAME_DOB_LOCATION_MATCH" if shared else "NAME_DOB_MATCH"
            return dict(explain({"sentences": [dob_agree_txt, loc_txt, name_txt], "context": [compared(None)], "evidence": ev}),
                        decision="SAME_ENTITY", reason_code=code)
        if prof.company and n_agree and shared:
            ev = []
            for e in loc_src:
                if e not in ev:
                    ev.append(e)
            return dict(explain({"sentences": [loc_txt, name_txt], "context": [compared(None)], "evidence": ev}),
                        decision="SAME_ENTITY", reason_code="NAME_LOCATION_MATCH")
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
        # what stopped a clear the facts alone would have given: each says why, and cites the record that stopped it
        why = []
        if dob_blocked:
            d, src = dobs[0]
            why.append(f"Note {and_join(dob_disputed)} says the customer's date of birth on file is wrong, so the record date of birth "
                       f"{fmt_date(d)} ({src}) is not used to clear the hit against its {hit.dob_text()}.")
            ev += [e for e in dob_disputed + [src] if e not in ev]
        if swapped and not dob_blocked:
            cd, src, hd = swapped[0]
            why.append(f"The customer's date of birth {fmt_date(cd)} ({src}) and the hit's {hit.dob_text()} have the same year with the day "
                       "and month swapped, a common data-entry error, so they are not treated as a contradiction"
                       + (f"; with the names agreeing, the country difference ({', '.join(sorted(cust_c))} against {', '.join(sorted(hit_c))}) "
                          "cannot clear the hit either." if n_agree and cust_c and hit_c and not shared and not loc_unplaced else "."))
            ev += [e for e in [src] + ([hd["src"]] if hd["src"] else []) if e not in ev]
        if loc_unplaced:
            what = []
            if hit.unplaced:
                what.append(f"the hit's place '{names_list(hit.unplaced)}' cannot be tied to a country")
            if prof.unplaced:
                srcs = list(dict.fromkeys(prof.unplaced_src))
                what.append(f"the customer's {and_join(srcs)} names a place that cannot be tied to a country")
                ev += [e for e in srcs if e not in ev]
            why.append(f"The customer is linked to {', '.join(sorted(cust_c))} and the hit to {', '.join(sorted(hit_c))}, but "
                       f"{and_join(what)}, so the country difference cannot clear the hit.")
        if not ev:
            ev = list(nsrc) or [prof.primary]
        tail = "Nothing in the customer's records contradicts the hit, and " + " and ".join(missing) + ", so the hit can be neither cleared nor confirmed."
        if why:
            tail = "Because " + " and ".join(missing) + ", the hit can be neither cleared nor confirmed." if missing else \
                "So a person must review the hit."
        sentences = [x for x in [loc_txt, name_txt] if x] + why + [tail]
        while len(sentences) > 4:
            sentences.pop(0)      # keep the stopping facts and the conclusion; drop agreement sentences first
        return dict(explain({"sentences": sentences, "context": [compared(None)], "evidence": ev}),
                    decision="REVIEW", reason_code="INSUFFICIENT_DATA")

    def decide_unresolved(self, hit, alert, path):
        """No customer record found: never clear on unverified screened data."""
        return {"decision": "REVIEW", "reason_code": "INSUFFICIENT_DATA", "customer_record_id": None,
                "reason": (f"No customer record in the system of record could be resolved for the screened customer "
                           f"{alert.get('customer_name')} ({path}). Without the customer's records nothing contradicts or confirms "
                           f"the hit {hit.name}, so it is left for review."),
                "evidence": []}
