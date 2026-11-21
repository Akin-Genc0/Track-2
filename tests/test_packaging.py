"""Submission packaging contract: the entry point the judges call, and what the repository must not track."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'system' / 'run'


class Packaging(unittest.TestCase):
    def test_run_is_executable(self):
        self.assertTrue(os.access(RUN, os.X_OK), 'system/run must keep its executable bit')

    def test_runs_from_any_directory_with_spaces_and_hostile_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repo with spaces'
            shutil.copytree(ROOT / 'system', root / 'system', ignore=shutil.ignore_patterns('__pycache__'))
            data = Path(tmp) / 'data folder'
            data.mkdir()
            (data / 'hits.jsonl').write_text(json.dumps({'hit_id': 'H-00000A', 'alert_id': 'A-00000A', 'name': 'Ann Lee'}) + '\n')
            (data / 'alerts.jsonl').write_text(json.dumps({'alert_id': 'A-00000A', 'hit_ids': ['H-00000A'],
                                                           'customer': {'name': 'Ann Lee'}}) + '\n')
            out = Path(tmp) / 'out dir' / 'dev.jsonl'
            env = {k: v for k, v in os.environ.items() if k != 'OPENROUTER_API_KEY'}
            env.update(PYTHONSAFEPATH='1', PYTHONPATH=str(Path(tmp) / 'missing'))
            proc = subprocess.run([str(root / 'system' / 'run'), str(data), str(out)], cwd='/',
                                  env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual([r['hit_id'] for r in rows], ['H-00000A'])
            self.assertEqual(set(rows[0]), {'hit_id', 'alert_id', 'decision', 'reason_code',
                                            'customer_record_id', 'reason', 'evidence'})

    def test_missing_data_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / 'no hits'
            empty.mkdir()
            blank = Path(tmp) / 'blank hits'
            blank.mkdir()
            (blank / 'hits.jsonl').write_text('\n')
            (blank / 'alerts.jsonl').write_text(json.dumps({'alert_id': 'A-00000A', 'hit_ids': ['H-00000A']}) + '\n')
            for folder, needle in ((Path(tmp) / 'missing', 'data folder not found'), (empty, 'hits.jsonl not found'),
                                   (blank, 'no readable hit records')):
                out = Path(tmp) / 'out.jsonl'
                proc = subprocess.run([str(RUN), str(folder), str(out)], capture_output=True, text=True, timeout=120)
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertIn(needle, proc.stderr)
                self.assertFalse(out.exists(), 'no output file may be written for a missing data folder')

    def test_no_data_or_secrets_tracked(self):
        if shutil.which('git') is None or not (ROOT / '.git').exists():
            self.skipTest('not a git checkout')
        files = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
        banned = re.compile(r'(^|/)(dev|data)/|\.xlsx$|(^|/)\.env($|\.)|(^|/)(alerts|customers|hits|accounts|onboarding|'
                            r'kyc_checks|notes|search_results|practice_labels)\.jsonl$')
        self.assertEqual([f for f in files if banned.search(f)], [])
        keys = subprocess.run(['git', 'grep', '-lI', '-E', 'sk-or-v1-[0-9a-f]{20,}'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(keys.stdout.strip(), '', 'an OpenRouter key is committed')


if __name__ == '__main__':
    unittest.main()
