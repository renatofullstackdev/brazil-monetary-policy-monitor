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
    post_form_bytes,
)
from .ingestion.focus import ensure_bcb_focus_metadata
from .ingestion.sgs import ensure_bcb_sgs_selic_metadata
from .pipelines.copom import update_copom_events
from .pipelines.credit import (
    DEFAULT_CREDIT_LOOKBACK_DAYS,
    DEFAULT_CREDIT_OVERLAP_DAYS,
    update_credit_context,
)
from .pipelines.external import (
    DEFAULT_EXTERNAL_LOOKBACK_DAYS,
    DEFAULT_EXTERNAL_OVERLAP_DAYS,
    update_external_context,
)
from .pipelines.fiscal import (
    DEFAULT_FISCAL_LOOKBACK_DAYS,
    DEFAULT_FISCAL_OVERLAP_DAYS,
    update_fiscal_context,
)
from .pipelines.focus import (
    DEFAULT_FOCUS_INITIAL_LOOKBACK_DAYS,
    DEFAULT_FOCUS_OVERLAP_DAYS,
    resolve_focus_incremental_start,
    rebuild_focus_policy_horizon_history,
    update_focus_ipca,
)
from .pipelines.policy import sync_policy_inputs
from .pipelines.macro import (
    DEFAULT_MACRO_LOOKBACK_DAYS,
    DEFAULT_MACRO_OVERLAP_DAYS,
    update_macro_context,
)
from .pipelines.market_curves import update_market_curves
from .pipelines.selic import (
    DEFAULT_OVERLAP_DAYS as DEFAULT_SELIC_OVERLAP_DAYS,
    resolve_incremental_start,
    update_selic,
)
from .pipelines.sgs import DEFAULT_WINDOW_YEARS
from .pipelines.us import (
    DEFAULT_US_LOOKBACK_DAYS,
    DEFAULT_US_OVERLAP_DAYS,
    update_us_context,
)
from .publish import publish_overview_json
from .publish.vintages import publish_vintage_archive


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



def _sync_policy_history(args: argparse.Namespace) -> int:
    result = sync_policy_inputs(
        database_path=args.database,
        overview_path=args.overview_output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _rebuild_focus_history(args: argparse.Namespace) -> int:
    result = rebuild_focus_policy_horizon_history(
        database_path=args.database,
        published_path=args.output,
        overview_path=args.overview_output,
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


def _update_external(args: argparse.Namespace) -> int:
    end = args.end or date.today()
    fetcher = partial(
        fetch_bytes,
        timeout=args.timeout,
        retries=args.retries,
        backoff_seconds=args.backoff_seconds,
    )
    result = update_external_context(
        database_path=args.database,
        raw_root=args.raw_dir,
        published_dir=args.published_dir,
        external_output_path=args.output,
        start=args.start,
        end=end,
        fetcher=fetcher,
        overlap_days=args.overlap_days,
        initial_lookback_days=args.initial_lookback_days,
        window_years=args.window_years,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _update_us(args: argparse.Namespace) -> int:
    end = args.end or date.today()
    fetcher = partial(fetch_bytes, timeout=args.timeout, retries=args.retries, backoff_seconds=args.backoff_seconds)
    result = update_us_context(
        database_path=args.database, raw_root=args.raw_dir, published_dir=args.published_dir,
        us_output_path=args.output, start=args.start, end=end, fetcher=fetcher,
        overlap_days=args.overlap_days, initial_lookback_days=args.initial_lookback_days,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _update_market_curves(args: argparse.Namespace) -> int:
    end = args.end or date.today()
    get_fetcher = partial(
        fetch_bytes,
        timeout=args.timeout,
        retries=args.retries,
        backoff_seconds=args.backoff_seconds,
        headers={"Accept": "application/zip,application/octet-stream,*/*", "User-Agent": "Mozilla/5.0 (compatible; brazil-monetary-policy-monitor/0.1)"},
    )
    post_fetcher = partial(
        post_form_bytes,
        timeout=args.timeout,
        retries=args.retries,
        backoff_seconds=args.backoff_seconds,
    )
    result = update_market_curves(
        database_path=args.database,
        raw_root=args.raw_dir,
        published_path=args.output,
        start=args.start,
        end=end,
        get_fetcher=get_fetcher,
        post_fetcher=post_fetcher,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _update_copom(args: argparse.Namespace) -> int:
    fetcher = partial(
        fetch_bytes,
        timeout=args.timeout,
        retries=args.retries,
        backoff_seconds=args.backoff_seconds,
    )
    result = update_copom_events(
        database_path=args.database,
        raw_root=args.raw_dir,
        output_path=args.output,
        yield_curve_output_path=args.yield_curve_output,
        fetcher=fetcher,
        quantity=args.quantity,
        detail_limit=args.detail_limit,
        rpm_quantity=args.rpm_quantity,
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



def _publish_vintages(args: argparse.Namespace) -> int:
    generated_at = datetime.now(timezone.utc)
    connection = initialize_database(args.database)
    try:
        selected_dates = None if not args.date else args.date
        target = publish_vintage_archive(
            connection,
            root=args.output_dir,
            generated_at=generated_at,
            selected_dates=selected_dates,
        )
    finally:
        connection.close()
    print(json.dumps({"index_path": str(target)}, ensure_ascii=False, indent=2))
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
    selic.add_argument("--overlap-days", type=int, default=DEFAULT_SELIC_OVERLAP_DAYS)
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
    focus.add_argument("--overlap-days", type=int, default=DEFAULT_FOCUS_OVERLAP_DAYS)
    focus.add_argument("--initial-lookback-days", type=int, default=DEFAULT_FOCUS_INITIAL_LOOKBACK_DAYS)
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

    focus_rebuild = subparsers.add_parser(
        "rebuild-focus-history",
        help="Rebuild historical policy-horizon Focus vintages from the local raw series",
    )
    focus_rebuild.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    focus_rebuild.add_argument("--output", type=Path, default=Path("data/published/br-focus-ipca-policy-horizon.json"))
    focus_rebuild.add_argument("--overview-output", type=Path, default=Path("web/data/overview.json"))
    focus_rebuild.set_defaults(handler=_rebuild_focus_history)

    policy_history = subparsers.add_parser(
        "sync-policy-history",
        help="Persist source-backed inflation-target, neutral-rate and output-gap history",
    )
    policy_history.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    policy_history.add_argument("--overview-output", type=Path, default=Path("web/data/overview.json"))
    policy_history.set_defaults(handler=_sync_policy_history)

    macro = subparsers.add_parser(
        "update-macro",
        help="Collect Brazilian inflation, activity and labor SGS series",
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
        help="Collect Brazilian fiscal SGS series and publish the current RMD profile",
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
        help="Collect Brazilian credit and monetary-transmission SGS series",
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


    external = subparsers.add_parser(
        "update-external",
        help="Collect Brazilian external-sector and exchange-rate SGS series",
    )
    external.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    external.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    external.add_argument("--published-dir", type=Path, default=Path("data/published"))
    external.add_argument("--output", type=Path, default=Path("web/data/external-sector.json"))
    external.add_argument("--start", type=_date_argument)
    external.add_argument("--end", type=_date_argument)
    external.add_argument("--overlap-days", type=int, default=DEFAULT_EXTERNAL_OVERLAP_DAYS)
    external.add_argument("--initial-lookback-days", type=int, default=DEFAULT_EXTERNAL_LOOKBACK_DAYS)
    external.add_argument(
        "--window-years", type=int, choices=range(1, 11), default=DEFAULT_WINDOW_YEARS,
        metavar="1..10", help="calendar years per SGS request (default: %(default)s)",
    )
    external.add_argument("--timeout", type=float, default=DEFAULT_HTTP_TIMEOUT)
    external.add_argument("--retries", type=int, default=DEFAULT_HTTP_RETRIES)
    external.add_argument("--backoff-seconds", type=float, default=DEFAULT_HTTP_BACKOFF_SECONDS)
    external.set_defaults(handler=_update_external)


    us = subparsers.add_parser(
        "update-us", help="Collect US benchmarks and Brazil-US differentials",
    )
    us.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    us.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    us.add_argument("--published-dir", type=Path, default=Path("data/published"))
    us.add_argument("--output", type=Path, default=Path("web/data/us-benchmark.json"))
    us.add_argument("--start", type=_date_argument)
    us.add_argument("--end", type=_date_argument)
    us.add_argument("--overlap-days", type=int, default=DEFAULT_US_OVERLAP_DAYS)
    us.add_argument("--initial-lookback-days", type=int, default=DEFAULT_US_LOOKBACK_DAYS)
    us.add_argument("--timeout", type=float, default=DEFAULT_HTTP_TIMEOUT)
    us.add_argument("--retries", type=int, default=DEFAULT_HTTP_RETRIES)
    us.add_argument("--backoff-seconds", type=float, default=DEFAULT_HTTP_BACKOFF_SECONDS)
    us.set_defaults(handler=_update_us)


    market_curves = subparsers.add_parser(
        "update-market-curves",
        help="Collect ANBIMA ETTJ and B3 DI1 and publish market term structures",
    )
    market_curves.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    market_curves.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    market_curves.add_argument("--output", type=Path, default=Path("web/data/yield-curve.json"))
    market_curves.add_argument("--start", type=_date_argument)
    market_curves.add_argument("--end", type=_date_argument)
    market_curves.add_argument("--timeout", type=float, default=max(DEFAULT_HTTP_TIMEOUT, 60.0))
    market_curves.add_argument("--retries", type=int, default=DEFAULT_HTTP_RETRIES)
    market_curves.add_argument("--backoff-seconds", type=float, default=DEFAULT_HTTP_BACKOFF_SECONDS)
    market_curves.set_defaults(handler=_update_market_curves)

    copom = subparsers.add_parser(
        "update-copom",
        help="Collect Copom statements/minutes, sync calendar events and publish annotations",
    )
    copom.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    copom.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    copom.add_argument("--output", type=Path, default=Path("web/data/copom-events.json"))
    copom.add_argument("--yield-curve-output", type=Path, default=Path("web/data/yield-curve.json"))
    copom.add_argument("--quantity", type=int, default=40, help="number of recent records requested from each Copom list")
    copom.add_argument("--detail-limit", type=int, default=8, help="number of most recent meetings whose detail endpoint is snapshotted")
    copom.add_argument("--rpm-quantity", type=int, default=12, help="number of published RPM records requested (default: %(default)s)")
    copom.add_argument("--timeout", type=float, default=DEFAULT_HTTP_TIMEOUT)
    copom.add_argument("--retries", type=int, default=DEFAULT_HTTP_RETRIES)
    copom.add_argument("--backoff-seconds", type=float, default=DEFAULT_HTTP_BACKOFF_SECONDS)
    copom.set_defaults(handler=_update_copom)

    vintages = subparsers.add_parser(
        "publish-vintages",
        help="Publish static as-known bundles from locally defensible vintages",
    )
    vintages.add_argument("--database", type=Path, default=Path("data/database/monitor.sqlite3"))
    vintages.add_argument("--output-dir", type=Path, default=Path("web/data/vintages"))
    vintages.add_argument(
        "--date",
        action="append",
        type=_date_argument,
        help="Publish only this YYYY-MM-DD cutoff; repeat for multiple dates. Default: first local date, monthly checkpoints and today.",
    )
    vintages.set_defaults(handler=_publish_vintages)

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
