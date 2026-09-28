"""Policy-event normalization for Copom documents, meetings and RPM releases."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import json
import sqlite3

from .collectors.bcb_copom import CopomDocument, decision_direction, extract_selic_rate
from .collectors.bcb_rpm import RpmCalendarEntry, RpmReport, reference_quarter
from .copom_calendar import COPOM_SCHEDULE
from .db.events import upsert_event

COPOM_SOURCE_KEY = "bcb.copom.documents"
COPOM_DOCS_URL = "https://www.bcb.gov.br/api/servico/sitebcb/copom/"
COPOM_DATASET_URL = "https://dadosabertos.bcb.gov.br/dataset/atas-comunicados-copom"
RPM_DATASET_URL = "https://dadosabertos.bcb.gov.br/dataset/relatorios-de-politica-monetaria-publicados"
RPM_PAGE_URL = "https://www.bcb.gov.br/publicacoes/rpm"


def ensure_copom_source(connection: sqlite3.Connection) -> int:
    connection.execute(
        """
        INSERT INTO sources(key, provider, name, url, documentation_url, license, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            provider = excluded.provider,
            name = excluded.name,
            url = excluded.url,
            documentation_url = excluded.documentation_url,
            license = excluded.license,
            metadata_json = excluded.metadata_json,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        """,
        (
            COPOM_SOURCE_KEY,
            "BCB",
            "Documentos, reuniões do Copom e Relatórios de Política Monetária",
            COPOM_DOCS_URL,
            COPOM_DATASET_URL,
            "Open Data Commons Open Database License (ODbL)",
            json.dumps(
                {
                    "copom_dataset_url": COPOM_DATASET_URL,
                    "rpm_dataset_url": RPM_DATASET_URL,
                    "copom_endpoints": ["atas", "atas_detalhes", "comunicados", "comunicados_detalhes"],
                    "rpm_endpoints": ["relatorios", "proximos-relatorios"],
                    "calendar_note": (
                        "2027 Copom dates come from Comunicado 45.452; future 2026 meeting dates "
                        "come from the official Copom calendar. RPM publication/schedule rows are collected from the RPM API."
                    ),
                },
                sort_keys=True,
            ),
        ),
    )
    connection.commit()
    return int(connection.execute("SELECT id FROM sources WHERE key = ?", (COPOM_SOURCE_KEY,)).fetchone()[0])


def _date_available(value: date) -> str:
    # The APIs expose date-level chronology, not historical intraday timestamps.
    # Noon UTC is a stable within-day marker; day-level as-known archives use EOD.
    return datetime.combine(value, time(12, 0), tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _retrieved_available(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def persist_document_events(
    connection: sqlite3.Connection,
    *,
    source_id: int,
    communicados: list[CopomDocument],
    atas: list[CopomDocument],
    retrieved_at: datetime,
) -> tuple[int, int]:
    inserted = 0
    unchanged = 0
    with connection:
        for doc in communicados:
            meeting = doc.meeting_number
            reference = doc.reference_date.isoformat()
            rate = extract_selic_rate(doc.title, doc.html_text)
            metadata = {
                "meeting_number": meeting,
                "document_kind": "statement",
                "decision_rate_percent": rate,
                "decision_direction": decision_direction(doc.title),
                "status": "published",
            }
            was_inserted, was_existing = upsert_event(
                connection,
                event_key=f"copom-{meeting}-decision",
                source_id=source_id,
                event_type="copom_decision",
                title=doc.title,
                occurred_at=reference,
                published_at=reference,
                available_at=_date_available(doc.reference_date),
                retrieved_at=retrieved_at,
                url=f"https://www.bcb.gov.br/controleinflacao/comunicadoscopom/{doc.reference_date.strftime('%d%m%Y')}",
                source_event_id=str(meeting),
                metadata=metadata,
            )
            inserted += int(was_inserted)
            unchanged += int(was_existing)

            meeting_inserted, meeting_existing = upsert_event(
                connection,
                event_key=f"copom-{meeting}-meeting",
                source_id=source_id,
                event_type="copom_meeting",
                title=f"{meeting}ª Reunião do Copom",
                occurred_at=reference,
                published_at=reference,
                available_at=_date_available(doc.reference_date),
                retrieved_at=retrieved_at,
                url="https://www.bcb.gov.br/controleinflacao/copom",
                source_event_id=str(meeting),
                metadata={
                    "meeting_number": meeting,
                    "status": "completed",
                    "decision_event_key": f"copom-{meeting}-decision",
                },
            )
            inserted += int(meeting_inserted)
            unchanged += int(meeting_existing)

        for doc in atas:
            publication = doc.publication_date or doc.reference_date
            metadata = {
                "meeting_number": doc.meeting_number,
                "document_kind": "minutes",
                "status": "published",
                "pdf_url": doc.pdf_url,
            }
            was_inserted, was_existing = upsert_event(
                connection,
                event_key=f"copom-{doc.meeting_number}-minutes",
                source_id=source_id,
                event_type="copom_minutes",
                title=f"Ata da {doc.title}",
                occurred_at=doc.reference_date.isoformat(),
                published_at=publication.isoformat(),
                available_at=_date_available(publication),
                retrieved_at=retrieved_at,
                url=f"https://www.bcb.gov.br/publicacoes/atascopom/{doc.reference_date.strftime('%d%m%Y')}",
                source_event_id=str(doc.meeting_number),
                metadata=metadata,
            )
            inserted += int(was_inserted)
            unchanged += int(was_existing)
    return inserted, unchanged


def persist_rpm_events(
    connection: sqlite3.Connection,
    *,
    source_id: int,
    reports: list[RpmReport],
    calendar_entries: list[RpmCalendarEntry],
    retrieved_at: datetime,
) -> tuple[int, int]:
    """Persist published RPMs and the near-term official release calendar.

    Published reports and schedule announcements are separate event identities.
    A schedule can later transition from ``scheduled`` to ``fulfilled`` through
    an immutable revision without making the release visible in earlier cuts.
    """

    inserted = 0
    unchanged = 0
    today = retrieved_at.astimezone(timezone.utc).date()
    published_months = {report.identifier for report in reports}

    with connection:
        for report in reports:
            quarter = reference_quarter(report.publication_date)
            was_inserted, was_existing = upsert_event(
                connection,
                event_key=f"rpm-release-{report.identifier}",
                source_id=source_id,
                event_type="rpm_release",
                title=f"Relatório de Política Monetária — {quarter}",
                occurred_at=report.publication_date.isoformat(),
                published_at=report.publication_date.isoformat(),
                available_at=_date_available(report.publication_date),
                retrieved_at=retrieved_at,
                url=report.page_url,
                source_event_id=report.identifier,
                metadata={
                    "status": "published",
                    "reference_quarter": quarter,
                    "identifier": report.identifier,
                    "pdf_url": report.url,
                    "edition": report.edition,
                    "volume": report.volume,
                },
            )
            inserted += int(was_inserted)
            unchanged += int(was_existing)

        # The calendar API contains historical rows as well, but it does not expose
        # when each schedule row was first announced.  Persist only a small near-term
        # window and use first local observation as the availability boundary.
        lower_bound = today - timedelta(days=45)
        for entry in calendar_entries:
            if entry.event != "Relatório de Política Monetária" or entry.event_date < lower_bound:
                continue
            identifier = entry.event_date.strftime("%Y%m")
            fulfilled = identifier in published_months
            status = "fulfilled" if fulfilled else "scheduled"
            quarter = reference_quarter(entry.event_date)
            was_inserted, was_existing = upsert_event(
                connection,
                event_key=f"rpm-schedule-{identifier}",
                source_id=source_id,
                event_type="rpm_schedule",
                title=f"Divulgação programada do Relatório de Política Monetária — {quarter}",
                occurred_at=entry.event_date.isoformat(),
                published_at=None,
                available_at=_retrieved_available(retrieved_at),
                retrieved_at=retrieved_at,
                url=RPM_PAGE_URL,
                source_event_id=identifier,
                metadata={
                    "status": status,
                    "reference_quarter": quarter,
                    "description": entry.description,
                    "fulfilled_by": f"rpm-release-{identifier}" if fulfilled else None,
                },
            )
            inserted += int(was_inserted)
            unchanged += int(was_existing)
    return inserted, unchanged


def persist_documentary_calendar(
    connection: sqlite3.Connection,
    *,
    source_id: int,
    retrieved_at: datetime,
) -> tuple[int, int]:
    inserted = 0
    unchanged = 0
    with connection:
        for entry in COPOM_SCHEDULE:
            published_on = entry.source_published_on
            if published_on is not None:
                available_at = _date_available(published_on)
            else:
                # These official future rows do not expose their historical
                # announcement timestamp in a machine-readable field.  Stay local-first.
                available_at = _retrieved_available(retrieved_at)
            metadata = dict(entry.metadata or {})
            metadata.update({"status": entry.status})
            if entry.meeting_number is not None:
                metadata["meeting_number"] = entry.meeting_number
            was_inserted, was_existing = upsert_event(
                connection,
                event_key=entry.key,
                source_id=source_id,
                event_type=entry.event_type,
                title=entry.title,
                occurred_at=entry.occurred_on.isoformat(),
                published_at=None if published_on is None else published_on.isoformat(),
                available_at=available_at,
                retrieved_at=retrieved_at,
                url=entry.source_url,
                source_event_id=None if entry.meeting_number is None else str(entry.meeting_number),
                metadata=metadata,
            )
            inserted += int(was_inserted)
            unchanged += int(was_existing)
    return inserted, unchanged
