"""
Mum Formasyonu Tespit Modülü (TA-Lib)

20+ mum formasyonunu tespit eder. Her formasyonun yönünü (bullish/bearish)
ve gücünü (strong/moderate/weak) raporlar.
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
import talib

logger = logging.getLogger(__name__)


@dataclass
class CandlePattern:
    name: str           # Türkçe ad
    english: str        # İngilizce ad
    direction: str      # "BULLISH", "BEARISH", "NEUTRAL"
    strength: str       # "STRONG", "MODERATE", "WEAK"
    value: int          # TA-Lib çıktı değeri (100/-100 güçlü, 200/-200 çok güçlü)


# TA-Lib fonksiyon adı -> (Türkçe ad, varsayılan yön)
PATTERN_DEFS: dict[str, tuple[str, str]] = {
    "CDLDOJI":            ("Doji",                "NEUTRAL"),
    "CDLDRAGONFLYDOJI":   ("Yusufçuk Doji",       "BULLISH"),
    "CDLGRAVESTONEDOJI":  ("Mezar Taşı Doji",     "BEARISH"),
    "CDLHAMMER":          ("Çekiç",               "BULLISH"),
    "CDLINVERTEDHAMMER":  ("Ters Çekiç",          "BULLISH"),
    "CDLHANGINGMAN":      ("Asılan Adam",         "BEARISH"),
    "CDLSHOOTINGSTAR":    ("Kayan Yıldız",        "BEARISH"),
    "CDLENGULFING":       ("Yutan Formasyon",     "DIRECTIONAL"),
    "CDLMORNINGSTAR":     ("Sabah Yıldızı",       "BULLISH"),
    "CDLEVENINGSTAR":     ("Akşam Yıldızı",       "BEARISH"),
    "CDL3WHITESOLDIERS":  ("Üç Beyaz Asker",      "BULLISH"),
    "CDL3BLACKCROWS":     ("Üç Kara Karga",       "BEARISH"),
    "CDLHARAMI":          ("Harami",              "DIRECTIONAL"),
    "CDLHARAMICROSS":     ("Harami Cross",        "DIRECTIONAL"),
    "CDLPIERCING":        ("Delici Çizgi",        "BULLISH"),
    "CDLDARKCLOUDCOVER":  ("Kara Bulut Örtüsü",   "BEARISH"),
    "CDLMARUBOZU":        ("Marubozu",            "DIRECTIONAL"),
    "CDLSPINNINGTOP":     ("Topaç",               "NEUTRAL"),
    "CDLBELTHOLD":        ("Kuşak Tutuş",         "DIRECTIONAL"),
    "CDL3INSIDE":         ("Üç İçeride",          "DIRECTIONAL"),
    "CDL3OUTSIDE":        ("Üç Dışarıda",         "DIRECTIONAL"),
    "CDLBREAKAWAY":       ("Kopuş",               "DIRECTIONAL"),
    "CDLKICKING":         ("Tekme",               "DIRECTIONAL"),
    "CDLMORNINGDOJISTAR":  ("Sabah Doji Yıldızı",  "BULLISH"),
    "CDLEVENINGDOJISTAR":  ("Akşam Doji Yıldızı",  "BEARISH"),
}


def _strength_from_value(val: int) -> str:
    """TA-Lib çıktı değerinden güç seviyesi."""
    abs_val = abs(val)
    if abs_val >= 200:
        return "STRONG"
    if abs_val >= 100:
        return "MODERATE"
    return "WEAK"


def _direction_from_value(val: int, default_dir: str) -> str:
    """TA-Lib çıktı değerinden yön belirle."""
    if default_dir != "DIRECTIONAL":
        return default_dir
    if val > 0:
        return "BULLISH"
    if val < 0:
        return "BEARISH"
    return "NEUTRAL"


def detect_patterns(df: pd.DataFrame, lookback: int = 5) -> list[CandlePattern]:
    """
    Son `lookback` mumda tetiklenen tüm formasyonları tespit eder.
    """
    if len(df) < 20:
        return []

    op = df["open"].values.astype(np.float64)
    hi = df["high"].values.astype(np.float64)
    lo = df["low"].values.astype(np.float64)
    cl = df["close"].values.astype(np.float64)

    patterns: list[CandlePattern] = []

    for func_name, (tr_name, default_dir) in PATTERN_DEFS.items():
        try:
            func = getattr(talib, func_name, None)
            if func is None:
                continue
            result = func(op, hi, lo, cl)
            recent = result[-lookback:]
            nonzero = recent[recent != 0]

            if len(nonzero) > 0:
                val = int(nonzero[-1])
                direction = _direction_from_value(val, default_dir)
                strength = _strength_from_value(val)
                patterns.append(CandlePattern(
                    name=tr_name,
                    english=func_name.replace("CDL", ""),
                    direction=direction,
                    strength=strength,
                    value=val,
                ))
        except Exception as e:
            logger.debug("Formasyon tarama hatası [%s]: %s", func_name, str(e))

    # Güçlü olanları öne al
    strength_order = {"STRONG": 0, "MODERATE": 1, "WEAK": 2}
    patterns.sort(key=lambda p: strength_order.get(p.strength, 3))

    return patterns


def _detect_tweezer_top(df: pd.DataFrame) -> bool:
    """Manuel Tweezer Top tespiti: son 2 mumun high'ları neredeyse eşit + ikincisi bearish."""
    if len(df) < 2:
        return False
    h1, h2 = df["high"].iloc[-2], df["high"].iloc[-1]
    c1, o1 = df["close"].iloc[-2], df["open"].iloc[-2]
    c2, o2 = df["close"].iloc[-1], df["open"].iloc[-1]
    pct_diff = abs(h1 - h2) / h1 if h1 > 0 else 1
    return pct_diff < 0.002 and c1 > o1 and c2 < o2


def _detect_tweezer_bottom(df: pd.DataFrame) -> bool:
    """Manuel Tweezer Bottom tespiti: son 2 mumun low'ları neredeyse eşit + ikincisi bullish."""
    if len(df) < 2:
        return False
    l1, l2 = df["low"].iloc[-2], df["low"].iloc[-1]
    c1, o1 = df["close"].iloc[-2], df["open"].iloc[-2]
    c2, o2 = df["close"].iloc[-1], df["open"].iloc[-1]
    pct_diff = abs(l1 - l2) / l1 if l1 > 0 else 1
    return pct_diff < 0.002 and c1 < o1 and c2 > o2


def detect_all_patterns(df: pd.DataFrame, lookback: int = 5) -> list[CandlePattern]:
    """TA-Lib formasyonlarını ve manuel ek formasyonları birleştirir."""
    patterns = detect_patterns(df, lookback)

    if _detect_tweezer_top(df):
        patterns.append(CandlePattern(
            name="Cımbız Tepe", english="TweezerTop",
            direction="BEARISH", strength="MODERATE", value=-100,
        ))
    if _detect_tweezer_bottom(df):
        patterns.append(CandlePattern(
            name="Cımbız Dip", english="TweezerBottom",
            direction="BULLISH", strength="MODERATE", value=100,
        ))

    return patterns


def pattern_bias(patterns: list[CandlePattern]) -> str:
    """Tespit edilen formasyonların genel yön eğilimi."""
    if not patterns:
        return "NONE"

    bullish = sum(1 for p in patterns if p.direction == "BULLISH")
    bearish = sum(1 for p in patterns if p.direction == "BEARISH")

    if bullish > 0 and bearish == 0:
        return "BULLISH"
    if bearish > 0 and bullish == 0:
        return "BEARISH"
    if bullish > 0 and bearish > 0:
        return "MIXED"
    return "NEUTRAL"


def patterns_summary(patterns: list[CandlePattern]) -> str:
    """Formasyonları tek satırda özetler."""
    if not patterns:
        return "Formasyon yok"
    names = [f"{p.name}({'+'if p.direction=='BULLISH' else '-' if p.direction=='BEARISH' else '~'})" for p in patterns[:4]]
    return ", ".join(names)
