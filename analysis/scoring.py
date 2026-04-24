"""
Skorlama Motoru (0-100 Puan)

Her hisse 5 kategoride puanlanır:
1. Trend Analizi        (25 puan)
2. Momentum Göstergeleri (25 puan)
3. Hacim Analizi        (20 puan)
4. Fiyat Pozisyonu      (15 puan)
5. Piyasa Rejimi Uyumu  (15 puan)
"""

import logging
from dataclasses import dataclass, field

import numpy as np

from analysis.market_regime import MarketRegime
from config import (
    RSI_IDEAL_LOW,
    RSI_IDEAL_HIGH,
    BETA_LOW,
    BETA_HIGH,
    VOLUME_MULTIPLIER,
)

logger = logging.getLogger(__name__)


@dataclass
class ScoreBreakdown:
    """Skor detay dökümü"""
    trend: float = 0.0
    momentum: float = 0.0
    volume: float = 0.0
    price_position: float = 0.0
    market_regime: float = 0.0
    total: float = 0.0
    details: dict = field(default_factory=dict)


def _safe(val) -> float:
    """NaN kontrolü; NaN ise 0 döndürür."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return 0.0
    return float(val)


def score_trend(indicators: dict) -> tuple[float, dict]:
    """
    Trend Analizi (max 25 puan)
    - Fiyat > 50 SMA       → +5
    - Fiyat > 200 SMA      → +5
    - 50 SMA > 200 SMA     → +8 (Golden Cross)
    - Trend eğimi pozitif   → +7
    """
    score = 0.0
    details = {}

    close = _safe(indicators.get("close"))
    sma_short = _safe(indicators.get("sma_short"))
    sma_long = _safe(indicators.get("sma_long"))
    slope = _safe(indicators.get("trend_slope"))

    # Fiyat > 50 SMA
    if sma_short > 0 and close > sma_short:
        score += 5
        details["price_above_sma50"] = True
    else:
        details["price_above_sma50"] = False

    # Fiyat > 200 SMA
    if sma_long > 0 and close > sma_long:
        score += 5
        details["price_above_sma200"] = True
    else:
        details["price_above_sma200"] = False

    # Golden Cross: 50 SMA > 200 SMA
    if sma_short > 0 and sma_long > 0 and sma_short > sma_long:
        score += 8
        details["golden_cross"] = True
    else:
        details["golden_cross"] = False

    # Trend eğimi pozitif (son 20 gün)
    if slope > 0:
        score += min(7, slope * 35)  # Eğime göre kademeli puan
        details["trend_slope_positive"] = True
    else:
        details["trend_slope_positive"] = False

    details["trend_slope_value"] = round(slope, 4)
    return min(25.0, score), details


def score_momentum(indicators: dict) -> tuple[float, dict]:
    """
    Momentum Göstergeleri (max 25 puan)
    - RSI 40-70 arası ideal   → +8
    - RSI > 50                → +4
    - MACD > sinyal hattı     → +6
    - Histogram pozitif + artıyor → +7
    """
    score = 0.0
    details = {}

    rsi = _safe(indicators.get("rsi"))
    macd = _safe(indicators.get("macd"))
    macd_signal = _safe(indicators.get("macd_signal"))
    macd_hist = _safe(indicators.get("macd_hist"))
    macd_hist_prev = _safe(indicators.get("macd_hist_prev"))

    # RSI ideal bölge (40-70)
    if RSI_IDEAL_LOW <= rsi <= RSI_IDEAL_HIGH:
        score += 8
        details["rsi_ideal_zone"] = True
    else:
        details["rsi_ideal_zone"] = False

    # RSI > 50
    if rsi > 50:
        score += 4
        details["rsi_above_50"] = True
    else:
        details["rsi_above_50"] = False

    # MACD sinyal hattı üzerinde
    if macd > macd_signal:
        score += 6
        details["macd_above_signal"] = True
    else:
        details["macd_above_signal"] = False

    # Histogram pozitif ve artıyor
    if macd_hist > 0 and macd_hist > macd_hist_prev:
        score += 7
        details["macd_hist_rising"] = True
    else:
        details["macd_hist_rising"] = False

    details["rsi_value"] = round(rsi, 2)
    return min(25.0, score), details


def score_volume(indicators: dict) -> tuple[float, dict]:
    """
    Hacim Analizi (max 20 puan)
    - Son 5 gün hacmi > 20 günlük ortalama → +10
    - OBV yükseliyor (OBV > OBV SMA)       → +10
    """
    score = 0.0
    details = {}

    vol_short = _safe(indicators.get("volume_short_avg"))
    vol_avg = _safe(indicators.get("volume_avg"))
    obv = _safe(indicators.get("obv"))
    obv_sma = _safe(indicators.get("obv_sma"))

    # Son 5 gün hacmi > 20 günlük ortalama
    if vol_avg > 0 and vol_short > vol_avg:
        ratio = vol_short / vol_avg
        score += min(10, ratio * 5)  # Orana göre kademeli puan
        details["volume_above_avg"] = True
        details["volume_ratio"] = round(ratio, 2)
    else:
        details["volume_above_avg"] = False
        details["volume_ratio"] = round(vol_short / vol_avg, 2) if vol_avg > 0 else 0

    # OBV yükseliyor
    if obv > obv_sma:
        score += 10
        details["obv_rising"] = True
    else:
        details["obv_rising"] = False

    return min(20.0, score), details


def score_price_position(indicators: dict) -> tuple[float, dict]:
    """
    Destek/Direnç & Fiyat Pozisyonu (max 15 puan)
    - 52 hafta pozisyonu: üst %70'te → +8
    - Bollinger orta bantın üzerinde  → +7
    """
    score = 0.0
    details = {}

    week52_pos = _safe(indicators.get("week52_position"))
    close = _safe(indicators.get("close"))
    bb_middle = _safe(indicators.get("bb_middle"))

    # 52 hafta pozisyonu: alt %30'da DEĞİL (yani > 0.3)
    # Üst %30'da bonus: > 0.7
    if week52_pos > 0.3:
        if week52_pos > 0.7:
            score += 8
        else:
            score += 4  # Orta bölge: kısmi puan
        details["52w_position_ok"] = True
    else:
        details["52w_position_ok"] = False

    details["52w_position"] = round(week52_pos, 2)

    # Bollinger orta bantın üzerinde
    if bb_middle > 0 and close > bb_middle:
        score += 7
        details["above_bb_middle"] = True
    else:
        details["above_bb_middle"] = False

    return min(15.0, score), details


def score_market_regime_fit(
    indicators: dict,
    market_regime: MarketRegime,
) -> tuple[float, dict]:
    """
    Piyasa Rejimi Uyumu (max 15 puan)
    - XU100 son 20 günde pozitif performans → +8
    - Hissenin beta'sı 0.5-1.5 arasında     → +7
    """
    score = 0.0
    details = {}

    # Endeks performansı
    if market_regime.performance_20d > 0:
        score += 8
        details["market_positive"] = True
    else:
        details["market_positive"] = False

    details["market_perf_20d"] = market_regime.performance_20d

    # Beta kontrolü
    beta = _safe(indicators.get("beta", 1.0))
    if BETA_LOW <= beta <= BETA_HIGH:
        score += 7
        details["beta_ok"] = True
    else:
        details["beta_ok"] = False

    details["beta_value"] = round(beta, 2)

    return min(15.0, score), details


def calculate_score(
    indicators: dict,
    market_regime: MarketRegime,
) -> ScoreBreakdown:
    """
    Hissenin toplam skorunu hesaplar (0-100).
    Tüm 5 kategoriyi puanlar ve toplar.
    """
    trend_score, trend_details = score_trend(indicators)
    momentum_score, momentum_details = score_momentum(indicators)
    volume_score, volume_details = score_volume(indicators)
    price_score, price_details = score_price_position(indicators)
    regime_score, regime_details = score_market_regime_fit(indicators, market_regime)

    total = trend_score + momentum_score + volume_score + price_score + regime_score

    return ScoreBreakdown(
        trend=round(trend_score, 1),
        momentum=round(momentum_score, 1),
        volume=round(volume_score, 1),
        price_position=round(price_score, 1),
        market_regime=round(regime_score, 1),
        total=round(min(100.0, total), 1),
        details={
            "trend": trend_details,
            "momentum": momentum_details,
            "volume": volume_details,
            "price_position": price_details,
            "market_regime": regime_details,
        },
    )
