"""Small HTTP transport with bounded retries for official-data collectors."""

from __future__ import annotations

import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderFetchError(RuntimeError):
    """Raised when an upstream provider cannot be fetched safely.

    HTTP failures retain the status code and response body so provider-specific
    collectors can distinguish a documented empty-result response from an
    actual transport or endpoint failure without parsing exception strings.
    """

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        status_code: int | None = None,
        response_body: bytes | None = None,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.status_code = status_code
        self.response_body = response_body


_USER_AGENT = "brazil-monetary-policy-monitor/0.1 (+official-data-collector)"
DEFAULT_HTTP_TIMEOUT = 30.0
DEFAULT_HTTP_RETRIES = 2
DEFAULT_HTTP_BACKOFF_SECONDS = 1.0


def fetch_bytes(
    url: str,
    *,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
    retries: int = DEFAULT_HTTP_RETRIES,
    backoff_seconds: float = DEFAULT_HTTP_BACKOFF_SECONDS,
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
        except HTTPError as exc:
            try:
                response_body = exc.read()
            except OSError:
                response_body = b""
            last_error = ProviderFetchError(
                f"HTTP Error {exc.code}: {exc.reason}",
                url=url,
                status_code=exc.code,
                response_body=response_body,
            )
            # Most client errors are deterministic. Retrying them only adds
            # load and delays useful diagnostics. 408/429 can be transient.
            if 400 <= exc.code < 500 and exc.code not in {408, 429}:
                break
            if attempt == retries:
                break
            time.sleep(backoff_seconds * (2**attempt))
        except (URLError, TimeoutError, OSError, ProviderFetchError) as exc:
            last_error = exc
            if attempt == retries:
                break
            time.sleep(backoff_seconds * (2**attempt))

    if isinstance(last_error, ProviderFetchError):
        raise ProviderFetchError(
            f"failed to fetch {url}: {last_error}",
            url=url,
            status_code=last_error.status_code,
            response_body=last_error.response_body,
        ) from last_error
    raise ProviderFetchError(f"failed to fetch {url}: {last_error}", url=url) from last_error
