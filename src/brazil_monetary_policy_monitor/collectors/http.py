"""Small HTTP transport with bounded retries for official-data collectors."""

from __future__ import annotations

import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderFetchError(RuntimeError):
    """Raised when an upstream provider cannot be fetched safely."""


_USER_AGENT = "brazil-monetary-policy-monitor/0.1 (+official-data-collector)"


def fetch_bytes(
    url: str,
    *,
    timeout: float = 20.0,
    retries: int = 2,
    backoff_seconds: float = 0.5,
) -> bytes:
    """Fetch bytes from ``url`` with a small bounded retry policy.

    Retries are intentionally conservative: scheduled collection benefits from
    tolerating brief network failures, but it must not hammer an official API
    or hide a persistent provider problem.
    """

    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if retries < 0:
        raise ValueError("retries cannot be negative")
    if backoff_seconds < 0:
        raise ValueError("backoff_seconds cannot be negative")

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        },
        method="GET",
    )

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise ProviderFetchError(f"unexpected HTTP status {status} for {url}")
                return response.read()
        except (HTTPError, URLError, TimeoutError, OSError, ProviderFetchError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(backoff_seconds * (2**attempt))

    raise ProviderFetchError(f"failed to fetch {url}: {last_error}") from last_error
