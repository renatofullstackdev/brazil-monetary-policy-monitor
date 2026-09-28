"""Runtime primitives shared by update pipelines."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

FetchBytes = Callable[[str], bytes]
Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def error_document(exc: BaseException) -> dict[str, str]:
    return {"type": type(exc).__name__, "message": str(exc)}
