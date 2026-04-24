"""
Buffett Skorlama Motoru (toplam 100)

Kategoriler:
1) Moat / İş Kalitesi          (40)
2) Mali Sağlık                  (25)
3) Değerleme & Margin of Safety (25)
4) Hissedar Politikası          (10)

İlkeler:
- Eksik veride sessiz default puan VERMEYİZ. Veri yoksa kategori N/A olur ve
  toplam o kategori hariç tutularak orantısal toplanır. Buna göre kullanıcıya
  "Yetersiz Veri" durumu net iletilir.
- Sektör (BANKA/GYO/SIGORTA) için bazı kalemler kapatılır. V1'de sade tutuyoruz:
  bankalarda Borç/Özsermaye anlamsız olduğu için bu kategori N/A geçilir.
- Skor = elde edilen puan / mümkün maksimum puan * 100. Yani N/A geçilen
  kategoriler "ücretsiz puan" olmaz.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from typing import Optional

from fundamentals.downloader import FundamentalsBundle

logger = logging.getLogger(__name__)


# ── Eşikler ──────────────────────────────────────────────────────────────────

ROE_GOOD = 0.15            # 5y ortalama ROE > 15% iyi
ROE_STD_TOLERANCE = 0.05   # std < 5% istikrarlı sayılır
DEBT_TO_EQUITY_MAX = 0.5   # banka hariç sektörlerde
INTEREST_COVERAGE_MIN = 5.0
CURRENT_RATIO_MIN = 1.5
PE_REASONABLE_MAX = 25.0   # F/K bunun üstündeyse pahalı sayılır
PB_REASONABLE_MAX = 4.0
P_FCF_REASONABLE_MAX = 15.0
MOS_TARGET = 0.30          # %30+ güvenlik marjı


# ── Yardımcılar ──────────────────────────────────────────────────────────────


def _ratio(numer: Optional[float], denom: Optional[float]) -> Optional[float]:
    if numer is None or denom is None or denom == 0:
        return None
    return numer / denom


def _pct_change_cagr(values: list[float]) -> Optional[float]:
    """En eski->en yeni değerlerden CAGR. Pozitif sayılar için anlamlı."""
    if len(values) < 2:
        return None
    start, end = values[0], values[-1]
    if start <= 0 or end <= 0:
        return None
    n = len(values) - 1
    return (end / start) ** (1 / n) - 1


def _last_n(rows: list[dict], key: str, n: int = 5) -> list[float]:
    """Son N yıldan key alanını al, None'ları at."""
    out: list[float] = []
    for row in rows[-n:]:
        v = row.get(key)
        if v is not None:
            out.append(float(v))
    return out


# ── Kategori puanlayıcılar ──────────────────────────────────────────────────


@dataclass
class CategoryResult:
    earned: float        # toplanan puan
    possible: float      # mümkün maksimum (N/A alt-kalemler düşülmüş olabilir)
    details: dict        # alt-puan dökümü
    is_na: bool = False  # tüm kategori N/A ise True


def score_moat(bundle: FundamentalsBundle) -> CategoryResult:
    """Moat / İş Kalitesi (max 40):
    - 5y ortalama ROE > %15 + std tolere → 15p
    - 5y net kâr CAGR pozitif             → 10p
    - Net marj sektör median'ı yerine     → 10p (V1: > %5 mutlak eşik)
    - Marj istikrarı (5y std düşük)       → 5p
    """
    details: dict = {}
    earned = 0.0
    possible = 0.0

    # ROE (5y avg + istikrar)
    income = bundle.income_annual
    balance = bundle.balance_annual

    roes: list[float] = []
    for inc, bal in zip(income[-5:], balance[-5:]):
        ni = inc.get("net_income")
        eq = bal.get("total_equity")
        r = _ratio(ni, eq)
        if r is not None:
            roes.append(r)

    if len(roes) >= 3:
        avg_roe = sum(roes) / len(roes)
        std_roe = statistics.pstdev(roes) if len(roes) > 1 else 0.0
        possible += 15
        # 8p ortalama, 7p istikrar
        if avg_roe >= ROE_GOOD:
            earned += 8
        elif avg_roe >= ROE_GOOD * 0.6:
            earned += 4
        if std_roe <= ROE_STD_TOLERANCE:
            earned += 7
        elif std_roe <= ROE_STD_TOLERANCE * 2:
            earned += 3
        details["roe_avg_5y"] = round(avg_roe, 4)
        details["roe_std_5y"] = round(std_roe, 4)
    else:
        details["roe_avg_5y"] = None

    # Net kâr CAGR
    ni_series = _last_n(income, "net_income", 5)
    if len(ni_series) >= 3:
        cagr = _pct_change_cagr(ni_series)
        possible += 10
        if cagr is not None and cagr > 0.10:
            earned += 10
        elif cagr is not None and cagr > 0:
            earned += 6
        elif cagr is not None and cagr > -0.05:
            earned += 2
        details["net_income_cagr"] = round(cagr, 4) if cagr is not None else None
    else:
        details["net_income_cagr"] = None

    # Net marj (V1: mutlak eşik)
    margins: list[float] = []
    for inc in income[-5:]:
        ni = inc.get("net_income")
        rev = inc.get("total_revenue")
        m = _ratio(ni, rev)
        if m is not None:
            margins.append(m)
    if len(margins) >= 3:
        avg_margin = sum(margins) / len(margins)
        possible += 10
        if avg_margin >= 0.15:
            earned += 10
        elif avg_margin >= 0.05:
            earned += 6
        elif avg_margin >= 0:
            earned += 2
        details["net_margin_avg_5y"] = round(avg_margin, 4)

        # Marj istikrarı
        std_margin = statistics.pstdev(margins) if len(margins) > 1 else 0.0
        possible += 5
        if std_margin <= 0.03:
            earned += 5
        elif std_margin <= 0.06:
            earned += 2
        details["net_margin_std_5y"] = round(std_margin, 4)
    else:
        details["net_margin_avg_5y"] = None

    if possible == 0:
        return CategoryResult(0.0, 0.0, details, is_na=True)
    return CategoryResult(earned, possible, details)


def score_financial_health(bundle: FundamentalsBundle) -> CategoryResult:
    """Mali Sağlık (max 25):
    - Borç/Özsermaye < 0.5      → 10p (BANKA için N/A)
    - Faiz karşılama > 5x       → 8p
    - Cari oran > 1.5           → 4p
    - Pozitif FCF (4/5 yıl)     → 3p
    """
    details: dict = {}
    earned = 0.0
    possible = 0.0

    sector_kind = bundle.sector.get("kind", "DIGER")
    income = bundle.income_annual
    balance = bundle.balance_annual
    cashflow = bundle.cashflow_annual

    # Borç / Özsermaye
    if sector_kind != "BANKA":
        latest = balance[-1] if balance else {}
        debt = latest.get("total_debt")
        equity = latest.get("total_equity")
        de = _ratio(debt, equity)
        if de is not None:
            possible += 10
            if de < DEBT_TO_EQUITY_MAX:
                earned += 10
            elif de < DEBT_TO_EQUITY_MAX * 2:
                earned += 5
            details["debt_to_equity"] = round(de, 3)
        else:
            details["debt_to_equity"] = None
    else:
        details["debt_to_equity"] = "N/A (banka)"

    # Faiz karşılama (EBIT / Interest Expense)
    latest_inc = income[-1] if income else {}
    ebit = latest_inc.get("ebit")
    interest = latest_inc.get("interest_expense")
    if interest is not None and abs(interest) > 0 and ebit is not None:
        coverage = ebit / abs(interest)
        possible += 8
        if coverage >= INTEREST_COVERAGE_MIN:
            earned += 8
        elif coverage >= 2:
            earned += 4
        details["interest_coverage"] = round(coverage, 2)
    else:
        details["interest_coverage"] = None

    # Cari oran
    if sector_kind != "BANKA":
        latest = balance[-1] if balance else {}
        ca = latest.get("current_assets")
        cl = latest.get("current_liabilities")
        cr = _ratio(ca, cl)
        if cr is None:
            cr = bundle.info.get("currentRatio")
        if cr is not None:
            possible += 4
            if cr >= CURRENT_RATIO_MIN:
                earned += 4
            elif cr >= 1.0:
                earned += 2
            details["current_ratio"] = round(cr, 2)
        else:
            details["current_ratio"] = None
    else:
        details["current_ratio"] = "N/A (banka)"

    # Pozitif FCF (5 yıldan kaç tanesi)
    fcf_values = _last_n(cashflow, "free_cash_flow", 5)
    if fcf_values:
        positives = sum(1 for v in fcf_values if v > 0)
        possible += 3
        if positives >= 4:
            earned += 3
        elif positives >= 3:
            earned += 2
        elif positives >= 2:
            earned += 1
        details["positive_fcf_years"] = positives
        details["fcf_years_evaluated"] = len(fcf_values)
    else:
        details["positive_fcf_years"] = None

    if possible == 0:
        return CategoryResult(0.0, 0.0, details, is_na=True)
    return CategoryResult(earned, possible, details)


def score_valuation(
    bundle: FundamentalsBundle,
    intrinsic_value_per_share: Optional[float],
    current_price: Optional[float],
) -> CategoryResult:
    """Değerleme & MoS (max 25):
    - F/K < 25           → 8p (sektör median V2'de gelir)
    - PD/DD < 4          → 6p
    - F/FCF makul (<15)  → 6p
    - DCF MoS >= 30%     → 5p
    """
    details: dict = {}
    earned = 0.0
    possible = 0.0
    info = bundle.info

    # F/K
    pe = info.get("trailingPE")
    if pe is not None and pe > 0:
        possible += 8
        if pe < 12:
            earned += 8
        elif pe < PE_REASONABLE_MAX:
            earned += 5
        elif pe < PE_REASONABLE_MAX * 1.5:
            earned += 2
        details["pe"] = round(pe, 2)
    else:
        details["pe"] = None

    # PD/DD
    pb = info.get("priceToBook")
    if pb is not None and pb > 0:
        possible += 6
        if pb < 1.5:
            earned += 6
        elif pb < PB_REASONABLE_MAX:
            earned += 3
        elif pb < PB_REASONABLE_MAX * 1.5:
            earned += 1
        details["pb"] = round(pb, 2)
    else:
        details["pb"] = None

    # F / FCF (market cap / free_cashflow)
    market_cap = info.get("marketCap")
    fcf_latest = info.get("freeCashflow")
    if fcf_latest is None:
        fcf_values = _last_n(bundle.cashflow_annual, "free_cash_flow", 1)
        fcf_latest = fcf_values[0] if fcf_values else None
    if market_cap and fcf_latest and fcf_latest > 0:
        p_fcf = market_cap / fcf_latest
        possible += 6
        if p_fcf < 10:
            earned += 6
        elif p_fcf < P_FCF_REASONABLE_MAX:
            earned += 4
        elif p_fcf < P_FCF_REASONABLE_MAX * 1.5:
            earned += 2
        details["p_fcf"] = round(p_fcf, 2)
    else:
        details["p_fcf"] = None

    # MoS - intrinsic vs price arasındaki büyüklük farkı 100x üstüyse
    # veri bütünlüğü şüpheli kabul edilir ve MoS skorlamaya katılmaz.
    if (
        intrinsic_value_per_share
        and current_price
        and intrinsic_value_per_share > 0
        and current_price > 0
    ):
        ratio = intrinsic_value_per_share / current_price
        if ratio > 100 or ratio < 0.01:
            details["margin_of_safety"] = None
            details["intrinsic_value"] = round(intrinsic_value_per_share, 4)
            details["margin_of_safety_anomaly"] = (
                f"Intrinsic/fiyat oranı {ratio:.1f}x - veri bütünlüğü şüpheli, MoS atlandı"
            )
        else:
            mos = (intrinsic_value_per_share - current_price) / intrinsic_value_per_share
            possible += 5
            if mos >= MOS_TARGET:
                earned += 5
            elif mos >= 0.10:
                earned += 3
            elif mos >= 0:
                earned += 1
            details["margin_of_safety"] = round(mos, 4)
            details["intrinsic_value"] = round(intrinsic_value_per_share, 4)
    else:
        details["margin_of_safety"] = None
        details["intrinsic_value"] = None

    if possible == 0:
        return CategoryResult(0.0, 0.0, details, is_na=True)
    return CategoryResult(earned, possible, details)


def score_shareholder_policy(bundle: FundamentalsBundle) -> CategoryResult:
    """Hissedar Politikası (max 10):
    - Son 5y temettü ödüyor + büyüyor → 6p
    - Hisse sayısı azalıyor / sabit    → 4p
    """
    details: dict = {}
    earned = 0.0
    possible = 0.0

    # Temettü
    div_rows = bundle.dividends_annual[-5:]
    div_amounts = [r["dividend"] for r in div_rows if r.get("dividend") is not None]
    if div_amounts:
        possible += 6
        paid_years = sum(1 for v in div_amounts if v > 0)
        if paid_years >= 4:
            earned += 4
        elif paid_years >= 2:
            earned += 2
        # Büyüyor mu?
        if len(div_amounts) >= 3 and div_amounts[-1] > div_amounts[0]:
            earned += 2
        details["dividend_paid_years"] = paid_years
        details["dividend_growing"] = (
            len(div_amounts) >= 3 and div_amounts[-1] > div_amounts[0]
        )
    else:
        details["dividend_paid_years"] = None

    # Hisse sayısı eğilimi
    shares: list[float] = []
    for bal in bundle.balance_annual[-5:]:
        s = bal.get("shares_outstanding")
        if s is not None:
            shares.append(s)
    if len(shares) >= 3:
        possible += 4
        if shares[-1] <= shares[0]:
            earned += 4
        elif shares[-1] <= shares[0] * 1.05:
            earned += 2
        details["shares_change_pct"] = round(
            (shares[-1] - shares[0]) / shares[0], 4
        )
    else:
        details["shares_change_pct"] = None

    if possible == 0:
        return CategoryResult(0.0, 0.0, details, is_na=True)
    return CategoryResult(earned, possible, details)


# ── Toplama ──────────────────────────────────────────────────────────────────


@dataclass
class BuffettScoreBreakdown:
    moat: CategoryResult
    financial: CategoryResult
    valuation: CategoryResult
    shareholder: CategoryResult
    total_score: float                  # 0-100, N/A kategorilere göre normalize
    data_quality_pct: float             # mümkün puan / 100
    has_minimum_data: bool

    def as_dict(self) -> dict:
        def cat(c: CategoryResult) -> dict:
            return {
                "earned": round(c.earned, 2),
                "possible": round(c.possible, 2),
                "is_na": c.is_na,
                "details": c.details,
            }
        return {
            "moat": cat(self.moat),
            "financial_health": cat(self.financial),
            "valuation": cat(self.valuation),
            "shareholder_policy": cat(self.shareholder),
            "total_score": round(self.total_score, 2),
            "data_quality_pct": round(self.data_quality_pct, 1),
            "has_minimum_data": self.has_minimum_data,
        }


# Kategorilerin "tam" maksimum puan ağırlıkları (referans için)
MAX_WEIGHTS = {
    "moat": 40.0,
    "financial": 25.0,
    "valuation": 25.0,
    "shareholder": 10.0,
}
TOTAL_MAX = sum(MAX_WEIGHTS.values())


def calculate_buffett_score(
    bundle: FundamentalsBundle,
    intrinsic_value_per_share: Optional[float] = None,
    current_price: Optional[float] = None,
) -> BuffettScoreBreakdown:
    """Tüm kategorileri puanlayıp normalize edilmiş 0-100 skorunu döndürür."""
    moat = score_moat(bundle)
    financial = score_financial_health(bundle)
    valuation = score_valuation(bundle, intrinsic_value_per_share, current_price)
    shareholder = score_shareholder_policy(bundle)

    earned_total = sum(c.earned for c in (moat, financial, valuation, shareholder))
    possible_total = sum(c.possible for c in (moat, financial, valuation, shareholder))

    if possible_total > 0:
        total_score = (earned_total / possible_total) * 100.0
    else:
        total_score = 0.0

    data_quality_pct = (possible_total / TOTAL_MAX) * 100.0

    return BuffettScoreBreakdown(
        moat=moat,
        financial=financial,
        valuation=valuation,
        shareholder=shareholder,
        total_score=min(100.0, total_score),
        data_quality_pct=min(100.0, data_quality_pct),
        has_minimum_data=bundle.has_minimum_data(),
    )
