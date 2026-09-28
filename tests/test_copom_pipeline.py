from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from brazil_monetary_policy_monitor.db import initialize_database
from brazil_monetary_policy_monitor.pipelines.copom import update_copom_events
from brazil_monetary_policy_monitor.publish.copom import build_copom_events_document
from brazil_monetary_policy_monitor.vintages import end_of_day_cutoff

from test_copom import (
    MINUTES,
    MINUTES_DETAIL,
    RPM_CALENDAR,
    RPM_REPORTS,
    STATEMENTS,
    STATEMENT_DETAIL,
)

NOW = datetime(2026, 9, 23, 15, 0, tzinfo=timezone.utc)


class CopomPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.database = root / "monitor.sqlite3"
        self.raw = root / "raw"
        self.output = root / "web" / "data" / "copom-events.json"
        self.curve = root / "web" / "data" / "yield-curve.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def _fetcher(url: str) -> bytes:
        if "comunicados_detalhes" in url:
            return STATEMENT_DETAIL
        if "atas_detalhes" in url:
            return MINUTES_DETAIL
        if "/copom/comunicados?" in url:
            return STATEMENTS
        if "/copom/atas?" in url:
            return MINUTES
        if "/rpm/relatorios?" in url:
            return RPM_REPORTS
        if "/rpm/proximos-relatorios?" in url:
            return RPM_CALENDAR
        raise AssertionError(f"unexpected URL {url}")

    def _run(self):
        return update_copom_events(
            database_path=self.database,
            raw_root=self.raw,
            output_path=self.output,
            yield_curve_output_path=self.curve,
            fetcher=self._fetcher,
            clock=lambda: NOW,
            quantity=1,
            detail_limit=1,
            rpm_quantity=1,
        )

    def test_pipeline_persists_documents_rpm_calendar_and_static_contract(self) -> None:
        result = self._run()
        self.assertEqual(result["status"], "succeeded")
        self.assertTrue(self.output.is_file())
        payload = json.loads(self.output.read_text(encoding="utf-8"))
        event_types = {event["type"] for event in payload["events"]}
        self.assertTrue({"copom_decision", "copom_minutes", "copom_meeting", "rpm_release", "rpm_schedule"} <= event_types)
        self.assertEqual(payload["decision_markers"][0]["rate"], 13.75)
        self.assertTrue(any(event["type"] == "rpm_schedule" and event["status"] == "scheduled" for event in payload["upcoming"]))

        snapshot = Path(result["snapshot_directory"])
        chunks = sorted(snapshot.glob("chunk-*.json"))
        self.assertEqual(len(chunks), 6)
        self.assertTrue((snapshot / "manifest.json").is_file())

    def test_minutes_do_not_appear_before_official_publication_date(self) -> None:
        self._run()
        connection = initialize_database(self.database)
        try:
            historical = build_copom_events_document(
                connection,
                generated_at=NOW,
                knowledge_mode="as_known",
                knowledge_cutoff=end_of_day_cutoff(datetime(2026, 9, 20, tzinfo=timezone.utc).date()),
            )
        finally:
            connection.close()
        types = {event["type"] for event in historical["events"]}
        self.assertIn("copom_decision", types)
        self.assertNotIn("copom_minutes", types)

    def test_identical_recollection_is_revision_idempotent(self) -> None:
        first = self._run()
        second = self._run()
        self.assertGreater(first["event_revisions_inserted"], 0)
        self.assertEqual(second["event_revisions_inserted"], 0)
        connection = initialize_database(self.database)
        try:
            revisions = connection.execute("SELECT COUNT(*) FROM event_revisions").fetchone()[0]
            events = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(revisions, events)


if __name__ == "__main__":
    unittest.main()
