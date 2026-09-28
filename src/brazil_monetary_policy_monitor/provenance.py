"""Shared provenance concepts used across collection, models and UI metadata."""

from enum import StrEnum


class DataKind(StrEnum):
    """Epistemic classification of values displayed by the dashboard."""

    OBSERVED = "observed"
    SURVEY = "survey"
    ESTIMATED = "estimated"
    DERIVED = "derived"
    SIMULATED = "simulated"
