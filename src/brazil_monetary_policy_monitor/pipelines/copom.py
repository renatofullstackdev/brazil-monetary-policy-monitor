"""Copom communication and RPM event pipeline."""

from __future__ import annotations

from pathlib import Path

from ..collectors.http import fetch_bytes
from ..db import initialize_database
from ..ingestion.runs import finish_ingestion_run, start_ingestion_run
from ..snapshots import RawSnapshotRun
from .runtime import Clock, FetchBytes, error_document, utc_now

def update_copom_events(
    *,
    database_path: str | Path,
    raw_root: str | Path,
    output_path: str | Path,
    yield_curve_output_path: str | Path | None = None,
    fetcher: FetchBytes = fetch_bytes,
    clock: Clock = utc_now,
    quantity: int = 40,
    detail_limit: int = 8,
    rpm_quantity: int = 12,
) -> dict[str, object]:
    """Collect Copom/RPM communication, preserve event revisions and publish annotations."""

    from ..collectors.bcb_copom import (
        CopomDocument,
        build_copom_detail_url,
        build_copom_list_url,
        parse_copom_detail,
        parse_copom_list,
    )
    from ..collectors.bcb_rpm import (
        build_rpm_calendar_url,
        build_rpm_reports_url,
        parse_rpm_calendar,
        parse_rpm_reports,
    )
    from ..copom_events import (
        ensure_copom_source,
        persist_document_events,
        persist_documentary_calendar,
        persist_rpm_events,
    )
    from ..publish.copom import publish_copom_events_json
    from ..publish.yield_curve import publish_yield_curve_json

    if quantity < 1:
        raise ValueError("quantity must be positive")
    if detail_limit < 0:
        raise ValueError("detail_limit cannot be negative")
    if rpm_quantity < 1:
        raise ValueError("rpm_quantity must be positive")

    connection = initialize_database(database_path)
    source_id = ensure_copom_source(connection)
    started_at = clock()
    run_id = start_ingestion_run(
        connection,
        source_id=source_id,
        started_at=started_at,
        collector_version="copom-events-v1",
        provider="BCB",
    )
    snapshots = RawSnapshotRun(
        root=Path(raw_root),
        provider="bcb",
        series_key="policy-events",
        run_id=run_id,
        started_at=started_at,
    )
    received = 0
    inserted = 0
    unchanged = 0
    persisted = False

    try:
        lists: dict[str, list] = {}
        index = 1
        for kind in ("comunicados", "atas"):
            url = build_copom_list_url(kind, quantity=quantity)
            payload = fetcher(url)
            snapshots.save_payload(index=index, url=url, payload=payload)
            index += 1
            lists[kind] = parse_copom_list(payload, kind=kind)

        documents: dict[str, list[CopomDocument]] = {"comunicados": [], "atas": []}
        for kind in ("comunicados", "atas"):
            rows = lists[kind]
            detailed_numbers = {row.meeting_number for row in rows[-detail_limit:]} if detail_limit else set()
            for row in rows:
                if row.meeting_number in detailed_numbers:
                    url = build_copom_detail_url(kind, row.meeting_number)
                    payload = fetcher(url)
                    snapshots.save_payload(index=index, url=url, payload=payload)
                    index += 1
                    document = parse_copom_detail(payload, kind=kind)
                else:
                    document = CopomDocument(
                        meeting_number=row.meeting_number,
                        reference_date=row.reference_date,
                        publication_date=row.publication_date,
                        title=row.title,
                        html_text="",
                        pdf_url=None,
                    )
                documents[kind].append(document)

        rpm_reports_url = build_rpm_reports_url(quantity=rpm_quantity)
        rpm_reports_payload = fetcher(rpm_reports_url)
        snapshots.save_payload(index=index, url=rpm_reports_url, payload=rpm_reports_payload)
        index += 1
        rpm_reports = parse_rpm_reports(rpm_reports_payload)

        rpm_calendar_url = build_rpm_calendar_url()
        rpm_calendar_payload = fetcher(rpm_calendar_url)
        snapshots.save_payload(index=index, url=rpm_calendar_url, payload=rpm_calendar_payload)
        rpm_calendar = parse_rpm_calendar(rpm_calendar_payload)

        received = (
            len(documents["comunicados"])
            + len(documents["atas"])
            + len(rpm_reports)
            + len(rpm_calendar)
        )
        retrieved_at = clock()
        event_inserted, event_existing = persist_document_events(
            connection,
            source_id=source_id,
            communicados=documents["comunicados"],
            atas=documents["atas"],
            retrieved_at=retrieved_at,
        )
        rpm_inserted, rpm_existing = persist_rpm_events(
            connection,
            source_id=source_id,
            reports=rpm_reports,
            calendar_entries=rpm_calendar,
            retrieved_at=retrieved_at,
        )
        calendar_inserted, calendar_existing = persist_documentary_calendar(
            connection,
            source_id=source_id,
            retrieved_at=retrieved_at,
        )
        inserted = event_inserted + rpm_inserted + calendar_inserted
        unchanged = event_existing + rpm_existing + calendar_existing
        persisted = True

        publish_copom_events_json(
            connection,
            output_path=output_path,
            generated_at=clock(),
        )
        if yield_curve_output_path is not None:
            try:
                publish_yield_curve_json(
                    connection,
                    output_path=yield_curve_output_path,
                    generated_at=clock(),
                )
            except LookupError:
                # Events are independently useful before the Tesouro source exists.
                pass

        finished_at = clock()
        finish_ingestion_run(
            connection,
            run_id=run_id,
            finished_at=finished_at,
            status="succeeded",
            records_received=received,
            records_inserted=inserted,
            records_unchanged=unchanged,
        )
        snapshots.write_manifest(
            status="succeeded",
            finished_at=finished_at,
            records_received=received,
        )
        return {
            "status": "succeeded",
            "run_id": run_id,
            "records_received": received,
            "event_revisions_inserted": inserted,
            "event_revisions_existing": unchanged,
            "output_path": str(output_path),
            "yield_curve_output_path": None if yield_curve_output_path is None else str(yield_curve_output_path),
            "snapshot_directory": str(snapshots.directory),
        }
    except Exception as exc:
        finished_at = clock()
        status = "partial" if persisted else "failed"
        error = error_document(exc)
        finish_ingestion_run(
            connection,
            run_id=run_id,
            finished_at=finished_at,
            status=status,
            records_received=received,
            records_inserted=inserted,
            records_unchanged=unchanged,
            error=error,
        )
        snapshots.write_manifest(
            status=status,
            finished_at=finished_at,
            records_received=received,
            error=error,
        )
        raise
    finally:
        connection.close()
