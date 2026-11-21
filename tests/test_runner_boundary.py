"""Regression contract: currently exposes the runner's unguarded HitFacts path."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'system'))
import screen

class RunnerBoundary(unittest.TestCase):
    def test_hitfacts_failure_still_writes_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'hits.jsonl').write_text(json.dumps({'hit_id':'H1','alert_id':'A1'})+'\n')
            (root/'alerts.jsonl').write_text(json.dumps({'alert_id':'A1','hit_ids':['H1']})+'\n')
            with patch.object(screen, 'HitFacts', side_effect=RuntimeError('injected failure')):
                screen.run(folder, str(root/'out.jsonl'))
            rows = [json.loads(l) for l in (root/'out.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['hit_id'], 'H1')
            self.assertEqual(rows[0]['decision'], 'REVIEW')
            self.assertEqual(rows[0]['reason_code'], 'INSUFFICIENT_DATA')

if __name__ == '__main__': unittest.main()
