"""
Elliott Wave Dalga Sayımı (Heuristik)

ZigZag tabanlı swing noktalarından muhtemel Elliott Wave yapısını çıkarır.
Not: EW kesin bir bilim değildir — tüm sonuçlar "tahmin" niteliğindedir.
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ElliottWaveResult:
    current_wave: str = "?"       # "1","2","3","4","5","A","B","C","?"
    phase: str = "UNCERTAIN"      # "IMPULSE", "CORRECTION", "UNCERTAIN"
    confidence: str = "LOW"       # "HIGH", "MEDIUM", "LOW"
    next_expected: str = ""       # Açıklama metni
    wave_count: int = 0           # Toplam tespit edilen dalga sayısı


def find_zigzag_points(
    df: pd.DataFrame,
    threshold_pct: float = 5.0,
) -> list[tuple[int, float, str]]:
    """
    Yüzde eşik bazlı ZigZag noktalarını bulur.

    Returns: [(index, price, "HIGH"/"LOW"), ...]
    """
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    n = len(close)

    if n < 20:
        return []

    threshold = threshold_pct / 100.0
    points: list[tuple[int, float, str]] = []

    last_type = ""
    last_idx = 0
    last_val = close[0]

    # İlk yönü belirle
    for i in range(1, min(20, n)):
        if high[i] > last_val * (1 + threshold):
            points.append((0, float(low[0]), "LOW"))
            last_type = "LOW"
            last_val = float(low[0])
            break
        elif low[i] < last_val * (1 - threshold):
            points.append((0, float(high[0]), "HIGH"))
            last_type = "HIGH"
            last_val = float(high[0])
            break

    if not points:
        return []

    for i in range(1, n):
        if last_type == "LOW":
            if high[i] > last_val * (1 + threshold):
                # Arada daha düşük bir low var mı kontrol et
                segment_low_idx = last_idx + int(np.argmin(low[last_idx:i + 1]))
                if segment_low_idx != last_idx:
                    points[-1] = (segment_low_idx, float(low[segment_low_idx]), "LOW")

                points.append((i, float(high[i]), "HIGH"))
                last_type = "HIGH"
                last_idx = i
                last_val = float(high[i])
            elif low[i] < points[-1][1]:
                points[-1] = (i, float(low[i]), "LOW")
                last_val = float(low[i])
                last_idx = i

        elif last_type == "HIGH":
            if low[i] < last_val * (1 - threshold):
                segment_high_idx = last_idx + int(np.argmax(high[last_idx:i + 1]))
                if segment_high_idx != last_idx:
                    points[-1] = (segment_high_idx, float(high[segment_high_idx]), "HIGH")

                points.append((i, float(low[i]), "LOW"))
                last_type = "LOW"
                last_idx = i
                last_val = float(low[i])
            elif high[i] > points[-1][1]:
                points[-1] = (i, float(high[i]), "HIGH")
                last_val = float(high[i])
                last_idx = i

    return points


def _classify_impulse(waves: list[tuple[int, float, str]]) -> ElliottWaveResult:
    """
    Son swing noktalarından impulse (5 dalga) yapısını kontrol eder.

    Kurallar (basitleştirilmiş):
    - Wave 2, Wave 1'in başlangıcının altına inmez
    - Wave 3 en kısa dalga olamaz
    - Wave 4, Wave 1'in tepesiyle örtüşmez (ideal)
    """
    if len(waves) < 6:
        return ElliottWaveResult()

    # Son 6 nokta: W0(start), W1(peak), W2(trough), W3(peak), W4(trough), W5(peak)
    pts = waves[-6:]

    # Yükselen impulse kontrolü: LOW-HIGH-LOW-HIGH-LOW-HIGH deseni
    types = [p[2] for p in pts]
    is_bullish = types == ["LOW", "HIGH", "LOW", "HIGH", "LOW", "HIGH"]
    is_bearish = types == ["HIGH", "LOW", "HIGH", "LOW", "HIGH", "LOW"]

    if is_bullish:
        w0, w1, w2, w3, w4, w5 = [p[1] for p in pts]
        wave1 = w1 - w0
        wave2_retrace = w1 - w2
        wave3 = w3 - w2
        wave4_retrace = w3 - w4
        wave5 = w5 - w4

        confidence = "LOW"
        violations = 0

        # Kural 1: Wave 2, başlangıcın altına inmez
        if w2 > w0:
            confidence = "MEDIUM"
        else:
            violations += 1

        # Kural 2: Wave 3 en kısa olmamalı
        if wave3 >= wave1 and wave3 >= wave5:
            if confidence == "MEDIUM":
                confidence = "HIGH"
        else:
            violations += 1

        # Kural 3: Wave 4, Wave 1 tepesiyle örtüşmemeli
        if w4 > w1:
            pass  # İdeal
        else:
            violations += 1

        if violations >= 2:
            return ElliottWaveResult(
                current_wave="?", phase="UNCERTAIN", confidence="LOW",
                next_expected="Dalga yapısı belirsiz", wave_count=len(waves),
            )

        # Mevcut pozisyon: Wave 5 tamamlanmış mı?
        current_price = w5
        if wave5 > 0 and w5 > w3:
            return ElliottWaveResult(
                current_wave="5",
                phase="IMPULSE",
                confidence=confidence,
                next_expected="Wave 5 tamamlanıyor olabilir, düzeltme (ABC) bekleniyor",
                wave_count=len(waves),
            )
        else:
            return ElliottWaveResult(
                current_wave="5",
                phase="IMPULSE",
                confidence=confidence,
                next_expected="Wave 5 devam ediyor, hedef Wave 3 zirvesi üzeri",
                wave_count=len(waves),
            )

    if is_bearish:
        w0, w1, w2, w3, w4, w5 = [p[1] for p in pts]
        return ElliottWaveResult(
            current_wave="5",
            phase="IMPULSE",
            confidence="MEDIUM",
            next_expected="Düşüş impulse devam ediyor, düzeltme bekleniyor",
            wave_count=len(waves),
        )

    return ElliottWaveResult()


def _classify_correction(waves: list[tuple[int, float, str]]) -> ElliottWaveResult:
    """Son 4 noktadan ABC düzeltme yapısı kontrol eder."""
    if len(waves) < 4:
        return ElliottWaveResult()

    pts = waves[-4:]
    types = [p[2] for p in pts]

    # ABC düşüş düzeltmesi: HIGH-LOW-HIGH-LOW
    if types == ["HIGH", "LOW", "HIGH", "LOW"]:
        a_start, a_end, b_end, c_end = [p[1] for p in pts]
        wave_a = a_start - a_end
        wave_b_retrace = b_end - a_end
        wave_c = b_end - c_end

        if wave_b_retrace < wave_a and wave_c > 0:
            confidence = "MEDIUM" if wave_c >= wave_a * 0.6 else "LOW"
            return ElliottWaveResult(
                current_wave="C",
                phase="CORRECTION",
                confidence=confidence,
                next_expected="ABC düzeltme tamamlanıyor olabilir, yeni impulse başlayabilir",
                wave_count=len(waves),
            )

    # ABC yükseliş düzeltmesi: LOW-HIGH-LOW-HIGH
    if types == ["LOW", "HIGH", "LOW", "HIGH"]:
        return ElliottWaveResult(
            current_wave="C",
            phase="CORRECTION",
            confidence="MEDIUM",
            next_expected="Yükseliş düzeltmesi tamamlanıyor, düşüş devam edebilir",
            wave_count=len(waves),
        )

    return ElliottWaveResult()


def _simple_wave_position(waves: list[tuple[int, float, str]]) -> ElliottWaveResult:
    """Yetersiz veri olduğunda basit dalga tahmini."""
    if len(waves) < 3:
        return ElliottWaveResult(
            current_wave="?", phase="UNCERTAIN", confidence="LOW",
            next_expected="Yeterli swing noktası yok", wave_count=len(waves),
        )

    last = waves[-1]
    prev = waves[-2]

    if last[2] == "HIGH" and last[1] > prev[1]:
        return ElliottWaveResult(
            current_wave="3?",
            phase="IMPULSE",
            confidence="LOW",
            next_expected="Yükseliş dalgası devam ediyor (muhtemel Wave 3)",
            wave_count=len(waves),
        )
    elif last[2] == "LOW" and last[1] < prev[1]:
        return ElliottWaveResult(
            current_wave="A?",
            phase="CORRECTION",
            confidence="LOW",
            next_expected="Düzeltme dalgası devam ediyor (muhtemel Wave A)",
            wave_count=len(waves),
        )

    return ElliottWaveResult(
        current_wave="?", phase="UNCERTAIN", confidence="LOW",
        next_expected="Dalga yapısı belirsiz", wave_count=len(waves),
    )


def analyze_elliott_wave(df: pd.DataFrame) -> ElliottWaveResult:
    """
    Tam Elliott Wave analizi. Önce impulse, sonra correction kontrol eder.
    """
    try:
        zigzag = find_zigzag_points(df, threshold_pct=5.0)

        if len(zigzag) < 3:
            return ElliottWaveResult(
                current_wave="?", phase="UNCERTAIN", confidence="LOW",
                next_expected="Yeterli swing noktası bulunamadı",
            )

        # Önce impulse (5 dalga) dene
        result = _classify_impulse(zigzag)
        if result.phase != "UNCERTAIN":
            return result

        # Sonra correction (ABC) dene
        result = _classify_correction(zigzag)
        if result.phase != "UNCERTAIN":
            return result

        # Hiçbiri uymadıysa basit tahmin
        return _simple_wave_position(zigzag)

    except Exception as e:
        logger.warning("Elliott Wave analiz hatası: %s", str(e))
        return ElliottWaveResult()
