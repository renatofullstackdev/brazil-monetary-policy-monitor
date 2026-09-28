"""Source registration for market term structures.

The current B3 DI1 source remains registered only for the existing dataset.
The next market-curves increment replaces it with TaxaSwap/PRE rather than extending this provisional
transport.
"""

from __future__ import annotations

import json
import sqlite3

ANBIMA_ETTJ_SOURCE_KEY = "anbima.ettj"
B3_DI1_SOURCE_KEY = "b3.di1"


def ensure_market_curve_sources(connection: sqlite3.Connection) -> tuple[int, int]:
    from ..collectors.anbima_ettj import (
        ANBIMA_ETTJ_DOWNLOAD_URL,
        ANBIMA_ETTJ_METHODOLOGY_URL,
        ANBIMA_ETTJ_PAGE_URL,
    )
    from ..collectors.b3_di1 import B3_PRICE_REPORT_CATALOG_URL, B3_PRICE_REPORT_PAGE_URL

    rows = (
        (
            ANBIMA_ETTJ_SOURCE_KEY,
            "ANBIMA",
            "Estrutura a Termo das Taxas de Juros (ETTJ)",
            ANBIMA_ETTJ_DOWNLOAD_URL,
            ANBIMA_ETTJ_METHODOLOGY_URL,
            None,
            {
                "frequency": "daily",
                "landing_page": ANBIMA_ETTJ_PAGE_URL,
                "curves": ["prefixada", "ipca", "inflacao_implicita"],
                "tenor_unit": "business_days",
                "model": "Svensson",
                "transport_status": "public-current-only; historical Feed integration planned",
            },
        ),
        (
            B3_DI1_SOURCE_KEY,
            "B3",
            "BVBG.187.01 - Simplified Price Report - Derivatives (DI1)",
            B3_PRICE_REPORT_PAGE_URL,
            B3_PRICE_REPORT_CATALOG_URL,
            None,
            {
                "frequency": "daily",
                "instrument": "DI1",
                "quote_fields": ["AdjstdQt", "AdjstdQtTax"],
                "tenor_unit": "business_days",
                "transport_status": "provisional; scheduled for replacement by TaxaSwap/PRE",
            },
        ),
    )
    for key, provider, name, url, documentation_url, license_name, metadata in rows:
        connection.execute(
            """
            INSERT INTO sources(key, provider, name, url, documentation_url, license, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                provider = excluded.provider,
                name = excluded.name,
                url = excluded.url,
                documentation_url = excluded.documentation_url,
                license = excluded.license,
                metadata_json = excluded.metadata_json,
                updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            """,
            (key, provider, name, url, documentation_url, license_name, json.dumps(metadata, sort_keys=True)),
        )
    connection.commit()
    ids: list[int] = []
    for key in (ANBIMA_ETTJ_SOURCE_KEY, B3_DI1_SOURCE_KEY):
        row = connection.execute("SELECT id FROM sources WHERE key = ?", (key,)).fetchone()
        assert row is not None
        ids.append(int(row[0]))
    return ids[0], ids[1]
