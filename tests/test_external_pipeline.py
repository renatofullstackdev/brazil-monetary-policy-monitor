from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import parse_qs, urlparse
import unittest

from brazil_monetary_policy_monitor.external_series import EXTERNAL_SERIES
from brazil_monetary_policy_monitor.pipelines.external import update_external_context


CODE_RE = re.compile(r"bcdata\.sgs\.(\d+)/")


def month_sequence(start_year: int, start_month: int, count: int):
    year, month = start_year, start_month
    for _ in range(count):
        yield date(year, month, 1)
        month += 1
        if month == 13:
            year += 1
            month = 1


DATES = list(month_sequence(2024, 1, 33))


def external_value(code: int, index: int) -> float:
    if code == 1:
        return 4.80 + index * 0.02
    if code == 13982:
        return 350_000.0 + index * 250.0
    if code == 11752:
        return 105.0 + index * 0.25
    if code == 23079:
        return -2.5 - index * 0.01
    if code == 23080:
        return 3.0 + index * 0.01
    if code == 22924:
        return -500.0 + index * 50.0
    raise AssertionError(code)


def fake_external_fetch(url: str) -> bytes:
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
            rows.append({
                "data": reference.strftime("%d/%m/%Y"),
                "valor": str(external_value(code, index)).replace(".", ","),
            })
    return json.dumps(rows).encode("utf-8")


class ExternalPipelineTests(unittest.TestCase):
    def test_pipeline_collects_six_series_and_publishes_external_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 9, 23, 15, tzinfo=timezone.utc)
            result = update_external_context(
                database_path=root / "monitor.sqlite3",
                raw_root=root / "raw",
                published_dir=root / "published",
                external_output_path=root / "web" / "external-sector.json",
                start=date(2024, 1, 1),
                end=date(2026, 9, 23),
                fetcher=fake_external_fetch,
                clock=lambda: now,
            )
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(len(result["series"]), len(EXTERNAL_SERIES))
            payload = json.loads((root / "web" / "external-sector.json").read_text())
            self.assertEqual(payload["schema_version"], 4)
            self.assertEqual(payload["view"], "external_sector")
            self.assertEqual(set(payload["groups"]), {
                "fx_nominal", "fx_real", "external_balance", "portfolio", "reserves"
            })
            self.assertEqual(payload["status"], "available")

    def test_contract_derives_fx_changes_and_descriptive_idp_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 9, 23, 15, tzinfo=timezone.utc)
            update_external_context(
                database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                published_dir=root / "published", external_output_path=root / "external.json",
                start=date(2024, 1, 1), end=date(2026, 9, 23),
                fetcher=fake_external_fetch, clock=lambda: now,
            )
            payload = json.loads((root / "external.json").read_text())
            nominal = payload["groups"]["fx_nominal"]["metrics"]
            self.assertEqual(nominal[1]["data_kind"], "derived")
            self.assertEqual(nominal[1]["unit"], "percent_change")
            self.assertTrue(nominal[1]["observations"])

            balance = payload["groups"]["external_balance"]["metrics"]
            coverage = balance[2]
            self.assertEqual(coverage["data_kind"], "derived")
            self.assertIn("não uma identidade de financiamento", coverage["interpretation"])
            expected = external_value(23080, 32) / abs(external_value(23079, 32)) * 100.0
            self.assertAlmostEqual(coverage["latest"]["value"], expected, places=10)

    def test_provider_failure_does_not_replace_existing_external_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "external.json"
            output.write_text('{"sentinel": true}\n', encoding="utf-8")

            def fail_midway(url: str) -> bytes:
                if "bcdata.sgs.23080/" in url:
                    raise RuntimeError("provider down")
                return fake_external_fetch(url)

            with self.assertRaises(RuntimeError):
                update_external_context(
                    database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                    published_dir=root / "published", external_output_path=output,
                    start=date(2024, 1, 1), end=date(2026, 9, 23),
                    fetcher=fail_midway,
                    clock=lambda: datetime(2026, 9, 23, 15, tzinfo=timezone.utc),
                )
            self.assertEqual(json.loads(output.read_text()), {"sentinel": True})

    def test_recollection_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kwargs = dict(
                database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                published_dir=root / "published", external_output_path=root / "external.json",
                start=date(2024, 1, 1), end=date(2026, 9, 23), fetcher=fake_external_fetch,
                clock=lambda: datetime(2026, 9, 23, 15, tzinfo=timezone.utc),
            )
            first = update_external_context(**kwargs)
            second = update_external_context(**kwargs)
            self.assertTrue(all(item["records_inserted"] == len(DATES) for item in first["series"]))
            self.assertTrue(all(item["records_inserted"] == 0 for item in second["series"]))
            self.assertTrue(all(item["records_unchanged"] == len(DATES) for item in second["series"]))

    def test_raw_snapshots_are_kept_for_every_external_series(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            update_external_context(
                database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                published_dir=root / "published", external_output_path=root / "external.json",
                start=date(2024, 1, 1), end=date(2026, 9, 23), fetcher=fake_external_fetch,
                clock=lambda: datetime(2026, 9, 23, 15, tzinfo=timezone.utc),
            )
            for spec in EXTERNAL_SERIES:
                manifests = list((root / "raw").rglob(f"sgs-{spec.code}/run-*/manifest.json"))
                self.assertEqual(len(manifests), 1, spec.key)


if __name__ == "__main__":
    unittest.main()
