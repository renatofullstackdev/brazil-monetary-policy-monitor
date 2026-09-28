from __future__ import annotations

from datetime import date, datetime, timezone
import json
import unittest

from brazil_monetary_policy_monitor.collectors.bcb_copom import (
    build_copom_detail_url,
    build_copom_list_url,
    decision_direction,
    extract_selic_rate,
    parse_copom_detail,
    parse_copom_list,
)
from brazil_monetary_policy_monitor.collectors.bcb_rpm import (
    build_rpm_calendar_url,
    build_rpm_reports_url,
    parse_rpm_calendar,
    parse_rpm_reports,
)
from brazil_monetary_policy_monitor.copom_events import ensure_copom_source
from brazil_monetary_policy_monitor.db import connect, migrate
from brazil_monetary_policy_monitor.db.events import events_as_known, events_latest, upsert_event


STATEMENTS = json.dumps({
    "conteudo": [
        {
            "nro_reuniao": 281,
            "dataReferencia": "2026-09-16",
            "titulo": "Copom reduz a taxa Selic para 13,75% a.a.",
        }
    ]
}).encode()

MINUTES = json.dumps({
    "conteudo": [
        {
            "nroReuniao": 281,
            "dataReferencia": "2026-09-16",
            "dataPublicacao": "2026-09-22",
            "titulo": "281ª Reunião - 16 de setembro de 2026",
        }
    ]
}).encode()

STATEMENT_DETAIL = json.dumps({
    "conteudo": [
        {
            "nro_reuniao": 281,
            "dataReferencia": "2026-09-16",
            "titulo": "Copom reduz a taxa Selic para 13,75% a.a.",
            "textoComunicado": "<p>O Copom decidiu reduzir a taxa Selic para 13,75% a.a.</p>",
        }
    ]
}).encode()

MINUTES_DETAIL = json.dumps({
    "conteudo": [
        {
            "nroReuniao": 281,
            "dataReferencia": "2026-09-16",
            "dataPublicacao": "2026-09-22",
            "titulo": "281ª Reunião - 16 de setembro de 2026",
            "textoAta": "<p>Ata da reunião.</p>",
            "urlPdfAta": "https://www.bcb.gov.br/content/copom/atascopom/Copom281-not20260916281.pdf",
        }
    ]
}).encode()

RPM_REPORTS = json.dumps({
    "conteudo": [
        {
            "url": "https://www.bcb.gov.br/content/ri/relatorioinflacao/202606/rpm202606p.pdf",
            "linkPaginaBC": "https://www.bcb.gov.br/publicacoes/rpm/202606",
            "identificador": "202606",
            "dataReferencia": "2026-06-25",
            "edicao": "2",
            "volume": "2",
        }
    ]
}).encode()

RPM_CALENDAR = json.dumps({
    "conteudo": [
        {
            "evento": "Relatório de Política Monetária",
            "dataEvento": "2026-09-24",
            "descricao": "Referência 3º trimestre de 2026",
        },
        {
            "evento": "Relatório de Política Monetária",
            "dataEvento": "2026-12-17",
            "descricao": "Referência 4º trimestre de 2026",
        },
    ]
}).encode()


class CopomCollectorTests(unittest.TestCase):
    def test_copom_urls_and_parsers_preserve_official_chronology(self) -> None:
        self.assertIn("quantidade=40", build_copom_list_url("atas", quantity=40))
        self.assertIn("nro_reuniao=281", build_copom_detail_url("comunicados", 281))

        statements = parse_copom_list(STATEMENTS, kind="comunicados")
        minutes = parse_copom_list(MINUTES, kind="atas")
        detail = parse_copom_detail(MINUTES_DETAIL, kind="atas")

        self.assertEqual(statements[0].reference_date, date(2026, 9, 16))
        self.assertIsNone(statements[0].publication_date)
        self.assertEqual(minutes[0].publication_date, date(2026, 9, 22))
        self.assertEqual(detail.pdf_url, "https://www.bcb.gov.br/content/copom/atascopom/Copom281-not20260916281.pdf")

    def test_decision_metadata_is_descriptive_not_sentiment_analysis(self) -> None:
        document = parse_copom_detail(STATEMENT_DETAIL, kind="comunicados")
        self.assertEqual(extract_selic_rate(document.title, document.html_text), 13.75)
        self.assertEqual(decision_direction(document.title), "cut")
        self.assertIsNone(decision_direction("Comunicado da reunião"))

    def test_rpm_endpoints_keep_publication_and_schedule_separate(self) -> None:
        self.assertIn("relatorios?quantidade=12", build_rpm_reports_url(quantity=12))
        self.assertIn("inicioAgenda=2025-01-01", build_rpm_calendar_url())
        reports = parse_rpm_reports(RPM_REPORTS)
        calendar = parse_rpm_calendar(RPM_CALENDAR)
        self.assertEqual(reports[0].identifier, "202606")
        self.assertEqual(reports[0].publication_date, date(2026, 6, 25))
        self.assertEqual(calendar[0].event_date, date(2026, 9, 24))


class EventRevisionTests(unittest.TestCase):
    def test_status_change_does_not_leak_into_earlier_as_known_cutoff(self) -> None:
        connection = connect()
        migrate(connection)
        source_id = ensure_copom_source(connection)
        first_seen = datetime(2026, 9, 23, 15, tzinfo=timezone.utc)
        published_seen = datetime(2026, 9, 24, 15, tzinfo=timezone.utc)
        try:
            with connection:
                upsert_event(
                    connection,
                    event_key="rpm-schedule-202609",
                    source_id=source_id,
                    event_type="rpm_schedule",
                    title="Divulgação programada do RPM — 2026-Q3",
                    occurred_at="2026-09-24",
                    published_at=None,
                    available_at="2026-09-23T15:00:00Z",
                    retrieved_at=first_seen,
                    url="https://www.bcb.gov.br/publicacoes/rpm",
                    source_event_id="202609",
                    metadata={"status": "scheduled"},
                )
            with connection:
                upsert_event(
                    connection,
                    event_key="rpm-schedule-202609",
                    source_id=source_id,
                    event_type="rpm_schedule",
                    title="Divulgação programada do RPM — 2026-Q3",
                    occurred_at="2026-09-24",
                    published_at=None,
                    available_at="2026-09-23T15:00:00Z",
                    retrieved_at=published_seen,
                    url="https://www.bcb.gov.br/publicacoes/rpm",
                    source_event_id="202609",
                    metadata={"status": "fulfilled"},
                )

            old = events_as_known(connection, "2026-09-23T23:59:59Z")
            current = events_latest(connection)
            self.assertEqual(json.loads(old[0]["metadata_json"])["status"], "scheduled")
            self.assertEqual(json.loads(current[0]["metadata_json"])["status"], "fulfilled")
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM event_revisions").fetchone()[0],
                2,
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
