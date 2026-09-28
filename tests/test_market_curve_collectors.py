from __future__ import annotations

from datetime import date
from io import BytesIO
import unittest
from zipfile import ZipFile

from brazil_monetary_policy_monitor.collectors.anbima_ettj import parse_anbima_ettj_csv, request_fields
from brazil_monetary_policy_monitor.collectors.b3_di1 import build_b3_sprd_url, parse_b3_di1_zip
from brazil_monetary_policy_monitor.models.term_structure import (
    ANBIMA_BREAKEVEN_CURVE,
    ANBIMA_NOMINAL_CURVE,
    ANBIMA_REAL_CURVE,
    discount_factor,
)


def anbima_fixture() -> bytes:
    return """24/09/2026;Beta 1;Beta 2;Beta 3;Beta 4;Lambda 1;Lambda 2\nPREFIXADOS;1;2;3;4;5;6\nIPCA;1;2;3;4;5;6\n\nETTJ Inflação Implicita (IPCA)\nVertices;ETTJ IPCA;ETTJ PREF;Inflação Implícita\n252;6,4868;13,5509;6,6337\n504;6,3000;12,9000;6,2098\n2.520;6,1000;12,0000;5,5608\n""".encode("cp1252")


def b3_fixture() -> bytes:
    def report(ticker: str, rate: float, du: int) -> str:
        price = 100000 * discount_factor(rate, du)
        return f"""<PricRpt><TradDt><Dt>2026-09-24</Dt></TradDt><SctyId><TckrSymb>{ticker}</TckrSymb></SctyId><FinInstrmAttrbts><AdjstdQt>{price:.8f}</AdjstdQt><AdjstdQtTax>{rate:.6f}</AdjstdQtTax></FinInstrmAttrbts></PricRpt>"""
    xml = f"<BizData>{report('DI1F28', 12.0, 252)}{report('DI1F29', 13.0, 504)}<PricRpt><TradDt><Dt>2026-09-24</Dt></TradDt><SctyId><TckrSymb>DOLV26</TckrSymb></SctyId><FinInstrmAttrbts><AdjstdQt>1</AdjstdQt><AdjstdQtTax>1</AdjstdQtTax></FinInstrmAttrbts></PricRpt></BizData>".encode()
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("SPRD260924.xml", xml)
    return buffer.getvalue()


class MarketCurveCollectorTests(unittest.TestCase):
    def test_anbima_parser_maps_three_zero_coupon_curves(self) -> None:
        rows = parse_anbima_ettj_csv(anbima_fixture())
        self.assertEqual(len(rows), 9)
        self.assertEqual({row.curve_key for row in rows}, {ANBIMA_NOMINAL_CURVE, ANBIMA_REAL_CURVE, ANBIMA_BREAKEVEN_CURVE})
        nominal_1y = next(row for row in rows if row.curve_key == ANBIMA_NOMINAL_CURVE and row.tenor_business_days == 252)
        self.assertEqual(nominal_1y.reference_date, date(2026, 9, 24))
        self.assertAlmostEqual(nominal_1y.rate_percent, 13.5509)
        nominal_10y = next(row for row in rows if row.curve_key == ANBIMA_NOMINAL_CURVE and row.tenor_business_days == 2520)
        self.assertAlmostEqual(nominal_10y.rate_percent, 12.0)
        self.assertEqual(request_fields(date(2026, 9, 24))["Dt_Ref"], "24/09/2026")

    def test_b3_parser_filters_di1_and_recovers_business_day_tenor(self) -> None:
        rows = parse_b3_di1_zip(b3_fixture())
        self.assertEqual([row.instrument_key for row in rows], ["DI1F28", "DI1F29"])
        self.assertEqual([row.tenor_business_days for row in rows], [252, 504])
        self.assertIn("SPRD260924.zip", build_b3_sprd_url(date(2026, 9, 24)))
