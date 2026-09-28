from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "brazil_monetary_policy_monitor"


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_monolithic_pipeline_and_ingestion_modules_do_not_exist(self) -> None:
        self.assertFalse((PACKAGE / "pipeline.py").exists())
        self.assertFalse((PACKAGE / "ingestion.py").exists())
        self.assertTrue((PACKAGE / "pipelines").is_dir())
        self.assertTrue((PACKAGE / "ingestion").is_dir())

    def test_source_and_tests_do_not_import_removed_monoliths(self) -> None:
        patterns = (
            re.compile(r"brazil_monetary_policy_monitor\.pipeline(?:\s|$)"),
            re.compile(r"brazil_monetary_policy_monitor\.ingestion(?:\s|$)"),
            re.compile(r"from \.pipeline import"),
            re.compile(r"from \.ingestion import"),
        )
        offenders: list[str] = []
        for root in (PACKAGE, ROOT / "tests"):
            for path in root.rglob("*.py"):
                source = path.read_text(encoding="utf-8")
                if any(pattern.search(source) for pattern in patterns):
                    offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_range_defaults_have_one_frontend_source_of_truth(self) -> None:
        config = (ROOT / "web/js/config.js").read_text(encoding="utf-8")
        self.assertIn("export const DEFAULT_RANGES", config)
        self.assertIn('monetaryPolicy: "10"', config)
        self.assertIn('indicatorDetails: "5"', config)
        for relative in (
            "web/js/indicator_details.js",
            "web/js/views/overview.js",
            "web/js/views/credit.js",
            "web/js/views/fiscal.js",
            "web/js/views/external.js",
            "web/js/views/us.js",
        ):
            source = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("DEFAULT_RANGES", source, relative)


    def test_legacy_tesouro_yield_curve_stack_is_removed(self) -> None:
        removed = (
            PACKAGE / "collectors" / "tesouro_direto.py",
            PACKAGE / "ingestion" / "tesouro.py",
            PACKAGE / "db" / "yield_curve.py",
            PACKAGE / "models" / "yield_curve.py",
            PACKAGE / "pipelines" / "yield_curve.py",
            ROOT / "scripts" / "update-yield-curve.sh",
        )
        for path in removed:
            with self.subTest(path=path.name):
                self.assertFalse(path.exists())
        migrations = "\n".join(path.read_text(encoding="utf-8") for path in (PACKAGE / "db" / "migrations").glob("*.sql"))
        self.assertNotIn("yield_curve_quotes", migrations)

    def test_indicator_input_contract_uses_public_labels(self) -> None:
        helper = (PACKAGE / "publish" / "indicator_contract.py").read_text(encoding="utf-8")
        details = (ROOT / "web/js/indicator_details.js").read_text(encoding="utf-8")
        self.assertIn('"label": label', helper)
        overview = (ROOT / "web/js/views/overview.js").read_text(encoding="utf-8")
        self.assertIn("value.label", details)
        self.assertNotIn("item.textContent = value;", details)
        self.assertNotIn("INDICATOR_INPUTS", overview)

    def test_indicator_metadata_contract_never_humanizes_unknown_machine_values_in_browser(self) -> None:
        helper = (PACKAGE / "publish" / "indicator_contract.py").read_text(encoding="utf-8")
        details = (ROOT / "web/js/indicator_details.js").read_text(encoding="utf-8")
        formatting = (ROOT / "web/js/format.js").read_text(encoding="utf-8")
        self.assertIn("FREQUENCY_LABELS", helper)
        self.assertIn("TRANSFORMATION_LABELS", helper)
        self.assertIn("missing public label for indicator frequency", helper)
        self.assertIn("missing public label for indicator transformation", helper)
        self.assertIn("publicMetadataLabel(indicator.frequency)", details)
        self.assertIn("publicMetadataLabel(indicator.transformation)", details)
        self.assertNotIn('replaceAll("_", " ")', details)
        self.assertNotIn('indicator.key ?? "Indicador"', details)
        self.assertNotIn("] ?? unit ??", formatting)
        self.assertNotIn("] ?? kind ??", formatting)

    def test_caveats_and_input_references_use_distinct_renderers(self) -> None:
        details = (ROOT / "web/js/indicator_details.js").read_text(encoding="utf-8")
        self.assertIn("referenceListSection", details)
        self.assertIn("textListSection", details)
        self.assertIn('textListSection("Ressalvas"', details)

    def test_analytical_tables_are_height_bounded_with_sticky_headers(self) -> None:
        css = (ROOT / "web/css/app.css").read_text(encoding="utf-8")
        self.assertIn(".data-table-panel > .table-wrap", css)
        self.assertIn("max-height: 24rem", css)
        self.assertIn("overflow: auto", css)
        self.assertIn("position: sticky", css)

    def test_indicator_details_do_not_use_semantic_fallbacks(self) -> None:
        source = (ROOT / "web/js/indicator_details.js").read_text(encoding="utf-8")
        self.assertNotIn("indicator.description", source)
        self.assertNotIn("indicator.note", source)
        self.assertIn("indicator.definition", source)
        self.assertIn("indicator.interpretation", source)
        self.assertIn("indicator.methodology", source)
        self.assertIn("indicator.caveats", source)
        self.assertIn("indicator.inputs", source)
        self.assertIn("indicator.missing_inputs", source)


if __name__ == "__main__":
    unittest.main()
