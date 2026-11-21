"""Rebuild a dev/ data folder (JSON Lines) from the organisers' browsing workbook.
The workbook flattens list fields to '; '-joined strings; we split them back to arrays."""
import json, os, re, sys
# Retain the legacy raw-folder invocation; otherwise locate a participant-provided workbook.
import tempfile
from pathlib import Path
from workbook import extract
if len(sys.argv) == 1:
    workbook_name = "Screening Dev Set - browse.xlsx"
    candidates = []
    if os.environ.get("TRACK2_XLSX"):
        candidates.append(Path(os.environ["TRACK2_XLSX"]).expanduser())
    candidates.extend([Path.cwd() / workbook_name,
                       Path.home() / "Track-2-data" / workbook_name])
    workbook = next((path for path in candidates if path.is_file()), None)
    if workbook is None:
        sys.exit("Participant dataset not found. Set TRACK2_XLSX to your workbook, "
                 "place 'Screening Dev Set - browse.xlsx' in the repository root, "
                 "or put it in ~/Track-2-data/. The dataset is not committed. "
                 "Alternatively, pass a ready dev/ folder directly to system/run.")
    raw = tempfile.TemporaryDirectory()
    src = raw.name
    dst = str(Path(__file__).resolve().parents[1] / "data" / "dev")
    extract(workbook, src)
elif len(sys.argv) == 3:
    src, dst = sys.argv[1:]
else:
    sys.exit("Usage: python3 tools/xlsx_to_dev.py [raw_folder output_folder]")
os.makedirs(dst, exist_ok=True)
LISTS = {
    'alerts': ['hit_ids'],
    'hits': ['aliases', 'dobs', 'place_of_birth', 'nationality', 'citizenship', 'countries', 'addresses',
             'identifiers', 'categories', 'relationships', 'sources', 'source_urls'],
    'practice_labels': ['reason_codes', 'customer_record_ids', 'evidence'],
}
for name in ['alerts', 'hits', 'customers', 'accounts', 'onboarding', 'kyc_checks', 'notes', 'search_results', 'practice_labels']:
    with open(f'{src}/{name}.jsonl') as f, open(f'{dst}/{name}.jsonl', 'w') as g:
        for line in f:
            d = json.loads(line)
            for k in LISTS.get(name, []):
                v = d.get(k)
                d[k] = [x.strip() for x in v.split('; ') if x.strip()] if isinstance(v, str) else ([] if v is None else v)
            if name == 'alerts' and d.get('hit_count') is not None:
                d['hit_count'] = int(float(d['hit_count']))
            if name == 'hits' and d.get('match_score') is not None:
                d['match_score'] = float(d['match_score'])
            g.write(json.dumps(d, ensure_ascii=False) + '\n')
# policy + name variants
txt = open(f'{src}/policy_sheet.txt').read()
txt = '\n'.join(l.rstrip() for l in txt.splitlines())
pol, _, nv = txt.partition('\nname_variants.json')
open(f'{dst}/POLICY.md', 'w').write(re.sub(r'\n{3,}', '\n\n', pol).strip() + '\n')
groups, forms = [], []
for l in nv.splitlines():
    l = l.strip()
    if l.startswith('Company legal forms:'):
        forms = [x.strip() for x in l.split(':', 1)[1].split(',') if x.strip()]
    elif ',' in l and not l.startswith('Groups'):
        groups.append([x.strip() for x in l.split(',') if x.strip()])
json.dump({'given_names': groups, 'company_legal_forms': forms}, open(f'{dst}/name_variants.json', 'w'), indent=1, ensure_ascii=False)
print('groups', len(groups), 'forms', len(forms))
