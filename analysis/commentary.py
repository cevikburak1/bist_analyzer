"""
Kural-Tabanlı Türkçe Yorum Motoru

Tüm göstergeleri sentezleyip profesyonel Türkçe yorum üretir.
API gerektirmez — tamamen deterministik, anlık.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from analysis.fibonacci import FibonacciResult
from analysis.candle_patterns import CandlePattern, pattern_bias, patterns_summary
from analysis.elliott_wave import ElliottWaveResult
from analysis.targets import TargetLevels
from analysis.timeframes import TimeframeSignals
from analysis.horizon_guidance import TechnicalHorizonGuidance
from config import SELL_THRESHOLD, STRONG_BUY_THRESHOLD

logger = logging.getLogger(__name__)


@dataclass
class Commentary:
    summary: str = ""           # "GÜÇLÜ AL", "ZAYIF SAT" gibi tek satır
    paragraph: str = ""         # 4-6 cümlelik tam yorum
    key_points: list = field(default_factory=list)
    risks: list = field(default_factory=list)


def _signal_strength(score: float, signal: str) -> str:
    """Additif Morpheus eşikleriyle uyumlu sinyal gücü etiketi."""
    if signal == "AL":
        if score >= STRONG_BUY_THRESHOLD:
            return "GÜÇLÜ AL"
        return "AL"
    elif signal == "SAT":
        if score <= SELL_THRESHOLD * 0.5:
            return "GÜÇLÜ SAT"
        return "SAT"
    return "BEKLE"


def _format_price(p: float) -> str:
    if p >= 1000:
        return f"{p:,.0f}"
    if p >= 10:
        return f"{p:.2f}"
    return f"{p:.3f}"


def _trend_sentence(indicators: dict) -> str:
    """Trend cümlesi."""
    close = indicators.get("close", 0)
    sma50 = indicators.get("sma_short", 0)
    sma200 = indicators.get("sma_long", 0)
    slope = indicators.get("trend_slope", 0)

    parts = []
    above_50 = close > sma50 > 0
    above_200 = close > sma200 > 0
    golden = sma50 > sma200 > 0

    if above_50 and above_200:
        parts.append("fiyat hem 50 hem 200 SMA üzerinde")
    elif above_50:
        parts.append("fiyat 50 SMA üzerinde ama 200 SMA altında")
    elif above_200:
        parts.append("fiyat 200 SMA üzerinde ama 50 SMA altında")
    else:
        parts.append("fiyat her iki SMA altında")

    if golden:
        parts.append("golden cross aktif")
    elif sma50 > 0 and sma200 > 0 and sma50 < sma200:
        parts.append("death cross mevcut")

    if slope > 0.1:
        trend_word = "güçlü yükseliş"
    elif slope > 0:
        trend_word = "hafif yükseliş"
    elif slope < -0.1:
        trend_word = "güçlü düşüş"
    elif slope < 0:
        trend_word = "hafif düşüş"
    else:
        trend_word = "yatay"

    return f"{trend_word} trendinde; {', '.join(parts)}."


def _momentum_sentence(indicators: dict) -> str:
    """RSI ve MACD cümlesi."""
    rsi = indicators.get("rsi", 50)
    macd_hist = indicators.get("macd_hist", 0)
    macd_hist_prev = indicators.get("macd_hist_prev", 0)

    if 40 <= rsi <= 60:
        rsi_text = f"RSI {rsi:.0f} ile nötr bölgede"
    elif 30 <= rsi < 40:
        rsi_text = f"RSI {rsi:.0f} ile aşırı satım bölgesine yakın"
    elif rsi < 30:
        rsi_text = f"RSI {rsi:.0f} ile aşırı satım bölgesinde"
    elif 60 < rsi <= 70:
        rsi_text = f"RSI {rsi:.0f} ile sağlıklı momentum bölgesinde"
    elif rsi > 75:
        rsi_text = f"RSI {rsi:.0f} ile aşırı alım bölgesinde — dikkat"
    else:
        rsi_text = f"RSI {rsi:.0f} ile alım bölgesinde"

    if macd_hist > 0 and macd_hist > macd_hist_prev:
        macd_text = "MACD histogramı pozitif ve genişliyor"
    elif macd_hist > 0:
        macd_text = "MACD histogramı pozitif ama zayıflıyor"
    elif macd_hist < 0 and macd_hist < macd_hist_prev:
        macd_text = "MACD histogramı negatif ve derinleşiyor"
    elif macd_hist < 0:
        macd_text = "MACD histogramı negatif ama toparlanıyor"
    else:
        macd_text = "MACD nötr"

    return f"{rsi_text}, {macd_text}."


def _volume_sentence(indicators: dict) -> str:
    """Hacim cümlesi."""
    vol_short = indicators.get("volume_short_avg", 0) or 0
    vol_avg = indicators.get("volume_avg", 0) or 0

    if vol_avg <= 0:
        return ""

    ratio = vol_short / vol_avg
    if ratio >= 1.5:
        return f"Hacim 5 günlük ortalama 20 günlüğün {ratio:.1f} katı — güçlü kurumsal ilgi."
    if ratio >= 1.2:
        return f"Hacim ortalamanın {ratio:.1f} katı — artan ilgi."
    if ratio >= 0.8:
        return "Hacim normal seviyelerde."
    return "Hacim ortalamanın altında — düşük katılım."


def _candle_sentence(patterns: list[CandlePattern]) -> str:
    """Mum formasyonu cümlesi."""
    if not patterns:
        return ""

    bias = pattern_bias(patterns)
    names = [p.name for p in patterns[:3]]
    joined = ", ".join(names)

    if bias == "BULLISH":
        return f"Yükseliş formasyonu tespit edildi: {joined}."
    if bias == "BEARISH":
        return f"Düşüş formasyonu tespit edildi: {joined}."
    if bias == "MIXED":
        return f"Karışık formasyon sinyalleri: {joined}."
    return f"Nötr formasyon: {joined}."


def _elliott_sentence(ew: ElliottWaveResult) -> str:
    """Elliott Wave cümlesi."""
    if ew.phase == "UNCERTAIN" or ew.current_wave == "?":
        return ""

    conf_text = {"HIGH": "yüksek", "MEDIUM": "orta", "LOW": "düşük"}.get(ew.confidence, "düşük")

    if ew.phase == "IMPULSE":
        return f"Elliott Wave {ew.current_wave} olası ({conf_text} güven). {ew.next_expected}."
    elif ew.phase == "CORRECTION":
        return f"Elliott dalga {ew.current_wave} düzeltme fazında ({conf_text} güven). {ew.next_expected}."

    return ""


def _fib_sentence(fib: FibonacciResult, close: float) -> str:
    """Fibonacci cümlesi."""
    if fib.nearest_support <= 0 and fib.nearest_resistance <= 0:
        return ""

    parts = []
    if fib.nearest_support > 0:
        pct = ((close - fib.nearest_support) / close) * 100
        parts.append(f"Fib destek {_format_price(fib.nearest_support)} (-%{pct:.1f})")
    if fib.nearest_resistance > 0:
        pct = ((fib.nearest_resistance - close) / close) * 100
        parts.append(f"direnç {_format_price(fib.nearest_resistance)} (+%{pct:.1f})")

    zone = fib.current_zone if fib.current_zone else ""
    zone_part = f" Fiyat {zone}." if zone else ""

    return f"Fibonacci: {', '.join(parts)}.{zone_part}"


def _targets_sentence(targets: TargetLevels, close: float) -> str:
    """Hedef fiyat cümlesi."""
    if targets.short_target <= 0:
        return ""

    return (
        f"Hedefler: Kısa {_format_price(targets.short_target)} "
        f"(+%{targets.short_reward_pct:.1f}), "
        f"Orta {_format_price(targets.medium_target)} "
        f"(+%{targets.medium_reward_pct:.1f}), "
        f"Uzun {_format_price(targets.long_target)} "
        f"(+%{targets.long_reward_pct:.1f})."
    )


def _build_risks(
    indicators: dict,
    fib: FibonacciResult,
    ew: ElliottWaveResult,
    patterns: list[CandlePattern],
) -> list[str]:
    """Risk uyarıları listesi."""
    risks = []
    rsi = indicators.get("rsi", 50)

    if rsi > 70:
        risks.append(f"RSI {rsi:.0f} ile aşırı alım bölgesinde — geri çekilme riski")
    if rsi < 30:
        risks.append(f"RSI {rsi:.0f} ile aşırı satım — dip bölgesi ama yakalama riski")

    sma50 = indicators.get("sma_short", 0)
    sma200 = indicators.get("sma_long", 0)
    if sma50 > 0 and sma200 > 0 and sma50 < sma200:
        risks.append("Death cross aktif — uzun vadeli trend olumsuz")

    vol_short = indicators.get("volume_short_avg", 0) or 0
    vol_avg = indicators.get("volume_avg", 0) or 0
    if vol_avg > 0 and vol_short / vol_avg < 0.7:
        risks.append("Düşük hacim — fiyat hareketinin sürdürülebilirliği belirsiz")

    bearish_patterns = [p for p in patterns if p.direction == "BEARISH"]
    if bearish_patterns:
        risks.append(f"Düşüş formasyonu: {bearish_patterns[0].name}")

    if ew.phase == "IMPULSE" and ew.current_wave == "5":
        risks.append("Elliott Wave 5 sonu — düzeltme başlayabilir")

    return risks


def _timeframe_alignment_sentence(tf: Optional[TimeframeSignals]) -> str:
    """Zaman dilimi sinyallerinin hizalanmasını cümleye çevir."""
    if tf is None:
        return ""
    parts: list[str] = []
    parts.append(f"günlük {tf.daily}")
    if tf.weekly:
        parts.append(f"haftalık {tf.weekly}")
    if tf.monthly:
        parts.append(f"aylık {tf.monthly}")
    if tf.yearly:
        parts.append(f"yıllık {tf.yearly}")
    if not parts:
        return ""

    signals = [tf.daily, tf.weekly, tf.monthly, tf.yearly]
    non_empty = [s for s in signals if s]
    if not non_empty:
        return ""

    distinct = set(non_empty)
    if len(distinct) == 1:
        verdict = next(iter(distinct))
        if verdict == "AL":
            tone = "tüm zaman dilimleri AL ile hizalı - güçlü teyit"
        elif verdict == "SAT":
            tone = "tüm zaman dilimleri SAT ile hizalı - geniş tabanlı zayıflık"
        else:
            tone = "tüm zaman dilimleri BEKLE - belirsizlik"
    else:
        tone = "zaman dilimleri arasında uyuşmazlık var - vade bazlı planlama gerek"
    return f"Zaman dilimi tablosu: {', '.join(parts)}; {tone}."


def _horizon_sentence(horizon: Optional[TechnicalHorizonGuidance]) -> str:
    if horizon is None:
        return ""
    return (
        f"Vade önerileri → Kısa: {horizon.short.label} ({horizon.short.verdict}); "
        f"Orta: {horizon.medium.label} ({horizon.medium.verdict}); "
        f"Uzun: {horizon.long.label} ({horizon.long.verdict})."
    )


def generate_commentary(
    symbol: str,
    signal: str,
    score: float,
    indicators: dict,
    fib: FibonacciResult,
    patterns: list[CandlePattern],
    ew: ElliottWaveResult,
    targets: TargetLevels,
    *,
    timeframes: Optional[TimeframeSignals] = None,
    horizon: Optional[TechnicalHorizonGuidance] = None,
) -> Commentary:
    """
    Tüm göstergeleri sentezleyip profesyonel Türkçe yorum üretir.
    """
    close = indicators.get("close", 0)
    strength = _signal_strength(score, signal)

    # Paragraf cümlelerini topla
    sentences = []
    sentences.append(f"{symbol} {_trend_sentence(indicators)}")
    sentences.append(_momentum_sentence(indicators))

    vol_s = _volume_sentence(indicators)
    if vol_s:
        sentences.append(vol_s)

    candle_s = _candle_sentence(patterns)
    if candle_s:
        sentences.append(candle_s)

    ew_s = _elliott_sentence(ew)
    if ew_s:
        sentences.append(ew_s)

    fib_s = _fib_sentence(fib, close)
    if fib_s:
        sentences.append(fib_s)

    if signal in ("AL", "SAT"):
        targets_s = _targets_sentence(targets, close)
        if targets_s:
            sentences.append(targets_s)

    tf_s = _timeframe_alignment_sentence(timeframes)
    if tf_s:
        sentences.append(tf_s)

    horizon_s = _horizon_sentence(horizon)
    if horizon_s:
        sentences.append(horizon_s)

    paragraph = " ".join(sentences)

    # Key points
    key_points = []
    key_points.append(f"Morpheus skoru: {score:.0f} (additif) → {strength}")
    if targets.stop_loss > 0:
        key_points.append(f"Stop Loss: {_format_price(targets.stop_loss)}")
    if targets.short_target > 0:
        key_points.append(
            f"Kısa hedef: {_format_price(targets.short_target)} (R/R {targets.short_rr:.1f})"
        )
    if targets.medium_target > 0:
        key_points.append(
            f"Orta hedef: {_format_price(targets.medium_target)} (R/R {targets.medium_rr:.1f})"
        )
    if fib.nearest_support > 0:
        key_points.append(f"Fib destek: {_format_price(fib.nearest_support)}")
    if patterns:
        key_points.append(f"Mum: {patterns_summary(patterns)}")
    if ew.current_wave != "?":
        key_points.append(f"Elliott: Wave {ew.current_wave} ({ew.confidence.lower()})")

    risks = _build_risks(indicators, fib, ew, patterns)

    return Commentary(
        summary=strength,
        paragraph=paragraph,
        key_points=key_points,
        risks=risks,
    )
