"""
Teknik Vade Bazlı Tutma Önerisi (Kısa / Orta / Uzun)

Mevcut teknik sinyal (AL/SAT/BEKLE) tek bir karar üretir; ancak yatırımcı
çoğunlukla "kısa, orta, uzun vadede ne yapayım?" sorusunu sorar. Bu modül
zaman dilimi sinyalleri (haftalık, aylık, yıllık) ile 3 vadeli hedef R/R
metriklerini birleştirip vade bazlı net bir karar + okunur gerekçe üretir.

Çıktı verdict değerleri:
- AL          : aktif giriş için elverişli
- BIRIKTIR    : kademeli birikim (yumuşak AL)
- TUT         : mevcudu koru, yeni alma
- IZLE        : tetik bekleme - gözlemde
- BEKLE       : pozisyon açma
- SAT         : pozisyon kapat / kısalt
- KACIN       : risk yüksek - uzak dur

Hiçbir durumda dummy "BEKLE" üretilmez; eldeki bilgi kıt ise verdict=IZLE
ve gerekçesi açıkça belirtilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from analysis.market_regime import MarketRegime
from analysis.targets import TargetLevels
from analysis.timeframes import TimeframeSignals


HORIZON_VERDICT_COLORS = {
    "AL":       "emerald",
    "BIRIKTIR": "lime",
    "TUT":      "sky",
    "IZLE":     "slate",
    "BEKLE":    "amber",
    "SAT":      "rose",
    "KACIN":    "rose",
}


@dataclass
class TechnicalHorizonVerdict:
    verdict: str
    label: str
    color: str
    reason: str
    factors: list[str] = field(default_factory=list)
    rr: Optional[float] = None
    target_price: Optional[float] = None
    reward_pct: Optional[float] = None

    def as_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "label": self.label,
            "color": self.color,
            "reason": self.reason,
            "factors": list(self.factors),
            "rr": self.rr,
            "target_price": self.target_price,
            "reward_pct": self.reward_pct,
        }


@dataclass
class TechnicalHorizonGuidance:
    short: TechnicalHorizonVerdict
    medium: TechnicalHorizonVerdict
    long: TechnicalHorizonVerdict
    overall: str = ""

    def as_dict(self) -> dict:
        return {
            "short": self.short.as_dict(),
            "medium": self.medium.as_dict(),
            "long": self.long.as_dict(),
            "overall": self.overall,
        }


# ── Yardımcılar ──────────────────────────────────────────────────────────────


def _verdict(
    verdict: str, label: str, reason: str, factors: list[str],
    *, rr: Optional[float] = None, target_price: Optional[float] = None,
    reward_pct: Optional[float] = None,
) -> TechnicalHorizonVerdict:
    return TechnicalHorizonVerdict(
        verdict=verdict,
        label=label,
        color=HORIZON_VERDICT_COLORS.get(verdict, "slate"),
        reason=reason,
        factors=factors,
        rr=rr,
        target_price=target_price,
        reward_pct=reward_pct,
    )


def _signal_word(sig: str) -> str:
    return {"AL": "AL", "SAT": "SAT", "BEKLE": "BEKLE"}.get(sig, sig or "BEKLE")


def _rr_quality(rr: Optional[float]) -> str:
    if rr is None or rr <= 0:
        return "olumsuz"
    if rr >= 2.0:
        return "çok iyi"
    if rr >= 1.5:
        return "iyi"
    if rr >= 1.0:
        return "kabul edilebilir"
    return "düşük"


def _regime_modifier(regime: MarketRegime) -> str:
    """Piyasa rejimini insan diline çevir."""
    if not regime:
        return ""
    return regime.label or regime.regime or ""


# ── Vade kararları ───────────────────────────────────────────────────────────


def _safe_rr(value: Optional[float]) -> Optional[float]:
    """Hedef hesaplanmamışsa (BEKLE) R/O 0 gelir; bu yanıltıcı olduğu için
    None'a çeviririz. Negatif veya 0 R/O gerçek bir bilgi taşımıyor."""
    if value is None:
        return None
    if value <= 0:
        return None
    return value


def _safe_price(value: Optional[float]) -> Optional[float]:
    if value is None or value <= 0:
        return None
    return value


def _decide_short(
    timeframes: Optional[TimeframeSignals],
    targets: Optional[TargetLevels],
    rsi: float,
    regime_label: str,
) -> TechnicalHorizonVerdict:
    weekly = _signal_word(timeframes.weekly if timeframes else "BEKLE")
    daily = _signal_word(timeframes.daily if timeframes else "BEKLE")
    rr = _safe_rr(targets.short_rr if targets else None)
    target_price = _safe_price(targets.short_target if targets else None)
    reward_pct = targets.short_reward_pct if (targets and target_price) else None

    factors = [
        f"Günlük sinyal {daily}",
        f"Haftalık sinyal {weekly}",
        f"RSI {rsi:.0f}",
        f"Kısa vade R/O {rr:.2f}" if rr is not None else "Kısa vade hedefi hesaplanmadı",
        f"Piyasa rejimi: {regime_label}" if regime_label else "Piyasa rejimi bilinmiyor",
    ]

    if daily == "AL" and weekly == "AL" and rr is not None and rr >= 1.5:
        return _verdict(
            "AL",
            "Kısa Vade: Aktif Al",
            f"Günlük ve haftalık sinyaller AL ile uyumlu, R/O {rr:.1f} ({_rr_quality(rr)})",
            factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
        )
    if daily == "AL" and weekly == "AL":
        reason_text = (
            f"Sinyaller pozitif ancak R/O {rr:.2f} ({_rr_quality(rr)}) - kademeli birikim güvenli"
            if rr is not None
            else "Sinyaller pozitif; R/O verisi yok - kademeli birikim güvenli"
        )
        return _verdict(
            "BIRIKTIR",
            "Kısa Vade: Kademeli Topla",
            reason_text,
            factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
        )
    if daily == "SAT" or (weekly == "SAT" and rsi > 70):
        return _verdict(
            "SAT",
            "Kısa Vade: Pozisyon Kısalt",
            f"Günlük {daily}, haftalık {weekly} - kısa vadede satış baskısı yüksek",
            factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
        )
    if daily == "BEKLE" and weekly == "AL":
        return _verdict(
            "IZLE",
            "Kısa Vade: Tetik Bekle",
            "Haftalık trend AL ama günlük tetik henüz yok - "
            "kırılım veya hacim teyidi bekle",
            factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
        )
    if daily == "BEKLE" and weekly == "SAT":
        return _verdict(
            "BEKLE",
            "Kısa Vade: Yeni Pozisyon Açma",
            "Haftalık trend zayıf - kısa vadede risk-getiri elverişsiz",
            factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
        )
    return _verdict(
        "BEKLE",
        "Kısa Vade: Bekle",
        f"Sinyaller karışık (G:{daily} / H:{weekly}); kısa vadede netlik yok",
        factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
    )


def _decide_medium(
    timeframes: Optional[TimeframeSignals],
    targets: Optional[TargetLevels],
    score: float,
    regime_label: str,
) -> TechnicalHorizonVerdict:
    monthly = _signal_word(timeframes.monthly if timeframes else "BEKLE")
    weekly = _signal_word(timeframes.weekly if timeframes else "BEKLE")
    rr = _safe_rr(targets.medium_rr if targets else None)
    target_price = _safe_price(targets.medium_target if targets else None)
    reward_pct = targets.medium_reward_pct if (targets and target_price) else None

    factors = [
        f"Haftalık sinyal {weekly}",
        f"Aylık sinyal {monthly}",
        f"Skor {score:.0f}/100",
        f"Orta vade R/O {rr:.2f}" if rr is not None else "Orta vade hedefi hesaplanmadı",
        f"Piyasa rejimi: {regime_label}" if regime_label else "",
    ]
    factors = [f for f in factors if f]

    if monthly == "AL" and weekly == "AL" and rr is not None and rr >= 1.5:
        return _verdict(
            "AL",
            "Orta Vade: Pozisyon Aç",
            f"Aylık ve haftalık trendler hizalı, R/O {rr:.1f} ({_rr_quality(rr)}) - "
            "orta vadeli alım için elverişli",
            factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
        )
    if monthly == "AL":
        reason_text = (
            f"Aylık trend AL; R/O {rr:.2f} sınırlı - kademeli birikim güvenli"
            if rr is not None
            else "Aylık trend AL; günlük sinyal henüz tetik vermediği için "
                 "hedef hesaplanmadı - kademeli birikim makul"
        )
        return _verdict(
            "BIRIKTIR",
            "Orta Vade: Kademeli Biriktir",
            reason_text,
            factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
        )
    if monthly == "SAT":
        return _verdict(
            "SAT",
            "Orta Vade: Pozisyondan Çık",
            "Aylık trend SAT - orta vadede aşağı baskı baskın",
            factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
        )
    if monthly == "BEKLE" and weekly == "AL":
        return _verdict(
            "IZLE",
            "Orta Vade: İzle - Onay Bekle",
            "Aylık trend henüz teyit etmedi; kırılım için izlemede tut",
            factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
        )
    return _verdict(
        "BEKLE",
        "Orta Vade: Bekle",
        f"Aylık trend {monthly}, haftalık {weekly} - orta vadeli yön belirsiz",
        factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
    )


def _decide_long(
    timeframes: Optional[TimeframeSignals],
    targets: Optional[TargetLevels],
    indicators: dict,
    regime_label: str,
) -> TechnicalHorizonVerdict:
    yearly = _signal_word(timeframes.yearly if timeframes else "BEKLE")
    monthly = _signal_word(timeframes.monthly if timeframes else "BEKLE")
    rr = _safe_rr(targets.long_rr if targets else None)
    target_price = _safe_price(targets.long_target if targets else None)
    reward_pct = targets.long_reward_pct if (targets and target_price) else None

    sma50 = indicators.get("sma_short", 0) or 0
    sma200 = indicators.get("sma_long", 0) or 0
    close = indicators.get("close", 0) or 0
    golden_cross = sma50 > 0 and sma200 > 0 and sma50 > sma200
    above_200 = close > 0 and sma200 > 0 and close > sma200

    factors = [
        f"Yıllık sinyal {yearly}",
        f"Aylık sinyal {monthly}",
        "200 SMA üzerinde" if above_200 else "200 SMA altında",
        "Golden Cross aktif" if golden_cross else "Death Cross / SMA50 < SMA200",
        f"Uzun vade R/O {rr:.2f}" if rr is not None else "Uzun vade hedefi hesaplanmadı",
        f"Piyasa rejimi: {regime_label}" if regime_label else "",
    ]
    factors = [f for f in factors if f]

    if yearly == "AL" and golden_cross and above_200:
        reason_text = (
            f"Yıllık trend AL, fiyat 200 SMA üstünde, golden cross aktif - "
            f"R/O {rr:.1f} ({_rr_quality(rr)})"
            if rr is not None
            else "Yıllık trend AL, fiyat 200 SMA üstünde, golden cross aktif - "
                 "uzun vade pozisyon için elverişli"
        )
        return _verdict(
            "AL",
            "Uzun Vade: Tut / Topla (3+ ay)",
            reason_text,
            factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
        )
    if yearly == "AL" and above_200:
        return _verdict(
            "BIRIKTIR",
            "Uzun Vade: Kademeli Topla",
            "Yıllık trend olumlu ve fiyat 200 SMA üstünde; "
            "golden cross henüz yok - kademeli alım",
            factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
        )
    if yearly == "SAT" and not above_200:
        return _verdict(
            "KACIN",
            "Uzun Vade: Trend Olumsuz",
            "Yıllık trend SAT ve fiyat 200 SMA altında - "
            "uzun vadeli pozisyon mantıksız",
            factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
        )
    if yearly == "SAT":
        return _verdict(
            "SAT",
            "Uzun Vade: Pozisyon Kapat",
            "Yıllık trend SAT - uzun vadeli görünüm bozulmuş",
            factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
        )
    if yearly == "BEKLE" and above_200:
        return _verdict(
            "TUT",
            "Uzun Vade: Mevcudu Tut",
            "Uzun trend zayıf-pozitif; fiyat 200 SMA üstünde - mevcut tutulabilir",
            factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
        )
    return _verdict(
        "IZLE",
        "Uzun Vade: Henüz Trend Oluşmadı",
        "Yıllık trend nötr veya 200 SMA altı - uzun vadeli giriş için izlemede kal",
        factors, rr=rr, target_price=target_price, reward_pct=reward_pct,
    )


# ── Public ───────────────────────────────────────────────────────────────────


def build_technical_horizon_guidance(
    timeframes: Optional[TimeframeSignals],
    targets: Optional[TargetLevels],
    indicators: dict,
    score: float,
    regime: Optional[MarketRegime] = None,
) -> TechnicalHorizonGuidance:
    """Teknik sinyalden vade bazlı bütünsel öneri seti üretir."""
    rsi = indicators.get("rsi", 50.0) or 50.0
    regime_label = _regime_modifier(regime) if regime else ""

    short = _decide_short(timeframes, targets, rsi, regime_label)
    medium = _decide_medium(timeframes, targets, score, regime_label)
    long = _decide_long(timeframes, targets, indicators, regime_label)

    overall = (
        f"Kısa: {short.label}. Orta: {medium.label}. Uzun: {long.label}."
    )
    return TechnicalHorizonGuidance(
        short=short, medium=medium, long=long, overall=overall,
    )
