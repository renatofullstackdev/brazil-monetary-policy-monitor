"""Publish static as-known bundles for the browser vintage experience."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3
import shutil
from typing import Callable

from ..vintages import coverage_summary, end_of_day_cutoff, known_dates
from .atomic import write_json_atomic
from .credit_transmission import publish_credit_transmission_json
from .copom import publish_copom_events_json
from .external import publish_external_json
from .fiscal import publish_fiscal_json
from .overview import publish_overview_json
from .us import publish_us_json
from .yield_curve import publish_yield_curve_json


Publisher = Callable[..., Path]

_CONTRACTS: tuple[tuple[str, str, Publisher], ...] = (
    ("overview", "overview.json", publish_overview_json),
    ("copom_events", "copom-events.json", publish_copom_events_json),
    ("credit_transmission", "credit-transmission.json", publish_credit_transmission_json),
    ("fiscal", "fiscal.json", publish_fiscal_json),
    ("external_sector", "external-sector.json", publish_external_json),
    ("us_benchmark", "us-benchmark.json", publish_us_json),
    ("yield_curve", "yield-curve.json", publish_yield_curve_json),
)


def _iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def publish_vintage_bundle(
    connection: sqlite3.Connection,
    *,
    root: str | Path,
    knowledge_date: date,
    generated_at: datetime,
) -> dict[str, object]:
    root = Path(root)
    label = knowledge_date.isoformat()
    target_dir = root / label
    cutoff = end_of_day_cutoff(knowledge_date)
    published: dict[str, str] = {}
    errors: dict[str, str] = {}

    for view, filename, publisher in _CONTRACTS:
        target = target_dir / filename
        try:
            publisher(
                connection,
                output_path=target,
                generated_at=generated_at,
                knowledge_mode="as_known",
                knowledge_cutoff=cutoff,
            )
        except LookupError as exc:
            # Some independent views (notably yield curve) require source
            # metadata that may not exist in very early/local test databases.
            errors[view] = str(exc)
            continue
        published[view] = f"{label}/{filename}"

    return {
        "date": label,
        "knowledge_cutoff": cutoff,
        "contracts": published,
        "errors": errors,
        "coverage": coverage_summary(connection, cutoff),
    }




def _default_archive_dates(
    connection: sqlite3.Connection, *, generated_at: datetime
) -> list[date]:
    """Choose static checkpoints without exploding on dense daily Selic rows.

    The archive selector existed before the Sprint 19 Selic availability repair and
    was driven by documentary/event/other-series knowledge dates.  Backdating the
    first official Selic vintage to the day in which the target was already in
    force would otherwise add almost every month since 1999 to the static archive.

    Selic remains fully available inside each bundle; it is excluded only from the
    *checkpoint trigger*.  All other knowledge dates keep the previous monthly
    checkpoint policy, preserving Copom/documentary checkpoints already exposed by
    the UI.
    """

    rows = connection.execute(
        """
        SELECT knowledge_date FROM (
            SELECT substr(o.available_at, 1, 10) AS knowledge_date
            FROM observations AS o
            JOIN series AS s ON s.id = o.series_id
            WHERE s.key <> 'br.selic.target'
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
    known = [date.fromisoformat(str(row[0])) for row in rows]

    checkpoints: set[date] = set()
    if known:
        checkpoints.add(known[0])
        by_month: dict[tuple[int, int], date] = {}
        for item in known:
            by_month[(item.year, item.month)] = item
        checkpoints.update(by_month.values())
    checkpoints.add(generated_at.astimezone(timezone.utc).date())
    return sorted(checkpoints)


def publish_vintage_archive(
    connection: sqlite3.Connection,
    *,
    root: str | Path,
    generated_at: datetime,
    selected_dates: list[date] | None = None,
) -> Path:
    """Publish one as-known bundle per local knowledge date plus an index."""

    root = Path(root)
    if selected_dates is None:
        dates = _default_archive_dates(connection, generated_at=generated_at)
    else:
        dates = sorted(set(selected_dates))
    entries = [
        publish_vintage_bundle(
            connection,
            root=root,
            knowledge_date=current,
            generated_at=generated_at,
        )
        for current in dates
    ]

    if selected_dates is None and root.exists():
        expected = {item.isoformat() for item in dates}
        for child in root.iterdir():
            if child.is_dir() and child.name not in expected:
                shutil.rmtree(child)

    index = {
        "view": "vintage_index",
        "generated_at": _iso_z(generated_at),
        "mode": "as_known",
        "entries": entries,
        "note": (
            "Cada data representa o estado defensável pelo campo available_at. "
            "Fontes sem histórico nativo de publicação/revisão não são retrodatadas."
        ),
    }
    return write_json_atomic(index, root / "index.json")
