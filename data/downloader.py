"""
Veri İndirme ve Cache Modülü

yfinance ile BIST hisselerinin günlük OHLCV verilerini çeker.
Parquet formatında cache'ler, aynı gün tekrar çekmez.
"""

import logging
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from config import (
    CACHE_DIR,
    DATA_PERIOD,
    INTRADAY_CACHE_DIR,
    INTRADAY_INTERVAL,
    INTRADAY_PERIOD,
    REQUEST_DELAY,
    SYMBOLS_FILE,
)

logger = logging.getLogger(__name__)


def load_symbols(filepath: Optional[Path] = None) -> list[str]:
    """symbols.txt dosyasından BIST sembol listesini okur."""
    filepath = filepath or SYMBOLS_FILE
    symbols: list[str] = []

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            symbols.append(line.upper())

    logger.info("Toplam %d sembol yüklendi", len(symbols))
    return symbols


def _cache_path(symbol: str, today: str) -> Path:
    """Belirli bir sembol ve tarih için cache dosya yolunu döndürür."""
    return CACHE_DIR / f"{symbol}_{today}.parquet"


def _intraday_cache_path(symbol: str, interval: str, today: str) -> Path:
    safe_interval = interval.replace("/", "_")
    return INTRADAY_CACHE_DIR / f"{symbol}_{safe_interval}_{today}.parquet"


def _clean_old_cache(symbol: str, today: str) -> None:
    """Aynı sembolün eski cache dosyalarını temizler."""
    for old_file in CACHE_DIR.glob(f"{symbol}_*.parquet"):
        if today not in old_file.name:
            old_file.unlink(missing_ok=True)


def _clean_old_intraday_cache(symbol: str, interval: str, today: str) -> None:
    safe_interval = interval.replace("/", "_")
    for old_file in INTRADAY_CACHE_DIR.glob(f"{symbol}_{safe_interval}_*.parquet"):
        if today not in old_file.name:
            old_file.unlink(missing_ok=True)


def download_stock(
    symbol: str,
    period: str = DATA_PERIOD,
    force: bool = False,
) -> Optional[pd.DataFrame]:
    """
    Tek bir hissenin verilerini indirir veya cache'ten okur.

    Returns:
        OHLCV DataFrame veya başarısız ise None
    """
    yahoo_symbol = f"{symbol}.IS"
    today = date.today().strftime("%Y%m%d")
    cache_file = _cache_path(symbol, today)

    # Cache kontrolü
    if not force and cache_file.exists():
        try:
            df = pd.read_parquet(cache_file)
            if len(df) > 0:
                logger.debug("Cache'ten okundu: %s (%d satır)", symbol, len(df))
                return df
        except Exception:
            logger.warning("Cache okunamadı, yeniden indiriliyor: %s", symbol)

    # yfinance ile indir
    try:
        ticker = yf.Ticker(yahoo_symbol)
        df = ticker.history(period=period, auto_adjust=True)

        if df is None or df.empty:
            logger.warning("Veri bulunamadı: %s", yahoo_symbol)
            return None

        # Sütun isimlerini standartlaştır
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]

        # Gereksiz sütunları temizle
        keep_cols = ["open", "high", "low", "close", "volume"]
        df = df[[c for c in keep_cols if c in df.columns]]

        # Index'i datetime olarak ayarla
        df.index = pd.to_datetime(df.index)
        df.index = df.index.tz_localize(None)

        # Eski cache dosyalarını temizle, yenisini yaz
        _clean_old_cache(symbol, today)
        df.to_parquet(cache_file)

        logger.info("İndirildi: %s (%d satır)", symbol, len(df))
        return df

    except Exception as e:
        logger.error("İndirme hatası [%s]: %s", yahoo_symbol, str(e))
        return None


def download_intraday_stock(
    symbol: str,
    period: str = INTRADAY_PERIOD,
    interval: str = INTRADAY_INTERVAL,
    force: bool = False,
) -> Optional[pd.DataFrame]:
    """
    Tek bir hissenin intraday OHLCV verisini indirir veya cache'ten okur.
    AMD modeli günlük sinyal hattından ayrı bir LTF veri penceresi kullanır.
    """
    yahoo_symbol = f"{symbol}.IS"
    today = date.today().strftime("%Y%m%d")
    cache_file = _intraday_cache_path(symbol, interval, today)

    if not force and cache_file.exists():
        try:
            df = pd.read_parquet(cache_file)
            if len(df) > 0:
                logger.debug("Intraday cache'ten okundu: %s %s (%d satır)", symbol, interval, len(df))
                return df
        except Exception:
            logger.warning("Intraday cache okunamadı, yeniden indiriliyor: %s", symbol)

    try:
        ticker = yf.Ticker(yahoo_symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=True)

        if df is None or df.empty:
            logger.warning("Intraday veri bulunamadı: %s %s", yahoo_symbol, interval)
            return None

        df.columns = [c.lower().replace(" ", "_") for c in df.columns]
        keep_cols = ["open", "high", "low", "close", "volume"]
        df = df[[c for c in keep_cols if c in df.columns]]
        df.index = pd.to_datetime(df.index).tz_localize(None)

        _clean_old_intraday_cache(symbol, interval, today)
        df.to_parquet(cache_file)

        logger.info("Intraday indirildi: %s %s (%d satır)", symbol, interval, len(df))
        return df

    except Exception as e:
        logger.error("Intraday indirme hatası [%s %s]: %s", yahoo_symbol, interval, str(e))
        return None


def download_all_stocks(
    symbols: Optional[list[str]] = None,
    period: str = DATA_PERIOD,
    force: bool = False,
) -> dict[str, pd.DataFrame]:
    """
    Tüm sembolleri sırayla indirir. Rate limiting uygular.

    Returns:
        {sembol: DataFrame} sözlüğü
    """
    if symbols is None:
        symbols = load_symbols()

    results: dict[str, pd.DataFrame] = {}
    failed: list[str] = []

    for i, symbol in enumerate(symbols, 1):
        logger.info("[%d/%d] İndiriliyor: %s", i, len(symbols), symbol)

        df = download_stock(symbol, period=period, force=force)
        if df is not None and not df.empty:
            results[symbol] = df
        else:
            failed.append(symbol)

        # Rate limiting
        if i < len(symbols):
            time.sleep(REQUEST_DELAY)

    logger.info(
        "Tamamlandı: %d başarılı, %d başarısız", len(results), len(failed)
    )
    if failed:
        logger.warning("Başarısız semboller: %s", ", ".join(failed))

    return results


def download_index(
    symbol: str = "XU100.IS",
    period: str = DATA_PERIOD,
) -> Optional[pd.DataFrame]:
    """Endeks verisini indirir (piyasa rejimi analizi için)."""
    return download_stock(symbol.replace(".IS", ""), period=period)
