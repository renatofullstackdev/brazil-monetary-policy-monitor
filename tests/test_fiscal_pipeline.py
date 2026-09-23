from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import parse_qs, urlparse
import unittest

from brazil_monetary_policy_monitor.fiscal_series import FISCAL_SERIES
from brazil_monetary_policy_monitor.pipeline import update_fiscal_context


CODE_RE = re.compile(r"bcdata\.sgs\.(\d+)/")


def month_sequence(start_year: int, start_month: int, count: int):
    year, month = start_year, start_month
    for _ in range(count):
        yield date(year, month, 1)
        month += 1
        if month == 13:
            year += 1
            month = 1


DATES = list(month_sequence(2024, 8, 25))


def fiscal_value(code: int, index: int) -> float:
    if code == 5793:
        return 0.5 + index * 0.02
    if code == 5760:
        return 6.0 + index * 0.03
    if code == 5727:
        return 6.5 + index * 0.05
    if code == 13762:
        return 75.0 + index * 0.15
    raise AssertionError(code)


def fake_fiscal_fetch(url: str) -> bytes:
    match = CODE_RE.search(url)
    if match is None:
        raise AssertionError(f"unexpected URL: {url}")
    code = int(match.group(1))
    query = parse_qs(urlparse(url).query)
    start = datetime.strptime(query["dataInicial"][0], "%d/%m/%Y").date()
    end = datetime.strptime(query["dataFinal"][0], "%d/%m/%Y").date()
    rows = []
    for index, reference in enumerate(DATES):
        if start <= reference <= end:
            rows.append({"data": reference.strftime("%d/%m/%Y"), "valor": str(fiscal_value(code, index)).replace(".", ",")})
    return json.dumps(rows).encode("utf-8")


class FiscalPipelineTests(unittest.TestCase):
    def test_pipeline_collects_four_bcb_series_and_publishes_rmd_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = update_fiscal_context(
                database_path=root / "monitor.sqlite3",
                raw_root=root / "raw",
                published_dir=root / "published",
                fiscal_output_path=root / "web" / "fiscal.json",
                start=date(2024, 8, 1),
                end=date(2026, 8, 31),
                fetcher=fake_fiscal_fetch,
                clock=lambda: datetime(2026, 9, 22, 20, tzinfo=timezone.utc),
            )
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(len(result["series"]), len(FISCAL_SERIES))
            payload = json.loads((root / "web" / "fiscal.json").read_text())
            self.assertEqual(payload["view"], "fiscal")
            self.assertEqual(len(payload["flows"]), 3)
            self.assertEqual(payload["debt"]["source"]["sgs_code"], 13762)
            self.assertEqual(payload["dpf_profile"]["reference_period"], "2026-07")
            self.assertEqual(payload["dpf_profile"]["metrics"]["br.dpf.average_term_years"]["value"], 4.05)

    def test_contract_preserves_nfsp_sign_convention_and_noncausal_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            update_fiscal_context(
                database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                published_dir=root / "published", fiscal_output_path=root / "fiscal.json",
                start=date(2024, 8, 1), end=date(2026, 8, 31), fetcher=fake_fiscal_fetch,
                clock=lambda: datetime(2026, 9, 22, 20, tzinfo=timezone.utc),
            )
            payload = json.loads((root / "fiscal.json").read_text())
            self.assertEqual(payload["sign_convention"]["nfsp"], "positive_deficit_negative_surplus")
            self.assertIn("não são tratados", payload["sign_convention"]["note"])

    def test_provider_failure_does_not_replace_existing_fiscal_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "fiscal.json"
            output.write_text('{"sentinel": true}\n', encoding="utf-8")
            def fail(url: str) -> bytes:
                if "bcdata.sgs.5727/" in url:
                    raise RuntimeError("provider down")
                return fake_fiscal_fetch(url)
            with self.assertRaises(RuntimeError):
                update_fiscal_context(
                    database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                    published_dir=root / "published", fiscal_output_path=output,
                    start=date(2024, 8, 1), end=date(2026, 8, 31), fetcher=fail,
                    clock=lambda: datetime(2026, 9, 22, 20, tzinfo=timezone.utc),
                )
            self.assertEqual(json.loads(output.read_text()), {"sentinel": True})

    def test_recollection_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kwargs = dict(
                database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                published_dir=root / "published", fiscal_output_path=root / "fiscal.json",
                start=date(2024, 8, 1), end=date(2026, 8, 31), fetcher=fake_fiscal_fetch,
                clock=lambda: datetime(2026, 9, 22, 20, tzinfo=timezone.utc),
            )
            first = update_fiscal_context(**kwargs)
            second = update_fiscal_context(**kwargs)
            self.assertTrue(all(item["records_inserted"] == 25 for item in first["series"]))
            self.assertTrue(all(item["records_inserted"] == 0 for item in second["series"]))
            self.assertEqual(second["profile_inputs_inserted"], 0)

    def test_snapshots_exist_for_each_fiscal_series(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            update_fiscal_context(
                database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                published_dir=root / "published", fiscal_output_path=root / "fiscal.json",
                start=date(2024, 8, 1), end=date(2026, 8, 31), fetcher=fake_fiscal_fetch,
                clock=lambda: datetime(2026, 9, 22, 20, tzinfo=timezone.utc),
            )
            for spec in FISCAL_SERIES:
                self.assertEqual(len(list((root / "raw").rglob(f"sgs-{spec.code}/run-*/manifest.json"))), 1)


if __name__ == "__main__":
    unittest.main()
