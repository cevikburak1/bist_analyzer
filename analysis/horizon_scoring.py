"""
Vade Bazlı (Horizon-Aware) Skorlama Motoru.

Her sembol için 4 ayrı skor + karar üretir:

- short  (G\u00fcnl\u00fck)   : G\u00fcnl\u00fck OHLCV \u00fczerinde momentum + hacim a\u011f\u0131rl\u0131kl\u0131
- swing  (Haftal\u0131k) : Haftal\u0131k bar trend + RSI a\u011f\u0131rl\u0131kl\u0131
- medium (Ayl\u0131k)    : Ayl\u0131k bar trend + 52w pozisyonu a\u011f\u0131rl\u0131kl\u0131
- long   (Y\u0131ll\u0131k)   : G\u00fcnl\u00fck SMA200 + uzun-vade e\u011fim baskin

Her vade kendi:
- skor (0-100)
- karar (AL / SAT / BEKLE)
- tek-c\u00fcmle reason
- detayl\u0131 reason_factors listesi (kullan\u0131c\u0131ya neden)
- kategori d\u00f6k\u00fcm\u00fc (trend/momentum/hacim/fiyat_pozisyonu/rejim)

al\u0131r.

Karar kurallari geri uyumlu: short vade kurallari mevcut analysis/signals.py
mantigina denk gelir; di\u011fer vadeler kendi e\u015fiklerine sahiptir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from analysis.indicators import (
    calculate_52_week_position,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_linear_regression_slope,
    calculate_macd,
    calculate_obv,
    calculate_obv_sma,
    calculate_rsi,
    calculate_sma,
)
from analysis.market_regime import MarketRegime

logger = logging.getLogger(__name__)


HORIZONS = ("short", "swing", "medium", "long")


@dataclass
class HorizonCategoryScore:
    earned: float
    possible: float
    factors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "earned": round(self.earned, 1),
            "possible": round(self.possible, 1),
            "factors": list(self.factors),
        }


@dataclass
class HorizonTargets:
    """Vade-spesifik stop/hedef seviyeleri."""
    direction: str         # "LONG" / "SHORT" / "NONE"
    entry: float = 0.0
    stop_loss: float = 0.0
    target_price: float = 0.0
    risk_pct: float = 0.0
    reward_pct: float = 0.0
    rr: float = 0.0
    note: str = ""         # Kullan\u0131c\u0131ya UI ipucu (\u00f6rn. "BEKLE - g\u00f6stericidir")

    def as_dict(self) -> dict:
        return {
            "direction": self.direction,
            "entry": round(self.entry, 4) if self.entry else 0.0,
            "stop_loss": round(self.stop_loss, 4) if self.stop_loss else 0.0,
            "target_price": round(self.target_price, 4) if self.target_price else 0.0,
            "risk_pct": round(self.risk_pct, 2),
            "reward_pct": round(self.reward_pct, 2),
            "rr": round(self.rr, 2),
            "note": self.note,
        }


@dataclass
class HorizonScore:
    horizon: str           # "short" | "swing" | "medium" | "long"
    label: str             # G\u00fcnl\u00fck / Haftal\u0131k / Ayl\u0131k / Y\u0131ll\u0131k
    total: float           # 0-100
    decision: str          # AL / SAT / BEKLE
    reason: str            # tek c\u00fcmle
    reason_factors: list[str] = field(default_factory=list)
    categories: dict[str, HorizonCategoryScore] = field(default_factory=dict)
    targets: Optional[HorizonTargets] = None

    def as_dict(self) -> dict:
        return {
            "horizon": self.horizon,
            "label": self.label,
            "total": round(self.total, 1),
            "decision": self.decision,
            "reason": self.reason,
            "reason_factors": list(self.reason_factors),
            "categories": {k: v.as_dict() for k, v in self.categories.items()},
            "targets": self.targets.as_dict() if self.targets else None,
        }


@dataclass
class HorizonScoreSet:
    short: HorizonScore
    swing: HorizonScore
    medium: HorizonScore
    long: HorizonScore

    def as_dict(self) -> dict:
        return {
            "short": self.short.as_dict(),
            "swing": self.swing.as_dict(),
            "medium": self.medium.as_dict(),
            "long": self.long.as_dict(),
        }


# ── Horizon konfig\u00fcrasyonlar\u0131 ─────────────────────────────────────────────


@dataclass
class HorizonConfig:
    horizon: str
    label: str
    resample_rule: Optional[str]   # None = g\u00fcnl\u00fck veriyi do\u011frudan kullan
    sma_fast: int
    sma_slow: int
    rsi_period: int
    weights: dict                  # kategori a\u011f\u0131rl\u0131klar\u0131 (toplam 100)
    buy_threshold: float
    sell_threshold: float
    hold_target_period: str        # "1-5 g\u00fcn", "1-4 hafta" gibi
    atr_stop_mult: float = 2.0     # ATR stop \u00e7arpan\u0131
    atr_target_mult: float = 4.0   # ATR hedef \u00e7arpan\u0131


HORIZON_CONFIGS: dict[str, HorizonConfig] = {
    "short": HorizonConfig(
        horizon="short",
        label="G\u00fcnl\u00fck",
        resample_rule=None,
        sma_fast=20,
        sma_slow=50,
        rsi_period=14,
        weights={
            "trend": 20, "momentum": 30, "volume": 25,
            "price_position": 15, "regime": 10,
        },
        buy_threshold=65,
        sell_threshold=35,
        hold_target_period="1-5 g\u00fcn",
        atr_stop_mult=1.5,
        atr_target_mult=2.5,
    ),
    "swing": HorizonConfig(
        horizon="swing",
        label="Haftal\u0131k",
        resample_rule="W",
        sma_fast=10,
        sma_slow=30,
        rsi_period=14,
        weights={
            "trend": 30, "momentum": 25, "volume": 15,
            "price_position": 20, "regime": 10,
        },
        buy_threshold=65,
        sell_threshold=35,
        hold_target_period="1-4 hafta",
        atr_stop_mult=2.0,
        atr_target_mult=4.0,
    ),
    "medium": HorizonConfig(
        horizon="medium",
        label="Ayl\u0131k",
        resample_rule="ME",
        sma_fast=6,
        sma_slow=12,
        rsi_period=14,
        weights={
            "trend": 35, "momentum": 20, "volume": 10,
            "price_position": 25, "regime": 10,
        },
        buy_threshold=65,
        sell_threshold=35,
        hold_target_period="1-6 ay",
        atr_stop_mult=3.0,
        atr_target_mult=6.0,
    ),
    "long": HorizonConfig(
        horizon="long",
        label="Y\u0131ll\u0131k",
        resample_rule=None,
        sma_fast=50,
        sma_slow=200,
        rsi_period=14,
        weights={
            "trend": 45, "momentum": 10, "volume": 5,
            "price_position": 30, "regime": 10,
        },
        buy_threshold=70,
        sell_threshold=30,
        hold_target_period="6 ay - 5+ y\u0131l",
        atr_stop_mult=4.0,
        atr_target_mult=10.0,
    ),
}


# ── Yard\u0131mc\u0131lar ───────────────────────────────────────────────────────────


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df.resample(rule).agg(agg).dropna()


def _safe(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return 0.0
    return float(value)


def _safe_last(series: pd.Series, default: float = 0.0) -> float:
    if series is None or len(series) == 0:
        return default
    val = series.iloc[-1]
    if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
        return default
    return float(val)


# ── Tek bir vade i\u00e7in skor ────────────────────────────────────────────────


def _build_horizon_indicators(df: pd.DataFrame, cfg: HorizonConfig) -> dict:
    """\u0130lgili vadeye \u00f6zg\u00fc indikat\u00f6r de\u011ferlerini d\u00f6nd\u00fcr\u00fcr."""
    if df is None or df.empty:
        return {}

    if cfg.resample_rule:
        try:
            base = _resample(df, cfg.resample_rule)
        except Exception:
            base = df
    else:
        base = df

    if base.empty:
        return {}

    close = base["close"]
    volume = base["volume"]
    high = base["high"]
    low = base["low"]

    sma_fast = calculate_sma(close, cfg.sma_fast)
    sma_slow = calculate_sma(close, cfg.sma_slow)
    rsi = calculate_rsi(close, cfg.rsi_period)
    macd_line, signal_line, histogram = calculate_macd(close)
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(close)
    obv = calculate_obv(close, volume)
    obv_sma = calculate_obv_sma(obv)
    atr = calculate_atr(high, low, close, period=14)

    slope_window = max(20, min(60, len(close) // 2))
    slope = calculate_linear_regression_slope(close, slope_window)

    week52_pos = calculate_52_week_position(close)

    vol_short = volume.tail(5).mean() if len(volume) >= 5 else 0.0
    vol_avg = volume.tail(20).mean() if len(volume) >= 20 else 0.0

    # Swing seviyeleri (vade-spesifik bar say\u0131s\u0131)
    swing_window = min(20, len(close))
    swing_low = float(low.tail(swing_window).min()) if swing_window else 0.0
    swing_high = float(high.tail(swing_window).max()) if swing_window else 0.0

    return {
        "close": _safe_last(close),
        "sma_fast": _safe_last(sma_fast),
        "sma_slow": _safe_last(sma_slow),
        "rsi": _safe_last(rsi, 50.0),
        "macd": _safe_last(macd_line),
        "macd_signal": _safe_last(signal_line),
        "macd_hist": _safe_last(histogram),
        "macd_hist_prev": (
            float(histogram.iloc[-2])
            if len(histogram) > 1 and not np.isnan(histogram.iloc[-2])
            else 0.0
        ),
        "bb_upper": _safe_last(bb_upper),
        "bb_middle": _safe_last(bb_middle),
        "bb_lower": _safe_last(bb_lower),
        "obv": _safe_last(obv),
        "obv_sma": _safe_last(obv_sma),
        "atr": _safe_last(atr),
        "swing_low": swing_low,
        "swing_high": swing_high,
        "volume_short_avg": float(vol_short) if vol_short else 0.0,
        "volume_avg": float(vol_avg) if vol_avg else 0.0,
        "trend_slope": slope,
        "week52_position": week52_pos,
        "bars_available": int(len(close)),
    }


def _score_trend(ind: dict, weight: float, cfg: HorizonConfig) -> HorizonCategoryScore:
    factors: list[str] = []
    earned = 0.0
    close = ind.get("close", 0.0)
    fast = ind.get("sma_fast", 0.0)
    slow = ind.get("sma_slow", 0.0)
    slope = ind.get("trend_slope", 0.0)

    # Fiyat > h\u0131zl\u0131 SMA: weight'in %25'i
    p1 = weight * 0.25
    if fast > 0 and close > fast:
        earned += p1
        factors.append(
            f"Fiyat {cfg.sma_fast} bar SMA \u00fczerinde (+{p1:.0f} puan)"
        )
    else:
        factors.append(f"Fiyat {cfg.sma_fast} bar SMA alt\u0131nda (0 puan)")

    # Fiyat > yava\u015f SMA: weight'in %25'i
    p2 = weight * 0.25
    if slow > 0 and close > slow:
        earned += p2
        factors.append(
            f"Fiyat {cfg.sma_slow} bar SMA \u00fczerinde (+{p2:.0f} puan)"
        )
    else:
        factors.append(f"Fiyat {cfg.sma_slow} bar SMA alt\u0131nda (0 puan)")

    # Golden Cross: weight'in %25'i
    p3 = weight * 0.25
    if fast > 0 and slow > 0 and fast > slow:
        earned += p3
        factors.append(
            f"Golden Cross aktif: SMA{cfg.sma_fast} > SMA{cfg.sma_slow} (+{p3:.0f} puan)"
        )
    else:
        factors.append(
            f"Death Cross / k\u0131sa SMA uzun SMA alt\u0131nda (0 puan)"
        )

    # E\u011fim: weight'in %25'i
    p4 = weight * 0.25
    if slope > 0:
        gain = min(p4, p4 * (slope / 0.2))   # %0.2/g\u00fcn = tam puan
        earned += gain
        factors.append(
            f"Trend e\u011fimi pozitif (slope %{slope:.2f}/bar) (+{gain:.0f} puan)"
        )
    else:
        factors.append(
            f"Trend e\u011fimi negatif/yatay (slope %{slope:.2f}/bar) (0 puan)"
        )

    return HorizonCategoryScore(earned=earned, possible=weight, factors=factors)


def _score_momentum(ind: dict, weight: float, cfg: HorizonConfig) -> HorizonCategoryScore:
    factors: list[str] = []
    earned = 0.0
    rsi = ind.get("rsi", 50.0)
    macd = ind.get("macd", 0.0)
    macd_signal = ind.get("macd_signal", 0.0)
    macd_hist = ind.get("macd_hist", 0.0)
    macd_hist_prev = ind.get("macd_hist_prev", 0.0)

    # RSI ideal band
    p1 = weight * 0.35
    if 40 <= rsi <= 70:
        earned += p1
        factors.append(f"RSI {rsi:.0f} ideal momentum band\u0131nda (+{p1:.0f} puan)")
    elif rsi > 70:
        factors.append(f"RSI {rsi:.0f} a\u015f\u0131r\u0131 al\u0131m b\u00f6lgesinde (0 puan)")
    elif rsi < 30:
        factors.append(f"RSI {rsi:.0f} a\u015f\u0131r\u0131 sat\u0131m b\u00f6lgesinde (0 puan)")
    else:
        factors.append(f"RSI {rsi:.0f} ideal band\u0131n d\u0131\u015f\u0131nda (0 puan)")

    # MACD signal hatt\u0131 \u00fczerinde
    p2 = weight * 0.30
    if macd > macd_signal:
        earned += p2
        factors.append("MACD signal hatt\u0131 \u00fczerinde - momentum pozitif " f"(+{p2:.0f} puan)")
    else:
        factors.append("MACD signal alt\u0131nda - momentum negatif (0 puan)")

    # MACD histogram artan ve pozitif
    p3 = weight * 0.35
    if macd_hist > 0 and macd_hist > macd_hist_prev:
        earned += p3
        factors.append(
            "MACD histogram pozitif ve geni\u015fliyor - moment\u0131m g\u00fc\u00e7leniyor "
            f"(+{p3:.0f} puan)"
        )
    elif macd_hist > 0:
        factors.append(
            "MACD histogram pozitif ama daral\u0131yor - moment\u0131m zay\u0131fl\u0131yor (0 puan)"
        )
    elif macd_hist < macd_hist_prev:
        factors.append("MACD histogram negatif ve derinle\u015fiyor (0 puan)")
    else:
        factors.append("MACD histogram negatif ama toparlan\u0131yor (0 puan)")

    return HorizonCategoryScore(earned=earned, possible=weight, factors=factors)


def _score_volume(ind: dict, weight: float, cfg: HorizonConfig) -> HorizonCategoryScore:
    factors: list[str] = []
    earned = 0.0
    vol_short = ind.get("volume_short_avg", 0.0)
    vol_avg = ind.get("volume_avg", 0.0)
    obv = ind.get("obv", 0.0)
    obv_sma = ind.get("obv_sma", 0.0)

    # K\u0131sa hacim ortalamas\u0131 / uzun: 50%
    p1 = weight * 0.5
    if vol_avg > 0:
        ratio = vol_short / vol_avg
        gain = min(p1, p1 * ratio / 1.5)    # 1.5x = tam puan
        earned += gain
        factors.append(
            f"Hacim ortalamas\u0131n\u0131n {ratio:.2f} kat\u0131 (+{gain:.0f}/{p1:.0f} puan)"
        )
    else:
        factors.append("Hacim ortalama verisi yetersiz (0 puan)")

    # OBV trend: 50%
    p2 = weight * 0.5
    if obv != 0 and obv > obv_sma:
        earned += p2
        factors.append("OBV (kurumsal hacim) artan trendde " f"(+{p2:.0f} puan)")
    else:
        factors.append("OBV (kurumsal hacim) zay\u0131f / yatay (0 puan)")

    return HorizonCategoryScore(earned=earned, possible=weight, factors=factors)


def _score_price_position(ind: dict, weight: float, cfg: HorizonConfig) -> HorizonCategoryScore:
    factors: list[str] = []
    earned = 0.0
    close = ind.get("close", 0.0)
    bb_middle = ind.get("bb_middle", 0.0)
    week52 = ind.get("week52_position", 0.5)

    # 52 hafta pozisyonu: 60%
    p1 = weight * 0.6
    if week52 >= 0.7:
        earned += p1
        factors.append(
            f"52 hafta aral\u0131\u011f\u0131nda \u00fcst %30 (poz {week52:.0%}) "
            f"(+{p1:.0f} puan)"
        )
    elif week52 >= 0.4:
        gain = p1 * 0.5
        earned += gain
        factors.append(
            f"52 hafta orta b\u00f6lgesinde (poz {week52:.0%}) (+{gain:.0f}/{p1:.0f} puan)"
        )
    else:
        factors.append(
            f"52 hafta dip b\u00f6lgesinde (poz {week52:.0%}) - dipten d\u00f6n\u00fc\u015f riski (0 puan)"
        )

    # Bollinger orta band \u00fczerinde: 40%
    p2 = weight * 0.4
    if bb_middle > 0 and close > bb_middle:
        earned += p2
        factors.append("Bollinger orta band\u0131 \u00fczerinde " f"(+{p2:.0f} puan)")
    else:
        factors.append("Bollinger orta band alt\u0131nda (0 puan)")

    return HorizonCategoryScore(earned=earned, possible=weight, factors=factors)


def _score_regime(weight: float, beta: float, regime: MarketRegime) -> HorizonCategoryScore:
    factors: list[str] = []
    earned = 0.0

    # Endeks 20g performans\u0131: 60%
    p1 = weight * 0.6
    perf = float(getattr(regime, "performance_20d", 0.0) or 0.0)
    if perf > 2:
        earned += p1
        factors.append(f"XU100 son 20g %{perf:.1f} - g\u00fc\u00e7l\u00fc rejim " f"(+{p1:.0f} puan)")
    elif perf > 0:
        gain = p1 * 0.5
        earned += gain
        factors.append(f"XU100 son 20g %{perf:.1f} - hafif pozitif " f"(+{gain:.0f}/{p1:.0f} puan)")
    else:
        factors.append(f"XU100 son 20g %{perf:.1f} - rejim olumsuz (0 puan)")

    # Beta uyumu: 40%
    p2 = weight * 0.4
    if 0.5 <= beta <= 1.5:
        earned += p2
        factors.append(f"Beta {beta:.2f} - dengeli (+{p2:.0f} puan)")
    elif beta > 1.5:
        factors.append(f"Beta {beta:.2f} - y\u00fcksek volatilite (0 puan)")
    else:
        factors.append(f"Beta {beta:.2f} - endeksten kopuk (0 puan)")

    return HorizonCategoryScore(earned=earned, possible=weight, factors=factors)


def _decide(
    cfg: HorizonConfig,
    score: float,
    ind: dict,
    regime: MarketRegime,
) -> tuple[str, str, list[str]]:
    """Horizon-spesifik karar + reason + reason_factors."""
    factors: list[str] = []
    rsi = ind.get("rsi", 50.0)
    close = ind.get("close", 0.0)
    sma_slow = ind.get("sma_slow", 0.0)
    bb_upper = ind.get("bb_upper", 0.0)
    macd = ind.get("macd", 0.0)
    macd_signal = ind.get("macd_signal", 0.0)
    vol_short = ind.get("volume_short_avg", 0.0)
    vol_avg = ind.get("volume_avg", 0.0)

    label = cfg.label.lower()

    # SAT kontrolleri (vade-spesifik)
    if score <= cfg.sell_threshold:
        factors.append(f"{cfg.label} skoru {score:.0f} - SAT e\u015fi\u011fi {cfg.sell_threshold:.0f} alt\u0131nda")
        reason = (
            f"{cfg.label} skor {score:.0f}/100 \u2264 {cfg.sell_threshold:.0f}: "
            f"{label} vadede sat\u0131\u015f bask\u0131s\u0131 bask\u0131n"
        )
        return "SAT", reason, factors

    if cfg.horizon == "short" and rsi > 75 and bb_upper > 0 and close > bb_upper:
        factors.append(f"RSI {rsi:.0f} > 75 + Bollinger \u00fcst kar\u0131lm\u0131\u015f - a\u015f\u0131r\u0131 al\u0131m geri \u00e7ekilme riski")
        return (
            "SAT",
            f"G\u00fcnl\u00fck a\u015f\u0131r\u0131 al\u0131m: RSI {rsi:.0f} ve fiyat Bollinger \u00fcst band \u00fczerinde - sat\u0131\u015f bask\u0131s\u0131 olas\u0131",
            factors,
        )

    if cfg.horizon in ("short", "swing") and macd < macd_signal and sma_slow > 0 and close < sma_slow:
        factors.append("MACD signal alt\u0131nda + fiyat uzun SMA alt\u0131nda - trend bozulmu\u015f")
        return (
            "SAT",
            f"{cfg.label} vadede MACD negatif ve fiyat SMA{cfg.sma_slow} alt\u0131nda - trend olumsuz",
            factors,
        )

    # Y\u0131ll\u0131k vadede SMA200 alt\u0131 zorunlu kal\u0131c\u0131 negatif
    if cfg.horizon == "long" and sma_slow > 0 and close < sma_slow:
        factors.append(f"Fiyat SMA200 alt\u0131nda - uzun vade trend k\u0131r\u0131k")
        return (
            "SAT",
            f"Uzun vadede fiyat SMA200 ({sma_slow:.2f}) alt\u0131nda - y\u0131ll\u0131k yat\u0131r\u0131m i\u00e7in trend k\u0131r\u0131k",
            factors,
        )

    # AL kontrolleri (vade-spesifik)
    score_ok = score >= cfg.buy_threshold
    rsi_ok = 30 <= rsi <= 70
    above_long_sma = sma_slow <= 0 or close > sma_slow

    # Hacim filtresi: g\u00fcnl\u00fckte zorunlu, ortada esnek, uzunda yok
    if cfg.horizon == "short":
        volume_ok = vol_avg <= 0 or vol_short >= vol_avg * 1.2
        volume_required = True
    elif cfg.horizon == "swing":
        volume_ok = vol_avg <= 0 or vol_short >= vol_avg * 1.0
        volume_required = True
    else:
        volume_ok = True
        volume_required = False

    if score_ok and rsi_ok and above_long_sma and volume_ok:
        factors.append(f"Skor {score:.0f} \u2265 AL e\u015fi\u011fi {cfg.buy_threshold:.0f}")
        factors.append(f"RSI {rsi:.0f} sa\u011fl\u0131kl\u0131 bantta (30-70)")
        factors.append(f"Fiyat SMA{cfg.sma_slow} \u00fczerinde - trend olumlu")
        if volume_required:
            factors.append("Hacim filtresi sa\u011fland\u0131")
        return (
            "AL",
            (
                f"{cfg.label} vadede skor {score:.0f}/100 \u2265 {cfg.buy_threshold:.0f}, "
                f"RSI {rsi:.0f} sa\u011fl\u0131kl\u0131, fiyat SMA{cfg.sma_slow} \u00fczerinde"
                + (" ve hacim teyitli" if volume_required else "")
                + f" - {cfg.hold_target_period} pozisyonu i\u00e7in elveri\u015fli"
            ),
            factors,
        )

    # BEKLE: hangi ko\u015full\u0131 eksik
    if score_ok:
        missing: list[str] = []
        if not rsi_ok:
            missing.append(f"RSI {rsi:.0f} ideal bant [30-70] d\u0131\u015f\u0131nda")
        if not above_long_sma:
            missing.append(f"fiyat SMA{cfg.sma_slow} alt\u0131nda")
        if not volume_ok:
            missing.append("hacim AL e\u015fi\u011fini kar\u015f\u0131lam\u0131yor")
        factors.extend(missing)
        reason = (
            f"{cfg.label} skor {score:.0f}/100 yeterli ama AL i\u00e7in eksikler: "
            + ", ".join(missing)
        )
    else:
        factors.append(
            f"Skor {score:.0f} ne AL ({cfg.buy_threshold:.0f}) ne SAT ({cfg.sell_threshold:.0f}) e\u015fi\u011fini ge\u00e7iyor"
        )
        reason = (
            f"{cfg.label} skor {score:.0f}/100 - n\u00f6tr; "
            f"{cfg.hold_target_period} i\u00e7in net y\u00f6n yok"
        )

    return "BEKLE", reason, factors


def _build_horizon_targets(
    cfg: HorizonConfig,
    decision: str,
    ind: dict,
) -> HorizonTargets:
    """Vade-spesifik stop/hedef \u00fcretir.

    Mevcut close + ATR baz alinir; her vade kendi atr_stop_mult ve
    atr_target_mult katsayilarini kullanir. AL/SAT yonune gore stop ve
    hedefler hesaplanir. BEKLE durumunda karara gore yine "indicative"
    seviyeler hesaplanir ve note alaninda gosterici oldugu belirtilir.
    """
    close = ind.get("close", 0.0)
    atr = ind.get("atr", 0.0)
    swing_low = ind.get("swing_low", 0.0)
    swing_high = ind.get("swing_high", 0.0)

    if close <= 0 or atr <= 0:
        return HorizonTargets(direction="NONE", note="Yetersiz fiyat/ATR verisi")

    # Y\u00f6n se\u00e7imi: AL\u2192LONG, SAT\u2192SHORT, BEKLE\u2192trend e\u011fimine g\u00f6re
    direction = "NONE"
    note = ""
    if decision == "AL":
        direction = "LONG"
    elif decision == "SAT":
        direction = "SHORT"
    else:
        # BEKLE - directional bias trend slope ile
        slope = ind.get("trend_slope", 0.0)
        sma_slow = ind.get("sma_slow", 0.0)
        if slope > 0 or (sma_slow > 0 and close > sma_slow):
            direction = "LONG"
        else:
            direction = "SHORT"
        note = "BEKLE - aktif giri\u015f \u00f6nerilmez; seviyeler g\u00f6stericidir"

    if direction == "LONG":
        stop = close - cfg.atr_stop_mult * atr
        # Swing low ile tampon: stop swing_low'un alt\u0131na ge\u00e7memeli (\u00e7ok yak\u0131nsa)
        if swing_low > 0 and swing_low > stop:
            stop = max(stop, swing_low * 0.985)
        target = close + cfg.atr_target_mult * atr
        risk = max(close - stop, 0.0)
        reward = max(target - close, 0.0)
    else:  # SHORT
        stop = close + cfg.atr_stop_mult * atr
        if swing_high > 0 and swing_high < stop:
            stop = min(stop, swing_high * 1.015)
        target = close - cfg.atr_target_mult * atr
        target = max(target, 0.01)
        risk = max(stop - close, 0.0)
        reward = max(close - target, 0.0)

    risk_pct = (risk / close) * 100 if close > 0 else 0.0
    reward_pct = (reward / close) * 100 if close > 0 else 0.0
    rr = (reward / risk) if risk > 0 else 0.0

    return HorizonTargets(
        direction=direction,
        entry=close,
        stop_loss=stop,
        target_price=target,
        risk_pct=risk_pct,
        reward_pct=reward_pct,
        rr=rr,
        note=note,
    )


def _calculate_one_horizon(
    df: pd.DataFrame,
    cfg: HorizonConfig,
    regime: MarketRegime,
    beta: float,
) -> HorizonScore:
    ind = _build_horizon_indicators(df, cfg)
    if not ind or ind.get("bars_available", 0) < cfg.sma_slow + 5:
        return HorizonScore(
            horizon=cfg.horizon,
            label=cfg.label,
            total=0.0,
            decision="BEKLE",
            reason=(
                f"{cfg.label} de\u011ferlendirme i\u00e7in yeterli bar say\u0131s\u0131 yok "
                f"(en az {cfg.sma_slow + 5} gerekli)"
            ),
            reason_factors=[
                f"Mevcut bar say\u0131s\u0131: {ind.get('bars_available', 0)}",
            ],
            categories={},
            targets=HorizonTargets(direction="NONE", note="Yetersiz veri"),
        )

    cats = {
        "trend": _score_trend(ind, cfg.weights["trend"], cfg),
        "momentum": _score_momentum(ind, cfg.weights["momentum"], cfg),
        "volume": _score_volume(ind, cfg.weights["volume"], cfg),
        "price_position": _score_price_position(ind, cfg.weights["price_position"], cfg),
        "regime": _score_regime(cfg.weights["regime"], beta, regime),
    }

    total = sum(c.earned for c in cats.values())
    decision, reason, factors = _decide(cfg, total, ind, regime)
    targets = _build_horizon_targets(cfg, decision, ind)

    return HorizonScore(
        horizon=cfg.horizon,
        label=cfg.label,
        total=min(100.0, total),
        decision=decision,
        reason=reason,
        reason_factors=factors,
        categories=cats,
        targets=targets,
    )


def calculate_horizon_score_set(
    df: pd.DataFrame,
    regime: MarketRegime,
    beta: float = 1.0,
) -> HorizonScoreSet:
    """T\u00fcm vadeler i\u00e7in skor seti \u00fcretir."""
    short = _calculate_one_horizon(df, HORIZON_CONFIGS["short"], regime, beta)
    swing = _calculate_one_horizon(df, HORIZON_CONFIGS["swing"], regime, beta)
    medium = _calculate_one_horizon(df, HORIZON_CONFIGS["medium"], regime, beta)
    long = _calculate_one_horizon(df, HORIZON_CONFIGS["long"], regime, beta)
    return HorizonScoreSet(short=short, swing=swing, medium=medium, long=long)
