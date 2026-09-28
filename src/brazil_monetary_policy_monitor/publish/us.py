"""Publish the static US benchmark and Brazil-US comparison contract."""
from __future__ import annotations

from bisect import bisect_right
from datetime import date, datetime, timezone
import calendar
import json
from pathlib import Path
import sqlite3
from typing import Any

from ..ingestion.market_curves import ANBIMA_ETTJ_SOURCE_KEY
from ..ingestion.fred import FRED_SOURCE_KEY
from ..models.monetary import classical_taylor
from ..models.term_structure import ANBIMA_NOMINAL_CURVE, ANBIMA_REAL_CURVE
from ..us_series import US_SERIES_BY_KEY
from ..vintages import KnowledgeContext, build_knowledge_context, market_curve_rows, observation_rows
from .atomic import write_json_atomic
from .indicator_contract import structure_indicator_contract

US_SCHEMA_VERSION = 4
US_INFLATION_TARGET = 2.0
US_CANONICAL_RSTAR = 2.0


def _iso_z(value: datetime) -> str:
    if value.tzinfo is None: raise ValueError("generated_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _history(connection, key, context: KnowledgeContext):
    return [{"date": str(r["reference_period"]), "value": float(r["value"]), "available_at": str(r["available_at"])} for r in observation_rows(connection, key, context)]


def _source(connection, key):
    row = connection.execute("SELECT * FROM sources WHERE key=?", (key,)).fetchone()
    if not row: return None
    return {"provider": row["provider"], "name": row["name"], "url": row["url"], "documentation_url": row["documentation_url"]}


def _doc(connection, key, context: KnowledgeContext, *, label=None, interpretation=""):
    spec = US_SERIES_BY_KEY[key]; obs = _history(connection, key, context); src = _source(connection, FRED_SOURCE_KEY)
    if src: src = {**src, "documentation_url": spec.documentation_url}
    return {"key": key, "label": label or spec.title, "title": spec.title, "definition": spec.description,
            "interpretation": interpretation, "status": "available" if obs else "unavailable",
            "data_kind": spec.data_kind, "unit": spec.unit_normalized, "frequency": spec.frequency,
            "transformation": spec.transformation, "latest": obs[-1] if obs else None, "observations": obs,
            "inputs": [], "missing_inputs": [] if obs else [key], "caveats": [], "source": src}


def _derived(key, label, unit, frequency, observations, description, interpretation, inputs, note=None):
    return {"key": key, "label": label, "title": label, "definition": description, "interpretation": interpretation,
            "status": "available" if observations else "unavailable", "data_kind": "derived", "unit": unit,
            "frequency": frequency, "transformation": key, "latest": observations[-1] if observations else None,
            "observations": observations, "inputs": inputs, "missing_inputs": [] if observations else inputs, "source": None, "caveats": [note] if note else []}


def _yoy(index_doc):
    by_month = {item["date"][:7]: item for item in index_doc["observations"]}
    out=[]
    for item in index_doc["observations"]:
        d=date.fromisoformat(item["date"]); prev_key=f"{d.year-1:04d}-{d.month:02d}"; prev=by_month.get(prev_key)
        if prev and float(prev["value"]) != 0:
            out.append({"date": item["date"], "value": (float(item["value"])/float(prev["value"])-1)*100,
                        "available_at": max(item["available_at"], prev["available_at"])})
    return out


def _exact_pair(a, b, fn):
    bb={x["date"]: x for x in b}; out=[]
    for x in a:
        y=bb.get(x["date"])
        if y:
            out.append({"date": x["date"], "value": fn(float(x["value"]), float(y["value"])),
                        "available_at": max(x["available_at"], y["available_at"])})
    return out


def _asof_value(obs, target):
    dates=[x["date"] for x in obs]; i=bisect_right(dates, target)-1
    return None if i < 0 else obs[i]


def _quarter_end(reference: str) -> str:
    d = date.fromisoformat(reference)
    month = d.month + 2
    year = d.year
    if month > 12:
        year += 1
        month -= 12
    return date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def _taylor_history(pce_yoy, real_gdp, potential_gdp):
    gap_by_date={x["date"]: x for x in _exact_pair(real_gdp, potential_gdp, lambda a,b:(a/b-1)*100)}
    out=[]
    for qdate, gap in gap_by_date.items():
        inflation=_asof_value(pce_yoy, _quarter_end(qdate))
        if not inflation: continue
        result=classical_taylor(realized_inflation=float(inflation["value"]), inflation_target=US_INFLATION_TARGET,
                                neutral_real_rate=US_CANONICAL_RSTAR, output_gap=float(gap["value"]))
        out.append({"date": qdate, "value": result.nominal_rate,
                    "available_at": max(inflation["available_at"], gap["available_at"])})
    return out, list(gap_by_date.values())


def _interpolated_curve_value(rows: list[sqlite3.Row], curve_key: str, target_du: int) -> tuple[float, str] | None:
    points = sorted(
        (
            (int(row["tenor_business_days"]), float(row["rate_percent"]), str(row["available_at"]))
            for row in rows
            if row["curve_key"] == curve_key and row["tenor_business_days"] is not None
        ),
        key=lambda item: item[0],
    )
    if not points or target_du < points[0][0] or target_du > points[-1][0]:
        return None
    for du, value, available_at in points:
        if du == target_du:
            return value, available_at
    for (left_du, left_value, left_available), (right_du, right_value, right_available) in zip(points, points[1:]):
        if left_du < target_du < right_du:
            weight = (target_du - left_du) / (right_du - left_du)
            value = left_value + weight * (right_value - left_value)
            return value, max(left_available, right_available)
    return None


def _anbima_10y_spreads(connection, us_nominal, us_real, context: KnowledgeContext):
    source = connection.execute("SELECT id FROM sources WHERE key=?", (ANBIMA_ETTJ_SOURCE_KEY,)).fetchone()
    if not source:
        return [], []
    rows = market_curve_rows(connection, source_id=int(source["id"]), context=context)
    by_date: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_date.setdefault(str(row["reference_date"]), []).append(row)
    nominal: list[dict[str, object]] = []
    real: list[dict[str, object]] = []
    for day, day_rows in sorted(by_date.items()):
        usn = _asof_value(us_nominal, day)
        usr = _asof_value(us_real, day)
        nominal_value = _interpolated_curve_value(day_rows, ANBIMA_NOMINAL_CURVE, 2520)
        real_value = _interpolated_curve_value(day_rows, ANBIMA_REAL_CURVE, 2520)
        if nominal_value is not None and usn:
            br_rate, br_available = nominal_value
            nominal.append({
                "date": day,
                "value": br_rate - float(usn["value"]),
                "available_at": max(br_available, usn["available_at"]),
            })
        if real_value is not None and usr:
            br_rate, br_available = real_value
            real.append({
                "date": day,
                "value": br_rate - float(usr["value"]),
                "available_at": max(br_available, usr["available_at"]),
            })
    return nominal, real


def publish_us_json(
    connection: sqlite3.Connection,
    *,
    output_path: str | Path,
    generated_at: datetime,
    knowledge_mode: str = "latest_revision",
    knowledge_cutoff: str | None = None,
) -> Path:
    context = build_knowledge_context(
        generated_at=generated_at, knowledge_mode=knowledge_mode, knowledge_cutoff=knowledge_cutoff
    )
    docs={key:_doc(connection,key,context) for key in US_SERIES_BY_KEY}
    pce_yoy=_yoy(docs["us.inflation.pce_index"])
    pce=_derived("us.inflation.pce_12m","Inflação PCE — 12 meses","percent","monthly",pce_yoy,
                 "Variação em 12 meses do índice PCE.","É a inflação realizada, não uma expectativa.",["us.inflation.pce_index"])
    taylor_obs,gap_obs=_taylor_history(pce_yoy, docs["us.gdp.real"]["observations"], docs["us.gdp.potential"]["observations"])
    gap=_derived("us.output_gap.cbo","Hiato do produto EUA — CBO","percent","quarterly",gap_obs,
                 "Diferença percentual entre PIB real e PIB potencial estimado pelo CBO.","Positivo indica produto acima do potencial estimado; a estimativa é revisável.",["us.gdp.real","us.gdp.potential"])
    taylor=_derived("us.taylor.classic","Taylor clássica EUA","percent_per_year","quarterly",taylor_obs,
                    "Benchmark canônico com PCE realizado, meta de 2%, r*=2% e pesos 0,5/0,5.",
                    "É um benchmark analítico, não uma regra seguida pelo FOMC nem uma estimativa do juro correto.",["us.inflation.pce_12m","us.output_gap.cbo"],
                    "O r*=2% é hipótese canônica da regra, não a estimativa HLW corrente do New York Fed.")
    effr=docs["us.policy.effr"]
    real_policy_obs=[]
    for x in effr["observations"]:
        inf=_asof_value(pce_yoy, x["date"])
        if inf: real_policy_obs.append({"date":x["date"],"value":float(x["value"])-float(inf["value"]),"available_at":max(x["available_at"],inf["available_at"])})
    real_policy=_derived("us.policy.real_ex_post","Fed funds real — aproximação","percentage_points","daily",real_policy_obs,
                         "EFFR menos inflação PCE em 12 meses mais recente disponível por data de referência.","É aproximação ex post, não taxa real ex ante.",["us.policy.effr","us.inflation.pce_12m"])
    slope_obs=_exact_pair(docs["us.treasury.10y"]["observations"], docs["us.treasury.2y"]["observations"], lambda a,b:a-b)
    slope=_derived("us.treasury.slope_10y_2y","Inclinação Treasury 10a−2a","percentage_points","daily",slope_obs,
                   "Diferença entre yields nominais de Treasury de 10 e 2 anos.","Valores negativos indicam inversão nesse trecho da curva.",["us.treasury.10y","us.treasury.2y"])

    selic=_history(connection,"br.selic.target",context)
    nominal_policy_spread=_exact_pair(selic, effr["observations"], lambda br,us:br-us)
    br_us_policy=_derived("br_us.policy_spread","Selic − EFFR","percentage_points","daily",nominal_policy_spread,
                          "Diferencial nominal entre a meta Selic e a taxa efetiva dos federal funds em datas coincidentes.","É diferencial de taxas de política, não prêmio soberano nem previsão cambial.",["br.selic.target","us.policy.effr"])
    _nominal_anbima, real10 = _anbima_10y_spreads(
        connection,
        docs["us.treasury.10y"]["observations"],
        docs["us.treasury.real_10y"]["observations"],
        context,
    )
    br_us_nom10 = {
        "key": "br_us.nominal_10y_spread",
        "label": "Brasil − EUA nominal ≈10a",
        "title": "Brasil − EUA nominal ≈10a",
        "definition": "Curva nominal brasileira de aproximadamente 10 anos menos Treasury nominal de 10 anos.",
        "interpretation": "O histórico será publicado quando a curva PRE/B3 definitiva substituir a fonte provisória do projeto.",
        "status": "unavailable",
        "data_kind": "derived",
        "unit": "percentage_points",
        "frequency": "daily",
        "transformation": "br_b3_pre_10y_minus_us_treasury_10y",
        "latest": None,
        "observations": [],
        "inputs": ["br.b3.pre.10y", "us.treasury.10y"],
        "missing_inputs": ["br.b3.pre.10y"],
        "source": None,
        "caveats": [
            "O monitor não usa yields de títulos ofertados do Tesouro Direto como proxy de uma curva nominal de 10 anos. A série permanece indisponível enquanto a curva PRE/B3 histórica não estiver disponível."
        ],
    }
    br_us_real10=_derived(
        "br_us.real_10y_spread",
        "Brasil − EUA real ≈10a",
        "percentage_points",
        "daily",
        real10,
        "ETTJ real ANBIMA em aproximadamente 10 anos menos Treasury real de 10 anos.",
        "Não isola risco-país; contém diferenças de liquidez, tributação e construção das curvas.",
        ["br.anbima.ettj.real.10y", "us.treasury.real_10y"],
    )

    groups={
      "policy":{"label":"Política monetária","metrics":[effr,taylor,real_policy],"chart_series":[effr,taylor]},
      "inflation_activity":{"label":"Inflação e atividade","metrics":[pce,gap],"chart_series":[pce,gap]},
      "treasuries":{"label":"Treasuries","metrics":[docs["us.treasury.2y"],docs["us.treasury.10y"],slope,docs["us.treasury.real_10y"],docs["us.inflation.breakeven_10y"]],"chart_series":[docs["us.treasury.2y"],docs["us.treasury.10y"]]},
      "br_us":{"label":"Brasil × EUA","metrics":[br_us_policy,br_us_nom10,br_us_real10],"chart_series":[br_us_policy,br_us_nom10,br_us_real10]},
    }
    latest_dates=[m["latest"]["date"] for g in groups.values() for m in g["metrics"] if m.get("latest")]
    payload=structure_indicator_contract({"schema_version":US_SCHEMA_VERSION,"view":"us_benchmark","generated_at":_iso_z(generated_at), **context.contract_fields(),
             "status":"available" if latest_dates else "unavailable","latest_reference":max(latest_dates) if latest_dates else None,
             "assumptions":{"inflation_target":US_INFLATION_TARGET,"canonical_rstar":US_CANONICAL_RSTAR,"alpha":0.5,"beta":0.5},
             "groups":groups,
             "methodology":{"taylor":"classic realized-PCE benchmark","rstar":"canonical 2 percent assumption; not current HLW estimate",
                            "revisions":"as_known filters by local available_at. Provider-native ALFRED historical vintages are not reconstructed without an authenticated FRED API transport."}})
    return write_json_atomic(payload, output_path)
