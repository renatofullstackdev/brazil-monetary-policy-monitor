from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class USWebTests(unittest.TestCase):
    def test_us_section_and_generic_details_are_wired(self):
        html=(ROOT/'web/index.html').read_text(); app=(ROOT/'web/js/app.js').read_text(); view=(ROOT/'web/js/views/us.js').read_text(); data=(ROOT/'web/js/data.js').read_text()
        self.assertIn('id="us-title"',html); self.assertIn('Brasil × EUA',html)
        self.assertIn('loadUSBenchmark',app); self.assertIn('renderUS',app); self.assertIn('us_benchmark',data)
        self.assertIn('openIndicatorDetails',view); self.assertIn('renderExternalChart',view)
    def test_us_layout_has_containment_hooks(self):
        css=(ROOT/'web/css/app.css').read_text(); self.assertIn('.us-chart svg { overflow: hidden; }',css); self.assertIn('.metric-grid-us',css)
if __name__=='__main__': unittest.main()
