"""B3 DI1 collector based on the public BVBG.187.01 simplified price report."""

from __future__ import annotations

from datetime import date
from io import BytesIO
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

from ..models.term_structure import B3_DI1_CURVE, MarketCurvePoint, business_days_from_di_price

B3_PRICE_REPORT_PAGE_URL = "https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/boletins-diarios/pesquisa-por-pregao/pesquisa-por-pregao/"
B3_PRICE_REPORT_CATALOG_URL = "https://www.b3.com.br/data/files/81/91/9A/17/27B5C710BD0885C7AC094EA8/Catalogo_precos_v1.2.1.pdf"
B3_DOWNLOAD_BASE_URL = "https://www.b3.com.br/pesquisapregao/download"


def build_b3_sprd_url(reference_date: date) -> str:
    return f"{B3_DOWNLOAD_BASE_URL}?filelist=SPRD{reference_date:%y%m%d}.zip"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first_text(element: ET.Element, name: str) -> str | None:
    for child in element.iter():
        if _local_name(child.tag) == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def _xml_payloads(payload: bytes) -> list[bytes]:
    try:
        with ZipFile(BytesIO(payload)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
            return [archive.read(name) for name in names]
    except BadZipFile as exc:
        raise ValueError("B3 simplified price report is not a valid ZIP archive") from exc


def parse_b3_di1_zip(payload: bytes) -> list[MarketCurvePoint]:
    result: list[MarketCurvePoint] = []
    for xml_payload in _xml_payloads(payload):
        root = ET.fromstring(xml_payload)
        for report in (element for element in root.iter() if _local_name(element.tag) == "PricRpt"):
            ticker = _first_text(report, "TckrSymb")
            if not ticker or not ticker.startswith("DI1"):
                continue
            date_text = _first_text(report, "Dt")
            rate_text = _first_text(report, "AdjstdQtTax")
            price_text = _first_text(report, "AdjstdQt")
            if not date_text or not rate_text or not price_text:
                continue
            try:
                reference = date.fromisoformat(date_text[:10])
                rate = float(rate_text.replace(",", "."))
                price = float(price_text.replace(",", "."))
                tenor = business_days_from_di_price(rate_percent=rate, price_value=price)
            except ValueError:
                continue
            result.append(
                MarketCurvePoint(
                    curve_key=B3_DI1_CURVE,
                    reference_date=reference,
                    point_key=f"ticker:{ticker}",
                    instrument_key=ticker,
                    tenor_business_days=tenor,
                    rate_percent=rate,
                    price_value=price,
                )
            )
    if not result:
        raise ValueError("B3 report contains no usable DI1 settlement points")
    by_ticker = {point.instrument_key: point for point in result}
    return sorted(by_ticker.values(), key=lambda point: int(point.tenor_business_days or 0))
