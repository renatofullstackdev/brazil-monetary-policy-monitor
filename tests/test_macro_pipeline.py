from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import parse_qs, urlparse
import unittest

from brazil_monetary_policy_monitor.collectors.http import ProviderFetchError
from brazil_monetary_policy_monitor.db import initialize_database
from brazil_monetary_policy_monitor.macro_series import MACRO_SERIES
from brazil_monetary_policy_monitor.collectors.bcb_sgs import SGSRecord
from brazil_monetary_policy_monitor.pipeline import (
    _coalesce_identical_cross_chunk_records,
    update_macro_context,
)
from brazil_monetary_policy_monitor.publish import build_overview_document


CODE_RE = re.compile(r"bcdata\.sgs\.(\d+)/")


def monthly_payload(code: int) -> bytes:
    values = {
        433: [0.20] * 12,
        10844: [0.30] * 12,
        11426: [0.25] * 12,
        24364: [100.0 + index for index in range(12)],
        24369: [6.5 - index * 0.02 for index in range(12)],
        24380: [3200.0 + index * 10 for index in range(12)],
    }[code]
    rows = []
    year, month = 2025, 9
    for value in values:
        rows.append({"data": f"01/{month:02d}/{year}", "valor": str(value).replace(".", ",")})
        month += 1
        if month == 13:
            month = 1
            year += 1
    return json.dumps(rows, ensure_ascii=False).encode("utf-8")


def fake_fetch(url: str) -> bytes:
    match = CODE_RE.search(url)
    if match is None:
        raise AssertionError(f"unexpected URL: {url}")
    return monthly_payload(int(match.group(1)))


class MacroPipelineTests(unittest.TestCase):
    def test_pipeline_collects_all_registered_series_and_policy_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clock = lambda: datetime(2026, 9, 22, 15, tzinfo=timezone.utc)
            result = update_macro_context(
                database_path=root / "monitor.sqlite3",
                raw_root=root / "raw",
                published_dir=root / "published",
                overview_path=root / "web" / "overview.json",
                start=date(2025, 9, 1), end=date(2026, 8, 31),
                fetcher=fake_fetch, clock=clock,
            )
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(len(result["series"]), len(MACRO_SERIES))
            self.assertEqual(result["policy_inputs_inserted"], 3)
            connection = initialize_database(root / "monitor.sqlite3")
            keys = {row[0] for row in connection.execute("SELECT key FROM series")}
            self.assertTrue({spec.key for spec in MACRO_SERIES}.issubset(keys))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM parameters").fetchone()[0], 3)
            connection.close()

    def test_overview_derives_macro_context_without_changing_source_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 9, 22, 15, tzinfo=timezone.utc)
            update_macro_context(
                database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                published_dir=root / "published", overview_path=root / "overview.json",
                start=date(2025, 9, 1), end=date(2026, 8, 31), fetcher=fake_fetch, clock=lambda: now,
            )
            connection = initialize_database(root / "monitor.sqlite3")
            document = build_overview_document(connection, generated_at=now)
            self.assertEqual(document["series"]["ipca_12m"]["status"], "available")
            self.assertAlmostEqual(document["series"]["ipca_12m"]["latest"]["value"], (1.002**12 - 1) * 100, places=8)
            self.assertEqual(document["series"]["unemployment_rate"]["data_kind"], "observed")
            self.assertEqual(document["series"]["real_earnings"]["unit"], "brl_real")
            self.assertAlmostEqual(document["series"]["ibc_br_mom"]["latest"]["value"], (111 / 110 - 1) * 100, places=8)
            raw_ipca = connection.execute(
                """SELECT COUNT(*) FROM observations o JOIN series s ON s.id=o.series_id WHERE s.key='br.ipca.monthly'"""
            ).fetchone()[0]
            self.assertEqual(raw_ipca, 12)
            connection.close()

    def test_provider_failure_does_not_replace_existing_overview(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            overview = root / "overview.json"
            overview.write_text('{"sentinel": true}\n', encoding="utf-8")

            def fail_on_core(url: str) -> bytes:
                if "bcdata.sgs.11426/" in url:
                    raise RuntimeError("provider down")
                return fake_fetch(url)

            with self.assertRaises(RuntimeError):
                update_macro_context(
                    database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                    published_dir=root / "published", overview_path=overview,
                    start=date(2025, 9, 1), end=date(2026, 8, 31), fetcher=fail_on_core,
                    clock=lambda: datetime(2026, 9, 22, 15, tzinfo=timezone.utc),
                )
            self.assertEqual(json.loads(overview.read_text()), {"sentinel": True})

    def test_raw_snapshots_are_kept_per_sgs_series(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            update_macro_context(
                database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                published_dir=root / "published", overview_path=root / "overview.json",
                start=date(2025, 9, 1), end=date(2026, 8, 31), fetcher=fake_fetch,
                clock=lambda: datetime(2026, 9, 22, 15, tzinfo=timezone.utc),
            )
            for spec in MACRO_SERIES:
                manifests = list((root / "raw").rglob(f"sgs-{spec.code}/run-*/manifest.json"))
                self.assertEqual(len(manifests), 1, spec.key)

    def test_recollection_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kwargs = dict(
                database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                published_dir=root / "published", overview_path=root / "overview.json",
                start=date(2025, 9, 1), end=date(2026, 8, 31), fetcher=fake_fetch,
                clock=lambda: datetime(2026, 9, 22, 15, tzinfo=timezone.utc),
            )
            first = update_macro_context(**kwargs)
            second = update_macro_context(**kwargs)
            self.assertTrue(all(item["records_inserted"] == 12 for item in first["series"]))
            self.assertTrue(all(item["records_inserted"] == 0 for item in second["series"]))
            self.assertTrue(all(item["records_unchanged"] == 12 for item in second["series"]))
            self.assertEqual(second["policy_inputs_unchanged"], 3)

    def test_incremental_empty_sgs_window_is_a_valid_zero_record_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 9, 22, 15, tzinfo=timezone.utc)
            empty_body = b'{"erro":{"statusCode":404,"detail":"br.gov.bcb.pec.sgs.comum.excecoes.SGSNegocioException: Value(s) not found"}}'

            def empty_fetch(url: str) -> bytes:
                raise ProviderFetchError(
                    "failed to fetch empty SGS interval",
                    url=url,
                    status_code=404,
                    response_body=empty_body,
                )

            result = update_macro_context(
                database_path=root / "monitor.sqlite3",
                raw_root=root / "raw",
                published_dir=root / "published",
                overview_path=root / "overview.json",
                start=date(2026, 9, 18),
                end=date(2026, 9, 22),
                fetcher=empty_fetch,
                clock=lambda: now,
            )

            self.assertEqual(result["status"], "succeeded")
            self.assertTrue(all(item["records_received"] == 0 for item in result["series"]))
            snapshots = list((root / "raw").rglob("chunk-*.json"))
            self.assertEqual(len(snapshots), len(MACRO_SERIES))
            self.assertIn("Value(s) not found", snapshots[0].read_text(encoding="utf-8"))

    def test_unrelated_sgs_404_remains_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def missing_endpoint(url: str) -> bytes:
                raise ProviderFetchError(
                    "missing endpoint",
                    url=url,
                    status_code=404,
                    response_body=b'{"erro":{"statusCode":404,"detail":"Series not found"}}',
                )

            with self.assertRaises(ProviderFetchError):
                update_macro_context(
                    database_path=root / "monitor.sqlite3",
                    raw_root=root / "raw",
                    published_dir=root / "published",
                    overview_path=root / "overview.json",
                    start=date(2026, 9, 18),
                    end=date(2026, 9, 22),
                    fetcher=missing_endpoint,
                    clock=lambda: datetime(2026, 9, 22, 15, tzinfo=timezone.utc),
                )

    def test_monthly_queries_align_explicit_start_to_first_day_of_month(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            urls: list[str] = []

            def capture_empty(url: str) -> bytes:
                urls.append(url)
                return b"[]"

            update_macro_context(
                database_path=root / "monitor.sqlite3",
                raw_root=root / "raw",
                published_dir=root / "published",
                overview_path=root / "overview.json",
                start=date(2021, 9, 18),
                end=date(2023, 9, 22),
                fetcher=capture_empty,
                clock=lambda: datetime(2026, 9, 22, 15, tzinfo=timezone.utc),
                window_years=1,
            )

            first_series_urls = urls[:3]
            intervals = []
            for url in first_series_urls:
                query = parse_qs(urlparse(url).query)
                intervals.append((query["dataInicial"][0], query["dataFinal"][0]))
            self.assertEqual(
                intervals,
                [
                    ("01/09/2021", "31/08/2022"),
                    ("01/09/2022", "31/08/2023"),
                    ("01/09/2023", "22/09/2023"),
                ],
            )

    def test_identical_cross_chunk_month_is_coalesced(self) -> None:
        records = [
            SGSRecord(date(2022, 9, 1), Decimal("0.50")),
            SGSRecord(date(2022, 8, 1), Decimal("0.40")),
            SGSRecord(date(2022, 9, 1), Decimal("0.50")),
        ]

        result = _coalesce_identical_cross_chunk_records(records)

        self.assertEqual(
            result,
            [
                SGSRecord(date(2022, 8, 1), Decimal("0.40")),
                SGSRecord(date(2022, 9, 1), Decimal("0.50")),
            ],
        )

    def test_conflicting_cross_chunk_month_remains_fatal(self) -> None:
        records = [
            SGSRecord(date(2022, 9, 1), Decimal("0.50")),
            SGSRecord(date(2022, 9, 1), Decimal("0.51")),
        ]

        with self.assertRaisesRegex(ValueError, "conflicting duplicate reference date"):
            _coalesce_identical_cross_chunk_records(records)


if __name__ == "__main__":
    unittest.main()
