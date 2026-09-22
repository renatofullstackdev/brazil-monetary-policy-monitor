from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.error import URLError

from brazil_monetary_policy_monitor.collectors.http import ProviderFetchError, fetch_bytes


class FakeResponse:
    status = 200

    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class HTTPTransportTests(unittest.TestCase):
    @patch("brazil_monetary_policy_monitor.collectors.http.time.sleep")
    @patch("brazil_monetary_policy_monitor.collectors.http.urlopen")
    def test_transient_failure_is_retried_with_bounded_backoff(
        self, mock_urlopen, mock_sleep
    ) -> None:
        mock_urlopen.side_effect = [URLError("temporary"), FakeResponse(b"[]")]

        payload = fetch_bytes("https://example.invalid/data", retries=2, backoff_seconds=0.25)

        self.assertEqual(payload, b"[]")
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(0.25)

    @patch("brazil_monetary_policy_monitor.collectors.http.time.sleep")
    @patch("brazil_monetary_policy_monitor.collectors.http.urlopen")
    def test_persistent_failure_is_reported_after_retry_budget(
        self, mock_urlopen, mock_sleep
    ) -> None:
        mock_urlopen.side_effect = URLError("down")

        with self.assertRaisesRegex(ProviderFetchError, "failed to fetch"):
            fetch_bytes("https://example.invalid/data", retries=1, backoff_seconds=0)

        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
