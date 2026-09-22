from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WebShellTests(unittest.TestCase):
    def test_overview_shell_has_accessible_structural_landmarks(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        for marker in (
            'lang="pt-BR"',
            '<main id="conteudo"',
            'id="primary-cards"',
            'id="assumption-cards"',
            'id="history-chart"',
            'id="metadata-dialog"',
            'aria-live="polite"',
        ):
            self.assertIn(marker, html)

    def test_frontend_has_no_runtime_cdn_dependency(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('<script src="http', html)
        self.assertNotIn('<link rel="stylesheet" href="http', html)

    def test_data_loader_reads_only_published_overview_contract(self) -> None:
        source = (ROOT / "web" / "js" / "data.js").read_text(encoding="utf-8")
        self.assertIn('./data/overview.json', source)
        self.assertNotIn('api.bcb.gov.br', source)
        self.assertNotIn('sidra', source.lower())


if __name__ == "__main__":
    unittest.main()
