"""Publish the static contract consumed by the Sprint 4 overview page."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any

from ..db.observations import observations_latest
from ..ingestion import SELIC_SERIES_KEY
from .atomic import write_json_atomic


OVERVIEW_SCHEMA_VERSION = 1


def _iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _unavailable(
    *,
    key: str,
    label: str,
    data_kind: str,
    unit: str,
    required_inputs: list[str],
    note: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": "unavailable",
        "data_kind": data_kind,
        "unit": unit,
        "required_inputs": required_inputs,
        "note": note,
        "latest": None,
        "observations": [],
        "source": None,
    }


def _selic_series(connection: sqlite3.Connection) -> dict[str, Any]:
    metadata = connection.execute(
        """
        SELECT
            s.key,
            s.title,
            s.description,
            s.unit_original,
            s.unit_normalized,
            s.frequency,
            s.data_kind,
            s.transformation,
            src.provider,
            src.name AS source_name,
            src.documentation_url
        FROM series AS s
        JOIN sources AS src ON src.id = s.source_id
        WHERE s.key = ?
        """,
        (SELIC_SERIES_KEY,),
    ).fetchone()
    if metadata is None:
        return _unavailable(
            key="selic",
            label="Selic",
            data_kind="observed",
            unit="percent_per_year",
            required_inputs=["br.selic.target"],
            note="A série oficial da meta Selic ainda não foi carregada no banco local.",
        )

    rows = observations_latest(connection, SELIC_SERIES_KEY)
    if not rows:
        return _unavailable(
            key="selic",
            label="Selic",
            data_kind="observed",
            unit=str(metadata["unit_normalized"]),
            required_inputs=["br.selic.target"],
            note="A série está cadastrada, mas ainda não possui observações.",
        )

    observations = [
        {
            "date": row["reference_period"],
            "value": row["value"],
            "available_at": row["available_at"],
        }
        for row in rows
    ]
    latest_row = rows[-1]
    return {
        "key": "selic",
        "series_key": metadata["key"],
        "label": "Selic",
        "title": metadata["title"],
        "description": metadata["description"],
        "status": "available",
        "data_kind": metadata["data_kind"],
        "unit": metadata["unit_normalized"],
        "display_unit": metadata["unit_original"],
        "frequency": metadata["frequency"],
        "transformation": metadata["transformation"],
        "required_inputs": [],
        "note": None,
        "latest": {
            "date": latest_row["reference_period"],
            "value": latest_row["value"],
            "available_at": latest_row["available_at"],
        },
        "observations": observations,
        "source": {
            "provider": metadata["provider"],
            "name": metadata["source_name"],
            "documentation_url": metadata["documentation_url"],
        },
    }


def build_overview_document(
    connection: sqlite3.Connection,
    *,
    generated_at: datetime,
) -> dict[str, Any]:
    """Build a view contract without fabricating unavailable analytical inputs."""

    series = {
        "selic": _selic_series(connection),
        "taylor_prospective": _unavailable(
            key="taylor_prospective",
            label="Taylor prospectiva",
            data_kind="derived",
            unit="percent_per_year",
            required_inputs=[
                "expected_inflation",
                "inflation_target",
                "neutral_real_rate",
                "output_gap",
            ],
            note=(
                "O cálculo será publicado quando expectativas, meta, taxa neutra "
                "e hiato estiverem disponíveis com proveniência explícita."
            ),
        ),
        "selic_minus_taylor": _unavailable(
            key="selic_minus_taylor",
            label="Selic − Taylor",
            data_kind="derived",
            unit="percentage_points",
            required_inputs=["selic", "taylor_prospective"],
            note="Depende da Taylor prospectiva publicada.",
        ),
        "ex_ante_real_rate": _unavailable(
            key="ex_ante_real_rate",
            label="Juro real ex ante",
            data_kind="derived",
            unit="percentage_points",
            required_inputs=["selic", "expected_inflation"],
            note="Depende da expectativa de inflação no horizonte definido.",
        ),
        "real_monetary_gap": _unavailable(
            key="real_monetary_gap",
            label="Gap monetário real",
            data_kind="derived",
            unit="percentage_points",
            required_inputs=["ex_ante_real_rate", "neutral_real_rate"],
            note="Depende do juro real ex ante e da taxa real neutra estimada.",
        ),
        "expected_inflation": _unavailable(
            key="expected_inflation",
            label="Inflação esperada",
            data_kind="survey",
            unit="percent_per_year",
            required_inputs=["focus.expected_inflation"],
            note="A coleta de expectativas Focus entra na Sprint 6.",
        ),
        "inflation_target": _unavailable(
            key="inflation_target",
            label="Meta de inflação",
            data_kind="observed",
            unit="percent_per_year",
            required_inputs=["inflation.target"],
            note="A meta será incorporada como dado oficial versionado.",
        ),
        "neutral_real_rate": _unavailable(
            key="neutral_real_rate",
            label="Taxa real neutra",
            data_kind="estimated",
            unit="percent_per_year",
            required_inputs=["neutral.real.rate"],
            note="A taxa neutra é estimada e ainda não foi incorporada ao banco.",
        ),
        "output_gap": _unavailable(
            key="output_gap",
            label="Hiato do produto",
            data_kind="estimated",
            unit="percentage_points",
            required_inputs=["output.gap"],
            note="O hiato é estimado e ainda não foi incorporado ao banco.",
        ),
    }

    available = sum(item["status"] == "available" for item in series.values())
    return {
        "schema_version": OVERVIEW_SCHEMA_VERSION,
        "view": "overview",
        "country": "BR",
        "generated_at": _iso_z(generated_at),
        "knowledge_mode": "latest_revision",
        "availability": {
            "status": "partial" if available < len(series) else "complete",
            "available_series": available,
            "total_series": len(series),
        },
        "series": series,
        "notes": [
            "Séries indisponíveis permanecem explícitas; o publicador não cria dados substitutos.",
            "A visão usa a revisão mais recente conhecida nesta sprint; seleção histórica de vintage virá depois.",
        ],
    }


def publish_overview_json(
    connection: sqlite3.Connection,
    *,
    output_path: str | Path,
    generated_at: datetime,
) -> Path:
    return write_json_atomic(
        build_overview_document(connection, generated_at=generated_at),
        output_path,
    )
