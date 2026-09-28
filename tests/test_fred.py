from datetime import date
from pathlib import Path
import sys, unittest
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from brazil_monetary_policy_monitor.collectors.fred import build_fred_url, parse_fred_csv

class FredCollectorTests(unittest.TestCase):
    def test_build_url_is_keyless_and_bounded(self):
        url=build_fred_url('DFF',date(2026,1,1),date(2026,9,23))
        self.assertIn('id=DFF',url); self.assertIn('cosd=2026-01-01',url); self.assertIn('coed=2026-09-23',url)
        self.assertNotIn('api_key',url)
    def test_parse_graph_csv_skips_missing_values(self):
        payload=b'observation_date,DFF\n2026-09-20,.\n2026-09-21,3.88\n'
        rows=parse_fred_csv(payload,series_id='DFF')
        self.assertEqual(len(rows),1); self.assertEqual(rows[0].reference_date,date(2026,9,21)); self.assertEqual(str(rows[0].value),'3.88')
    def test_parse_accepts_DATE_header(self):
        rows=parse_fred_csv(b'DATE,DGS2\n2026-09-21,4.76\n',series_id='DGS2')
        self.assertEqual(float(rows[0].value),4.76)
if __name__=='__main__': unittest.main()
