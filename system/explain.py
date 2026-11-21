"""Pure, provenance-preserving rendering of facts selected by the decision engine.

explain(facts) -> {reason, evidence}. No inference, I/O, or decision changes.
Facts: reason_code, customer_record_id, hit_name, grounds (mapping).
Each ground: customer, hit (display strings), evidence (decisive record IDs).
Review grounds use detail instead; ambiguous detail must describe EACH candidate.
Values must preserve partial dates/ranges and all alternatives. Evidence is supplied
by fact producers, never a list of every record visited. See audit/REASONS.md.
"""

_REQUIREMENTS = {
    'ENTITY_TYPE_MISMATCH': ('type',), 'DECEASED': ('death',),
    'TEMPORAL_IMPOSSIBILITY': ('time',), 'DOB_MISMATCH': ('dob',),
    'LOCATION_MISMATCH': ('location',), 'NAME_MISMATCH_VERIFIED': ('name',),
    'NAME_DOB_LOCATION_MATCH': ('name', 'dob', 'location'),
    'NAME_DOB_MATCH': ('name', 'dob'), 'NAME_LOCATION_MATCH': ('name', 'location'),
    'INSUFFICIENT_DATA': ('missing',), 'AMBIGUOUS_CUSTOMER_RECORD': ('ambiguity',),
}
_TEMPLATES = {
    'ENTITY_TYPE_MISMATCH': 'The customer is {customer}; the hit is {hit}.',
    'DECEASED': 'The hit died {hit}; the customer was screened {customer}.',
    'TEMPORAL_IMPOSSIBILITY': 'The customer {customer}; the earliest dated report for the hit is {hit}.',
    'DOB_MISMATCH': 'The customer birth or incorporation date is {customer}; every hit date ({hit}) is contradicted.',
    'LOCATION_MISMATCH': 'The complete customer country set is {customer}; the hit country set is {hit}, with no overlap.',
    'NAME_MISMATCH_VERIFIED': 'The verified customer name {customer} disagrees with all hit names and aliases ({hit}).',
}


def explain(facts):
    """Require explicit deciding facts; fail loudly rather than invent grounds.

    Optional resolution_evidence contains only IDs necessary to establish which
    person supplied the selected facts (including duplicate-record links).
    Ground evidence must include every source needed to establish its claim;
    redundancy cannot safely be inferred from IDs alone.
    """
    code = facts['reason_code']
    required = _REQUIREMENTS[code]
    grounds = facts['grounds']
    sentences, evidence = [], set(facts.get('resolution_evidence', ()))
    for key in required:
        ground = grounds[key]
        evidence.update(ground['evidence'])
        if key in ('missing', 'ambiguity'):
            text = ground['detail'].strip()
            if not text:
                raise ValueError('Review requires specific missing or conflicting facts')
            sentences.append(text.rstrip('.') + '.')
        elif code in _TEMPLATES:
            if not ground['customer'] or not ground['hit']:
                raise ValueError('Both sides of a decisive comparison are required')
            sentences.append(_TEMPLATES[code].format(**ground))
        else:
            if not ground['customer'] or not ground['hit']:
                raise ValueError('Agreement requires both values')
            label = {'name': 'name', 'dob': 'date of birth', 'location': 'country'}[key]
            sentences.append(f"The customer {label} ({ground['customer']}) agrees with the hit ({ground['hit']}).")
    if len(sentences) == 1:
        who = facts['customer_record_id'] or 'unresolved customer'
        sentences.append(f"This is the deciding ground for {who} against {facts['hit_name']}.")
    if any(not isinstance(e, str) or not e for e in evidence):
        raise ValueError('Evidence must contain nonempty record IDs')
    return {'reason': ' '.join(sentences), 'evidence': sorted(evidence)}
