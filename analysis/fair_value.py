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
    "BANKA": [0.22, 0.30, 0.00, 0.00, 0.00, 0.18, 0.00, 0.00, 0.30, 0.00],
    "SIGORTA": [0.25, 0.25, 0.00, 0.00, 0.00, 0.20, 0.00, 0.00, 0.30, 0.00],
    "GYO": [0.08, 0.12, 0.00, 0.10, 0.15, 0.08, 0.12, 0.05, 0.25, 0.05],
    "SANAYI": [0.12, 0.08, 0.15, 0.15, 0.08, 0.10, 0.08, 0.12, 0.05, 0.07],
    "DIGER": [0.12, 0.12, 0.12, 0.12, 0.10, 0.12, 0.10, 0.10, 0.05, 0.05],
}

SECTOR_MULTIPLES = {
    "BANKA": {"pe": 8.0, "ev_ebit": None, "ev_ebitda": None, "ev_revenue": None, "ps": None, "p_fcf": None, "pb": 1.2},
    "SIGORTA": {"pe": 10.0, "ev_ebit": None, "ev_ebitda": None, "ev_revenue": None, "ps": None, "p_fcf": None, "pb": 1.5},
    "GYO": {"pe": 12.0, "ev_ebit": 10.0, "ev_ebitda": 12.0, "ev_revenue": 5.0, "ps": 4.0, "p_fcf": 12.0, "pb": 0.9},
    "SANAYI": {"pe": 14.0, "ev_ebit": 10.0, "ev_ebitda": 8.0, "ev_revenue": 1.5, "ps": 1.3, "p_fcf": 15.0, "pb": 2.2},
    "DIGER": {"pe": 12.0, "ev_ebit": 9.0, "ev_ebitda": 8.0, "ev_revenue": 1.4, "ps": 1.2, "p_fcf": 14.0, "pb": 1.8},
}

FINANCIAL_SECTORS = {"BANKA", "SIGORTA"}


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
    if numer is None or denom is None or denom <= 0:
        return None
    return numer / denom


def _positive(value: Any) -> float | None:
    result = _safe(value)
    return result if result is not None and result > 0 else None


def _period_year(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _ordered_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annual rows ordered by fiscal year, with stable fallback for old data."""
    return sorted(
        rows,
        key=lambda row: (
            _period_year(row.get("period")) is not None,
            _period_year(row.get("period")) or 0,
        ),
    )


def _latest(rows: list[dict[str, Any]], key: str) -> float | None:
    for row in reversed(_ordered_rows(rows)):
        value = _safe(row.get(key))
        if value is not None:
            return value
    return None


def _growth(values: list[float]) -> float | None:
    """Compound annual growth rate for equally spaced annual observations."""
    if len(values) < 2 or values[0] <= 0 or values[-1] <= 0:
        return None
    return (values[-1] / values[0]) ** (1 / (len(values) - 1)) - 1


def _annual_growth(
    rows: list[dict[str, Any]], key: str, n: int = 5
) -> float | None:
    """CAGR using the actual fiscal-year span when periods are available."""
    observations: dict[int, float] = {}
    fallback: list[float] = []
    for row in _ordered_rows(rows)[-n:]:
        value = _safe(row.get(key))
        if value is None:
            continue
        fallback.append(value)
        year = _period_year(row.get("period"))
        if year is not None:
            observations[year] = value

    if len(observations) >= 2:
        years = sorted(observations)
        start, end = observations[years[0]], observations[years[-1]]
        span = years[-1] - years[0]
        if span > 0 and start > 0 and end > 0:
            return (end / start) ** (1 / span) - 1
        return None
    return _growth(fallback)


def _net_debt(bundle: FundamentalsBundle) -> float | None:
    """Return debt minus cash only when both components are known."""
    debt = _safe(bundle.info.get("totalDebt"))
    if debt is None:
        debt = _latest(bundle.balance_annual, "total_debt")
    cash = _safe(bundle.info.get("totalCash"))
    if cash is None:
        cash = _latest(bundle.balance_annual, "cash")
    if debt is None or cash is None or debt < 0 or cash < 0:
        return None
    return debt - cash


def _detect_market(bundle: FundamentalsBundle) -> str:
    currency = str(bundle.info.get("currency") or "").upper()
    exchange = str(bundle.info.get("exchange") or "").upper()
    info_declared = str(bundle.info.get("market") or "").upper()
    bundle_declared = str(getattr(bundle, "market", "")).upper()
    if (
        info_declared in {"BIST", "TR", "TURKEY"}
        or currency == "TRY"
        or bundle.symbol.upper().endswith(".IS")
        or any(token in exchange for token in ("IST", "BIST", "ISE"))
    ):
        return "BIST"
    # A non-TRY quote currency is more specific than the dataclass's BIST
    # compatibility default and keeps manually constructed US bundles valid.
    if currency:
        return "US"
    if bundle_declared in {"BIST", "TR", "TURKEY"}:
        return "BIST"
    return "US"


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
    rows: list[dict[str, Any]] = []
    income = {
        year: row for row in bundle.income_annual
        if (year := _period_year(row.get("period"))) is not None
    }
    cashflow = {
        year: row for row in bundle.cashflow_annual
        if (year := _period_year(row.get("period"))) is not None
    }
    balance = {
        year: row for row in bundle.balance_annual
        if (year := _period_year(row.get("period"))) is not None
    }
    years = sorted(set(income) | set(cashflow) | set(balance))[-8:]
    for year in years:
        inc = income.get(year, {})
        cf = cashflow.get(year, {})
        bal = balance.get(year, {})
        equity = _safe(bal.get("total_equity"))
        net = _safe(inc.get("net_income"))
        rows.append({
            "period": inc.get("period") or cf.get("period") or bal.get("period") or str(year),
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
    market = _detect_market(bundle)
    currency = str(info.get("currency") or ("TRY" if market == "BIST" else "USD"))
    price = _positive(info.get("currentPrice")) or _positive(info.get("previousClose"))
    shares = _positive(info.get("sharesOutstanding")) or _positive(
        _latest(bundle.balance_annual, "shares_outstanding")
    )
    net_debt = _net_debt(bundle)

    # info fields are trailing-twelve-month values when Yahoo supplies them.
    # Annual statement rows are individual fiscal years and must never be
    # summed as though four annual rows were quarterly TTM observations.
    net_income_ttm = _safe(info.get("netIncomeToCommon"))
    revenue_ttm = _safe(info.get("totalRevenue"))
    fcf_ttm = _safe(info.get("freeCashflow"))
    net_income = net_income_ttm if net_income_ttm is not None else _latest(bundle.income_annual, "net_income")
    revenue = revenue_ttm if revenue_ttm is not None else _latest(bundle.income_annual, "total_revenue")
    ebit = _latest(bundle.income_annual, "ebit")
    fcf = fcf_ttm if fcf_ttm is not None else _latest(bundle.cashflow_annual, "free_cash_flow")
    earnings_source = "trailing-twelve-month" if net_income_ttm is not None else "latest-annual"
    revenue_source = "trailing-twelve-month" if revenue_ttm is not None else "latest-annual"
    fcf_source = "trailing-twelve-month" if fcf_ttm is not None else "latest-annual"
    equity = _latest(bundle.balance_annual, "total_equity")
    bvps = _ratio(equity, shares)
    eps = _ratio(net_income, shares)
    sales_per_share = _ratio(revenue, shares)
    fcf_per_share = _ratio(fcf, shares)
    roe = _ratio(net_income, equity)
    if roe is None and (equity is None or equity > 0):
        roe = _safe(info.get("returnOnEquity"))
    revenue_growth = _annual_growth(bundle.income_annual, "total_revenue")
    earnings_growth = _annual_growth(bundle.income_annual, "net_income")
    safe_revenue_growth = max(-0.20, min(0.50, revenue_growth)) if revenue_growth is not None else None
    safe_earnings_growth = max(-0.20, min(0.50, earnings_growth)) if earnings_growth is not None else None

    forward_eps = (
        _ratio(net_income * (1 + safe_earnings_growth), shares)
        if net_income is not None and safe_earnings_growth is not None else eps
    )
    forward_eps_source = (
        f"{earnings_source}-cagr-projection"
        if safe_earnings_growth is not None else f"{earnings_source}-no-growth"
    )
    forward_sales = (
        _ratio(revenue * (1 + safe_revenue_growth), shares)
        if revenue is not None and safe_revenue_growth is not None else sales_per_share
    )

    # This family is anchored to book value, not to the P/E method. The old
    # PE × ROE × BVPS formula simplifies exactly to PE × EPS and therefore
    # counted the same earnings valuation twice. Scale the sector-normal P/B
    # by ROE relative to the model's required return, with a conservative cap.
    required_return = 0.20 if market == "BIST" else 0.10
    roe_quality = (
        min(1.5, max(0.5, roe / required_return))
        if roe is not None and roe > 0 else None
    )
    roe_pb_value = (
        bvps * multiples["pb"] * roe_quality
        if bvps is not None and multiples["pb"] and roe_quality is not None else None
    )

    methods: dict[str, dict[str, Any]] = {}
    methods["net_earnings_pe"] = _method(
        eps * multiples["pe"] if eps is not None and multiples["pe"] else None,
        "Net Earnings P/E", f"{earnings_source}; sector multiple", weights[0],
    )
    methods["roe_based"] = _method(
        roe_pb_value,
        "ROE / P/B-Based", "sector P/B × ROE quality × BVPS", weights[1],
    )
    methods["ev_ebit"] = _method(
        ((ebit * multiples["ev_ebit"] - net_debt) / shares)
        if ebit is not None and multiples["ev_ebit"] and shares and net_debt is not None else None,
        "EV/EBIT", "sector EV/EBIT; net-debt adjusted", weights[2],
    )
    ebitda = _safe(info.get("ebitda"))
    methods["ev_ebitda"] = _method(
        ((ebitda * multiples["ev_ebitda"] - net_debt) / shares)
        if ebitda is not None and multiples["ev_ebitda"] and shares and net_debt is not None else None,
        "EV/EBITDA", "sector EV/EBITDA; net-debt adjusted", weights[3],
    )
    methods["ev_revenue"] = _method(
        ((revenue * multiples["ev_revenue"] - net_debt) / shares)
        if revenue is not None and multiples["ev_revenue"] and shares and net_debt is not None else None,
        "EV/Revenue", f"{revenue_source}; net-debt adjusted", weights[4],
    )
    methods["forward_pe"] = _method(
        forward_eps * multiples["pe"] if forward_eps is not None and multiples["pe"] else None,
        "Forward P/E", forward_eps_source, weights[5],
    )
    methods["forward_ps"] = _method(
        forward_sales * multiples["ps"]
        if forward_sales is not None and multiples["ps"] else None,
        "Forward P/S", f"{revenue_source}-cagr-projection", weights[6],
    )
    methods["p_fcf"] = _method(
        fcf_per_share * multiples["p_fcf"]
        if sector_key not in FINANCIAL_SECTORS
        and fcf_per_share is not None and multiples["p_fcf"] else None,
        "P/FCF", f"{fcf_source}; FCFE proxy", weights[7],
    )
    methods["graham_number"] = _method(math.sqrt(22.5 * eps * bvps) if eps and eps > 0 and bvps and bvps > 0 else None, "Graham Number", "sqrt(22.5×EPS×BVPS)", weights[8])
    dcf_value = None
    if sector_key not in FINANCIAL_SECTORS and fcf is not None and fcf > 0 and shares:
        discount = 0.20 if market == "BIST" else 0.10
        terminal = 0.03 if market == "BIST" else 0.025
        observed_growth = revenue_growth if revenue_growth is not None else earnings_growth
        growth = min(0.15, max(-0.05, observed_growth if observed_growth is not None else 0.03))
        pv = 0.0
        current_fcf = fcf
        for year in range(1, 4):
            current_fcf *= (1 + growth)
            pv += current_fcf / ((1 + discount) ** year)
        terminal_value = current_fcf * (1 + terminal) / max(discount - terminal, 0.01)
        # Yahoo FCF = CFO - CapEx. Interest is already reflected in CFO, so
        # the downloaded series is treated as an FCFE proxy. Subtracting net
        # debt here would mix FCFE and FCFF semantics and double-adjust debt.
        dcf_value = (pv + terminal_value / ((1 + discount) ** 3)) / shares
    methods["dcf"] = _method(
        dcf_value, "DCF", "FCFE proxy; 3y projection + terminal", weights[9]
    )

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
    if sector_key in FINANCIAL_SECTORS:
        alerts.append("Corporate FCF/EV methods unavailable for financial sector")

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
        bond_benchmark=(
            "TR10Y context only; DCF discount is static 20% (no live yield)"
            if market == "BIST"
            else "US10Y context only; DCF discount is static 10% (no live yield)"
        ),
        inflation_region="TR CPI" if market == "BIST" else "US CPI",
        high_inflation_warning=market == "BIST",
        sector_key=sector_key,
        sector_label=sector_label,
        forward_eps_source=forward_eps_source,
        methods=methods,
        financials_table=_financial_rows(bundle),
        alerts=alerts,
    )
