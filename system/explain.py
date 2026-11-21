"""Reason renderer: every decision's reason is two to four sentences naming this hit's own facts.

explain(facts) -> {reason, evidence}. No inference, I/O or decision changes: decide.py selects the facts.
Facts:
  sentences  the deciding facts, most important first (each already names its values and source IDs)
  context    sentences on what else was compared or is missing, used only to reach two sentences
  evidence   the record IDs the decision cites (chosen by decide.py; see README "How evidence is represented")
Returns lead too (the first deciding sentence), which explain_candidates quotes when more than one person fits.
Fails loudly rather than emit a reason outside two to four sentences or an empty evidence ID.
See audit/REASONS.md for the audit that motivated this module."""
import re

MIN_SENTENCES, MAX_SENTENCES = 2, 4


def _sentence(s):
    s = re.sub(r"\s+", " ", s or "").strip()
    if not s:
        return ""
    s = s[0].upper() + s[1:]
    s = re.sub(r"\.{2,}$", ".", s)            # a name ending in "." ("Mark E.") before the full stop
    return s if s[-1] in ".!?" else s + "."


def explain(facts):
    deciding = [x for x in (_sentence(s) for s in facts.get("sentences", ())) if x]
    if not deciding:
        raise ValueError("A reason needs at least one deciding fact")
    out = deciding[:MAX_SENTENCES]
    for s in (_sentence(s) for s in facts.get("context", ())):
        if len(out) >= MIN_SENTENCES:
            break
        if s and s not in out:
            out.append(s)
    if len(out) < MIN_SENTENCES:
        raise ValueError("A reason needs two to four sentences: add what was compared or what is missing")
    evidence = list(facts.get("evidence", ()))
    if any(not isinstance(e, str) or not e for e in evidence):
        raise ValueError("Evidence must contain nonempty record IDs")
    return {"reason": " ".join(out), "evidence": evidence, "lead": out[0]}


# Plain words for one candidate's outcome, so an ambiguity reason never prints bare enum values.
OUTCOME = {"DIFFERENT_ENTITY": "cleared", "SAME_ENTITY": "confirmed", "REVIEW": "left for review"}
GROUND = {"ENTITY_TYPE_MISMATCH": "person versus company", "DECEASED": "the hit died before screening",
          "TEMPORAL_IMPOSSIBILITY": "too young at the hit's earliest dated report", "DOB_MISMATCH": "date of birth contradicts",
          "LOCATION_MISMATCH": "no shared country", "NAME_MISMATCH_VERIFIED": "verified legal name does not match",
          "NAME_DOB_LOCATION_MATCH": "name, date of birth and country agree", "NAME_DOB_MATCH": "name and date of birth agree",
          "NAME_LOCATION_MATCH": "name and country agree", "INSUFFICIENT_DATA": "nothing settles it",
          "AMBIGUOUS_CUSTOMER_RECORD": "more than one person fits"}


def _ids(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def _for(pid, r):
    """One candidate's deciding fact, e.g. 'For CUS-1, the customer's date of birth ... (KYC-2) but ...'."""
    lead = _sentence(r.get("lead") or r.get("reason", "").split(". ")[0])
    if lead.startswith("The "):
        lead = "t" + lead[1:]
    return f"For {pid}, {lead}"


def _union(groups):
    out = []
    for g in groups:
        for e in g:
            if e and e not in out:
                out.append(e)
    return out


def explain_candidates(results, header):
    """Reason for an alert that more than one person fits. results: [(person_id, decide_person result)].
    Names every candidate, what each would lead to and the deciding fact of each one that would be cleared or
    confirmed; evidence adds each candidate's own record to the records that decided them."""
    groups = {}
    for pid, r in results:
        groups.setdefault((r["decision"], r["reason_code"]), []).append(pid)
    parts = [f"{OUTCOME[d]} for {_ids(pids)} ({GROUND.get(c, c)})" for (d, c), pids in groups.items()]
    out = [header, "The hit would be " + (parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]) + "."]
    for want in ("SAME_ENTITY", "DIFFERENT_ENTITY"):
        for pid, r in results:
            if r["decision"] == want and len(out) < MAX_SENTENCES:
                out.append(_for(pid, r))
                break
    evidence = _union([r["evidence"] for _, r in results] + [[pid for pid, _ in results]])
    return {"reason": " ".join(_sentence(x) for x in out), "evidence": evidence}


def explain_each_cleared(results, fits=None):
    """Every person who fits is cleared: show each one's own contradiction, so the reason matches the evidence.
    fits labels the people in the opening sentence (default: their IDs)."""
    out = [f"{len(results)} different people in the system of record fit the alert ({fits or _ids(pid for pid, _ in results)}), "
           "and the hit is cleared for each of them."]
    if len(results) < MAX_SENTENCES:
        out += [_for(pid, r) for pid, r in results]
    else:
        shown, rest = results[:MAX_SENTENCES - 2], results[MAX_SENTENCES - 2:]
        out += [_for(pid, r) for pid, r in shown]
        cited = _union(r["evidence"] for _, r in shown)
        more = [e for e in _union(r["evidence"] for _, r in rest) if e not in cited]
        grounds = "; ".join(dict.fromkeys(GROUND.get(r["reason_code"], r["reason_code"]) for _, r in rest))
        out.append(f"For {_ids(pid for pid, _ in rest)}, the hit is likewise cleared ({grounds}" + (f": {', '.join(more)})" if more else ")"))
    return {"reason": " ".join(_sentence(x) for x in out), "evidence": _union(r["evidence"] for _, r in results)}
