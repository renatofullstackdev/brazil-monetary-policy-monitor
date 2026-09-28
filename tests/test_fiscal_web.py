from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


class FiscalWebTests(unittest.TestCase):
    def test_shell_exposes_fiscal_flow_debt_and_profile_sections(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="fiscal-chart"', html)
        self.assertIn('data-fiscal-mode="flows"', html)
        self.assertIn('data-fiscal-mode="debt"', html)
        self.assertIn('>Estoques<', html)
        self.assertIn('id="fiscal-profile-metrics"', html)
        self.assertIn('id="fiscal-composition"', html)

    def test_fiscal_contract_is_loaded_as_static_json(self) -> None:
        data = (ROOT / "web" / "js" / "data.js").read_text(encoding="utf-8")
        app = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('./data/fiscal.json', data)
        self.assertIn('loadFiscal', app)
        self.assertNotIn('api.bcb.gov.br', data)


    @unittest.skipUnless(NODE, "Node.js is optional; fiscal loader contract test skipped")
    def test_fiscal_loader_accepts_structurally_valid_contract_without_version(self) -> None:
        javascript = r"""
globalThis.fetch = async () => ({
  ok: true,
  status: 200,
  json: async () => ({ view: "fiscal", flows: [], debt_positions: [], dpf_profile: {} }),
});
const { loadFiscal } = await import("./web/js/data.js");
const payload = await loadFiscal("./data/fiscal.json");
console.log(JSON.stringify(payload));
"""
        completed = subprocess.run(
            [NODE, "--input-type=module", "-e", javascript],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["view"], "fiscal")
        self.assertNotIn("schema_version", payload)

    @unittest.skipUnless(NODE, "Node.js is optional; fiscal loader contract test skipped")
    def test_fiscal_loader_rejects_invalid_structure(self) -> None:
        javascript = r"""
globalThis.fetch = async () => ({
  ok: true,
  status: 200,
  json: async () => ({ view: "fiscal", flows: [] }),
});
const { loadFiscal } = await import("./web/js/data.js");
try {
  await loadFiscal("./data/fiscal.json");
  process.exit(2);
} catch (error) {
  console.log(error.message);
}
"""
        completed = subprocess.run(
            [NODE, "--input-type=module", "-e", javascript],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("Contrato fiscal sem debt_positions válido", completed.stdout)

    def test_copy_keeps_dbgg_dpf_and_causality_distinct(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8").lower()
        view = (ROOT / "web" / "js" / "views" / "fiscal.js").read_text(encoding="utf-8").lower()
        self.assertIn("são canais diferentes", html)
        self.assertIn("não atribui os juros nominais exclusivamente à selic", html)
        self.assertIn("dpf, dbgg, dlgg e dlsp têm coberturas e metodologias distintas", html)
        self.assertIn("dbgg mede exposição bruta", view)
        self.assertIn("dlgg", view)
        self.assertIn("dlsp", view)


if __name__ == "__main__":
    unittest.main()
