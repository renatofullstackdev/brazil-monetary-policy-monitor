"""Knowledge-cutoff helpers for revision-aware publication.

The vintage layer makes the distinction between ``latest_revision`` and ``as_known``
explicit at publication time.  The helpers in this module deliberately use
``available_at`` as the knowledge boundary.  They never infer an earlier
availability date merely from the economic reference period.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
import sqlite3
from typing import Literal

from .db.observations import observations_as_known, observations_latest
from .db.parameters import parameter_latest
from .db.market_curves import market_curve_points_as_known, market_curve_points_latest

KnowledgeMode = Literal["latest_revision", "as_known"]


@dataclass(frozen=True)
class KnowledgeContext:
    mode: KnowledgeMode
    generated_at: datetime
    cutoff: str | None = None

    @property
    def effective_datetime(self) -> datetime:
        if self.mode == "latest_revision":
            return self.generated_at.astimezone(timezone.utc)
        assert self.cutoff is not None
        return datetime.fromisoformat(self.cutoff.replace("Z", "+00:00")).astimezone(timezone.utc)

    @property
    def effective_date(self) -> date:
        return self.effective_datetime.date()

    def contract_fields(self) -> dict[str, str | None]:
        return {
            "knowledge_mode": self.mode,
            "knowledge_cutoff": self.cutoff if self.mode == "as_known" else None,
        }


def iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def end_of_day_cutoff(value: date) -> str:
    return iso_z(datetime.combine(value, time.max, tzinfo=timezone.utc))


def build_knowledge_context(
    *,
    generated_at: datetime,
    knowledge_mode: KnowledgeMode = "latest_revision",
    knowledge_cutoff: str | None = None,
) -> KnowledgeContext:
    if generated_at.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    if knowledge_mode not in ("latest_revision", "as_known"):
        raise ValueError(f"unsupported knowledge mode: {knowledge_mode}")
    if knowledge_mode == "latest_revision":
        if knowledge_cutoff is not None:
            raise ValueError("knowledge_cutoff is only valid with as_known")
        return KnowledgeContext(mode=knowledge_mode, generated_at=generated_at)
    if not knowledge_cutoff:
        raise ValueError("as_known requires knowledge_cutoff")
    parsed = datetime.fromisoformat(knowledge_cutoff.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("knowledge_cutoff must be timezone-aware")
    normalized = iso_z(parsed)
    return KnowledgeContext(mode=knowledge_mode, generated_at=generated_at, cutoff=normalized)


def observation_rows(
    connection: sqlite3.Connection,
    series_key: str,
    context: KnowledgeContext,
) -> list[sqlite3.Row]:
    if context.mode == "latest_revision":
        return observations_latest(connection, series_key)
    assert context.cutoff is not None
    return observations_as_known(connection, series_key, context.cutoff)


def parameter_row(
    connection: sqlite3.Connection,
    key: str,
    context: KnowledgeContext,
) -> sqlite3.Row | None:
    # Even latest_revision is evaluated at generated_at so a parameter announced
    # for future effectiveness is not used early.
    cutoff = context.cutoff if context.mode == "as_known" else iso_z(context.generated_at)
    return parameter_latest(connection, key, knowledge_cutoff=cutoff)


def market_curve_rows(
    connection: sqlite3.Connection,
    *,
    context: KnowledgeContext,
    source_id: int | None = None,
    curve_key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[sqlite3.Row]:
    if context.mode == "latest_revision":
        return market_curve_points_latest(
            connection, source_id=source_id, curve_key=curve_key,
            start_date=start_date, end_date=end_date,
        )
    assert context.cutoff is not None
    return market_curve_points_as_known(
        connection, knowledge_cutoff=context.cutoff, source_id=source_id,
        curve_key=curve_key, start_date=start_date, end_date=end_date,
    )


def known_dates(connection: sqlite3.Connection) -> list[date]:
    """Return distinct local knowledge dates represented by persisted vintages."""

    rows = connection.execute(
        """
        SELECT knowledge_date FROM (
            SELECT substr(available_at, 1, 10) AS knowledge_date FROM observations
            UNION
            SELECT substr(available_at, 1, 10) AS knowledge_date FROM parameters

            UNION
            SELECT substr(available_at, 1, 10) AS knowledge_date FROM market_curve_points
            UNION
            SELECT substr(available_at, 1, 10) AS knowledge_date FROM event_revisions
        )
        WHERE knowledge_date IS NOT NULL AND length(knowledge_date) = 10
        ORDER BY knowledge_date
        """
    ).fetchall()
    return [date.fromisoformat(str(row[0])) for row in rows]


def coverage_summary(connection: sqlite3.Connection, cutoff: str) -> dict[str, object]:
    """Describe what the local database can actually know by ``cutoff``.

    This does not claim complete provider-native real-time history.  It counts
    local series/parameters with at least one defensibly available value by the
    cutoff and surfaces the first local knowledge date for context.
    """

    first_row = connection.execute(
        """
        SELECT MIN(value) FROM (
            SELECT available_at AS value FROM observations
            UNION ALL SELECT available_at FROM parameters
            UNION ALL SELECT available_at FROM market_curve_points
            UNION ALL SELECT available_at FROM event_revisions
        )
        """
    ).fetchone()
    series_count = connection.execute(
        """
        SELECT COUNT(DISTINCT series_id)
        FROM observations
        WHERE available_at <= ?
        """,
        (cutoff,),
    ).fetchone()[0]
    parameter_count = connection.execute(
        """SELECT COUNT(DISTINCT key) FROM parameters WHERE available_at <= ?""",
        (cutoff,),
    ).fetchone()[0]
    curve_count = connection.execute(
        """
        SELECT COUNT(DISTINCT source_id)
        FROM market_curve_points
        WHERE available_at <= ?
        """,
        (cutoff,),
    ).fetchone()[0]
    event_count = connection.execute(
        "SELECT COUNT(DISTINCT event_id) FROM event_revisions WHERE available_at <= ?",
        (cutoff,),
    ).fetchone()[0]
    return {
        "coverage": "local_defensible_vintages",
        "first_local_knowledge_at": None if first_row is None else first_row[0],
        "series_with_known_values": int(series_count or 0),
        "parameters_with_known_values": int(parameter_count or 0),
        "curve_sources_with_known_values": int(curve_count or 0),
        "policy_events_known": int(event_count or 0),
        "caveat": (
            "As-known usa available_at. Backfills cuja fonte não fornece publicação/revisão "
            "histórica confiável só se tornam conhecidos quando o monitor os observa; não há "
            "retrodatação para o período econômico."
        ),
    }
