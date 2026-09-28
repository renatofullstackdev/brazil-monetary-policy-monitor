"""Revision-aware persistence and knowledge-cutoff queries for policy events."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import sqlite3


def _iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def event_hash(
    *,
    title: str,
    occurred_at: str,
    published_at: str | None,
    url: str | None,
    metadata: dict[str, object],
) -> str:
    canonical = json.dumps(
        {
            "title": title,
            "occurred_at": occurred_at,
            "published_at": published_at,
            "url": url,
            "metadata": metadata,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def upsert_event(
    connection: sqlite3.Connection,
    *,
    event_key: str,
    source_id: int,
    event_type: str,
    title: str,
    occurred_at: str,
    published_at: str | None,
    available_at: str,
    retrieved_at: datetime,
    url: str | None,
    source_event_id: str | None,
    metadata: dict[str, object],
) -> tuple[bool, bool]:
    """Persist an immutable event representation.

    The first observed representation may use a defensible provider publication
    date as ``available_at``.  If that event later changes, the new representation
    only becomes knowable when this monitor observes the change.  This prevents a
    later correction/status transition from leaking into earlier ``as_known`` cuts.

    Returns ``(revision_inserted, revision_already_known)``.
    """

    retrieved = _iso_z(retrieved_at)
    digest = event_hash(
        title=title,
        occurred_at=occurred_at,
        published_at=published_at,
        url=url,
        metadata=metadata,
    )
    row = connection.execute(
        "SELECT id FROM events WHERE event_key = ?", (event_key,)
    ).fetchone()

    if row is None:
        cursor = connection.execute(
            """
            INSERT INTO events(
                event_key, source_id, event_type, title, occurred_at, published_at,
                url, source_event_id, metadata_json, available_at, retrieved_at,
                last_seen_at, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_key,
                source_id,
                event_type,
                title,
                occurred_at,
                published_at,
                url,
                source_event_id,
                json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                available_at,
                retrieved,
                retrieved,
                digest,
            ),
        )
        event_id = int(cursor.lastrowid)
        revision_available_at = available_at
    else:
        event_id = int(row["id"])
        known = connection.execute(
            "SELECT id FROM event_revisions WHERE event_id = ? AND content_hash = ?",
            (event_id, digest),
        ).fetchone()
        if known is not None:
            connection.execute(
                """
                UPDATE event_revisions
                SET last_seen_at = ?
                WHERE id = ?
                """,
                (retrieved, int(known["id"])),
            )
            connection.execute(
                "UPDATE events SET last_seen_at = ? WHERE id = ?",
                (retrieved, event_id),
            )
            return False, True

        # A changed representation was only observed now.  Even if the underlying
        # event is old, backdating this new content would create look-ahead.
        revision_available_at = retrieved
        connection.execute(
            """
            UPDATE events
            SET source_id = ?, event_type = ?, title = ?, occurred_at = ?, published_at = ?,
                url = ?, source_event_id = ?, metadata_json = ?, available_at = ?,
                retrieved_at = ?, last_seen_at = ?, content_hash = ?
            WHERE id = ?
            """,
            (
                source_id,
                event_type,
                title,
                occurred_at,
                published_at,
                url,
                source_event_id,
                json.dumps(metadata, ensure_ascii=False, sort_keys=True),
                revision_available_at,
                retrieved,
                retrieved,
                digest,
                event_id,
            ),
        )

    connection.execute(
        """
        INSERT INTO event_revisions(
            event_id, title, occurred_at, published_at, url, metadata_json,
            available_at, retrieved_at, last_seen_at, content_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            title,
            occurred_at,
            published_at,
            url,
            json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            revision_available_at,
            retrieved,
            retrieved,
            digest,
        ),
    )
    return True, False


def _revision_query(*, as_known: bool) -> str:
    cutoff_clause = "AND candidate.available_at <= ?" if as_known else ""
    return f"""
        SELECT
            event.id,
            event.event_key,
            event.source_id,
            event.event_type,
            revision.title,
            revision.occurred_at,
            revision.published_at,
            revision.url,
            event.source_event_id,
            revision.metadata_json,
            revision.available_at,
            revision.retrieved_at,
            revision.last_seen_at,
            revision.content_hash,
            revision.created_at
        FROM events AS event
        JOIN event_revisions AS revision
          ON revision.id = (
              SELECT candidate.id
              FROM event_revisions AS candidate
              WHERE candidate.event_id = event.id
                {cutoff_clause}
              ORDER BY candidate.available_at DESC, candidate.retrieved_at DESC, candidate.id DESC
              LIMIT 1
          )
        ORDER BY revision.occurred_at, event.event_type, event.id
    """


def events_latest(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(connection.execute(_revision_query(as_known=False)))


def events_as_known(connection: sqlite3.Connection, knowledge_cutoff: str) -> list[sqlite3.Row]:
    return list(connection.execute(_revision_query(as_known=True), (knowledge_cutoff,)))
