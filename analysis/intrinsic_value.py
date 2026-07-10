"""
Basit DCF (İskonto Edilmiş Nakit Akışı) + Margin of Safety.

Semantik:
- Downloader'ın ``Free Cash Flow`` alanı CFO - CapEx'tir. Faiz ödemeleri CFO
  içinde bulunduğundan varsayılan olarak FCFE vekili kabul edilir ve bugünkü
  değerden net borç tekrar düşülmez.
- Açıkça ``cash_flow_type="FCFF"`` seçilirse bugünkü değer enterprise value'dur;
  özsermaye değerine ulaşmak için net borç bir kez düşülür.
- ``enterprise_value`` alanı geriye uyumluluk için korunur ama yalnızca gerçek
  enterprise value hesaplanabiliyorsa doldurulur. FCFE'de net borç bilinmiyorsa
  bu alan None, ``equity_value`` ise doludur.

Hesap:
    Terminal Değer = FCF_N × (1 + g_terminal) / (r - g_terminal)
    FCFE özsermaye değeri = tahmin dönemi PV + terminal PV
    FCFF özsermaye değeri = enterprise value - net borç
    Adil Hisse Fiyatı = özsermaye değeri / pozitif hisse sayısı
    MoS = (Adil - Mevcut) / Adil

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
import math
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
    cash_flow_type: str = "FCFE"          # FCFE (varsayılan) veya açıkça FCFF


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
    equity_value: Optional[float] = None
    net_debt: Optional[float] = None
    cash_flow_type: str = "FCFE"

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
            "equity_value": (
                round(self.equity_value, 2) if self.equity_value is not None else None
            ),
            "net_debt": round(self.net_debt, 2) if self.net_debt is not None else None,
            "cash_flow_type": self.cash_flow_type,
        }


def _fcf_cagr(values: list[float], year_span: Optional[int] = None) -> Optional[float]:
    """FCF CAGR. Negatif başlangıç/bitiş varsa None."""
    if len(values) < 2 or not all(math.isfinite(value) for value in values):
        return None
    start, end = values[0], values[-1]
    if start <= 0 or end <= 0:
        return None
    n = year_span if year_span is not None else len(values) - 1
    if n <= 0:
        return None
    return (end / start) ** (1 / n) - 1


def _period_year(value: object) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _fcf_observations(
    bundle: FundamentalsBundle, years: int
) -> list[tuple[Optional[int], float]]:
    ordered = sorted(
        bundle.cashflow_annual,
        key=lambda row: (
            _period_year(row.get("period")) is not None,
            _period_year(row.get("period")) or 0,
        ),
    )[-years:]
    observations: list[tuple[Optional[int], float]] = []
    for row in ordered:
        value = row.get("free_cash_flow")
        try:
            numeric = float(value) if value is not None else None
        except (TypeError, ValueError):
            numeric = None
        if numeric is not None and math.isfinite(numeric):
            observations.append((_period_year(row.get("period")), numeric))
    return observations


def _fcf_history(bundle: FundamentalsBundle, years: int) -> list[float]:
    """Eski->yeni sıralı FCF değerleri (None'lar atılır)."""
    return [value for _, value in _fcf_observations(bundle, years)]


def _safe_nonnegative(value: object) -> Optional[float]:
    try:
        result = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return (
        result
        if result is not None and math.isfinite(result) and result >= 0
        else None
    )


def _net_debt(bundle: FundamentalsBundle) -> Optional[float]:
    """Net debt only when both debt and cash are explicitly available."""
    debt = _safe_nonnegative(bundle.info.get("totalDebt"))
    cash = _safe_nonnegative(bundle.info.get("totalCash"))
    for bal in reversed(bundle.balance_annual):
        if debt is None:
            debt = _safe_nonnegative(bal.get("total_debt"))
        if cash is None:
            cash = _safe_nonnegative(bal.get("cash"))
        if debt is not None and cash is not None:
            break
    return debt - cash if debt is not None and cash is not None else None


def _shares_outstanding(bundle: FundamentalsBundle) -> Optional[float]:
    """Hisse adedini bul. Bilanço fallback'i bazen 'Common Stock' satırını döner;
    bu rakam yfinance'te par değer olabildiği için info ile çapraz kontrol yapar.

    Strateji:
    - Önce info["sharesOutstanding"] (en güvenilir kaynak) varsa onu baz al.
    - Bilanço değeri ile arasında 10x'ten fazla fark yoksa bilanço daha taze
      olabilir; ona güven.
    - Aksi halde info değerini koru.
    - Hiçbiri yoksa son çare bilanço değeri.
    """
    info_shares = bundle.info.get("sharesOutstanding")
    try:
        info_numeric = float(info_shares) if info_shares is not None else None
    except (TypeError, ValueError):
        info_numeric = None
    info_val: Optional[float] = (
        info_numeric
        if info_numeric is not None and math.isfinite(info_numeric) and info_numeric > 0
        else None
    )

    bs_val: Optional[float] = None
    for bal in reversed(bundle.balance_annual):
        s = bal.get("shares_outstanding")
        try:
            numeric = float(s) if s is not None else None
        except (TypeError, ValueError):
            numeric = None
        if numeric is not None and math.isfinite(numeric) and numeric > 0:
            bs_val = numeric
            break

    if info_val is None and bs_val is None:
        return None
    if info_val is None:
        return bs_val
    if bs_val is None:
        return info_val

    ratio = bs_val / info_val if info_val > 0 else 0.0
    if 0.1 <= ratio <= 10:
        return bs_val
    return info_val


def calculate_intrinsic_value(
    bundle: FundamentalsBundle,
    current_price: Optional[float] = None,
    assumptions: Optional[DCFAssumptions] = None,
) -> IntrinsicValueResult:
    """Bundle üzerinden semantiği açık FCFE/FCFF DCF + MoS hesaplar."""
    a = assumptions or DCFAssumptions()
    flow_type = str(a.cash_flow_type or "").upper()

    if current_price is None:
        current_price = bundle.info.get("currentPrice") or bundle.info.get("previousClose")
    try:
        current_numeric = float(current_price) if current_price is not None else None
    except (TypeError, ValueError):
        current_numeric = None
    current_price = (
        current_numeric
        if current_numeric is not None and math.isfinite(current_numeric) and current_numeric > 0
        else None
    )

    if flow_type not in {"FCFE", "FCFF"}:
        return IntrinsicValueResult(
            intrinsic_value_per_share=None, enterprise_value=None,
            base_fcf=None, growth_used=None,
            discount_rate=a.discount_rate, terminal_growth=a.terminal_growth,
            projection_years=a.projection_years, shares_outstanding=None,
            margin_of_safety=None, current_price=current_price,
            is_na=True, reason="cash_flow_type FCFE veya FCFF olmalı",
            cash_flow_type=flow_type,
        )

    if bundle.sector.get("kind") in {"BANKA", "SIGORTA"}:
        return IntrinsicValueResult(
            intrinsic_value_per_share=None, enterprise_value=None,
            base_fcf=None, growth_used=None,
            discount_rate=a.discount_rate, terminal_growth=a.terminal_growth,
            projection_years=a.projection_years,
            shares_outstanding=_shares_outstanding(bundle),
            margin_of_safety=None, current_price=current_price,
            is_na=True,
            reason="Kurumsal FCF DCF modeli banka/sigorta için uygun değil",
            cash_flow_type=flow_type,
        )

    if (
        not all(math.isfinite(value) for value in (
            a.discount_rate,
            a.terminal_growth,
            a.growth_min,
            a.growth_max,
        ))
        or a.projection_years <= 0
        or a.fcf_history_years <= 0
        or a.discount_rate <= -1
        or a.terminal_growth <= -1
        or a.growth_min <= -1
        or a.growth_max < a.growth_min
    ):
        return IntrinsicValueResult(
            intrinsic_value_per_share=None, enterprise_value=None,
            base_fcf=None, growth_used=None,
            discount_rate=a.discount_rate, terminal_growth=a.terminal_growth,
            projection_years=a.projection_years, shares_outstanding=None,
            margin_of_safety=None, current_price=current_price,
            is_na=True, reason="Geçersiz DCF varsayımları",
            cash_flow_type=flow_type,
        )

    observations = _fcf_observations(bundle, a.fcf_history_years)
    fcfs = [value for _, value in observations]
    if not fcfs:
        return IntrinsicValueResult(
            intrinsic_value_per_share=None, enterprise_value=None,
            base_fcf=None, growth_used=None,
            discount_rate=a.discount_rate, terminal_growth=a.terminal_growth,
            projection_years=a.projection_years, shares_outstanding=None,
            margin_of_safety=None, current_price=current_price,
            is_na=True, reason="Serbest nakit akışı verisi yok",
            cash_flow_type=flow_type,
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
            cash_flow_type=flow_type,
        )

    observation_years = [year for year, _ in observations if year is not None]
    year_span = (
        observation_years[-1] - observation_years[0]
        if len(observation_years) == len(observations) and len(observation_years) >= 2
        else None
    )
    cagr = _fcf_cagr(fcfs, year_span=year_span)
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
            cash_flow_type=flow_type,
        )

    pv_sum = 0.0
    fcf_t = base_fcf
    for t in range(1, a.projection_years + 1):
        fcf_t = base_fcf * ((1 + growth) ** t)
        pv_sum += fcf_t / ((1 + a.discount_rate) ** t)

    terminal_value = (fcf_t * (1 + a.terminal_growth)) / (a.discount_rate - a.terminal_growth)
    pv_terminal = terminal_value / ((1 + a.discount_rate) ** a.projection_years)
    discounted_cash_flows = pv_sum + pv_terminal
    net_debt = _net_debt(bundle)

    if flow_type == "FCFE":
        equity_value = discounted_cash_flows
        enterprise_value = (
            equity_value + net_debt if net_debt is not None else None
        )
    else:
        enterprise_value = discounted_cash_flows
        if net_debt is None:
            return IntrinsicValueResult(
                intrinsic_value_per_share=None,
                enterprise_value=enterprise_value,
                base_fcf=base_fcf, growth_used=growth,
                discount_rate=a.discount_rate, terminal_growth=a.terminal_growth,
                projection_years=a.projection_years,
                shares_outstanding=_shares_outstanding(bundle),
                margin_of_safety=None, current_price=current_price,
                is_na=True,
                reason="FCFF özsermaye değeri için net borç ve nakit verisi gerekli",
                net_debt=None, cash_flow_type=flow_type,
            )
        equity_value = enterprise_value - net_debt

    if equity_value <= 0:
        return IntrinsicValueResult(
            intrinsic_value_per_share=None, enterprise_value=enterprise_value,
            base_fcf=base_fcf, growth_used=growth,
            discount_rate=a.discount_rate, terminal_growth=a.terminal_growth,
            projection_years=a.projection_years,
            shares_outstanding=_shares_outstanding(bundle),
            margin_of_safety=None, current_price=current_price,
            is_na=True, reason="DCF sonrası özsermaye değeri pozitif değil",
            equity_value=equity_value, net_debt=net_debt,
            cash_flow_type=flow_type,
        )

    shares = _shares_outstanding(bundle)
    if not shares:
        return IntrinsicValueResult(
            intrinsic_value_per_share=None, enterprise_value=enterprise_value,
            base_fcf=base_fcf, growth_used=growth,
            discount_rate=a.discount_rate, terminal_growth=a.terminal_growth,
            projection_years=a.projection_years, shares_outstanding=None,
            margin_of_safety=None, current_price=current_price,
            is_na=True, reason="Hisse sayısı bulunamadı",
            equity_value=equity_value, net_debt=net_debt,
            cash_flow_type=flow_type,
        )

    intrinsic = equity_value / shares

    # Sağlıklılık kontrolü: intrinsic ile mevcut fiyat arasında 100x üstü
    # büyüklük farkı varsa veri (özellikle hisse adedi veya FCF birimi)
    # neredeyse her zaman bozuktur. Bu durumda MoS hesaplamak yanıltıcı bir
    # %-X.XXX değeri ürettiği için modeli N/A olarak işaretliyoruz.
    if current_price and current_price > 0 and intrinsic > 0:
        ratio = intrinsic / current_price
        if ratio > 100 or ratio < 0.01:
            inverse = 1.0 / ratio if ratio > 0 else 0.0
            if ratio > 1:
                gap_text = f"{ratio:.0f}x daha büyük"
            else:
                gap_text = f"{inverse:.0f}x daha küçük"
            return IntrinsicValueResult(
                intrinsic_value_per_share=round(intrinsic, 4),
                enterprise_value=enterprise_value,
                base_fcf=base_fcf,
                growth_used=growth,
                discount_rate=a.discount_rate,
                terminal_growth=a.terminal_growth,
                projection_years=a.projection_years,
                shares_outstanding=shares,
                margin_of_safety=None,
                current_price=current_price,
                is_na=True,
                reason=(
                    f"Adil değer ({intrinsic:.4f}) mevcut fiyat ({current_price:.2f}) ile "
                    f"karşılaştırıldığında {gap_text} - hisse adedi veya FCF birim eşleşmesi "
                    "şüpheli, MoS güvenilir değil"
                ),
                equity_value=equity_value,
                net_debt=net_debt,
                cash_flow_type=flow_type,
            )

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
        equity_value=equity_value,
        net_debt=net_debt,
        cash_flow_type=flow_type,
    )
