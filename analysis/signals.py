"""
Sinyal Üretimi (AL / SAT / BEKLE)

Skorlama motorunun çıktısı ve teknik gösterge değerlerine göre
her hisse için alım-satım sinyali üretir.

Fibonacci, mum formasyonları, Elliott Wave, 3 vadeli hedef ve
kural-tabanlı Türkçe yorum entegrasyonunu orkestre eder.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from analysis.market_regime import MarketRegime, should_filter_buy_signals
from analysis.scoring import ScoreBreakdown
from analysis.timeframes import TimeframeSignals
from analysis.fibonacci import FibonacciResult, calculate_fibonacci
from analysis.candle_patterns import CandlePattern, detect_all_patterns, patterns_summary, pattern_bias
from analysis.elliott_wave import ElliottWaveResult, analyze_elliott_wave
from analysis.targets import TargetLevels, calculate_targets
from analysis.commentary import Commentary, generate_commentary
from config import (
    BUY_THRESHOLD,
    SELL_THRESHOLD,
    RSI_OVERBOUGHT,
    RSI_BUY_LOW,
    RSI_BUY_HIGH,
    VOLUME_MULTIPLIER,
)

ATR_STOP_MULTIPLIER = 2.0
ATR_TARGET_MULTIPLIER = 3.0

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """Hisse sinyali — tüm analiz sonuçlarını taşır."""
    symbol: str
    signal: str           # "AL", "SAT", "BEKLE"
    score: float          # 0-100
    score_breakdown: ScoreBreakdown
    price: float
    rsi: float
    trend: str            # "YUKARI", "ASAGI", "YATAY"
    volume_status: str    # "YÜKSEK", "NORMAL", "DÜŞÜK"
    reason: str
    indicators: dict
    # Risk yönetimi (eski)
    entry: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0
    risk_pct: float = 0.0
    reward_pct: float = 0.0
    rr_ratio: float = 0.0
    # Çoklu zaman dilimi
    timeframes: Optional[TimeframeSignals] = None
    # ── Yeni profesyonel analiz alanları ──
    fibonacci: Optional[FibonacciResult] = None
    candle_patterns: list[CandlePattern] = field(default_factory=list)
    candle_bias: str = "NONE"
    elliott_wave: Optional[ElliottWaveResult] = None
    targets: Optional[TargetLevels] = None
    commentary: Optional[Commentary] = None
    summary: str = ""


def _trend_label(indicators: dict) -> str:
    slope = indicators.get("trend_slope", 0)
    if slope > 0.05:
        return "YUKARI"
    elif slope < -0.05:
        return "ASAGI"
    return "YATAY"


def _volume_label(indicators: dict) -> str:
    vol_short = indicators.get("volume_short_avg", 0) or 0
    vol_avg = indicators.get("volume_avg", 0) or 0
    if vol_avg <= 0:
        return "?"
    ratio = vol_short / vol_avg
    if ratio >= VOLUME_MULTIPLIER:
        return "YÜKSEK"
    elif ratio >= 0.8:
        return "NORMAL"
    return "DÜŞÜK"


def _safe(val, default=0.0) -> float:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    return float(val)


def calculate_stop_and_target(indicators: dict, signal: str) -> dict:
    """ATR tabanlı stop-loss ve hedef."""
    close = _safe(indicators.get("close"))
    atr = _safe(indicators.get("atr"))
    swing_low = _safe(indicators.get("swing_low_20"))
    swing_high = _safe(indicators.get("swing_high_20"))

    result = {"entry": close, "stop_loss": 0.0, "target": 0.0,
              "risk_pct": 0.0, "reward_pct": 0.0, "rr_ratio": 0.0}

    if close <= 0 or atr <= 0:
        return result

    if signal == "AL":
        atr_stop = close - ATR_STOP_MULTIPLIER * atr
        stop = max(atr_stop, swing_low * 0.99) if swing_low > 0 else atr_stop
        target = close + ATR_TARGET_MULTIPLIER * atr
        risk, reward = close - stop, target - close
        result.update({
            "stop_loss": round(stop, 2), "target": round(target, 2),
            "risk_pct": round((risk / close) * 100, 2) if close > 0 else 0.0,
            "reward_pct": round((reward / close) * 100, 2) if close > 0 else 0.0,
            "rr_ratio": round(reward / risk, 2) if risk > 0 else 0.0,
        })
    elif signal == "SAT":
        atr_stop = close + ATR_STOP_MULTIPLIER * atr
        stop = min(atr_stop, swing_high * 1.01) if swing_high > 0 else atr_stop
        target = close - ATR_TARGET_MULTIPLIER * atr
        risk, reward = stop - close, close - target
        result.update({
            "stop_loss": round(stop, 2), "target": round(max(0.01, target), 2),
            "risk_pct": round((risk / close) * 100, 2) if close > 0 else 0.0,
            "reward_pct": round((reward / close) * 100, 2) if close > 0 else 0.0,
            "rr_ratio": round(reward / risk, 2) if risk > 0 else 0.0,
        })
    return result


def generate_signal(
    symbol: str,
    indicators: dict,
    score_breakdown: ScoreBreakdown,
    market_regime: MarketRegime,
    df=None,
) -> Signal:
    """
    Hisse için tam sinyal üretir: temel sinyal + fibonacci + mum formasyonları +
    Elliott Wave + 3 vadeli hedef + Türkçe yorum.
    """
    score = score_breakdown.total
    close = _safe(indicators.get("close"))
    rsi = _safe(indicators.get("rsi"))
    sma_short = _safe(indicators.get("sma_short"))
    sma_long = _safe(indicators.get("sma_long"))
    bb_upper = _safe(indicators.get("bb_upper"))
    macd = _safe(indicators.get("macd"))
    macd_signal_val = _safe(indicators.get("macd_signal"))
    vol_short = _safe(indicators.get("volume_short_avg"))
    vol_avg = _safe(indicators.get("volume_avg"))

    trend = _trend_label(indicators)
    vol_status = _volume_label(indicators)

    signal = "BEKLE"
    reason = ""

    # ── SAT kontrolleri ──
    if score <= SELL_THRESHOLD:
        signal = "SAT"
        reason = f"Düşük skor ({score:.0f})"
    elif rsi > RSI_OVERBOUGHT and bb_upper > 0 and close > bb_upper:
        signal = "SAT"
        reason = f"Aşırı alım (RSI={rsi:.0f}) + BB üst band kırıldı"
    elif macd < macd_signal_val and sma_short > 0 and close < sma_short:
        signal = "SAT"
        reason = f"MACD negatif + SMA50 altında"
    # ── AL kontrolleri ──
    elif (
        score >= BUY_THRESHOLD
        and RSI_BUY_LOW <= rsi <= RSI_BUY_HIGH
        and (sma_long <= 0 or close > sma_long)
        and (vol_avg <= 0 or vol_short >= vol_avg * VOLUME_MULTIPLIER)
    ):
        signal = "AL"
        reason = f"Güçlü skor ({score:.0f}) + tüm koşullar sağlandı"
        if should_filter_buy_signals(market_regime):
            signal = "BEKLE"
            reason = f"AL filtresi (düşüş rejimi): skor {score:.0f}"
    # ── BEKLE ──
    else:
        if score >= BUY_THRESHOLD:
            reason = f"Skor yeterli ({score:.0f}) ama bazı koşullar sağlanmadı"
        else:
            reason = f"Skor orta ({score:.0f})"

    # ── Stop / Hedef (eski sistem) ──
    risk_data = calculate_stop_and_target(indicators, signal)

    # ── Çoklu zaman dilimi ──
    tf_signals: Optional[TimeframeSignals] = None
    if df is not None:
        try:
            from analysis.timeframes import calculate_timeframe_signals
            tf_signals = calculate_timeframe_signals(df, signal)
        except Exception as e:
            logger.warning("Zaman dilimi hatası [%s]: %s", symbol, str(e))

    # ── Fibonacci ──
    fib = FibonacciResult()
    if df is not None:
        try:
            fib = calculate_fibonacci(df, close)
        except Exception as e:
            logger.warning("Fibonacci hatası [%s]: %s", symbol, str(e))

    # ── Mum Formasyonları ──
    candles: list[CandlePattern] = []
    c_bias = "NONE"
    if df is not None:
        try:
            candles = detect_all_patterns(df)
            c_bias = pattern_bias(candles)
        except Exception as e:
            logger.warning("Mum formasyon hatası [%s]: %s", symbol, str(e))

    # ── Elliott Wave ──
    ew = ElliottWaveResult()
    if df is not None:
        try:
            ew = analyze_elliott_wave(df)
        except Exception as e:
            logger.warning("Elliott Wave hatası [%s]: %s", symbol, str(e))

    # ── 3 Vadeli Hedefler ──
    tgt = TargetLevels(stop_loss=risk_data["stop_loss"])
    try:
        tgt = calculate_targets(close, _safe(indicators.get("atr")),
                                risk_data["stop_loss"], fib, signal)
    except Exception as e:
        logger.warning("Hedef hesaplama hatası [%s]: %s", symbol, str(e))

    # ── Yorum ──
    comm = Commentary()
    try:
        comm = generate_commentary(
            symbol, signal, score, indicators, fib, candles, ew, tgt,
        )
    except Exception as e:
        logger.warning("Yorum hatası [%s]: %s", symbol, str(e))

    return Signal(
        symbol=symbol,
        signal=signal,
        score=score,
        score_breakdown=score_breakdown,
        price=close,
        rsi=round(rsi, 1),
        trend=trend,
        volume_status=vol_status,
        reason=reason,
        indicators=indicators,
        entry=risk_data["entry"],
        stop_loss=risk_data["stop_loss"],
        target=risk_data["target"],
        risk_pct=risk_data["risk_pct"],
        reward_pct=risk_data["reward_pct"],
        rr_ratio=risk_data["rr_ratio"],
        timeframes=tf_signals,
        fibonacci=fib,
        candle_patterns=candles,
        candle_bias=c_bias,
        elliott_wave=ew,
        targets=tgt,
        commentary=comm,
        summary=comm.summary,
    )


def generate_all_signals(
    all_indicators: dict[str, dict],
    all_scores: dict[str, ScoreBreakdown],
    market_regime: MarketRegime,
) -> list[Signal]:
    signals: list[Signal] = []
    for symbol in all_indicators:
        score = all_scores.get(symbol)
        if score is None:
            continue
        sig = generate_signal(symbol, all_indicators[symbol], score, market_regime)
        signals.append(sig)
    signals.sort(key=lambda s: s.score, reverse=True)
    return signals
