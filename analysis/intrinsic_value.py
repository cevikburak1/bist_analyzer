"""
Basit DCF (İskonto Edilmiş Nakit Akışı) + Margin of Safety.

Formül:
    Adil Şirket Değeri = SUM_t=1..N [ FCF_0 * (1+g)^t / (1+r)^t ]
                       + Terminal Değer / (1+r)^N
    Terminal Değer    = FCF_N * (1 + g_terminal) / (r - g_terminal)
    Adil Hisse Fiyatı = Adil Şirket Değeri / Hisse Sayısı
    MoS               = (Adil - Mevcut) / Adil

V1 varsayımları (aşağıdaki DCFAssumptions ile değiştirilebilir):
- Geçmiş 5 yıl FCF ortalaması başlangıç FCF
- Büyüme = son 5 yıl FCF CAGR, [-5%, +15%] aralığında klempe
- Projeksiyon süresi = 10 yıl
- Terminal büyüme = %3
- İskonto oranı = %20 (TR risksiz + risk primi tahmini)
- Negatif başlangıç FCF veya hisse sayısı yoksa hesap N/A döndürür

Bu basit modeldir. V2'de sektörel iskonto + kullanıcı override + sermaye
yapısına göre WACC hesabı eklenebilir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fundamentals.downloader import FundamentalsBundle

logger = logging.getLogger(__name__)


@dataclass
class DCFAssumptions:
    discount_rate: float = 0.20            # %20
    terminal_growth: float = 0.03          # %3
    projection_years: int = 10
    growth_min: float = -0.05              # büyümeyi [-5%, 15%] aralığına sıkıştır
    growth_max: float = 0.15
    fcf_history_years: int = 5


@dataclass
class IntrinsicValueResult:
    intrinsic_value_per_share: Optional[float]
    enterprise_value: Optional[float]
    base_fcf: Optional[float]
    growth_used: Optional[float]
    discount_rate: float
    terminal_growth: float
    projection_years: int
    shares_outstanding: Optional[float]
    margin_of_safety: Optional[float]
    current_price: Optional[float]
    is_na: bool
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "intrinsic_value_per_share": (
                round(self.intrinsic_value_per_share, 4)
                if self.intrinsic_value_per_share is not None else None
            ),
            "enterprise_value": (
                round(self.enterprise_value, 2) if self.enterprise_value is not None else None
            ),
            "base_fcf": round(self.base_fcf, 2) if self.base_fcf is not None else None,
            "growth_used": round(self.growth_used, 4) if self.growth_used is not None else None,
            "discount_rate": self.discount_rate,
            "terminal_growth": self.terminal_growth,
            "projection_years": self.projection_years,
            "shares_outstanding": self.shares_outstanding,
            "margin_of_safety": (
                round(self.margin_of_safety, 4) if self.margin_of_safety is not None else None
            ),
            "current_price": (
                round(self.current_price, 4) if self.current_price is not None else None
            ),
            "is_na": self.is_na,
            "reason": self.reason,
        }


def _fcf_cagr(values: list[float]) -> Optional[float]:
    """FCF CAGR. Negatif başlangıç/bitiş varsa None."""
    if len(values) < 2:
        return None
    start, end = values[0], values[-1]
    if start <= 0 or end <= 0:
        return None
    n = len(values) - 1
    return (end / start) ** (1 / n) - 1


def _fcf_history(bundle: FundamentalsBundle, years: int) -> list[float]:
    """Eski->yeni sıralı FCF değerleri (None'lar atılır)."""
    return [
        float(r["free_cash_flow"])
        for r in bundle.cashflow_annual[-years:]
        if r.get("free_cash_flow") is not None
    ]


def _shares_outstanding(bundle: FundamentalsBundle) -> Optional[float]:
    """Önce balance sheet, sonra info."""
    for bal in reversed(bundle.balance_annual):
        s = bal.get("shares_outstanding")
        if s is not None and s > 0:
            return float(s)
    s = bundle.info.get("sharesOutstanding")
    if s and s > 0:
        return float(s)
    return None


def calculate_intrinsic_value(
    bundle: FundamentalsBundle,
    current_price: Optional[float] = None,
    assumptions: Optional[DCFAssumptions] = None,
) -> IntrinsicValueResult:
    """Bundle üzerinden DCF + MoS hesaplar."""
    a = assumptions or DCFAssumptions()

    if current_price is None:
        current_price = bundle.info.get("currentPrice") or bundle.info.get("previousClose")

    fcfs = _fcf_history(bundle, a.fcf_history_years)
    if not fcfs:
        return IntrinsicValueResult(
            intrinsic_value_per_share=None, enterprise_value=None,
            base_fcf=None, growth_used=None,
            discount_rate=a.discount_rate, terminal_growth=a.terminal_growth,
            projection_years=a.projection_years, shares_outstanding=None,
            margin_of_safety=None, current_price=current_price,
            is_na=True, reason="Serbest nakit akışı verisi yok",
        )

    base_fcf = sum(fcfs) / len(fcfs)
    if base_fcf <= 0:
        return IntrinsicValueResult(
            intrinsic_value_per_share=None, enterprise_value=None,
            base_fcf=base_fcf, growth_used=None,
            discount_rate=a.discount_rate, terminal_growth=a.terminal_growth,
            projection_years=a.projection_years,
            shares_outstanding=_shares_outstanding(bundle),
            margin_of_safety=None, current_price=current_price,
            is_na=True, reason="Ortalama FCF negatif - DCF anlamsız",
        )

    cagr = _fcf_cagr(fcfs)
    growth = max(a.growth_min, min(a.growth_max, cagr if cagr is not None else 0.0))

    if a.discount_rate <= a.terminal_growth:
        return IntrinsicValueResult(
            intrinsic_value_per_share=None, enterprise_value=None,
            base_fcf=base_fcf, growth_used=growth,
            discount_rate=a.discount_rate, terminal_growth=a.terminal_growth,
            projection_years=a.projection_years,
            shares_outstanding=_shares_outstanding(bundle),
            margin_of_safety=None, current_price=current_price,
            is_na=True, reason="İskonto oranı <= terminal büyüme - model çalışmaz",
        )

    pv_sum = 0.0
    fcf_t = base_fcf
    for t in range(1, a.projection_years + 1):
        fcf_t = base_fcf * ((1 + growth) ** t)
        pv_sum += fcf_t / ((1 + a.discount_rate) ** t)

    terminal_value = (fcf_t * (1 + a.terminal_growth)) / (a.discount_rate - a.terminal_growth)
    pv_terminal = terminal_value / ((1 + a.discount_rate) ** a.projection_years)
    enterprise_value = pv_sum + pv_terminal

    shares = _shares_outstanding(bundle)
    if not shares:
        return IntrinsicValueResult(
            intrinsic_value_per_share=None, enterprise_value=enterprise_value,
            base_fcf=base_fcf, growth_used=growth,
            discount_rate=a.discount_rate, terminal_growth=a.terminal_growth,
            projection_years=a.projection_years, shares_outstanding=None,
            margin_of_safety=None, current_price=current_price,
            is_na=True, reason="Hisse sayısı bulunamadı",
        )

    intrinsic = enterprise_value / shares
    mos: Optional[float] = None
    if current_price and intrinsic > 0:
        mos = (intrinsic - current_price) / intrinsic

    return IntrinsicValueResult(
        intrinsic_value_per_share=intrinsic,
        enterprise_value=enterprise_value,
        base_fcf=base_fcf,
        growth_used=growth,
        discount_rate=a.discount_rate,
        terminal_growth=a.terminal_growth,
        projection_years=a.projection_years,
        shares_outstanding=shares,
        margin_of_safety=mos,
        current_price=current_price,
        is_na=False,
        reason="",
    )
