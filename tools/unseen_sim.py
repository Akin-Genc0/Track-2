"""Exercise schema mutations in disposable /tmp copies; exit nonzero on regressions."""
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'system'))
from data import ALIASES


def run(folder, output):
    p = subprocess.run([str(ROOT / 'system/run'), str(folder), str(output)], capture_output=True, text=True)
    if p.returncode: return None, p.stderr[-1000:]
    try: return [json.loads(l) for l in output.read_text().splitlines()], None
    except Exception as e: return None, str(e)


def main(folder):
    failures = 0
    with tempfile.TemporaryDirectory(prefix='clearsight-unseen-', dir='/tmp') as tmp:
        root = Path(tmp)
        baseline, error = run(folder, root / 'baseline.jsonl')
        if error: print(error); return 1
        base = {r['hit_id']: r['decision'] for r in baseline}
        for mode in ('renamed', 'stringified', 'nested', 'optional_missing', 'corrupt', 'shuffled', 'extra'):
            dest = root / mode
            shutil.copytree(folder, dest)
            if mode == 'optional_missing':
                for name in ('practice_labels.jsonl', 'search_results.jsonl', 'notes.jsonl', 'POLICY.md', 'name_variants.json', 'onboarding.jsonl', 'kyc_checks.jsonl'):
                    (dest / name).unlink(missing_ok=True)
            for path in dest.glob('*.jsonl'):
                rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
                for r in rows:
                    if mode == 'renamed':
                        for k, aliases in ALIASES.get(path.stem, {}).items():
                            if k in r: r[aliases[0]] = r.pop(k)
                    if mode == 'stringified':
                        for k, v in list(r.items()):
                            if isinstance(v, list): r[k] = json.dumps(v)
                    if mode == 'extra': r['unknown_extra'] = {'id': 'DO-NOT-USE', 'value': None}
                if mode == 'nested': rows = [{'record': r} for r in rows]
                if mode == 'shuffled': random.Random(42).shuffle(rows)
                text = '\r\n'.join(json.dumps(r) for r in rows) + '\r\n'
                if mode == 'corrupt': text = '\ufeff\n{broken\n\n' + text
                path.write_text(text)
            rows, error = run(dest, root / (mode + '.jsonl'))
            missing = len(base) if rows is None else len(set(base) - {r['hit_id'] for r in rows}) + abs(len(rows)-len(base))
            clears = [] if rows is None else [r['hit_id'] for r in rows if r['decision'] == 'DIFFERENT_ENTITY' and base.get(r['hit_id']) != 'DIFFERENT_ENTITY']
            print(json.dumps(dict(mutation=mode, crash=error, missing=missing, moves_to_clear=clears)))
            failures += bool(error or missing or clears)
    return bool(failures)

if __name__ == '__main__': sys.exit(main(Path(sys.argv[1] if len(sys.argv)>1 else 'dev')))
