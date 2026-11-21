"""Reason renderer: every decision's reason is two to four sentences naming this hit's own facts.

explain(facts) -> {reason, evidence}. No inference, I/O or decision changes: decide.py selects the facts.
Facts:
  sentences  the deciding facts, most important first (each already names its values and source IDs)
  context    sentences on what else was compared or is missing, used only to reach two sentences
  evidence   the record IDs the decision cites (chosen by decide.py; see README "How evidence is represented")
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
    return {"reason": " ".join(out), "evidence": evidence}
