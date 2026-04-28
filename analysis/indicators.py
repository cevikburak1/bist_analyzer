"""
Teknik Göstergeler Modülü

Tüm teknik indikatör hesaplamalarını içerir:
SMA, RSI, MACD, Bollinger Bands, OBV, Lineer Regresyon Eğimi
"""

import logging

import numpy as np
import pandas as pd
from scipy import stats

from config import (
    SMA_SHORT,
    SMA_LONG,
    EMA_FAST,
    EMA_SIGNAL,
    EMA_PERFECT_FAST,
    EMA_PERFECT_MID,
    EMA_PERFECT_SLOW,
    RSI_PERIOD,
    MACD_FAST,
    MACD_SLOW,
    MACD_SIGNAL,
    BB_PERIOD,
    BB_STD,
    OBV_SMA_PERIOD,
    ADX_PERIOD,
    VOLUME_AVG_PERIOD,
    VOLUME_SHORT_PERIOD,
    TREND_REGRESSION_PERIOD,
)

logger = logging.getLogger(__name__)


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Basit Hareketli Ortalama (Simple Moving Average)"""
    return series.rolling(window=period, min_periods=period).mean()


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Üssel Hareketli Ortalama (Exponential Moving Average)"""
    return series.ewm(span=period, min_periods=period, adjust=False).mean()


def calculate_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """
    Relative Strength Index (RSI)
    Wilder'ın orijinal yöntemi ile hesaplanır.
    """
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(
    close: pd.Series,
    fast: int = MACD_FAST,
    slow: int = MACD_SLOW,
    signal: int = MACD_SIGNAL,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    MACD (Moving Average Convergence Divergence)

    Returns:
        (macd_line, signal_line, histogram)
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(
    close: pd.Series,
    period: int = BB_PERIOD,
    std_dev: float = BB_STD,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bantları

    Returns:
        (upper_band, middle_band, lower_band)
    """
    middle = close.rolling(window=period, min_periods=period).mean()
    std = close.rolling(window=period, min_periods=period).std()
    upper = middle + (std_dev * std)
    lower = middle - (std_dev * std)
    return upper, middle, lower


def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On Balance Volume (OBV)"""
    direction = np.sign(close.diff())
    direction.iloc[0] = 0
    obv = (direction * volume).cumsum()
    return obv


def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Average True Range (ATR) — volatilite göstergesi.
    Stop-loss ve hedef fiyat hesaplamaları için kullanılır.
    """
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def calculate_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = ADX_PERIOD,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Average Directional Index.

    ADX trendin gücünü, +DI/-DI ise yön baskısını gösterir.
    """
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    up_move = high - prev_high
    down_move = prev_low - low
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    atr = calculate_atr(high, low, close, period)
    plus_di = 100 * plus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean() / atr.replace(0, np.nan)
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx = dx.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return adx, plus_di, minus_di


def calculate_obv_sma(obv: pd.Series, period: int = OBV_SMA_PERIOD) -> pd.Series:
    """OBV'nin hareketli ortalaması (trend yönü tespiti için)"""
    return obv.rolling(window=period, min_periods=period).mean()


def calculate_linear_regression_slope(
    series: pd.Series,
    period: int = TREND_REGRESSION_PERIOD,
) -> float:
    """
    Son N günlük verinin lineer regresyon eğimini hesaplar.
    Pozitif = yükselen trend, negatif = düşen trend.
    Eğim, yüzde cinsinden normalize edilir.
    """
    data = series.dropna().tail(period)
    if len(data) < period:
        return 0.0

    x = np.arange(len(data))
    y = data.values
    slope, _, _, _, _ = stats.linregress(x, y)

    # Fiyata göre normalize et (yüzde değişim/gün)
    mean_price = np.mean(y)
    if mean_price == 0:
        return 0.0
    return (slope / mean_price) * 100


def calculate_52_week_position(close: pd.Series) -> float:
    """
    Fiyatın 52 haftalık (252 iş günü) yüksek-düşük aralığındaki pozisyonu.
    0.0 = en düşükte, 1.0 = en yüksekte
    """
    lookback = min(252, len(close))
    period_data = close.tail(lookback)

    high_52 = period_data.max()
    low_52 = period_data.min()

    if high_52 == low_52:
        return 0.5

    current = close.iloc[-1]
    return (current - low_52) / (high_52 - low_52)


def calculate_beta(
    stock_close: pd.Series,
    market_close: pd.Series,
    period: int = 252,
) -> float:
    """
    Hissenin piyasa endeksine göre beta değerini hesaplar.
    Beta = Cov(stock, market) / Var(market)
    """
    stock_returns = stock_close.pct_change().dropna().tail(period)
    market_returns = market_close.pct_change().dropna().tail(period)

    # İki serinin uzunluğunu eşitle
    min_len = min(len(stock_returns), len(market_returns))
    if min_len < 30:
        return 1.0  # Yetersiz veri durumunda varsayılan

    stock_returns = stock_returns.tail(min_len)
    market_returns = market_returns.tail(min_len)

    cov = stock_returns.cov(market_returns)
    var = market_returns.var()

    if var == 0:
        return 1.0

    return cov / var


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame'e tüm teknik göstergeleri ekler.
    Giriş: OHLCV verileri (open, high, low, close, volume)
    Çıkış: Tüm indikatörler eklenmiş DataFrame
    """
    result = df.copy()
    close = result["close"]
    volume = result["volume"]

    # SMA
    result["sma_short"] = calculate_sma(close, SMA_SHORT)
    result["sma_long"] = calculate_sma(close, SMA_LONG)

    # EMA dizilimleri
    result["ema_fast"] = calculate_ema(close, EMA_FAST)
    result["ema_signal"] = calculate_ema(close, EMA_SIGNAL)
    result["ema20"] = calculate_ema(close, EMA_PERFECT_FAST)
    result["ema50"] = calculate_ema(close, EMA_PERFECT_MID)
    result["ema200"] = calculate_ema(close, EMA_PERFECT_SLOW)
    result["perfect_order"] = (
        (close > result["ema20"])
        & (result["ema20"] > result["ema50"])
        & (result["ema50"] > result["ema200"])
    )

    # RSI
    result["rsi"] = calculate_rsi(close)

    # MACD
    macd_line, signal_line, histogram = calculate_macd(close)
    result["macd"] = macd_line
    result["macd_signal"] = signal_line
    result["macd_hist"] = histogram

    # Bollinger Bands
    upper, middle, lower = calculate_bollinger_bands(close)
    result["bb_upper"] = upper
    result["bb_middle"] = middle
    result["bb_lower"] = lower
    result["bb_width_pct"] = ((upper - lower) / middle.replace(0, np.nan)) * 100
    width_window = min(120, max(BB_PERIOD, len(result)))
    rolling_width = result["bb_width_pct"].rolling(width_window, min_periods=BB_PERIOD)
    result["bb_width_p20"] = rolling_width.quantile(0.20)
    result["squeeze_on"] = result["bb_width_pct"] <= result["bb_width_p20"]
    result["squeeze_breakout"] = (
        result["squeeze_on"].shift(1).fillna(False)
        & (close > upper)
        & (volume > result["volume"].rolling(VOLUME_AVG_PERIOD, min_periods=VOLUME_SHORT_PERIOD).mean())
    )

    # OBV
    result["obv"] = calculate_obv(close, volume)
    result["obv_sma"] = calculate_obv_sma(result["obv"])

    # ATR (volatilite — stop/hedef için)
    result["atr"] = calculate_atr(result["high"], result["low"], close)

    # ADX / DMI
    result["adx"], result["plus_di"], result["minus_di"] = calculate_adx(
        result["high"], result["low"], close,
    )

    # Hacim ortalamaları
    result["volume_avg"] = volume.rolling(
        window=VOLUME_AVG_PERIOD, min_periods=VOLUME_AVG_PERIOD
    ).mean()
    result["volume_short_avg"] = volume.rolling(
        window=VOLUME_SHORT_PERIOD, min_periods=VOLUME_SHORT_PERIOD
    ).mean()
    result["v_kat"] = volume / result["volume_avg"].replace(0, np.nan)
    result["ema_distance_pct"] = ((close - result["ema_fast"]) / result["ema_fast"].replace(0, np.nan)) * 100

    return result


def get_latest_indicators(df: pd.DataFrame) -> dict:
    """
    DataFrame'in son satırından tüm gösterge değerlerini sözlük olarak döndürür.
    Skorlama ve sinyal modülleri için hazır özet.
    """
    if df.empty:
        return {}

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last

    close_series = df["close"]

    return {
        "close": last["close"],
        "open": last["open"],
        "high": last["high"],
        "low": last["low"],
        "volume": last["volume"],
        # SMA
        "sma_short": last.get("sma_short", np.nan),
        "sma_long": last.get("sma_long", np.nan),
        # EMA / Morpheus dizilimleri
        "ema_fast": last.get("ema_fast", np.nan),
        "ema_signal": last.get("ema_signal", np.nan),
        "ema20": last.get("ema20", np.nan),
        "ema50": last.get("ema50", np.nan),
        "ema200": last.get("ema200", np.nan),
        "perfect_order": bool(last.get("perfect_order", False)),
        # RSI
        "rsi": last.get("rsi", np.nan),
        # MACD
        "macd": last.get("macd", np.nan),
        "macd_signal": last.get("macd_signal", np.nan),
        "macd_hist": last.get("macd_hist", np.nan),
        "macd_hist_prev": prev.get("macd_hist", np.nan),
        # Bollinger Bands
        "bb_upper": last.get("bb_upper", np.nan),
        "bb_middle": last.get("bb_middle", np.nan),
        "bb_lower": last.get("bb_lower", np.nan),
        "bb_width_pct": last.get("bb_width_pct", np.nan),
        "bb_width_p20": last.get("bb_width_p20", np.nan),
        "squeeze_on": bool(last.get("squeeze_on", False)),
        "squeeze_breakout": bool(last.get("squeeze_breakout", False)),
        # OBV
        "obv": last.get("obv", np.nan),
        "obv_sma": last.get("obv_sma", np.nan),
        # ADX
        "adx": last.get("adx", np.nan),
        "plus_di": last.get("plus_di", np.nan),
        "minus_di": last.get("minus_di", np.nan),
        # Hacim
        "volume_avg": last.get("volume_avg", np.nan),
        "volume_short_avg": last.get("volume_short_avg", np.nan),
        "v_kat": last.get("v_kat", np.nan),
        "ema_distance_pct": last.get("ema_distance_pct", np.nan),
        # ATR (stop/hedef için)
        "atr": last.get("atr", np.nan),
        # Son 20 gün swing seviyeleri (destek/direnç)
        "swing_low_20": df["low"].tail(20).min(),
        "swing_high_20": df["high"].tail(20).max(),
        # Trend
        "trend_slope": calculate_linear_regression_slope(close_series),
        # 52 hafta pozisyonu
        "week52_position": calculate_52_week_position(close_series),
    }
