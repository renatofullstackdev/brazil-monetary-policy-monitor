"""Shared temporal primitives.

The monitor distinguishes three independent notions of time:

* ``reference_period``: what economic period a value describes;
* ``as_of_date``/``source_observation_at``: when the source statistic or estimate
  was dated;
* ``available_at``: when that information can defensibly be treated as known.

Keeping these notions separate is required for revision-aware historical analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone


def iso_z(value: datetime) -> str:
    """Serialize a timezone-aware datetime as canonical UTC ISO-8601."""

    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
