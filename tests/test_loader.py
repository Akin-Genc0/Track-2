import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'system'))
from data import as_list, normalize, read_jsonl

class LoaderTests(unittest.TestCase):
    def test_encoded(self):
        self.assertEqual(as_list('["a", "b"]'), ['a', 'b'])
        self.assertEqual(as_list('a;b'), ['a', 'b'])
    def test_envelope(self):
        r = normalize({'record': {'id': 'H1', 'date_of_birth': ['1980']}}, 'hits')
        self.assertEqual(r['hit_id'], 'H1')
        self.assertEqual(r['dobs'], ['1980'])
    def test_bad_lines(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'x'
            p.write_text('\ufeff{}\r\n\n{bad\nnull\n[]\n{"id":1}\n')
            self.assertEqual(read_jsonl(p), [{}, {'id': 1}])

if __name__ == '__main__': unittest.main()
