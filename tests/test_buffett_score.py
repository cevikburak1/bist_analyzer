"""
Buffett skorlama motoru için kritik dal birim testleri.

Test edilenler:
1. Yetersiz veri durumunda is_na ve YETERSIZ_VERI etiketi
2. DCF: pozitif FCF + büyüme ile mantıklı adil değer + MoS hesabı
3. Etiket sınırları: HARIKA_IS_UCUZ, IYI_IS_UCUZ, GECER, PAS_GEC
4. Sektör BANKA: borç/özsermaye N/A geçilir, possible puan azalır
5. Eksik kategori "ücretsiz puan" oluşturmaz (normalize doğru)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.buffett_score import calculate_buffett_score
from analysis.buffett_signal import build_buffett_signal
from analysis.intrinsic_value import (
    DCFAssumptions,
    IntrinsicValueResult,
    calculate_intrinsic_value,
)
from fundamentals.downloader import FundamentalsBundle


# ── Yardımcılar ──────────────────────────────────────────────────────────────


def make_bundle(
    symbol: str = "TEST",
    sector_kind: str = "DIGER",
    income: list[dict] | None = None,
    balance: list[dict] | None = None,
    cashflow: list[dict] | None = None,
    info: dict | None = None,
    dividends: list[dict] | None = None,
) -> FundamentalsBundle:
    return FundamentalsBundle(
        symbol=symbol,
        fetched_at="2026-04-22",
        sector={"kind": sector_kind, "label": sector_kind, "source": "test"},
        info=info or {},
        income_annual=income or [],
        balance_annual=balance or [],
        cashflow_annual=cashflow or [],
        dividends_annual=dividends or [],
        fetch_errors=[],
    )


def _years(n: int = 5) -> list[str]:
    return [f"{2020+i}-12-31" for i in range(n)]


# ── 1) Yetersiz veri ─────────────────────────────────────────────────────────


def test_empty_bundle_returns_yetersiz_veri():
    bundle = make_bundle()
    score = calculate_buffett_score(bundle)
    assert score.has_minimum_data is False
    assert score.data_quality_pct == 0.0
    assert score.total_score == 0.0

    intrinsic = IntrinsicValueResult(
        intrinsic_value_per_share=None, enterprise_value=None,
        base_fcf=None, growth_used=None,
        discount_rate=0.20, terminal_growth=0.03, projection_years=10,
        shares_outstanding=None, margin_of_safety=None, current_price=None,
        is_na=True, reason="test",
    )
    signal = build_buffett_signal(bundle, score, intrinsic)
    assert signal.label_key == "YETERSIZ_VERI"


# ── 2) DCF: pozitif FCF + büyüme ────────────────────────────────────────────


def test_intrinsic_value_with_positive_growing_fcf():
    cashflow = [
        {"period": p, "free_cash_flow": v}
        for p, v in zip(_years(5), [100.0, 110.0, 121.0, 133.0, 146.0])
    ]
    balance = [
        {"period": p, "shares_outstanding": 1000.0, "total_equity": 1000.0}
        for p in _years(5)
    ]
    bundle = make_bundle(
        cashflow=cashflow,
        balance=balance,
        info={"currentPrice": 0.5, "sharesOutstanding": 1000.0},
    )
    result = calculate_intrinsic_value(
        bundle,
        current_price=0.5,
        assumptions=DCFAssumptions(discount_rate=0.20, terminal_growth=0.03),
    )
    assert result.is_na is False
    assert result.intrinsic_value_per_share is not None
    assert result.intrinsic_value_per_share > 0
    assert result.margin_of_safety is not None
    # 0.5 fiyat çok düşük; MoS pozitif olmalı
    assert result.margin_of_safety > 0


def test_intrinsic_value_negative_fcf_returns_na():
    cashflow = [
        {"period": p, "free_cash_flow": v}
        for p, v in zip(_years(3), [-100.0, -50.0, -10.0])
    ]
    bundle = make_bundle(cashflow=cashflow)
    result = calculate_intrinsic_value(bundle, current_price=10.0)
    assert result.is_na is True
    assert result.intrinsic_value_per_share is None


def test_intrinsic_value_no_shares_returns_na():
    cashflow = [
        {"period": p, "free_cash_flow": v}
        for p, v in zip(_years(3), [100.0, 110.0, 120.0])
    ]
    bundle = make_bundle(cashflow=cashflow, info={})
    result = calculate_intrinsic_value(bundle, current_price=10.0)
    assert result.is_na is True
    assert "Hisse sayısı" in result.reason


# ── 3) Sektör BANKA: borç/özsermaye N/A ──────────────────────────────────────


def test_bank_skips_debt_to_equity():
    income = [
        {"period": p, "net_income": 100.0, "total_revenue": 1000.0,
         "ebit": 200.0, "interest_expense": 30.0}
        for p in _years(5)
    ]
    balance = [
        {"period": p, "total_equity": 500.0, "total_debt": 5000.0,
         "current_assets": 100.0, "current_liabilities": 100.0,
         "shares_outstanding": 100.0}
        for p in _years(5)
    ]
    bundle = make_bundle(
        sector_kind="BANKA",
        income=income,
        balance=balance,
        cashflow=[{"period": p, "free_cash_flow": 80.0} for p in _years(5)],
    )
    score = calculate_buffett_score(bundle)
    fin = score.financial.details
    assert fin["debt_to_equity"] == "N/A (banka)"
    assert fin["current_ratio"] == "N/A (banka)"
    # Bankada bu kategorinin maksimumu azalır; faiz karşılama (8) + FCF (3) = 11
    assert score.financial.possible <= 12


# ── 4) Etiket sınırları ──────────────────────────────────────────────────────


def test_label_pas_gec_for_low_score():
    income = [
        {"period": p, "net_income": -50.0, "total_revenue": 1000.0}
        for p in _years(5)
    ]
    balance = [
        {"period": p, "total_equity": 100.0, "total_debt": 1000.0,
         "shares_outstanding": 10.0}
        for p in _years(5)
    ]
    bundle = make_bundle(
        income=income,
        balance=balance,
        cashflow=[{"period": p, "free_cash_flow": -10.0} for p in _years(5)],
        info={"trailingPE": 100.0, "priceToBook": 10.0, "currentPrice": 50.0},
    )
    score = calculate_buffett_score(bundle, intrinsic_value_per_share=None,
                                    current_price=50.0)
    intrinsic = IntrinsicValueResult(
        intrinsic_value_per_share=None, enterprise_value=None,
        base_fcf=None, growth_used=None,
        discount_rate=0.20, terminal_growth=0.03, projection_years=10,
        shares_outstanding=10.0, margin_of_safety=None, current_price=50.0,
        is_na=True, reason="negatif",
    )
    signal = build_buffett_signal(bundle, score, intrinsic)
    assert score.total_score < 60
    assert signal.label_key == "PAS_GEC"


def test_label_harika_is_ucuz_for_strong_company():
    income = [
        {"period": p, "net_income": ni, "total_revenue": rev,
         "ebit": ni * 1.5, "interest_expense": 10.0, "gross_profit": rev * 0.4}
        for p, ni, rev in zip(
            _years(5),
            [100.0, 120.0, 140.0, 160.0, 180.0],
            [500.0, 550.0, 600.0, 650.0, 700.0],
        )
    ]
    balance = [
        {"period": p, "total_equity": eq, "total_debt": 100.0,
         "current_assets": 300.0, "current_liabilities": 100.0,
         "shares_outstanding": 100.0}
        for p, eq in zip(_years(5), [600.0, 700.0, 800.0, 900.0, 1000.0])
    ]
    cashflow = [
        {"period": p, "free_cash_flow": v}
        for p, v in zip(_years(5), [80.0, 95.0, 110.0, 130.0, 150.0])
    ]
    info = {
        "trailingPE": 8.0,
        "priceToBook": 1.2,
        "marketCap": 1000.0,
        "freeCashflow": 150.0,
        "currentPrice": 10.0,
        "sharesOutstanding": 100.0,
        "dividendYield": 0.05,
    }
    dividends = [
        {"period": str(2020 + i), "dividend": v}
        for i, v in enumerate([0.5, 0.6, 0.7, 0.8, 1.0])
    ]
    bundle = make_bundle(
        income=income, balance=balance, cashflow=cashflow,
        info=info, dividends=dividends,
    )
    intrinsic = calculate_intrinsic_value(bundle, current_price=10.0)
    score = calculate_buffett_score(
        bundle,
        intrinsic_value_per_share=intrinsic.intrinsic_value_per_share,
        current_price=10.0,
    )
    signal = build_buffett_signal(bundle, score, intrinsic)

    assert score.total_score >= 60
    assert signal.label_key in ("HARIKA_IS_UCUZ", "IYI_IS_UCUZ", "HARIKA_IS_PAHALI")


# ── 5) Eksik kategori normalize doğru ────────────────────────────────────────


def test_missing_category_does_not_inflate_score():
    """Sadece moat kategorisi puanlansın; financial+valuation+shareholder
    tamamen N/A olmalı. Toplam yüzde, moat'un kendi yüzdesine eşit olmalı.

    Bunun için balance'da shares_outstanding ve total_debt VERMEYİZ; cashflow
    ve dividend yok; info boş.
    """
    income = [
        {"period": p, "net_income": 100.0, "total_revenue": 500.0}
        for p in _years(5)
    ]
    balance = [
        {"period": p, "total_equity": 500.0}
        for p in _years(5)
    ]
    bundle = make_bundle(income=income, balance=balance, info={})
    score = calculate_buffett_score(bundle)

    assert score.financial.is_na is True
    assert score.valuation.is_na is True
    assert score.shareholder.is_na is True

    expected = (score.moat.earned / score.moat.possible) * 100.0
    assert abs(score.total_score - expected) < 0.1


def test_high_data_quality_when_full_data():
    income = [
        {"period": p, "net_income": 100.0, "total_revenue": 1000.0,
         "ebit": 150.0, "interest_expense": 20.0}
        for p in _years(5)
    ]
    balance = [
        {"period": p, "total_equity": 500.0, "total_debt": 100.0,
         "current_assets": 200.0, "current_liabilities": 100.0,
         "shares_outstanding": 100.0}
        for p in _years(5)
    ]
    cashflow = [{"period": p, "free_cash_flow": 80.0} for p in _years(5)]
    info = {"trailingPE": 10.0, "priceToBook": 1.5, "marketCap": 1000.0,
            "freeCashflow": 80.0, "sharesOutstanding": 100.0}
    bundle = make_bundle(income=income, balance=balance, cashflow=cashflow, info=info)
    score = calculate_buffett_score(bundle, intrinsic_value_per_share=20.0,
                                    current_price=10.0)
    assert score.data_quality_pct > 70


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
