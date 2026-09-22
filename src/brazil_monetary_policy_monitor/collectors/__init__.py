"""Provider collectors and transport primitives."""

from .bcb_sgs import SGSRecord, build_sgs_url, iter_date_windows, parse_sgs_json
from .http import ProviderFetchError, fetch_bytes

__all__ = [
    "ProviderFetchError",
    "SGSRecord",
    "build_sgs_url",
    "fetch_bytes",
    "iter_date_windows",
    "parse_sgs_json",
]
