"""Small persistence helpers shared by source-specific ingestion modules."""

from __future__ import annotations

from decimal import Decimal
import hashlib


def canonical_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def stable_hash(*parts: object) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()
