"""Regression contract: guards initialization, resolution, per-hit failures and incomplete sources."""
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

    def test_setup_and_resolution_failures_preserve_queue(self):
        for target in ('DataRoom', 'NameMatcher', 'CustomerIndex', 'build_search_index', 'Decider', 'CustomerIndex.resolve'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root/'hits.jsonl').write_text(json.dumps({'hit_id':'H1','alert_id':'A1'})+'\n')
                (root/'alerts.jsonl').write_text(json.dumps({'alert_id':'A1','hit_ids':['H1','H2']})+'\n')
                with patch('screen.' + target, side_effect=RuntimeError('injected')):
                    rows = screen.run(folder, str(root/'out'))
                self.assertEqual({r['hit_id'] for r in rows}, {'H1', 'H2'})
                self.assertTrue(all(r['decision']=='REVIEW' and not r['evidence'] for r in rows))

    def test_profile_failure_keeps_resolved_customer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'hits.jsonl').write_text(json.dumps({'hit_id':'H1','alert_id':'A1'})+'\n')
            persons = ([{'primary': 'CUS-1', 'records': ['CUS-1']}], 'test')
            with patch.object(screen.CustomerIndex, 'resolve', return_value=persons), patch.object(screen, 'Profile', side_effect=RuntimeError('injected')):
                rows = screen.run(folder, str(root/'out'))
            self.assertEqual(rows[0]['customer_record_id'], 'CUS-1')
            self.assertEqual(rows[0]['decision'], 'REVIEW')
            self.assertEqual(rows[0]['evidence'], [])

    def test_missing_core_downgrades_only_clears(self):
        for decision in ('DIFFERENT_ENTITY', 'SAME_ENTITY'):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                (root/'hits.jsonl').write_text(json.dumps({'hit_id':'H1','alert_id':'A1'})+'\n')
                result = dict(decision=decision, reason_code='DOB_MISMATCH', reason='A. B.', evidence=[])
                with patch.object(screen.Decider, 'decide_unresolved', return_value=result):
                    rows = screen.run(folder, str(root/'out'))
                self.assertEqual(rows[0]['decision'], 'REVIEW' if decision=='DIFFERENT_ENTITY' else decision)
                if decision=='DIFFERENT_ENTITY':
                    self.assertIn('notes.jsonl', rows[0]['reason'])

    def test_corrupt_core_and_noncore_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in screen.CORE:
                (root/(name+'.jsonl')).write_text('')
            (root/'hits.jsonl').write_text(json.dumps({'hit_id':'H1','alert_id':'A1'})+'\n')
            result = dict(decision='DIFFERENT_ENTITY', reason_code='DOB_MISMATCH', reason='A. B.', evidence=[])
            with patch.object(screen.Decider, 'decide_unresolved', return_value=result):
                self.assertEqual(screen.run(folder, str(root/'out'))[0]['decision'], 'DIFFERENT_ENTITY')
                (root/'notes.jsonl').write_text('{broken\n')
                self.assertEqual(screen.run(folder, str(root/'out'))[0]['decision'], 'REVIEW')
                (root/'notes.jsonl').write_bytes(b'\xff')
                self.assertEqual(screen.run(folder, str(root/'out'))[0]['decision'], 'REVIEW')

if __name__ == '__main__': unittest.main()
