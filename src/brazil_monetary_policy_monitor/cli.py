"""Command-line entry points for scheduled data updates."""

from __future__ import annotations

import argparse
from datetime import date
import json
from functools import partial
from pathlib import Path

from .db import initialize_database
from .collectors.http import (
    DEFAULT_HTTP_BACKOFF_SECONDS,
    DEFAULT_HTTP_RETRIES,
    DEFAULT_HTTP_TIMEOUT,
    fetch_bytes,
)
from .ingestion import ensure_bcb_sgs_selic_metadata
from .pipeline import DEFAULT_WINDOW_YEARS, resolve_incremental_start, update_selic


def _date_argument(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected date in YYYY-MM-DD format") from exc


def _update_selic(args: argparse.Namespace) -> int:
    end = args.end or date.today()
    if args.start is None:
        connection = initialize_database(args.database)
        try:
            ensure_bcb_sgs_selic_metadata(connection)
            start = resolve_incremental_start(
                connection,
                end=end,
                overlap_days=args.overlap_days,
            )
        finally:
            connection.close()
    else:
        start = args.start

    fetcher = partial(
        fetch_bytes,
        timeout=args.timeout,
        retries=args.retries,
        backoff_seconds=args.backoff_seconds,
    )

    result = update_selic(
        database_path=args.database,
        raw_root=args.raw_dir,
        published_path=args.output,
        start=start,
        end=end,
        fetcher=fetcher,
        window_years=args.window_years,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    selic = subparsers.add_parser(
        "update-selic",
        help="Collect, persist and publish BCB SGS series 432",
    )
    selic.add_argument(
        "--database",
        type=Path,
        default=Path("data/database/monitor.sqlite3"),
    )
    selic.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    selic.add_argument(
        "--output",
        type=Path,
        default=Path("data/published/br-selic-target.json"),
    )
    selic.add_argument("--start", type=_date_argument)
    selic.add_argument("--end", type=_date_argument)
    selic.add_argument("--overlap-days", type=int, default=7)
    selic.add_argument(
        "--window-years",
        type=int,
        choices=range(1, 11),
        default=DEFAULT_WINDOW_YEARS,
        metavar="1..10",
        help="calendar years per SGS request (default: %(default)s)",
    )
    selic.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_HTTP_TIMEOUT,
        help="HTTP socket timeout in seconds (default: %(default)s)",
    )
    selic.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_HTTP_RETRIES,
        help="retries after the first HTTP attempt (default: %(default)s)",
    )
    selic.add_argument(
        "--backoff-seconds",
        type=float,
        default=DEFAULT_HTTP_BACKOFF_SECONDS,
        help="initial exponential retry backoff in seconds (default: %(default)s)",
    )
    selic.set_defaults(handler=_update_selic)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
