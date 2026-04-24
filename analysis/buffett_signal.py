"""
Buffett etiketleme + tez bozulma uyarıları.

Çıktı "AL/SAT" değil; aşağıdaki etiketlerden biri:
- HARIKA_IS_UCUZ        ("Harika İş - Adil/Ucuz Fiyat")
- HARIKA_IS_PAHALI      ("Harika İş - Pahalı - Bekle")
- IYI_IS_UCUZ           ("İyi İş - Ucuz")
- GECER                 ("Geçer - Dikkat")
- PAS_GEC               ("Pas Geç")
- YETERSIZ_VERI         ("Yetersiz Veri - Değerlendirilemez")

Tez Bozulma Uyarıları:
- ROE son yılda 5y ortalamanın yarısı altına düştü
- Borç/Özsermaye 1 yılda 2x oldu
- Net kâr son yıl negatif (zarar)
- FCF son yıl negatif
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from analysis.buffett_score import BuffettScoreBreakdown
from analysis.intrinsic_value import IntrinsicValueResult
from fundamentals.downloader import FundamentalsBundle


# ── Etiket sabitleri ────────────────────────────────────────────────────────


LABELS = {
    "HARIKA_IS_UCUZ":   ("Harika İş - Adil/Ucuz Fiyat", "emerald"),
    "HARIKA_IS_PAHALI": ("Harika İş - Pahalı - Bekle",  "amber"),
    "IYI_IS_UCUZ":      ("İyi İş - Ucuz",                "lime"),
    "GECER":            ("Geçer - Dikkat",               "slate"),
    "PAS_GEC":          ("Pas Geç",                      "rose"),
    "YETERSIZ_VERI":    ("Yetersiz Veri - Değerlendirilemez", "sky"),
}


@dataclass
class BuffettSignal:
    symbol: str
    label_key: str
    label: str
    color: str
    total_score: float
    margin_of_safety: Optional[float]
    holding_recommendation: str
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "label_key": self.label_key,
            "label": self.label,
            "color": self.color,
            "total_score": round(self.total_score, 2),
            "margin_of_safety": (
                round(self.margin_of_safety, 4) if self.margin_of_safety is not None else None
            ),
            "holding_recommendation": self.holding_recommendation,
            "warnings": list(self.warnings),
        }


# ── Etiket kararı ───────────────────────────────────────────────────────────


def _classify(
    score: BuffettScoreBreakdown,
    mos: Optional[float],
) -> str:
    """Skor + MoS -> etiket key."""
    # Veri kalitesi yetersiz
    if score.data_quality_pct < 50 or not score.has_minimum_data:
        return "YETERSIZ_VERI"

    total = score.total_score
    has_mos = mos is not None and mos >= 0.30

    if total >= 75 and has_mos:
        return "HARIKA_IS_UCUZ"
    if total >= 75:
        return "HARIKA_IS_PAHALI"
    if 60 <= total < 75 and has_mos:
        return "IYI_IS_UCUZ"
    if 60 <= total < 75:
        return "GECER"
    return "PAS_GEC"


def _holding_recommendation(label_key: str) -> str:
    """Buffett zihniyetinde tutma süresi önerisi."""
    return {
        "HARIKA_IS_UCUZ":   "Önerilen Tutma: 5-10+ yıl (yüksek inanç)",
        "HARIKA_IS_PAHALI": "Şirket harika; daha düşük fiyatı bekle",
        "IYI_IS_UCUZ":      "Önerilen Tutma: 3-5+ yıl",
        "GECER":            "Daha iyi fırsat çıkana kadar gözlem",
        "PAS_GEC":          "Bu şirkete yatırım önerilmez",
        "YETERSIZ_VERI":    "Manuel inceleme gerek",
    }[label_key]


# ── Tez bozulma uyarıları ───────────────────────────────────────────────────


def _detect_warnings(
    bundle: FundamentalsBundle,
    score: BuffettScoreBreakdown,
) -> list[str]:
    warnings: list[str] = []

    # Son yıl ROE 5y ortalamasının yarısı altına düştü mü
    income = bundle.income_annual
    balance = bundle.balance_annual

    roes: list[float] = []
    for inc, bal in zip(income[-5:], balance[-5:]):
        ni = inc.get("net_income")
        eq = bal.get("total_equity")
        if ni is not None and eq is not None and eq != 0:
            roes.append(ni / eq)
    if len(roes) >= 3:
        avg = sum(roes[:-1]) / len(roes[:-1])
        last = roes[-1]
        if avg > 0 and last < avg * 0.5:
            warnings.append(
                f"ROE son yılda %{last*100:.1f}, önceki ortalama %{avg*100:.1f} (sert düşüş)"
            )

    # Borç/Özsermaye 1 yılda 2x oldu mu
    if len(balance) >= 2:
        prev_bal = balance[-2]
        last_bal = balance[-1]
        prev_de = (
            (prev_bal.get("total_debt") or 0) / prev_bal["total_equity"]
            if prev_bal.get("total_equity") else None
        )
        last_de = (
            (last_bal.get("total_debt") or 0) / last_bal["total_equity"]
            if last_bal.get("total_equity") else None
        )
        if prev_de is not None and last_de is not None and prev_de > 0 and last_de >= prev_de * 2:
            warnings.append(
                f"Borç/Özsermaye 1 yılda {prev_de:.2f} -> {last_de:.2f} (2 katından fazla arttı)"
            )

    # Net kâr son yıl negatif
    if income:
        last_ni = income[-1].get("net_income")
        if last_ni is not None and last_ni < 0:
            warnings.append("Şirket son yıl zarar açıkladı")

    # FCF son yıl negatif
    cf = bundle.cashflow_annual
    if cf:
        last_fcf = cf[-1].get("free_cash_flow")
        if last_fcf is not None and last_fcf < 0:
            warnings.append("Son yıl serbest nakit akışı negatif")

    # Veri kalitesi düşük ama "Yetersiz Veri" değilse uyar
    if 50 <= score.data_quality_pct < 70:
        warnings.append(
            f"Veri kalitesi sınırlı (%{score.data_quality_pct:.0f}); skoru ihtiyatlı yorumla"
        )

    return warnings


# ── Public ───────────────────────────────────────────────────────────────────


def build_buffett_signal(
    bundle: FundamentalsBundle,
    score: BuffettScoreBreakdown,
    intrinsic: IntrinsicValueResult,
) -> BuffettSignal:
    label_key = _classify(score, intrinsic.margin_of_safety)
    label, color = LABELS[label_key]
    warnings = _detect_warnings(bundle, score)

    return BuffettSignal(
        symbol=bundle.symbol,
        label_key=label_key,
        label=label,
        color=color,
        total_score=score.total_score,
        margin_of_safety=intrinsic.margin_of_safety,
        holding_recommendation=_holding_recommendation(label_key),
        warnings=warnings,
    )
