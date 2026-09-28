from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


class StaticContractCompatibilityTests(unittest.TestCase):
    @unittest.skipUnless(NODE, "Node.js is optional; browser contract compatibility test skipped")
    def test_current_publishers_are_accepted_by_current_browser_loaders(self) -> None:
        javascript = r"""
import fs from "node:fs";
globalThis.fetch = async (url) => ({
  ok: true,
  status: 200,
  json: async () => JSON.parse(fs.readFileSync(String(url), "utf8")),
});
const data = await import("./web/js/data.js");
await data.loadOverview("web/data/overview.json");
await data.loadYieldCurve("web/data/yield-curve.json");
await data.loadCreditTransmission("web/data/credit-transmission.json");
await data.loadFiscal("web/data/fiscal.json");
await data.loadExternalSector("web/data/external-sector.json");
await data.loadUSBenchmark("web/data/us-benchmark.json");
await data.loadCopomEvents("web/data/copom-events.json");
console.log("ok");
"""
        completed = subprocess.run(
            [NODE, "--input-type=module", "-e", javascript],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.stdout.strip(), "ok")

    def test_internal_static_contracts_do_not_duplicate_schema_versions(self) -> None:
        data_js = (ROOT / "web" / "js" / "data.js").read_text(encoding="utf-8")
        self.assertNotIn("schema_version", data_js)
        for path in (ROOT / "web" / "data").glob("*.json"):
            with self.subTest(path=path.name):
                self.assertNotIn('"schema_version"', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
