"""Validate submission structure and provenance: OUTPUT [DATA_FOLDER]."""
import collections
import json
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'system'))
from data import DataRoom, read_jsonl, as_list


def validate(output, folder):
    room = DataRoom(folder)
    errors = []
    expected = {h['hit_id']: h.get('alert_id') for h in room.hits}
    for a in room.alerts:
        for hid in as_list(a.get('hit_ids')):
            expected.setdefault(hid, a.get('alert_id'))
    alerts = {a.get('alert_id') for a in room.alerts}
    policy = Path(folder) / 'POLICY.md'
    pairs = set(re.findall(r'\|\s*`(DIFFERENT_ENTITY|SAME_ENTITY|REVIEW)`\s*\|\s*`([A-Z_]+)`', policy.read_text()) ) if policy.exists() else set()
    if not pairs:
        errors.append('POLICY.md missing or reason table unreadable')
    ids = set()
    def collect(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if (k == 'id' or k.endswith('_id')) and isinstance(x, str): ids.add(x)
                collect(x)
        elif isinstance(v, list):
            for x in v: collect(x)
    for path in Path(folder).glob('*.jsonl'):
        if path.stem != 'practice_labels':
            for r in read_jsonl(path): collect(r)
    seen = collections.Counter()
    for n, line in enumerate(Path(output).read_text(encoding='utf-8-sig').splitlines(), 1):
        try:
            r = json.loads(line)
            assert isinstance(r, dict)
            hid = r.get('hit_id'); seen[hid] += 1
            assert hid in expected, 'unknown hit'
            assert r.get('alert_id') in alerts and (not expected[hid] or r['alert_id'] == expected[hid]), 'invalid alert'
            assert (r.get('decision'), r.get('reason_code')) in pairs, 'invalid decision/reason code'
            assert 'customer_record_id' in r and (r['customer_record_id'] in (None, 'AMBIGUOUS') or r['customer_record_id'] in room.customers), 'invalid customer'
            assert isinstance(r.get('reason'), str) and 2 <= len(re.findall(r'[.!?](?:\s|$)', r['reason'])) <= 4, 'reason must contain 2-4 sentences'
            assert isinstance(r.get('evidence'), list) and all(isinstance(e, str) and e in ids for e in r['evidence']), 'unknown evidence'
            assert r['evidence'] or r['decision'] == 'REVIEW', 'conclusive decision without evidence'
        except (AssertionError, ValueError, TypeError, KeyError) as e:
            errors.append(f'line {n}: {e}')
    errors.extend(f'{hid}: expected once, found {seen[hid]}' for hid in expected if seen[hid] != 1)
    return errors

if __name__ == '__main__':
    errors = validate(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'dev')
    print('\n'.join(errors) if errors else 'PASS')
    sys.exit(bool(errors))
