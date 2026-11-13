import unittest
from pathlib import Path
from shared_map import parse_line, integer, fingerprint

class DecimalLogTests(unittest.TestCase):
    def test_actual_game_snapshots(self):
        lines=Path(__file__).with_name('real_snapshots.txt').read_text().splitlines()
        first,last=map(parse_line,lines)
        self.assertEqual(first['seed'],7062026)
        self.assertEqual(first['level'],0)
        self.assertEqual(len(first['nodes']),21)
        self.assertEqual(first['position'],[82,261])
        self.assertEqual(last['position'],[43,168])
        self.assertEqual(fingerprint(first),fingerprint(last))
    def test_integral_decimal_only(self):
        for value in ['7062026.0',7062026.0,'0.0','123.000']:
            self.assertEqual(integer(value,0,4294967295),int(float(value)))
        for value in ['1.5','nan','inf','1e3',True,'4294967296.0','1.000001']:
            with self.assertRaises(ValueError): integer(value,0,4294967295)
