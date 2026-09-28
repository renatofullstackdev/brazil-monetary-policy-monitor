"""Publish the static Copom communication/event contract."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from ..copom_events import COPOM_SOURCE_KEY
from ..db.events import events_as_known, events_latest
from ..vintages import build_knowledge_context
from .atomic import write_json_atomic



def _iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _source(connection: sqlite3.Connection) -> sqlite3.Row | None:
    return connection.execute("SELECT * FROM sources WHERE key = ?", (COPOM_SOURCE_KEY,)).fetchone()


def _event_document(row: sqlite3.Row) -> dict[str, object]:
    metadata = json.loads(row["metadata_json"] or "{}")
    return {
        "key": row["event_key"],
        "type": row["event_type"],
        "title": row["title"],
        "occurred_at": row["occurred_at"],
        "published_at": row["published_at"],
        "available_at": row["available_at"],
        "url": row["url"],
        "source_event_id": row["source_event_id"],
        "meeting_number": metadata.get("meeting_number"),
        "status": metadata.get("status", "published"),
        "decision_rate_percent": metadata.get("decision_rate_percent"),
        "decision_direction": metadata.get("decision_direction"),
        "metadata": metadata,
    }


def build_copom_events_document(
    connection: sqlite3.Connection,
    *,
    generated_at: datetime,
    knowledge_mode: str = "latest_revision",
    knowledge_cutoff: str | None = None,
) -> dict[str, object]:
    context = build_knowledge_context(
        generated_at=generated_at,
        knowledge_mode=knowledge_mode,
        knowledge_cutoff=knowledge_cutoff,
    )
    source = _source(connection)
    rows = events_latest(connection) if context.mode == "latest_revision" else events_as_known(connection, context.cutoff or "")
    events = [_event_document(row) for row in rows]
    decision_markers = [
        {
            "date": event["occurred_at"][:10],
            "title": event["title"],
            "meeting_number": event["meeting_number"],
            "rate": event["decision_rate_percent"],
            "direction": event["decision_direction"],
            "url": event["url"],
        }
        for event in events
        if event["type"] == "copom_decision"
    ]
    upcoming = [
        event for event in events
        if event["status"] in {"scheduled", "scheduled_unverified"}
        and str(event["occurred_at"])[:10] >= context.effective_date.isoformat()
    ]
    recent = sorted(
        [event for event in events if str(event["occurred_at"])[:10] <= context.effective_date.isoformat()],
        key=lambda item: (str(item["occurred_at"]), str(item["type"])),
        reverse=True,
    )[:24]
    return {
        "view": "copom_events",
        "generated_at": _iso_z(generated_at),
        **context.contract_fields(),
        "status": "available" if events else "unavailable",
        "source": None if source is None else {
            "provider": source["provider"],
            "name": source["name"],
            "url": source["url"],
            "documentation_url": source["documentation_url"],
            "license": source["license"],
        },
        "decision_markers": decision_markers,
        "recent": recent,
        "upcoming": upcoming[:16],
        "events": events,
        "methodology": {
            "availability": (
                "Comunicados usam a data oficial da decisão; atas usam dataPublicacao do BCB. "
                "Datas futuras sem publicação histórica explícita só se tornam conhecidas quando observadas pelo monitor."
            ),
            "caveat": "Um evento registra comunicação e cronologia; não classifica o tom da decisão nem infere causalidade.",
        },
    }


def publish_copom_events_json(
    connection: sqlite3.Connection,
    *,
    output_path: str | Path,
    generated_at: datetime,
    knowledge_mode: str = "latest_revision",
    knowledge_cutoff: str | None = None,
) -> Path:
    return write_json_atomic(
        build_copom_events_document(
            connection,
            generated_at=generated_at,
            knowledge_mode=knowledge_mode,
            knowledge_cutoff=knowledge_cutoff,
        ),
        output_path,
    )
