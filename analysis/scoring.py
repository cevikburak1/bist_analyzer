"""
Morpheus tarzı additive skorlama motoru.

Her hisse 5 temel başlıkta puanlanır:
1. Trendin Yönü ve Gücü
2. Momentum ve Trend Kuvveti
3. Hacim Patlaması ve Para Akışı
4. Fiyat Pozisyonu
5. Sıkışma ve Kırılım Potansiyeli
"""

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from analysis.market_regime import MarketRegime
from config import (
    RSI_IDEAL_LOW,
    RSI_IDEAL_HIGH,
    OVEREXTENSION_DISTANCE_PCT,
)

logger = logging.getLogger(__name__)


@dataclass
class ScoreBreakdown:
    """Skor detay dökümü"""
    trend: float = 0.0
    momentum: float = 0.0
    volume: float = 0.0
    price_position: float = 0.0
    squeeze_breakout: float = 0.0
    total: float = 0.0
    wr_pct: float = 0.0
    wr_samples: int = 0
    adx: float = 0.0
    v_kat: float = 0.0
    dzl_ok: bool = False
    sqz_ok: bool = False
    ema_distance_pct: float = 0.0
    overextended: bool = False
    details: dict = field(default_factory=dict)


def _safe(val) -> float:
    """NaN kontrolü; NaN ise 0 döndürür."""
    if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
        return 0.0
    return float(val)


def _bool(value) -> bool:
    try:
        if pd.isna(value):
            return False
    except TypeError:
        pass
    return bool(value)


def _calculate_win_rate(df: pd.DataFrame | None, horizon: int = 3, lookback: int = 110) -> tuple[float, int, dict]:
    if df is None or df.empty or len(df) < horizon + 20:
        return 0.0, 0, {"status": "insufficient_data"}

    work = df.tail(lookback + horizon + 5).copy()
    required = {"close", "perfect_order", "adx", "v_kat", "macd", "macd_signal"}
    if not required.issubset(work.columns):
        return 0.0, 0, {"status": "missing_columns"}

    candidates = work.iloc[:-horizon].copy()
    future_close = work["close"].shift(-horizon).reindex(candidates.index)
    entry_mask = (
        candidates["perfect_order"].fillna(False)
        & (candidates["adx"].fillna(0) >= 25)
        & (candidates["v_kat"].fillna(0) >= 1.0)
        & (candidates["macd"].fillna(0) > candidates["macd_signal"].fillna(0))
    )
    entries = candidates[entry_mask]
    if entries.empty:
        return 0.0, 0, {"status": "no_similar_entries"}

    outcomes = future_close.reindex(entries.index) > entries["close"]
    outcomes = outcomes.dropna()
    if outcomes.empty:
        return 0.0, 0, {"status": "no_outcomes"}

    wr_pct = float(outcomes.mean() * 100)
    return wr_pct, int(len(outcomes)), {
        "status": "ok",
        "horizon_bars": horizon,
        "lookback_bars": lookback,
    }


def score_trend(indicators: dict, wr_pct: float, wr_samples: int) -> tuple[float, dict]:
    """
    Trendin Yönü ve Gücü.
    - Perfect Order ana bonusu
    - EMA dizilimi ve trend eğimi
    - Geçmiş benzer girişlerin WR güveni
    """
    score = 0.0
    details = {}

    close = _safe(indicators.get("close"))
    ema20 = _safe(indicators.get("ema20"))
    ema50 = _safe(indicators.get("ema50"))
    ema200 = _safe(indicators.get("ema200"))
    slope = _safe(indicators.get("trend_slope"))
    perfect_order = close > ema20 > ema50 > ema200 > 0

    if perfect_order:
        score += 35
    details["perfect_order"] = perfect_order

    if ema20 > 0 and close > ema20:
        score += 15
        details["price_above_ema20"] = True
    else:
        details["price_above_ema20"] = False

    if ema20 > 0 and ema50 > 0 and ema20 > ema50:
        score += 12
        details["ema20_above_ema50"] = True
    else:
        details["ema20_above_ema50"] = False

    if ema50 > 0 and ema200 > 0 and ema50 > ema200:
        score += 12
        details["ema50_above_ema200"] = True
    else:
        details["ema50_above_ema200"] = False

    if slope > 0:
        gain = min(15, slope * 30)
        score += gain
        details["trend_slope_positive"] = True
        details["trend_slope_points"] = round(gain, 1)
    else:
        details["trend_slope_positive"] = False
        details["trend_slope_points"] = 0

    if wr_samples >= 3:
        wr_points = min(25, wr_pct * 0.25)
        score += wr_points
        details["wr_points"] = round(wr_points, 1)
    else:
        details["wr_points"] = 0

    details["ema20"] = round(ema20, 4)
    details["ema50"] = round(ema50, 4)
    details["ema200"] = round(ema200, 4)
    details["wr_pct"] = round(wr_pct, 1)
    details["wr_samples"] = wr_samples
    details["trend_slope_value"] = round(slope, 4)
    return score, details


def score_momentum(indicators: dict) -> tuple[float, dict]:
    """
    Momentum ve Trend Kuvveti.
    ADX, RSI, MACD ve EMA13 uzaklığı birlikte okunur.
    """
    score = 0.0
    details = {}

    rsi = _safe(indicators.get("rsi"))
    macd = _safe(indicators.get("macd"))
    macd_signal = _safe(indicators.get("macd_signal"))
    macd_hist = _safe(indicators.get("macd_hist"))
    macd_hist_prev = _safe(indicators.get("macd_hist_prev"))
    adx = _safe(indicators.get("adx"))
    plus_di = _safe(indicators.get("plus_di"))
    minus_di = _safe(indicators.get("minus_di"))
    ema_distance = _safe(indicators.get("ema_distance_pct"))

    if adx > 25:
        adx_points = min(45, (adx - 25) * 0.9)
        score += adx_points
        details["adx_strong"] = True
        details["adx_points"] = round(adx_points, 1)
    else:
        details["adx_strong"] = False
        details["adx_points"] = 0

    if plus_di > minus_di:
        score += 8
        details["dmi_bullish"] = True
    else:
        details["dmi_bullish"] = False

    if RSI_IDEAL_LOW <= rsi <= RSI_IDEAL_HIGH:
        score += 10
        details["rsi_ideal_zone"] = True
    else:
        details["rsi_ideal_zone"] = False

    if rsi > 50:
        score += 6
        details["rsi_above_50"] = True
    else:
        details["rsi_above_50"] = False

    if macd > macd_signal:
        score += 10
        details["macd_above_signal"] = True
    else:
        details["macd_above_signal"] = False

    if macd_hist > 0 and macd_hist > macd_hist_prev:
        score += 10
        details["macd_hist_rising"] = True
    else:
        details["macd_hist_rising"] = False

    if 0 <= ema_distance <= OVEREXTENSION_DISTANCE_PCT:
        distance_points = max(0, 10 - abs(ema_distance - 5))
        score += distance_points
        details["healthy_ema_distance"] = True
        details["ema_distance_points"] = round(distance_points, 1)
    else:
        details["healthy_ema_distance"] = False
        details["ema_distance_points"] = 0

    details["overextended"] = ema_distance > OVEREXTENSION_DISTANCE_PCT
    details["adx"] = round(adx, 1)
    details["plus_di"] = round(plus_di, 1)
    details["minus_di"] = round(minus_di, 1)
    details["rsi_value"] = round(rsi, 2)
    details["ema_distance_pct"] = round(ema_distance, 2)
    return score, details


def score_volume(indicators: dict) -> tuple[float, dict]:
    """
    Hacim Patlaması ve Para Akışı.
    V_KAT ve OBV para akışı birlikte puanlanır.
    """
    score = 0.0
    details = {}

    v_kat = _safe(indicators.get("v_kat"))
    obv = _safe(indicators.get("obv"))
    obv_sma = _safe(indicators.get("obv_sma"))

    if v_kat > 0:
        volume_points = min(35, max(0, v_kat - 0.8) * 22)
        score += volume_points
        details["v_kat_points"] = round(volume_points, 1)
        details["volume_above_avg"] = v_kat >= 1.0
    else:
        details["v_kat_points"] = 0
        details["volume_above_avg"] = False

    if obv > obv_sma:
        score += 18
        details["obv_rising"] = True
    else:
        details["obv_rising"] = False

    if v_kat >= 1.5 and _bool(indicators.get("squeeze_breakout")):
        score += 12
        details["breakout_volume"] = True
    else:
        details["breakout_volume"] = False

    details["v_kat"] = round(v_kat, 2)
    return score, details


def score_price_position(indicators: dict) -> tuple[float, dict]:
    """
    Fiyat Pozisyonu.
    52 hafta konumu, Bollinger orta bant ve son swing bölgesi.
    """
    score = 0.0
    details = {}

    week52_pos = _safe(indicators.get("week52_position"))
    close = _safe(indicators.get("close"))
    bb_middle = _safe(indicators.get("bb_middle"))

    if week52_pos > 0.3:
        if week52_pos >= 0.7:
            score += 20
        elif week52_pos >= 0.5:
            score += 14
        else:
            score += 8
        details["52w_position_ok"] = True
    else:
        details["52w_position_ok"] = False

    details["52w_position"] = round(week52_pos, 2)

    if bb_middle > 0 and close > bb_middle:
        score += 10
        details["above_bb_middle"] = True
    else:
        details["above_bb_middle"] = False

    swing_low = _safe(indicators.get("swing_low_20"))
    swing_high = _safe(indicators.get("swing_high_20"))
    if swing_low > 0 and swing_high > swing_low:
        range_pos = (close - swing_low) / (swing_high - swing_low)
        if 0.45 <= range_pos <= 0.95:
            score += 8
            details["swing_position_ok"] = True
        else:
            details["swing_position_ok"] = False
        details["swing_position"] = round(range_pos, 2)

    return score, details


def score_squeeze_breakout(indicators: dict) -> tuple[float, dict]:
    """
    Sıkışma ve Kırılım Potansiyeli.
    Bollinger bant sıkışması, kırılım ve hacim teyidi.
    """
    score = 0.0
    details = {}

    squeeze_on = _bool(indicators.get("squeeze_on"))
    squeeze_breakout = _bool(indicators.get("squeeze_breakout"))
    bb_width = _safe(indicators.get("bb_width_pct"))
    bb_width_p20 = _safe(indicators.get("bb_width_p20"))
    close = _safe(indicators.get("close"))
    bb_upper = _safe(indicators.get("bb_upper"))
    v_kat = _safe(indicators.get("v_kat"))

    if squeeze_on:
        score += 35
        details["squeeze_on"] = True
    else:
        details["squeeze_on"] = False

    if bb_width > 0 and bb_width_p20 > 0 and bb_width <= bb_width_p20 * 0.85:
        score += 10
        details["deep_squeeze"] = True
    else:
        details["deep_squeeze"] = False

    if squeeze_breakout:
        score += 35
        details["squeeze_breakout"] = True
    else:
        details["squeeze_breakout"] = False

    if bb_upper > 0 and close >= bb_upper * 0.98 and v_kat >= 1.2:
        score += 12
        details["near_breakout_with_volume"] = True
    else:
        details["near_breakout_with_volume"] = False

    details["bb_width_pct"] = round(bb_width, 2)
    details["bb_width_p20"] = round(bb_width_p20, 2)
    return score, details


def calculate_score(
    indicators: dict,
    market_regime: MarketRegime,
    df: pd.DataFrame | None = None,
) -> ScoreBreakdown:
    """
    Hissenin additive Morpheus skorunu hesaplar.
    """
    wr_pct, wr_samples, wr_details = _calculate_win_rate(df)
    trend_score, trend_details = score_trend(indicators, wr_pct, wr_samples)
    momentum_score, momentum_details = score_momentum(indicators)
    volume_score, volume_details = score_volume(indicators)
    price_score, price_details = score_price_position(indicators)
    squeeze_score, squeeze_details = score_squeeze_breakout(indicators)

    total = trend_score + momentum_score + volume_score + price_score + squeeze_score
    overextended = bool(momentum_details.get("overextended", False))

    return ScoreBreakdown(
        trend=round(trend_score, 1),
        momentum=round(momentum_score, 1),
        volume=round(volume_score, 1),
        price_position=round(price_score, 1),
        squeeze_breakout=round(squeeze_score, 1),
        total=round(total, 1),
        wr_pct=round(wr_pct, 1),
        wr_samples=wr_samples,
        adx=round(_safe(indicators.get("adx")), 1),
        v_kat=round(_safe(indicators.get("v_kat")), 2),
        dzl_ok=bool(trend_details.get("perfect_order", False)),
        sqz_ok=bool(squeeze_details.get("squeeze_on", False) or squeeze_details.get("squeeze_breakout", False)),
        ema_distance_pct=round(_safe(indicators.get("ema_distance_pct")), 2),
        overextended=overextended,
        details={
            "trend": trend_details,
            "momentum": momentum_details,
            "volume": volume_details,
            "price_position": price_details,
            "squeeze_breakout": squeeze_details,
            "wr": wr_details,
            "market_regime": {
                "label": market_regime.label,
                "performance_20d": market_regime.performance_20d,
            },
        },
    )
