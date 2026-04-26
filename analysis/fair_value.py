"""
Multi-method fair value model for BIST and US-style equities.

The model estimates fair price with 10 methods, then aggregates valid methods
with sector-aware weights by default. It is robust to missing fields: unavailable
methods return null and the confidence score reflects method dispersion.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any

from fundamentals.downloader import FundamentalsBundle


METHODS = [
    "net_earnings_pe",
    "roe_based",
    "ev_ebit",
    "ev_ebitda",
    "ev_revenue",
    "forward_pe",
    "forward_ps",
    "p_fcf",
    "graham_number",
    "dcf",
]

SECTOR_WEIGHTS = {
    "BANKA": [0.18, 0.27, 0.00, 0.00, 0.00, 0.13, 0.00, 0.10, 0.22, 0.10],
    "GYO": [0.08, 0.12, 0.00, 0.10, 0.15, 0.08, 0.12, 0.05, 0.25, 0.05],
    "SANAYI": [0.12, 0.08, 0.15, 0.15, 0.08, 0.10, 0.08, 0.12, 0.05, 0.07],
    "DIGER": [0.12, 0.12, 0.12, 0.12, 0.10, 0.12, 0.10, 0.10, 0.05, 0.05],
}

SECTOR_MULTIPLES = {
    "BANKA": {"pe": 8.0, "ev_ebit": None, "ev_ebitda": None, "ev_revenue": None, "ps": 1.5, "p_fcf": 8.0, "pb": 1.2},
    "GYO": {"pe": 12.0, "ev_ebit": 10.0, "ev_ebitda": 12.0, "ev_revenue": 5.0, "ps": 4.0, "p_fcf": 12.0, "pb": 0.9},
    "SANAYI": {"pe": 14.0, "ev_ebit": 10.0, "ev_ebitda": 8.0, "ev_revenue": 1.5, "ps": 1.3, "p_fcf": 15.0, "pb": 2.2},
    "DIGER": {"pe": 12.0, "ev_ebit": 9.0, "ev_ebitda": 8.0, "ev_revenue": 1.4, "ps": 1.2, "p_fcf": 14.0, "pb": 1.8},
}


@dataclass
class FairValueResult:
    fair_value: float | None
    current_price: float | None
    margin_pct: float | None
    aggregation_method: str
    confidence_label: str
    confidence_cv: float | None
    valid_methods: int
    market: str
    currency: str
    bond_benchmark: str
    inflation_region: str
    high_inflation_warning: bool
    sector_key: str
    sector_label: str
    forward_eps_source: str
    methods: dict[str, dict[str, Any]]
    financials_table: list[dict[str, Any]]
    alerts: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "fair_value": round(self.fair_value, 4) if self.fair_value is not None else None,
            "current_price": round(self.current_price, 4) if self.current_price is not None else None,
            "margin_pct": round(self.margin_pct, 2) if self.margin_pct is not None else None,
            "aggregation_method": self.aggregation_method,
            "confidence_label": self.confidence_label,
            "confidence_cv": round(self.confidence_cv, 2) if self.confidence_cv is not None else None,
            "valid_methods": self.valid_methods,
            "market": self.market,
            "currency": self.currency,
            "bond_benchmark": self.bond_benchmark,
            "inflation_region": self.inflation_region,
            "high_inflation_warning": self.high_inflation_warning,
            "sector_key": self.sector_key,
            "sector_label": self.sector_label,
            "forward_eps_source": self.forward_eps_source,
            "methods": self.methods,
            "financials_table": self.financials_table,
            "alerts": self.alerts,
        }


def _safe(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _ratio(numer: float | None, denom: float | None) -> float | None:
    if numer is None or denom in (None, 0):
        return None
    return numer / denom


def _latest(rows: list[dict[str, Any]], key: str) -> float | None:
    for row in reversed(rows):
        value = _safe(row.get(key))
        if value is not None:
            return value
    return None


def _sum_latest(rows: list[dict[str, Any]], key: str, n: int = 4) -> float | None:
    values = [_safe(row.get(key)) for row in rows[-n:]]
    valid = [value for value in values if value is not None]
    return sum(valid) if valid else None


def _growth(values: list[float]) -> float | None:
    if len(values) < 2 or values[0] <= 0 or values[-1] <= 0:
        return None
    return max(-0.2, min(0.8, values[-1] / values[0] - 1))


def _method(value: float | None, label: str, source: str, weight: float) -> dict[str, Any]:
    return {
        "label": label,
        "value": round(value, 4) if value is not None and value > 0 else None,
        "source": source,
        "weight": round(weight, 4),
    }


def _confidence(values: list[float]) -> tuple[str, float | None]:
    if len(values) < 3:
        return "Düşük", None
    cleaned = sorted(values)
    if len(cleaned) >= 5:
        cleaned = cleaned[1:-1]
    mean = statistics.mean(cleaned)
    if mean == 0:
        return "Düşük", None
    cv = abs(statistics.pstdev(cleaned) / mean) * 100
    if cv < 15:
        return "Yüksek", cv
    if cv < 30:
        return "Orta", cv
    return "Düşük", cv


def _aggregate(methods: dict[str, dict[str, Any]], sector_key: str) -> float | None:
    weights = SECTOR_WEIGHTS.get(sector_key) or SECTOR_WEIGHTS["DIGER"]
    weighted_sum = 0.0
    total_weight = 0.0
    for method_name, weight in zip(METHODS, weights):
        value = methods[method_name]["value"]
        if value is not None and weight > 0:
            weighted_sum += value * weight
            total_weight += weight
    return weighted_sum / total_weight if total_weight > 0 else None


def _financial_rows(bundle: FundamentalsBundle) -> list[dict[str, Any]]:
    rows = []
    income = bundle.income_annual[-8:]
    cashflow = bundle.cashflow_annual[-8:]
    balance = bundle.balance_annual[-8:]
    for idx in range(max(len(income), len(cashflow), len(balance))):
        inc = income[idx] if idx < len(income) else {}
        cf = cashflow[idx] if idx < len(cashflow) else {}
        bal = balance[idx] if idx < len(balance) else {}
        equity = _safe(bal.get("total_equity"))
        net = _safe(inc.get("net_income"))
        rows.append({
            "period": inc.get("period") or cf.get("period") or bal.get("period"),
            "net_earnings": net,
            "revenue": _safe(inc.get("total_revenue")),
            "ebit": _safe(inc.get("ebit")),
            "ebitda": None,
            "fcf": _safe(cf.get("free_cash_flow")),
            "roe": _ratio(net, equity),
        })
    return rows


def calculate_fair_value(bundle: FundamentalsBundle) -> FairValueResult:
    info = bundle.info
    sector_key = bundle.sector.get("kind", "DIGER")
    sector_label = bundle.sector.get("label", sector_key)
    multiples = SECTOR_MULTIPLES.get(sector_key) or SECTOR_MULTIPLES["DIGER"]
    weights = SECTOR_WEIGHTS.get(sector_key) or SECTOR_WEIGHTS["DIGER"]
    market = "BIST" if (info.get("currency") == "TRY" or bundle.symbol.endswith(".IS")) else "US"
    currency = str(info.get("currency") or ("TRY" if market == "BIST" else "USD"))
    price = _safe(info.get("currentPrice")) or _safe(info.get("previousClose"))
    shares = _safe(info.get("sharesOutstanding")) or _latest(bundle.balance_annual, "shares_outstanding")
    market_cap = _safe(info.get("marketCap")) or ((price or 0) * shares if price and shares else None)
    net_debt = (_safe(info.get("totalDebt")) or _latest(bundle.balance_annual, "total_debt") or 0) - (_safe(info.get("totalCash")) or _latest(bundle.balance_annual, "cash") or 0)
    enterprise_value = (market_cap + net_debt) if market_cap is not None else None

    net_income = _sum_latest(bundle.income_annual, "net_income")
    revenue = _sum_latest(bundle.income_annual, "total_revenue")
    ebit = _sum_latest(bundle.income_annual, "ebit")
    fcf = _sum_latest(bundle.cashflow_annual, "free_cash_flow")
    equity = _latest(bundle.balance_annual, "total_equity")
    bvps = _ratio(equity, shares)
    eps = _ratio(net_income, shares)
    sales_per_share = _ratio(revenue, shares)
    fcf_per_share = _ratio(fcf, shares)
    roe = _ratio(net_income, equity) or _safe(info.get("returnOnEquity"))
    revenue_values = [_safe(row.get("total_revenue")) for row in bundle.income_annual[-5:]]
    revenue_growth = _growth([value for value in revenue_values if value is not None]) or 0.0
    earnings_values = [_safe(row.get("net_income")) for row in bundle.income_annual[-5:]]
    earnings_growth = _growth([value for value in earnings_values if value is not None]) or 0.0

    forward_eps = _ratio(net_income * (1 + earnings_growth), shares) if net_income and shares else eps
    forward_eps_source = "growth-projection" if forward_eps != eps else "ttm-fallback"
    forward_sales = _ratio(revenue * (1 + revenue_growth), shares) if revenue and shares else sales_per_share

    methods: dict[str, dict[str, Any]] = {}
    methods["net_earnings_pe"] = _method(eps * multiples["pe"] if eps and multiples["pe"] else None, "Net Earnings P/E", "sector-normal", weights[0])
    methods["roe_based"] = _method((multiples["pe"] * roe * bvps) if multiples["pe"] and roe and bvps else None, "ROE-Based", "PE × ROE × BVPS", weights[1])
    methods["ev_ebit"] = _method(((ebit * multiples["ev_ebit"] - net_debt) / shares) if ebit and multiples["ev_ebit"] and shares else None, "EV/EBIT", "sector EV/EBIT", weights[2])
    methods["ev_ebitda"] = _method(((_safe(info.get("ebitda")) or ebit or 0) * multiples["ev_ebitda"] - net_debt) / shares if multiples["ev_ebitda"] and shares and (_safe(info.get("ebitda")) or ebit) else None, "EV/EBITDA", "sector EV/EBITDA", weights[3])
    methods["ev_revenue"] = _method(((revenue * multiples["ev_revenue"] - net_debt) / shares) if revenue and multiples["ev_revenue"] and shares else None, "EV/Revenue", "sector EV/Revenue", weights[4])
    methods["forward_pe"] = _method(forward_eps * multiples["pe"] if forward_eps and multiples["pe"] else None, "Forward P/E", forward_eps_source, weights[5])
    methods["forward_ps"] = _method(forward_sales * multiples["ps"] if forward_sales and multiples["ps"] else None, "Forward P/S", "growth-projection", weights[6])
    methods["p_fcf"] = _method(fcf_per_share * multiples["p_fcf"] if fcf_per_share and multiples["p_fcf"] else None, "P/FCF", "sector P/FCF", weights[7])
    methods["graham_number"] = _method(math.sqrt(22.5 * eps * bvps) if eps and eps > 0 and bvps and bvps > 0 else None, "Graham Number", "sqrt(22.5×EPS×BVPS)", weights[8])
    dcf_value = None
    if fcf and fcf > 0 and shares:
        discount = 0.20 if market == "BIST" else 0.10
        terminal = 0.03 if market == "BIST" else 0.025
        growth = min(0.25, max(-0.05, revenue_growth or earnings_growth or 0.03))
        pv = 0.0
        current_fcf = fcf
        for year in range(1, 4):
            current_fcf *= (1 + growth)
            pv += current_fcf / ((1 + discount) ** year)
        terminal_value = current_fcf * (1 + terminal) / max(discount - terminal, 0.01)
        dcf_value = (pv + terminal_value / ((1 + discount) ** 3) - net_debt) / shares
    methods["dcf"] = _method(dcf_value, "DCF", "3y projection + terminal", weights[9])

    valid_values = [method["value"] for method in methods.values() if method["value"] is not None]
    fair_value = _aggregate(methods, sector_key)
    confidence_label, confidence_cv = _confidence(valid_values)
    margin_pct = ((fair_value - price) / price * 100) if fair_value and price else None
    alerts = []
    if margin_pct is not None and margin_pct >= 20:
        alerts.append("Discount opportunity")
    if margin_pct is not None and margin_pct <= -20:
        alerts.append("Premium warning")
    if confidence_cv is not None and confidence_cv > 40:
        alerts.append("Low confidence")

    return FairValueResult(
        fair_value=fair_value,
        current_price=price,
        margin_pct=margin_pct,
        aggregation_method="Sector Weighted",
        confidence_label=confidence_label,
        confidence_cv=confidence_cv,
        valid_methods=len(valid_values),
        market=market,
        currency=currency,
        bond_benchmark="TR10Y" if market == "BIST" else "US10Y",
        inflation_region="TR CPI" if market == "BIST" else "US CPI",
        high_inflation_warning=market == "BIST",
        sector_key=sector_key,
        sector_label=sector_label,
        forward_eps_source=forward_eps_source,
        methods=methods,
        financials_table=_financial_rows(bundle),
        alerts=alerts,
    )
