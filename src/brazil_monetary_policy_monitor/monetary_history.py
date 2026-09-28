"""Historical reconstruction of Brazil's monetary-policy posture.

The reconstruction is driven by Focus expectation vintages.  Each published
point uses only inputs that were defensibly available by that point's knowledge
boundary.  Derived series are not persisted: official/provider observations and
documentary parameters remain the sources of truth, while the rule is rebuilt
reproducibly at publication time.
"""

from __future__ import annotations

from datetime import date, datetime
import json
import sqlite3
from typing import Any

from .db.observations import observation_vintages
from .db.parameters import parameter_for_reference_date
from .ingestion.focus import FOCUS_IPCA_POLICY_HORIZON_SERIES_KEY
from .ingestion.policy import OUTPUT_GAP_SERIES_KEY
from .ingestion.sgs import SELIC_SERIES_KEY
from .models.monetary import ex_ante_real_rate, prospective_taylor, real_monetary_gap
from .vintages import KnowledgeContext, iso_z


def _date_from_timestamp(value: str) -> date:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _weekly_focus_rows(
    connection: sqlite3.Connection,
    context: KnowledgeContext,
) -> list[sqlite3.Row]:
    """Keep the last defensibly available Focus point in each ISO week."""

    cutoff = context.cutoff if context.mode == "as_known" else iso_z(context.generated_at)
    rows = observation_vintages(
        connection,
        FOCUS_IPCA_POLICY_HORIZON_SERIES_KEY,
        knowledge_cutoff=cutoff,
    )
    by_week: dict[tuple[int, int], sqlite3.Row] = {}
    for row in rows:
        available_date = _date_from_timestamp(str(row["available_at"]))
        iso = available_date.isocalendar()
        bucket = (iso.year, iso.week)
        previous = by_week.get(bucket)
        if previous is None or (
            str(row["available_at"]),
            str(row["source_observation_at"] or ""),
            int(row["id"]),
        ) > (
            str(previous["available_at"]),
            str(previous["source_observation_at"] or ""),
            int(previous["id"]),
        ):
            by_week[bucket] = row
    return sorted(
        by_week.values(),
        key=lambda row: (str(row["available_at"]), str(row["source_observation_at"] or ""), int(row["id"])),
    )


def _latest_observation_as_of(
    connection: sqlite3.Connection,
    *,
    series_key: str,
    knowledge_cutoff: str,
    reference_date: str,
    allow_current_period: bool = False,
) -> sqlite3.Row | None:
    reference_predicate = (
        "o.reference_start <= :reference_date"
        if allow_current_period
        else "o.reference_end <= :reference_date"
    )
    return connection.execute(
        f"""
        SELECT o.*
        FROM observations AS o
        JOIN series AS s ON s.id = o.series_id
        WHERE s.key = :series_key
          AND o.available_at <= :knowledge_cutoff
          AND {reference_predicate}
        ORDER BY
            o.reference_start DESC,
            o.reference_end DESC,
            o.available_at DESC,
            COALESCE(o.source_observation_at, '') DESC,
            o.first_seen_at DESC,
            o.id DESC
        LIMIT 1
        """,
        {
            "series_key": series_key,
            "knowledge_cutoff": knowledge_cutoff,
            "reference_date": reference_date,
        },
    ).fetchone()


def _parameter_lineage(row: sqlite3.Row, *, label: str) -> dict[str, Any]:
    metadata = json.loads(row["metadata_json"] or "{}")
    return {
        "label": label,
        "value": row["value"],
        "available_at": row["available_at"],
        "effective_from": row["effective_from"],
        "effective_to": row["effective_to"],
        "reference_period": metadata.get("reference_period"),
        "source_reference": row["source_reference"],
        "version_key": row["version_key"],
    }


def _observation_lineage(
    row: sqlite3.Row,
    *,
    label: str,
    include_provenance: bool = False,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "label": label,
        "value": row["value"],
        "reference_period": row["reference_period"],
        "reference_start": row["reference_start"],
        "reference_end": row["reference_end"],
        "available_at": row["available_at"],
        "source_observation_at": row["source_observation_at"],
        "source_revision": row["source_revision"],
        "vintage_key": row["vintage_key"],
    }
    if include_provenance:
        try:
            flags = json.loads(row["quality_flags_json"] or "[]")
        except json.JSONDecodeError:
            flags = []
        provenance = next(
            (flag for flag in flags if isinstance(flag, dict) and flag.get("report_key")),
            None,
        )
        if provenance:
            item["source_label"] = provenance.get("source_label")
            item["source_url"] = provenance.get("source_url")
            item["source_reference"] = provenance.get("source_reference")
    return item


def build_monetary_posture_history(
    connection: sqlite3.Connection,
    *,
    context: KnowledgeContext,
) -> dict[str, list[dict[str, Any]]]:
    """Reconstruct weekly derived posture series with point-level lineage.

    The Focus proxy is the clock because the prospective metrics cannot change
    meaningfully without a new expectation vintage.  Since the provider's exact
    historical release timestamp is unavailable, one point is kept per ISO week:
    the latest Focus vintage whose conservative ``available_at`` falls in that
    week.  Every other input is then selected with an as-of join at that same
    knowledge boundary.
    """

    history: dict[str, list[dict[str, Any]]] = {
        "ex_ante_real_rate": [],
        "real_monetary_gap": [],
        "taylor_prospective": [],
        "selic_minus_taylor": [],
    }

    for expected in _weekly_focus_rows(connection, context):
        cutoff = str(expected["available_at"])
        evaluation_date = _date_from_timestamp(cutoff).isoformat()

        selic = _latest_observation_as_of(
            connection,
            series_key=SELIC_SERIES_KEY,
            knowledge_cutoff=cutoff,
            reference_date=evaluation_date,
        )
        neutral = parameter_for_reference_date(
            connection,
            "br.neutral_real_rate.rpm",
            reference_date=evaluation_date,
            knowledge_cutoff=cutoff,
        )
        target = parameter_for_reference_date(
            connection,
            "br.inflation.target",
            reference_date=str(expected["reference_end"]),
            knowledge_cutoff=cutoff,
        )
        output_gap = _latest_observation_as_of(
            connection,
            series_key=OUTPUT_GAP_SERIES_KEY,
            knowledge_cutoff=cutoff,
            reference_date=evaluation_date,
            allow_current_period=True,
        )

        expected_lineage = _observation_lineage(
            expected,
            label="Inflação esperada no horizonte da política monetária",
        )
        common = {
            "date": evaluation_date,
            "available_at": cutoff,
            "as_of_date": expected["source_observation_at"],
            "reference_period": expected["reference_period"],
        }

        ex_ante_value: float | None = None
        if selic is not None:
            ex_ante_value = ex_ante_real_rate(
                nominal_rate=float(selic["value"]),
                expected_inflation=float(expected["value"]),
            )
            ex_ante_lineage = {
                "selic": _observation_lineage(selic, label="Meta Selic"),
                "expected_inflation": expected_lineage,
            }
            history["ex_ante_real_rate"].append({
                **common,
                "value": ex_ante_value,
                "lineage": ex_ante_lineage,
            })

        if ex_ante_value is not None and neutral is not None:
            history["real_monetary_gap"].append({
                **common,
                "value": real_monetary_gap(
                    ex_ante_rate=ex_ante_value,
                    neutral_real_rate=float(neutral["value"]),
                ),
                "lineage": {
                    "selic": _observation_lineage(selic, label="Meta Selic"),
                    "expected_inflation": expected_lineage,
                    "neutral_real_rate": _parameter_lineage(
                        neutral, label="Taxa real neutra assumida pelo Copom"
                    ),
                },
            })

        if target is None or neutral is None or output_gap is None:
            continue
        taylor_result = prospective_taylor(
            expected_inflation=float(expected["value"]),
            inflation_target=float(target["value"]),
            neutral_real_rate=float(neutral["value"]),
            output_gap=float(output_gap["value"]),
        )
        taylor_lineage = {
            "expected_inflation": expected_lineage,
            "inflation_target": _parameter_lineage(
                target, label="Meta de inflação aplicável ao horizonte"
            ),
            "neutral_real_rate": _parameter_lineage(
                neutral, label="Taxa real neutra assumida pelo Copom"
            ),
            "output_gap": _observation_lineage(
                output_gap,
                label="Hiato do produto estimado pelo Copom",
                include_provenance=True,
            ),
        }
        taylor_point = {
            **common,
            "value": taylor_result.nominal_rate,
            "decomposition": {
                "neutral_real_rate": taylor_result.decomposition.neutral_real_rate,
                "inflation": taylor_result.decomposition.inflation,
                "inflation_gap_response": taylor_result.decomposition.inflation_gap_response,
                "output_gap_response": taylor_result.decomposition.output_gap_response,
            },
            "lineage": taylor_lineage,
        }
        history["taylor_prospective"].append(taylor_point)

        if selic is not None:
            history["selic_minus_taylor"].append({
                **common,
                "value": float(selic["value"]) - taylor_result.nominal_rate,
                "lineage": {
                    "selic": _observation_lineage(selic, label="Meta Selic"),
                    **taylor_lineage,
                },
            })

    return history
