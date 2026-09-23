from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import parse_qs, urlparse
import unittest

from brazil_monetary_policy_monitor.credit_series import CREDIT_SERIES
from brazil_monetary_policy_monitor.db import initialize_database
from brazil_monetary_policy_monitor.ingestion import (
    ensure_bcb_sgs_series_metadata,
    persist_sgs_records,
    start_ingestion_run,
)
from brazil_monetary_policy_monitor.macro_series import MACRO_SERIES_BY_KEY
from brazil_monetary_policy_monitor.collectors.bcb_sgs import SGSRecord
from brazil_monetary_policy_monitor.pipeline import update_credit_context
from brazil_monetary_policy_monitor.publish.credit_transmission import build_credit_transmission_document
from decimal import Decimal


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


def credit_value(code: int, index: int) -> float:
    if code == 20542:
        return 1000.0 + index * 15.0
    if code == 20593:
        return 900.0 + index * 8.0
    if code == 20717:
        return 40.0 + index * 0.1
    if code == 20756:
        return 10.0 + index * 0.05
    if code == 21085:
        return 4.2 - index * 0.01
    if code == 21132:
        return 1.4 + index * 0.005
    raise AssertionError(code)


def fake_credit_fetch(url: str) -> bytes:
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
            rows.append(
                {
                    "data": reference.strftime("%d/%m/%Y"),
                    "valor": str(credit_value(code, index)).replace(".", ","),
                }
            )
    return json.dumps(rows).encode("utf-8")


def seed_ipca(connection, root: Path, now: datetime) -> None:
    spec = MACRO_SERIES_BY_KEY["br.ipca.monthly"]
    source_id, series_id = ensure_bcb_sgs_series_metadata(connection, spec)
    run_id = start_ingestion_run(connection, source_id=source_id, started_at=now)
    records = [SGSRecord(reference, Decimal("0.20")) for reference in DATES]
    persist_sgs_records(
        connection,
        series_id=series_id,
        run_id=run_id,
        records=records,
        retrieved_at=now,
    )


class CreditPipelineTests(unittest.TestCase):
    def test_pipeline_collects_all_credit_series_and_publishes_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 9, 22, 15, tzinfo=timezone.utc)
            result = update_credit_context(
                database_path=root / "monitor.sqlite3",
                raw_root=root / "raw",
                published_dir=root / "published",
                credit_output_path=root / "web" / "credit-transmission.json",
                start=date(2024, 8, 1),
                end=date(2026, 8, 31),
                fetcher=fake_credit_fetch,
                clock=lambda: now,
            )
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(len(result["series"]), len(CREDIT_SERIES))
            payload = json.loads((root / "web" / "credit-transmission.json").read_text())
            self.assertEqual(payload["view"], "credit_transmission")
            self.assertEqual(payload["groups"]["interest_rates"]["series"][0]["status"], "available")
            self.assertEqual(payload["groups"]["real_growth"]["series"][0]["status"], "unavailable")

    def test_real_credit_growth_uses_same_interval_ipca(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime(2026, 9, 22, 15, tzinfo=timezone.utc)
            update_credit_context(
                database_path=root / "monitor.sqlite3",
                raw_root=root / "raw",
                published_dir=root / "published",
                credit_output_path=root / "credit.json",
                start=date(2024, 8, 1), end=date(2026, 8, 31),
                fetcher=fake_credit_fetch, clock=lambda: now,
            )
            connection = initialize_database(root / "monitor.sqlite3")
            seed_ipca(connection, root, now)
            document = build_credit_transmission_document(connection, generated_at=now)
            free = document["groups"]["real_growth"]["series"][0]
            self.assertEqual(free["status"], "available")
            self.assertEqual(free["latest"]["date"], "2026-08-01")
            current = credit_value(20542, 24)
            previous = credit_value(20542, 12)
            inflation = (1.002 ** 12 - 1.0) * 100.0
            expected = ((current / previous) / (1.0 + inflation / 100.0) - 1.0) * 100.0
            self.assertAlmostEqual(free["latest"]["value"], expected, places=10)
            connection.close()

    def test_provider_failure_does_not_replace_existing_credit_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "credit.json"
            output.write_text('{"sentinel": true}\n', encoding="utf-8")

            def fail_midway(url: str) -> bytes:
                if "bcdata.sgs.20756/" in url:
                    raise RuntimeError("provider down")
                return fake_credit_fetch(url)

            with self.assertRaises(RuntimeError):
                update_credit_context(
                    database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                    published_dir=root / "published", credit_output_path=output,
                    start=date(2024, 8, 1), end=date(2026, 8, 31),
                    fetcher=fail_midway,
                    clock=lambda: datetime(2026, 9, 22, 15, tzinfo=timezone.utc),
                )
            self.assertEqual(json.loads(output.read_text()), {"sentinel": True})

    def test_recollection_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            kwargs = dict(
                database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                published_dir=root / "published", credit_output_path=root / "credit.json",
                start=date(2024, 8, 1), end=date(2026, 8, 31), fetcher=fake_credit_fetch,
                clock=lambda: datetime(2026, 9, 22, 15, tzinfo=timezone.utc),
            )
            first = update_credit_context(**kwargs)
            second = update_credit_context(**kwargs)
            self.assertTrue(all(item["records_inserted"] == 25 for item in first["series"]))
            self.assertTrue(all(item["records_inserted"] == 0 for item in second["series"]))
            self.assertTrue(all(item["records_unchanged"] == 25 for item in second["series"]))

    def test_raw_snapshot_is_kept_for_each_credit_series(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            update_credit_context(
                database_path=root / "monitor.sqlite3", raw_root=root / "raw",
                published_dir=root / "published", credit_output_path=root / "credit.json",
                start=date(2024, 8, 1), end=date(2026, 8, 31), fetcher=fake_credit_fetch,
                clock=lambda: datetime(2026, 9, 22, 15, tzinfo=timezone.utc),
            )
            for spec in CREDIT_SERIES:
                manifests = list((root / "raw").rglob(f"sgs-{spec.code}/run-*/manifest.json"))
                self.assertEqual(len(manifests), 1, spec.key)


if __name__ == "__main__":
    unittest.main()
