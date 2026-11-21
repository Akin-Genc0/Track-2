import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from harness import CODES, COST, read, score, validate


def prediction(decision='REVIEW'):
    return dict(hit_id='h', alert_id='a', decision=decision, reason_code=sorted(CODES[decision])[0],
                customer_record_id=None, reason='Facts are missing. A person must review.', evidence=[])


class HarnessTests(unittest.TestCase):
    def test_all_nine_costs(self):
        expected = [[0, 3, 3], [60, 0, 2], [60, 2, 0]]
        for i, truth in enumerate(CODES):
            for j, decision in enumerate(CODES):
                self.assertEqual(score({'h': prediction(decision)}, {'h': {'decision': truth}})['cost'], expected[i][j])

    def test_baseline_perfect_floor_and_reason_alternatives(self):
        labels = {str(i): dict(decision=d, reason_codes=sorted(CODES[d])) for i, d in enumerate(CODES)}
        rows = {i: prediction(x['decision']) for i, x in labels.items()}
        result = score(rows, labels)
        self.assertEqual(result['decision_score'], 1)
        self.assertEqual(result['reason_code_accuracy'], 1)
        self.assertEqual(score({i: prediction() for i in labels}, labels)['decision_score'], 0)
        result = score({i: prediction('DIFFERENT_ENTITY') for i in labels}, labels)
        self.assertEqual(result['decision_score'], 0)
        self.assertEqual(result['unsafe_clearances'], 2)
        self.assertIsNone(score({'h': prediction()}, {'h': {'decision': 'REVIEW'}})['decision_score'])

    def test_schema_and_coverage(self):
        row = prediction()
        self.assertFalse(validate({'h': row})[0])
        for field, value in [('decision', []), ('reason_code', 'DOB_MISMATCH'), ('evidence', 'x'), ('customer_record_id', 3)]:
            self.assertTrue(validate({'h': dict(row, **{field: value})})[0])
        self.assertTrue(validate({'h': row}, {'other': {'alert_id': 'a'}})[0])
        with self.assertRaises(ValueError):
            score({'h': row}, {'missing': {'decision': 'REVIEW'}})

    def test_json_duplicates_and_blank_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'output'
            for text in ['{"hit_id":"h","hit_id":"x"}\n', '\n', json.dumps(prediction())+'\n'+json.dumps(prediction())]:
                path.write_text(text)
                with self.assertRaises(ValueError):
                    read(path)

    def test_repro_success_and_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp)/'fixture.py'
            script.write_text('import json,sys\nfrom pathlib import Path\np='+repr(prediction())+'\n'
                              'if len(sys.argv)>2 and "run-3" in sys.argv[1]: p["reason_code"]="INSUFFICIENT_DATA"\n'
                              'Path(sys.argv[1]).write_text(json.dumps(p)+"\\n")\n')
            cmd = [sys.executable, str(Path(__file__).with_name('repro.py')), '--data', tmp, '--', sys.executable, str(script), '{output}']
            good = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertEqual(json.loads(good.stdout)['runs'], 5)
            bad = subprocess.run(cmd+['vary'], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1, bad.stderr)
            self.assertEqual(json.loads(bad.stdout)['differences'][0]['run'], 3)

if __name__ == '__main__':
    unittest.main()
