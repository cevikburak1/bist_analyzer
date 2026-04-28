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
from analysis.anka_v2 import AnkaV2Result, calculate_anka_v2
from analysis.amd_model import AmdModelResult, calculate_amd_model
from analysis.cup_handle import CupHandleQuality, calculate_cup_handle_quality
from analysis.horizon_guidance import (
    TechnicalHorizonGuidance,
    build_technical_horizon_guidance,
)
from analysis.horizon_scoring import (
    HorizonScoreSet,
)
from config import (
    BUY_THRESHOLD,
    STRONG_BUY_THRESHOLD,
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
    score: float          # additive Morpheus skoru
    score_breakdown: ScoreBreakdown
    price: float
    rsi: float
    trend: str            # "YUKARI", "ASAGI", "YATAY"
    volume_status: str    # "YÜKSEK", "NORMAL", "DÜŞÜK"
    reason: str
    indicators: dict
    action: str = ""      # Morpheus tablo aksiyonu: AL / GÜÇLÜ AL / BEKLE / SAT / KAR AL
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
    # Vade bazlı tutma önerisi (kısa/orta/uzun) + gerekçe
    horizon_guidance: Optional[TechnicalHorizonGuidance] = None
    reason_factors: list[str] = field(default_factory=list)
    # Vade bazlı skorlar ve kararlar (short/swing/medium/long)
    horizon_scores: Optional[HorizonScoreSet] = None
    # ANKA v2.0 sentez analizi
    anka_v2: Optional[AnkaV2Result] = None
    amd_model: Optional[AmdModelResult] = None
    tradingview_snapshot: Optional[dict] = None
    cup_handle_quality: Optional[CupHandleQuality] = None


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


def _target_direction(indicators: dict, signal: str) -> str:
    if signal == "SAT":
        return "SHORT"
    if signal == "AL":
        return "LONG"

    close = _safe(indicators.get("close"))
    ema200 = _safe(indicators.get("ema200"))
    slope = _safe(indicators.get("trend_slope"))
    plus_di = _safe(indicators.get("plus_di"))
    minus_di = _safe(indicators.get("minus_di"))
    if (ema200 > 0 and close >= ema200) or slope >= 0 or plus_di >= minus_di:
        return "LONG"
    return "SHORT"


def _effective_atr(close: float, atr: float, swing_low: float, swing_high: float) -> float:
    if atr > 0:
        return atr
    if swing_high > swing_low > 0:
        return max((swing_high - swing_low) / 4, close * 0.01)
    if close > 0:
        return close * 0.03
    return 0.0


def calculate_stop_and_target(indicators: dict, signal: str) -> dict:
    """ATR tabanlı stop-loss ve hedef; tüm aksiyonlarda gösterge seviye üretir."""
    close = _safe(indicators.get("close"))
    swing_low = _safe(indicators.get("swing_low_20"))
    swing_high = _safe(indicators.get("swing_high_20"))
    atr = _effective_atr(close, _safe(indicators.get("atr")), swing_low, swing_high)
    direction = _target_direction(indicators, signal)

    result = {"entry": close, "stop_loss": 0.0, "target": 0.0,
              "risk_pct": 0.0, "reward_pct": 0.0, "rr_ratio": 0.0,
              "direction": direction, "atr": atr}

    if close <= 0 or atr <= 0:
        return result

    if direction == "LONG":
        atr_stop = close - ATR_STOP_MULTIPLIER * atr
        stop = max(atr_stop, swing_low * 0.99) if swing_low > 0 else atr_stop
        stop = min(stop, close * 0.98)
        target = close + ATR_TARGET_MULTIPLIER * atr
        risk, reward = close - stop, target - close
        result.update({
            "stop_loss": round(stop, 2), "target": round(target, 2),
            "risk_pct": round((risk / close) * 100, 2) if close > 0 else 0.0,
            "reward_pct": round((reward / close) * 100, 2) if close > 0 else 0.0,
            "rr_ratio": round(reward / risk, 2) if risk > 0 else 0.0,
        })
    else:
        atr_stop = close + ATR_STOP_MULTIPLIER * atr
        stop = min(atr_stop, swing_high * 1.01) if swing_high > 0 else atr_stop
        stop = max(stop, close * 1.02)
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
    intraday_df=None,
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
    reason_factors: list[str] = []

    score_buy_ok = score >= BUY_THRESHOLD
    rsi_buy_ok = RSI_BUY_LOW <= rsi <= RSI_BUY_HIGH
    above_ema200 = _safe(indicators.get("ema200")) <= 0 or close > _safe(indicators.get("ema200"))
    volume_ok = _safe(indicators.get("v_kat")) >= 1.0 or vol_avg <= 0 or vol_short >= vol_avg * VOLUME_MULTIPLIER
    overextended = bool(score_breakdown.overextended)
    strong_confirmation = (
        score >= STRONG_BUY_THRESHOLD
        and score_breakdown.wr_pct >= 70
        and score_breakdown.adx >= 25
        and score_breakdown.v_kat >= 1.0
    )
    action = "BEKLE"

    # ── SAT kontrolleri ──
    if score <= SELL_THRESHOLD:
        signal = "SAT"
        action = "SAT"
        reason = f"Düşük Morpheus skor ({score:.0f} ≤ {SELL_THRESHOLD}) - SAT eşiği aşıldı"
        reason_factors.append(f"Skor {score:.0f} ≤ SAT eşiği {SELL_THRESHOLD}")
    elif rsi > RSI_OVERBOUGHT and bb_upper > 0 and close > bb_upper:
        signal = "BEKLE"
        action = "KAR AL"
        reason = (
            f"Aşırı alım: RSI {rsi:.0f} > {RSI_OVERBOUGHT} ve fiyat Bollinger üst "
            f"band {bb_upper:.2f} üzerinde - kar alma/geri çekilme riski"
        )
        reason_factors.append(f"RSI {rsi:.0f} > {RSI_OVERBOUGHT}")
        reason_factors.append("BB üst band kırılımı")
    elif overextended and score_buy_ok:
        signal = "BEKLE"
        action = "KAR AL"
        reason = (
            f"Skor güçlü ({score:.0f}) ancak fiyat EMA13'ten "
            f"%{score_breakdown.ema_distance_pct:.1f} uzak - lastik fazla gerilmiş"
        )
        reason_factors.append(
            f"EMA13 uzaklığı %{score_breakdown.ema_distance_pct:.1f} > aşırı bölge"
        )
    elif macd < macd_signal_val and sma_short > 0 and close < sma_short:
        signal = "SAT"
        action = "SAT"
        reason = (
            "MACD signal'in altında ve fiyat SMA50 altında - "
            "kısa/orta vade trend bozulması"
        )
        reason_factors.append("MACD < signal")
        reason_factors.append("Fiyat SMA50 altında")
    # ── AL kontrolleri ──
    elif score_buy_ok and rsi_buy_ok and above_ema200 and volume_ok:
        signal = "AL"
        action = "GÜÇLÜ AL" if strong_confirmation else "AL"
        reason = (
            f"Morpheus skor güçlü ({score:.0f} ≥ {BUY_THRESHOLD}), RSI sağlıklı bantta, "
            "fiyat EMA200 üstünde ve hacim teyitli - AL koşulları sağlandı"
        )
        reason_factors.extend([
            f"Skor {score:.0f} ≥ AL eşiği {BUY_THRESHOLD}",
            f"RSI {rsi:.0f} ∈ [{RSI_BUY_LOW},{RSI_BUY_HIGH}]",
            "Fiyat EMA200 üstünde",
            "Hacim AL eşiğini karşılıyor",
        ])
        if strong_confirmation:
            reason_factors.append("WR%, ADX ve V_KAT güçlü teyit veriyor")
        if should_filter_buy_signals(market_regime):
            signal = "BEKLE"
            action = "BEKLE"
            reason = (
                f"AL koşulları sağlandı (skor {score:.0f}) ancak piyasa rejimi "
                f"'{market_regime.label}' - düşüş rejiminde AL filtreleniyor"
            )
            reason_factors.append(f"Piyasa rejimi filtresi: {market_regime.label}")
    # ── BEKLE ──
    else:
        action = "BEKLE"
        if score_buy_ok:
            missing: list[str] = []
            if not rsi_buy_ok:
                missing.append(f"RSI {rsi:.0f} alım bandı [{RSI_BUY_LOW},{RSI_BUY_HIGH}] dışında")
            if not above_ema200:
                missing.append("fiyat EMA200 altında")
            if not volume_ok:
                missing.append("hacim AL eşiğini karşılamıyor")
            reason = (
                f"Skor yeterli ({score:.0f}) ama AL için eksik: " + ", ".join(missing)
            )
            reason_factors.extend(missing)
        else:
            reason = (
                f"Morpheus skor orta ({score:.0f}) - AL eşiği {BUY_THRESHOLD}, "
                f"SAT eşiği {SELL_THRESHOLD}; her iki tarafa da net sinyal yok"
            )
            reason_factors.append(f"Skor {score:.0f} aralığı [{SELL_THRESHOLD+1},{BUY_THRESHOLD-1}]")

    # ── Stop / Hedef ──
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

    # ── ANKA v2.0 sentez motoru ──
    anka_v2: Optional[AnkaV2Result] = None
    if df is not None:
        try:
            anka_v2 = calculate_anka_v2(
                df,
                base_score=score,
                base_signal=signal,
                fibonacci=fib,
            )
        except Exception as e:
            logger.warning("ANKA v2.0 hatası [%s]: %s", symbol, str(e))

    # ── Cup and Handle Quality ──
    cup_handle_quality: Optional[CupHandleQuality] = None
    if df is not None:
        try:
            cup_handle_quality = calculate_cup_handle_quality(df)
        except Exception as e:
            logger.warning("Cup and Handle hatası [%s]: %s", symbol, str(e))

    # ── AMD Model (intraday Power of 3) ──
    amd_model: Optional[AmdModelResult] = None
    if intraday_df is not None:
        try:
            amd_model = calculate_amd_model(intraday_df)
        except Exception as e:
            logger.warning("AMD model hatası [%s]: %s", symbol, str(e))

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
        target_signal = signal if signal in {"AL", "SAT"} else (
            "AL" if risk_data.get("direction") == "LONG" else "SAT"
        )
        tgt = calculate_targets(close, _safe(risk_data.get("atr")),
                                risk_data["stop_loss"], fib, target_signal)
    except Exception as e:
        logger.warning("Hedef hesaplama hatası [%s]: %s", symbol, str(e))

    # ── Vade bazlı tutma önerisi ──
    horizon = None
    try:
        horizon = build_technical_horizon_guidance(
            tf_signals, tgt, indicators, score, market_regime,
        )
    except Exception as e:
        logger.warning("Vade önerisi hatası [%s]: %s", symbol, str(e))

    # Eski vade bazlı skor motoru 0-100 kategorilere dayanıyordu; ana çıktı yalnızca Morpheus skoru taşır.
    horizon_scores: Optional[HorizonScoreSet] = None

    # ── Yorum ──
    comm = Commentary()
    try:
        comm = generate_commentary(
            symbol, signal, score, indicators, fib, candles, ew, tgt,
            timeframes=tf_signals, horizon=horizon,
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
        action=action,
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
        horizon_guidance=horizon,
        reason_factors=reason_factors,
        horizon_scores=horizon_scores,
        anka_v2=anka_v2,
        amd_model=amd_model,
        tradingview_snapshot=indicators.get("tradingview_snapshot"),
        cup_handle_quality=cup_handle_quality,
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
