"""Command-line entry points for scheduled data updates."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
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
from .ingestion import ensure_bcb_sgs_selic_metadata, ensure_bcb_focus_metadata
from .pipeline import (
    DEFAULT_WINDOW_YEARS,
    DEFAULT_MACRO_LOOKBACK_DAYS,
    DEFAULT_MACRO_OVERLAP_DAYS,
    DEFAULT_CREDIT_LOOKBACK_DAYS,
    DEFAULT_CREDIT_OVERLAP_DAYS,
    DEFAULT_FISCAL_LOOKBACK_DAYS,
    DEFAULT_FISCAL_OVERLAP_DAYS,
    DEFAULT_YIELD_CURVE_LOOKBACK_DAYS,
    DEFAULT_YIELD_CURVE_OVERLAP_DAYS,
    resolve_focus_incremental_start,
    resolve_incremental_start,
    update_focus_ipca,
    update_macro_context,
    update_credit_context,
    update_fiscal_context,
    update_yield_curve,
    update_selic,
)
from .publish import publish_overview_json


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



def _update_focus(args: argparse.Namespace) -> int:
    end = args.end or date.today()
    if args.start is None:
        connection = initialize_database(args.database)
        try:
            ensure_bcb_focus_metadata(connection)
            start = resolve_focus_incremental_start(
                connection,
                end=end,
                overlap_days=args.overlap_days,
                initial_lookback_days=args.initial_lookback_days,
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
    result = update_focus_ipca(
        database_path=args.database,
        raw_root=args.raw_dir,
        published_path=args.output,
        overview_path=args.overview_output,
        start=start,
        end=end,
        fetcher=fetcher,
        page_size=args.page_size,
        window_days=args.window_days,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0



def _update_macro(args: argparse.Namespace) -> int:
    end = args.end or date.today()
    fetcher = partial(
        fetch_bytes,
        timeout=args.timeout,
        retries=args.retries,
        backoff_seconds=args.backoff_seconds,
    )
    result = update_macro_context(
        database_path=args.database,
        raw_root=args.raw_dir,
        published_dir=args.published_dir,
        overview_path=args.overview_output,
        start=args.start,
        end=end,
        fetcher=fetcher,
        overlap_days=args.overlap_days,
        initial_lookback_days=args.initial_lookback_days,
        window_years=args.window_years,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0



def _update_credit(args: argparse.Namespace) -> int:
    end = args.end or date.today()
    fetcher = partial(
        fetch_bytes,
        timeout=args.timeout,
        retries=args.retries,
        backoff_seconds=args.backoff_seconds,
    )
    result = update_credit_context(
        database_path=args.database,
        raw_root=args.raw_dir,
        published_dir=args.published_dir,
        credit_output_path=args.output,
        start=args.start,
        end=end,
        fetcher=fetcher,
        overlap_days=args.overlap_days,
        initial_lookback_days=args.initial_lookback_days,
        window_years=args.window_years,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0

def _update_fiscal(args: argparse.Namespace) -> int:
    end = args.end or date.today()
    fetcher = partial(
        fetch_bytes,
        timeout=args.timeout,
        retries=args.retries,
        backoff_seconds=args.backoff_seconds,
    )
    result = update_fiscal_context(
        database_path=args.database,
        raw_root=args.raw_dir,
        published_dir=args.published_dir,
        fiscal_output_path=args.output,
        start=args.start,
        end=end,
        fetcher=fetcher,
        overlap_days=args.overlap_days,
        initial_lookback_days=args.initial_lookback_days,
        window_years=args.window_years,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _update_yield_curve(args: argparse.Namespace) -> int:
    end = args.end or date.today()
    fetcher = partial(
        fetch_bytes,
        timeout=args.timeout,
        retries=args.retries,
        backoff_seconds=args.backoff_seconds,
    )
    result = update_yield_curve(
        database_path=args.database,
        raw_root=args.raw_dir,
        published_path=args.output,
        start=args.start,
        end=end,
        fetcher=fetcher,
        overlap_days=args.overlap_days,
        initial_lookback_days=args.initial_lookback_days,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _publish_overview(args: argparse.Namespace) -> int:
    connection = initialize_database(args.database)
    try:
        target = publish_overview_json(
            connection,
            output_path=args.output,
            generated_at=datetime.now(timezone.utc),
        )
    finally:
        connection.close()

    print(json.dumps({"published_path": str(target)}, ensure_ascii=False, indent=2))
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

    focus = subparsers.add_parser(
        "update-focus",
        help="Collect Focus monthly IPCA medians and derive the Copom-horizon expectation",
    )
    focus.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    focus.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    focus.add_argument(
        "--output",
        type=Path,
        default=Path("data/published/br-focus-ipca-policy-horizon.json"),
    )
    focus.add_argument(
        "--overview-output",
        type=Path,
        default=Path("web/data/overview.json"),
    )
    focus.add_argument("--start", type=_date_argument)
    focus.add_argument("--end", type=_date_argument)
    focus.add_argument("--overlap-days", type=int, default=21)
    focus.add_argument("--initial-lookback-days", type=int, default=730)
    focus.add_argument("--page-size", type=int, default=10000)
    focus.add_argument(
        "--window-days",
        type=int,
        choices=range(1, 367),
        default=30,
        metavar="1..366",
        help="calendar days per Focus request (default: %(default)s)",
    )
    focus.add_argument("--timeout", type=float, default=DEFAULT_HTTP_TIMEOUT)
    focus.add_argument("--retries", type=int, default=DEFAULT_HTTP_RETRIES)
    focus.add_argument("--backoff-seconds", type=float, default=DEFAULT_HTTP_BACKOFF_SECONDS)
    focus.set_defaults(handler=_update_focus)

    macro = subparsers.add_parser(
        "update-macro",
        help="Collect Sprint 7 inflation, activity and labor SGS series",
    )
    macro.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    macro.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    macro.add_argument("--published-dir", type=Path, default=Path("data/published"))
    macro.add_argument("--overview-output", type=Path, default=Path("web/data/overview.json"))
    macro.add_argument("--start", type=_date_argument)
    macro.add_argument("--end", type=_date_argument)
    macro.add_argument("--overlap-days", type=int, default=DEFAULT_MACRO_OVERLAP_DAYS)
    macro.add_argument("--initial-lookback-days", type=int, default=DEFAULT_MACRO_LOOKBACK_DAYS)
    macro.add_argument(
        "--window-years", type=int, choices=range(1, 11), default=DEFAULT_WINDOW_YEARS,
        metavar="1..10", help="calendar years per SGS request (default: %(default)s)",
    )
    macro.add_argument("--timeout", type=float, default=DEFAULT_HTTP_TIMEOUT)
    macro.add_argument("--retries", type=int, default=DEFAULT_HTTP_RETRIES)
    macro.add_argument("--backoff-seconds", type=float, default=DEFAULT_HTTP_BACKOFF_SECONDS)
    macro.set_defaults(handler=_update_macro)


    fiscal = subparsers.add_parser(
        "update-fiscal",
        help="Collect Sprint 10 fiscal SGS series and publish the RMD profile",
    )
    fiscal.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    fiscal.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    fiscal.add_argument("--published-dir", type=Path, default=Path("data/published"))
    fiscal.add_argument("--output", type=Path, default=Path("web/data/fiscal.json"))
    fiscal.add_argument("--start", type=_date_argument)
    fiscal.add_argument("--end", type=_date_argument)
    fiscal.add_argument("--overlap-days", type=int, default=DEFAULT_FISCAL_OVERLAP_DAYS)
    fiscal.add_argument("--initial-lookback-days", type=int, default=DEFAULT_FISCAL_LOOKBACK_DAYS)
    fiscal.add_argument(
        "--window-years", type=int, choices=range(1, 11), default=DEFAULT_WINDOW_YEARS, metavar="1..10"
    )
    fiscal.add_argument("--timeout", type=float, default=DEFAULT_HTTP_TIMEOUT)
    fiscal.add_argument("--retries", type=int, default=DEFAULT_HTTP_RETRIES)
    fiscal.add_argument("--backoff-seconds", type=float, default=DEFAULT_HTTP_BACKOFF_SECONDS)
    fiscal.set_defaults(handler=_update_fiscal)

    credit = subparsers.add_parser(
        "update-credit",
        help="Collect Sprint 9 credit and transmission SGS series",
    )
    credit.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    credit.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    credit.add_argument("--published-dir", type=Path, default=Path("data/published"))
    credit.add_argument("--output", type=Path, default=Path("web/data/credit-transmission.json"))
    credit.add_argument("--start", type=_date_argument)
    credit.add_argument("--end", type=_date_argument)
    credit.add_argument("--overlap-days", type=int, default=DEFAULT_CREDIT_OVERLAP_DAYS)
    credit.add_argument("--initial-lookback-days", type=int, default=DEFAULT_CREDIT_LOOKBACK_DAYS)
    credit.add_argument(
        "--window-years", type=int, choices=range(1, 11), default=DEFAULT_WINDOW_YEARS,
        metavar="1..10", help="calendar years per SGS request (default: %(default)s)",
    )
    credit.add_argument("--timeout", type=float, default=DEFAULT_HTTP_TIMEOUT)
    credit.add_argument("--retries", type=int, default=DEFAULT_HTTP_RETRIES)
    credit.add_argument("--backoff-seconds", type=float, default=DEFAULT_HTTP_BACKOFF_SECONDS)
    credit.set_defaults(handler=_update_credit)


    curve = subparsers.add_parser(
        "update-yield-curve",
        help="Collect Tesouro Direto offered-title rates and publish curve proxies",
    )
    curve.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    curve.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    curve.add_argument("--output", type=Path, default=Path("web/data/yield-curve.json"))
    curve.add_argument("--start", type=_date_argument)
    curve.add_argument("--end", type=_date_argument)
    curve.add_argument("--overlap-days", type=int, default=DEFAULT_YIELD_CURVE_OVERLAP_DAYS)
    curve.add_argument("--initial-lookback-days", type=int, default=DEFAULT_YIELD_CURVE_LOOKBACK_DAYS)
    curve.add_argument("--timeout", type=float, default=max(DEFAULT_HTTP_TIMEOUT, 60.0))
    curve.add_argument("--retries", type=int, default=DEFAULT_HTTP_RETRIES)
    curve.add_argument("--backoff-seconds", type=float, default=DEFAULT_HTTP_BACKOFF_SECONDS)
    curve.set_defaults(handler=_update_yield_curve)

    overview = subparsers.add_parser(
        "publish-overview",
        help="Publish the static JSON contract consumed by the overview page",
    )
    overview.add_argument(
        "--database",
        type=Path,
        default=Path("data/database/monitor.sqlite3"),
    )
    overview.add_argument(
        "--output",
        type=Path,
        default=Path("web/data/overview.json"),
    )
    overview.set_defaults(handler=_publish_overview)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
