"""Regression tests for fundamental valuation safety and accounting semantics."""

from __future__ import annotations

import pandas as pd
import pytest

from analysis.buffett_score import (
    score_financial_health,
    score_moat,
    score_shareholder_policy,
)
from analysis.fair_value import (
    _annual_growth,
    _financial_rows,
    _growth,
    calculate_fair_value,
)
from analysis.intrinsic_value import DCFAssumptions, calculate_intrinsic_value
from fundamentals.downloader import FundamentalsBundle, _annualize


def make_bundle(
    *,
    symbol: str = "TEST",
    sector: str = "DIGER",
    info: dict | None = None,
    income: list[dict] | None = None,
    balance: list[dict] | None = None,
    cashflow: list[dict] | None = None,
    dividends: list[dict] | None = None,
    market: str = "BIST",
) -> FundamentalsBundle:
    return FundamentalsBundle(
        symbol=symbol,
        fetched_at="2026-07-11",
        sector={"kind": sector, "label": sector, "source": "test"},
        info=info or {},
        income_annual=income or [],
        balance_annual=balance or [],
        cashflow_annual=cashflow or [],
        dividends_annual=dividends or [],
        market=market,
    )


def test_annual_statements_are_not_summed_as_four_quarters() -> None:
    years = range(2021, 2025)
    bundle = make_bundle(
        info={"currentPrice": 10.0, "sharesOutstanding": 1.0},
        income=[
            {"period": f"{year}-12-31", "net_income": 1.0, "total_revenue": 10.0}
            for year in years
        ],
        balance=[
            {"period": f"{year}-12-31", "total_equity": 5.0, "shares_outstanding": 1.0}
            for year in years
        ],
        cashflow=[
            {"period": f"{year}-12-31", "free_cash_flow": 0.8}
            for year in years
        ],
    )

    result = calculate_fair_value(bundle)

    assert result.methods["net_earnings_pe"]["value"] == pytest.approx(12.0)
    assert result.methods["p_fcf"]["value"] == pytest.approx(11.2)


def test_growth_is_true_cagr_not_total_change() -> None:
    assert _growth([100.0, 110.0, 121.0]) == pytest.approx(0.10)


def test_growth_uses_actual_year_span_when_years_are_missing() -> None:
    rows = [
        {"period": "2020-12-31", "net_income": 100.0},
        {"period": "2024-12-31", "net_income": 146.41},
    ]
    assert _annual_growth(rows, "net_income") == pytest.approx(0.10)


def test_roe_book_value_method_is_not_pe_method_counted_twice() -> None:
    bundle = make_bundle(
        info={"sharesOutstanding": 100.0},
        income=[{"period": "2024-12-31", "net_income": 100.0}],
        balance=[
            {
                "period": "2024-12-31",
                "total_equity": 500.0,
                "shares_outstanding": 100.0,
            }
        ],
    )

    methods = calculate_fair_value(bundle).methods

    assert methods["net_earnings_pe"]["value"] == pytest.approx(12.0)
    assert methods["roe_based"]["value"] == pytest.approx(9.0)
    assert methods["roe_based"]["value"] != methods["net_earnings_pe"]["value"]
    assert "P/B" in methods["roe_based"]["source"]


def test_financial_table_matches_statements_by_fiscal_period() -> None:
    bundle = make_bundle(
        income=[
            {"period": "2022-12-31", "net_income": 20.0},
            {"period": "2023-12-31", "net_income": 30.0},
        ],
        balance=[
            {"period": "2023-12-31", "total_equity": 300.0},
            {"period": "2022-12-31", "total_equity": 100.0},
        ],
        cashflow=[{"period": "2023-12-31", "free_cash_flow": 12.0}],
    )

    rows = {str(row["period"])[:4]: row for row in _financial_rows(bundle)}

    assert rows["2022"]["roe"] == pytest.approx(0.20)
    assert rows["2023"]["roe"] == pytest.approx(0.10)
    assert rows["2022"]["fcf"] is None
    assert rows["2023"]["fcf"] == 12.0


def test_buffett_roe_matches_periods_and_rejects_negative_equity() -> None:
    income = [
        {"period": "2022-12-31", "net_income": 20.0, "total_revenue": 100.0},
        {"period": "2023-12-31", "net_income": 30.0, "total_revenue": 100.0},
        {"period": "2024-12-31", "net_income": 40.0, "total_revenue": 100.0},
    ]
    balance = [
        {"period": "2024-12-31", "total_equity": -400.0},
        {"period": "2022-12-31", "total_equity": 100.0},
        {"period": "2023-12-31", "total_equity": 300.0},
    ]

    result = score_moat(make_bundle(income=income, balance=balance))

    # 2024 negative equity is excluded; only two valid ROEs remain, so the
    # minimum-three-year ROE sub-score is unavailable rather than inflated.
    assert result.details["roe_avg_5y"] is None


def test_buffett_roe_uses_average_opening_and_closing_equity() -> None:
    income = [
        {"period": "2022-12-31", "net_income": 20.0, "total_revenue": 100.0},
        {"period": "2023-12-31", "net_income": 30.0, "total_revenue": 100.0},
        {"period": "2024-12-31", "net_income": 40.0, "total_revenue": 100.0},
    ]
    balance = [
        {"period": "2021-12-31", "total_equity": 100.0},
        {"period": "2022-12-31", "total_equity": 300.0},
        {"period": "2023-12-31", "total_equity": 300.0},
        {"period": "2024-12-31", "total_equity": 500.0},
    ]

    result = score_moat(make_bundle(income=income, balance=balance))

    assert result.details["roe_avg_5y"] == pytest.approx(0.10)
    assert result.details["roe_average_equity_years"] == 3


def test_negative_equity_never_earns_low_debt_score() -> None:
    bundle = make_bundle(
        balance=[
            {
                "period": "2024-12-31",
                "total_debt": 100.0,
                "total_equity": -50.0,
            }
        ]
    )
    result = score_financial_health(bundle)
    assert result.details["debt_to_equity"] is None
    assert result.earned == 0


def test_zero_shares_are_ignored_without_division_by_zero() -> None:
    balance = [
        {"period": f"{year}-12-31", "shares_outstanding": 0.0, "total_equity": 100.0}
        for year in range(2022, 2025)
    ]
    bundle = make_bundle(
        info={"sharesOutstanding": 0.0, "currentPrice": 10.0},
        balance=balance,
        income=[{"period": "2024-12-31", "net_income": 10.0}],
    )

    fair_value = calculate_fair_value(bundle)
    shareholder = score_shareholder_policy(bundle)

    assert fair_value.fair_value is None
    assert shareholder.details["shares_change_pct"] is None


def test_currency_missing_bundle_still_uses_declared_bist_market() -> None:
    result = calculate_fair_value(
        make_bundle(symbol="THYAO", info={"currentPrice": 10.0}, market="BIST")
    )
    assert result.market == "BIST"
    assert result.currency == "TRY"
    assert "TR10Y" in result.bond_benchmark
    assert "static" in result.bond_benchmark


def test_explicit_us_currency_overrides_bist_compatibility_default() -> None:
    result = calculate_fair_value(
        make_bundle(symbol="AAPL", info={"currency": "USD"})
    )
    assert result.market == "US"
    assert "US10Y" in result.bond_benchmark
    assert "static" in result.bond_benchmark


def test_fcfe_dcf_does_not_subtract_net_debt_twice() -> None:
    bundle = make_bundle(
        info={
            "sharesOutstanding": 10.0,
            "totalDebt": 100.0,
            "totalCash": 0.0,
        },
        cashflow=[{"period": "2024-12-31", "free_cash_flow": 100.0}],
    )
    assumptions = DCFAssumptions(
        discount_rate=0.20,
        terminal_growth=0.0,
        projection_years=1,
        growth_min=0.0,
        growth_max=0.0,
        cash_flow_type="FCFE",
    )

    result = calculate_intrinsic_value(bundle, assumptions=assumptions)

    assert result.is_na is False
    assert result.equity_value == pytest.approx(500.0)
    assert result.enterprise_value == pytest.approx(600.0)
    assert result.intrinsic_value_per_share == pytest.approx(50.0)
    assert result.cash_flow_type == "FCFE"


def test_fcff_dcf_subtracts_net_debt_exactly_once() -> None:
    bundle = make_bundle(
        info={
            "sharesOutstanding": 10.0,
            "totalDebt": 100.0,
            "totalCash": 0.0,
        },
        cashflow=[{"period": "2024-12-31", "free_cash_flow": 100.0}],
    )
    assumptions = DCFAssumptions(
        discount_rate=0.20,
        terminal_growth=0.0,
        projection_years=1,
        growth_min=0.0,
        growth_max=0.0,
        cash_flow_type="FCFF",
    )

    result = calculate_intrinsic_value(bundle, assumptions=assumptions)

    assert result.is_na is False
    assert result.enterprise_value == pytest.approx(500.0)
    assert result.equity_value == pytest.approx(400.0)
    assert result.intrinsic_value_per_share == pytest.approx(40.0)
    assert result.net_debt == pytest.approx(100.0)


@pytest.mark.parametrize("sector", ["BANKA", "SIGORTA"])
def test_financial_sector_skips_inappropriate_fcf_metrics(sector: str) -> None:
    bundle = make_bundle(
        sector=sector,
        info={
            "sharesOutstanding": 10.0,
            "marketCap": 1000.0,
            "freeCashflow": 100.0,
            "trailingPE": 8.0,
            "priceToBook": 1.0,
        },
        cashflow=[{"period": "2024-12-31", "free_cash_flow": 100.0}],
    )

    intrinsic = calculate_intrinsic_value(bundle)
    fair_value = calculate_fair_value(bundle)
    health = score_financial_health(bundle)

    assert intrinsic.is_na is True
    assert fair_value.methods["p_fcf"]["value"] is None
    assert fair_value.methods["dcf"]["value"] is None
    assert health.is_na is True
    assert health.possible == 0


def test_minimum_data_requires_same_fiscal_year() -> None:
    bundle = make_bundle(
        income=[{"period": "2024-12-31", "net_income": 10.0}],
        balance=[{"period": "2023-12-31", "total_equity": 100.0}],
    )
    assert bundle.has_minimum_data() is False


@pytest.mark.parametrize("equity", [0.0, -100.0])
def test_minimum_data_rejects_nonpositive_equity(equity: float) -> None:
    bundle = make_bundle(
        income=[{"period": "2024-12-31", "net_income": 10.0}],
        balance=[{"period": "2024-12-31", "total_equity": equity}],
    )
    assert bundle.has_minimum_data() is False


def test_annualize_keeps_individual_years_in_chronological_order() -> None:
    frame = pd.DataFrame(
        {
            pd.Timestamp("2024-12-31"): [40.0],
            pd.Timestamp("2022-12-31"): [20.0],
            pd.Timestamp("2023-12-31"): [30.0],
        },
        index=["Net Income"],
    )
    rows = _annualize(frame, {"net_income": ("Net Income",)})

    assert [row["period"] for row in rows] == [
        "2022-12-31",
        "2023-12-31",
        "2024-12-31",
    ]
    assert [row["net_income"] for row in rows] == [20.0, 30.0, 40.0]
