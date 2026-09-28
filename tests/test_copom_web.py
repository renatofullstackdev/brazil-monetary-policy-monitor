from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CopomWebTests(unittest.TestCase):
    def test_shell_exposes_policy_communication_chronology(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="copom-recent"', html)
        self.assertIn('id="copom-upcoming"', html)
        self.assertIn("O que mudou nas decisões e na comunicação do Copom?", html)
        self.assertIn('id="copom-recent-toggle"', html)
        self.assertIn('id="copom-upcoming-toggle"', html)

    def test_static_contract_is_loaded_and_vintages_route_copom_file(self) -> None:
        data = (ROOT / "web" / "js" / "data.js").read_text(encoding="utf-8")
        vintage = (ROOT / "web" / "js" / "vintage.js").read_text(encoding="utf-8")
        self.assertIn("./data/copom-events.json", data)
        self.assertIn('copom: "copom-events.json"', vintage)
        self.assertNotIn("api/servico/sitebcb/copom", data)

    def test_history_chart_supports_decision_markers_without_causal_copy(self) -> None:
        chart = (ROOT / "web" / "js" / "charts" / "history.js").read_text(encoding="utf-8")
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("policy-event-line", chart)
        self.assertIn("policy-event-marker", chart)
        self.assertIn("sem atribuir a elas, isoladamente", html)


if __name__ == "__main__":
    unittest.main()
