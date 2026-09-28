from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys, tempfile, unittest
from urllib.parse import parse_qs, urlparse
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from brazil_monetary_policy_monitor.pipelines.us import update_us_context

SERIES_DATA={
'DFF':[('2025-03-31','4.25'),('2025-04-01','4.25'),('2026-03-31','3.88')],
'DGS2':[('2025-03-31','4.10'),('2026-03-31','4.70')],
'DGS10':[('2025-03-31','4.30'),('2026-03-31','5.00')],
'DFII10':[('2025-03-31','1.90'),('2026-03-31','2.30')],
'T10YIE':[('2025-03-31','2.40'),('2026-03-31','2.70')],
'PCEPI':[('2024-01-01','120'),('2024-02-01','121'),('2024-03-01','122'),('2025-01-01','123'),('2025-02-01','124'),('2025-03-01','125'),('2026-01-01','127'),('2026-02-01','128'),('2026-03-01','129')],
'GDPC1':[('2025-01-01','23000'),('2026-01-01','24000')],
'GDPPOT':[('2025-01-01','22800'),('2026-01-01','23800')],
}
def fake_fetch(url):
    sid=parse_qs(urlparse(url).query)['id'][0]
    return ('observation_date,'+sid+'\n'+'\n'.join(f'{d},{v}' for d,v in SERIES_DATA[sid])+'\n').encode()
class USPipelineTests(unittest.TestCase):
    def test_pipeline_publishes_us_contract_and_taylor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); out=root/'web/data/us-benchmark.json'
            result=update_us_context(database_path=root/'db.sqlite3',raw_root=root/'raw',published_dir=root/'published',us_output_path=out,start=date(2024,1,1),end=date(2026,3,31),fetcher=fake_fetch,clock=lambda:datetime(2026,9,23,tzinfo=timezone.utc))
            self.assertEqual(result['status'],'succeeded'); self.assertEqual(len(result['series']),8)
            payload=json.loads(out.read_text())
            self.assertEqual(payload['schema_version'],4); self.assertEqual(payload['view'],'us_benchmark')
            self.assertEqual(payload['assumptions']['canonical_rstar'],2.0)
            taylor=payload['groups']['policy']['metrics'][1]
            self.assertEqual(taylor['data_kind'],'derived'); self.assertTrue(taylor['observations'])
            self.assertIn('não a estimativa HLW', ' '.join(taylor['caveats']))
            br_us = {metric['key']: metric for metric in payload['groups']['br_us']['metrics']}
            nominal = br_us['br_us.nominal_10y_spread']
            self.assertEqual(nominal['status'], 'unavailable')
            self.assertEqual(nominal['observations'], [])
            self.assertEqual(nominal['missing_inputs'], [
                {'key': 'br.b3.pre.10y', 'label': 'Curva PRE da B3 em 10 anos'}
            ])
            self.assertTrue(all(isinstance(item, dict) and item.get('label') for item in nominal['inputs']))
    def test_pipeline_snapshots_each_fred_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            update_us_context(database_path=root/'db.sqlite3',raw_root=root/'raw',published_dir=root/'published',us_output_path=root/'us.json',start=date(2024,1,1),end=date(2026,3,31),fetcher=fake_fetch,clock=lambda:datetime(2026,9,23,tzinfo=timezone.utc))
            self.assertTrue(any((root/'raw/fred').rglob('chunk-001.csv')))
if __name__=='__main__': unittest.main()
