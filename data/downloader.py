"""
Veri İndirme ve Cache Modülü

yfinance ile BIST hisselerinin günlük OHLCV verilerini çeker.
Parquet formatında cache'ler, aynı gün tekrar çekmez.
"""

import logging
import os
import time
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

from config import (
    CACHE_DIR,
    DATA_PERIOD,
    INTRADAY_CACHE_DIR,
    INTRADAY_INTERVAL,
    INTRADAY_PERIOD,
    INTRADAY_REFRESH_MINUTES,
    REQUEST_DELAY,
    SYMBOLS_FILE,
)

logger = logging.getLogger(__name__)

MARKET_TIMEZONE = ZoneInfo("Europe/Istanbul")
MARKET_OPEN_TIME = dt_time(10, 0)
MARKET_CLOSE_TIME = dt_time(18, 10)
MARKET_REFRESH_END_TIME = dt_time(18, 50)
BAR_COMPLETION_GRACE = timedelta(minutes=5)


def _env_minutes(name: str, default: int) -> int:
    """Return a positive cache duration without making config mandatory."""
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        logger.warning("Geçersiz %s; varsayılan %d dakika kullanılıyor", name, default)
        return default


# During the session, both the daily candle and intraday bars change.  A short
# TTL keeps scheduled snapshots current without disabling the cache for the
# hundreds of symbols in the universe.  Outside the session a longer TTL avoids
# repeatedly requesting an unchanged close.
DAILY_CACHE_TTL_MINUTES = _env_minutes(
    "BIST_DAILY_CACHE_TTL_MINUTES", INTRADAY_REFRESH_MINUTES
)
INTRADAY_CACHE_TTL_MINUTES = _env_minutes(
    "BIST_INTRADAY_CACHE_TTL_MINUTES", min(INTRADAY_REFRESH_MINUTES, 12)
)
CLOSED_MARKET_CACHE_TTL_MINUTES = _env_minutes(
    "BIST_CLOSED_CACHE_TTL_MINUTES", 360
)
POST_CLOSE_RETRY_MINUTES = _env_minutes("BIST_POST_CLOSE_RETRY_MINUTES", 10)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_istanbul(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=MARKET_TIMEZONE)
    return value.astimezone(MARKET_TIMEZONE)


def _session_time(day, value: dt_time) -> datetime:
    return datetime.combine(day, value, tzinfo=MARKET_TIMEZONE)


def _is_market_open(now: Optional[datetime] = None) -> bool:
    """Best-effort BIST session check (weekends included, exchange holidays not)."""
    local_now = _as_istanbul(now or _utc_now())
    return (
        local_now.weekday() < 5
        and MARKET_OPEN_TIME <= local_now.time() < MARKET_CLOSE_TIME
    )


def _use_session_cache_ttl(now: Optional[datetime] = None) -> bool:
    """Keep the short TTL through the first post-close completed snapshot."""
    local_now = _as_istanbul(now or _utc_now())
    return (
        local_now.weekday() < 5
        and MARKET_OPEN_TIME <= local_now.time() < MARKET_REFRESH_END_TIME
    )


def _interval_delta(interval: str) -> timedelta:
    value = interval.strip().lower()
    units = {
        "m": "minutes",
        "h": "hours",
        "d": "days",
        "wk": "weeks",
    }
    for suffix in ("wk", "m", "h", "d"):
        if value.endswith(suffix):
            try:
                amount = int(value[: -len(suffix)])
            except ValueError as exc:
                raise ValueError(f"Geçersiz bar aralığı: {interval}") from exc
            if amount <= 0:
                break
            return timedelta(**{units[suffix]: amount})
    raise ValueError(f"Desteklenmeyen bar aralığı: {interval}")


def _normalize_index(index: pd.Index) -> pd.DatetimeIndex:
    normalized = pd.DatetimeIndex(pd.to_datetime(index, errors="coerce"))
    if normalized.tz is None:
        # Existing cache files were written after dropping yfinance's timezone;
        # those timestamps represented Istanbul wall-clock time.
        normalized = normalized.tz_localize(
            MARKET_TIMEZONE, ambiguous="infer", nonexistent="shift_forward"
        )
    else:
        normalized = normalized.tz_convert(MARKET_TIMEZONE)
    return normalized


def _bar_completion_time(timestamp: pd.Timestamp, interval: Optional[str]) -> datetime:
    local_ts = timestamp.to_pydatetime().astimezone(MARKET_TIMEZONE)
    session_close = _session_time(local_ts.date(), MARKET_CLOSE_TIME)
    if interval is None:
        return session_close + BAR_COMPLETION_GRACE

    expected_end = local_ts + _interval_delta(interval)
    if expected_end > session_close:
        expected_end = session_close
    return expected_end + BAR_COMPLETION_GRACE


def _prepare_ohlcv(
    raw: pd.DataFrame,
    *,
    now: Optional[datetime] = None,
    interval: Optional[str] = None,
) -> pd.DataFrame:
    """Normalize, validate and retain only completed OHLCV bars."""
    if raw is None or raw.empty:
        return pd.DataFrame()

    current = _as_istanbul(now or _utc_now())
    df = raw.copy()
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated(keep="last")]

    required = ["open", "high", "low", "close", "volume"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Eksik OHLCV sütunları: {', '.join(missing)}")
    df = df[required]

    df.index = _normalize_index(df.index)
    df = df.loc[~df.index.isna()].sort_index()
    df = df.loc[~df.index.duplicated(keep="last")]
    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    before_quality = len(df)
    valid = (
        df[required].notna().all(axis=1)
        & np.isfinite(df[required]).all(axis=1)
        & (df[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (df["volume"] >= 0)
        & (df["high"] >= df[["open", "low", "close"]].max(axis=1))
        & (df["low"] <= df[["open", "high", "close"]].min(axis=1))
    )
    df = df.loc[valid].copy()
    dropped_quality = before_quality - len(df)

    before_completion = len(df)
    if not df.empty:
        complete = [
            _bar_completion_time(pd.Timestamp(ts), interval) <= current
            for ts in df.index
        ]
        df = df.loc[complete].copy()
    dropped_incomplete = before_completion - len(df)

    df.attrs.update(
        {
            "timezone": str(MARKET_TIMEZONE),
            "data_as_of": df.index[-1].isoformat() if not df.empty else None,
            "dropped_invalid_bars": dropped_quality,
            "dropped_incomplete_bars": dropped_incomplete,
            "contains_only_completed_bars": True,
        }
    )
    return df


def _cache_file_is_fresh(
    path: Path,
    *,
    now: Optional[datetime] = None,
    intraday: bool = False,
) -> bool:
    current = now or _utc_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    ttl = (
        INTRADAY_CACHE_TTL_MINUTES if intraday else DAILY_CACHE_TTL_MINUTES
    ) if _use_session_cache_ttl(current) else CLOSED_MARKET_CACHE_TTL_MINUTES
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age = max(timedelta(0), current.astimezone(timezone.utc) - modified)
    return age <= timedelta(minutes=ttl)


def _intraday_bar_is_recent(
    df: pd.DataFrame,
    interval: str,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """Reject a fresh-on-disk cache whose last completed bar is too old."""
    if df is None or df.empty:
        return False
    current = _as_istanbul(now or _utc_now())
    if not _is_market_open(current):
        return True

    delta = _interval_delta(interval)
    session_open = _session_time(current.date(), MARKET_OPEN_TIME)
    if current <= session_open + delta + BAR_COMPLETION_GRACE:
        # No full current-session bar is guaranteed yet.
        return True

    latest = pd.Timestamp(df.index[-1])
    if latest.tzinfo is None:
        latest = latest.tz_localize(MARKET_TIMEZONE)
    else:
        latest = latest.tz_convert(MARKET_TIMEZONE)
    if latest.date() != current.date():
        return False

    completed_at = _bar_completion_time(latest, interval)
    # Immediately before the next bar completes, the most recent confirmed bar
    # can legitimately be almost one full interval old.
    return current <= completed_at + delta


def _daily_cache_session_coverage(
    df: pd.DataFrame,
    *,
    now: Optional[datetime] = None,
) -> Optional[bool]:
    """Return whether a daily cache covers the session, or None outside it.

    Confirmed daily bars do not change during the session.  Once today's bar
    can be considered final (close + grace), however, a cache ending on an
    earlier date must be refreshed even if its file mtime is recent.
    """
    if df is None or df.empty:
        return False
    current = _as_istanbul(now or _utc_now())
    if current.weekday() >= 5:
        return None

    completion_cutoff = (
        datetime.combine(current.date(), MARKET_CLOSE_TIME, tzinfo=MARKET_TIMEZONE)
        + BAR_COMPLETION_GRACE
    )
    session_open = _session_time(current.date(), MARKET_OPEN_TIME)
    latest = pd.Timestamp(df.index[-1])
    if latest.tzinfo is None:
        latest = latest.tz_localize(MARKET_TIMEZONE)
    else:
        latest = latest.tz_convert(MARKET_TIMEZONE)

    if session_open <= current < completion_cutoff:
        age_days = (current.date() - latest.date()).days
        if 0 < age_days <= 4:
            return True
        # On a long exchange holiday, avoid hammering the provider after this
        # process has already checked the old last-traded bar today.  A week-old
        # cache that has not been rechecked is never accepted blindly.
        checked_at = df.attrs.get("downloaded_at")
        if checked_at:
            checked = pd.Timestamp(checked_at)
            if checked.tzinfo is None:
                checked = checked.tz_localize(timezone.utc)
            checked_local = checked.to_pydatetime().astimezone(MARKET_TIMEZONE)
            checked_age = (current - checked_local).total_seconds() / 60
            return checked_local.date() == current.date() and checked_age <= DAILY_CACHE_TTL_MINUTES
        return False
    if current >= completion_cutoff:
        if latest.date() == current.date():
            return True
        # Yahoo may publish the completed daily candle after 18:15.  A missing
        # current-session bar is therefore retried on a short cooldown rather
        # than being accepted for the entire evening after the first check.
        checked_at = df.attrs.get("downloaded_at")
        if checked_at:
            checked = pd.Timestamp(checked_at)
            if checked.tzinfo is None:
                checked = checked.tz_localize(timezone.utc)
            checked_local = checked.to_pydatetime().astimezone(MARKET_TIMEZONE)
            checked_age = (current - checked_local).total_seconds() / 60
            return checked_local >= completion_cutoff and checked_age <= POST_CLOSE_RETRY_MINUTES
        return False
    return None


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
    now = _utc_now()
    today = _as_istanbul(now).strftime("%Y%m%d")
    cache_file = _cache_path(symbol, today)

    # Cache kontrolü: piyasa açıkken kısa TTL, kapalıyken daha uzun TTL.
    if not force and cache_file.exists():
        try:
            cached = pd.read_parquet(cache_file)
            cached_period = cached.attrs.get("period")
            df = _prepare_ohlcv(cached, now=now)
            session_coverage = _daily_cache_session_coverage(df, now=now)
            time_is_usable = (
                session_coverage
                if session_coverage is not None
                else _cache_file_is_fresh(cache_file, now=now)
            )
            if (
                len(df) > 0
                and cached_period == period
                and time_is_usable
            ):
                df.attrs["cache_status"] = "fresh"
                logger.debug("Cache'ten okundu: %s (%d satır)", symbol, len(df))
                return df
            if cached_period != period:
                logger.info(
                    "Günlük cache periyodu uyuşmuyor (%s != %s), yenileniyor: %s",
                    cached_period or "bilinmiyor",
                    period,
                    symbol,
                )
            elif session_coverage is False:
                logger.info(
                    "Günlük cache son tamamlanmış seansı kapsamıyor, yenileniyor: %s",
                    symbol,
                )
            else:
                logger.info("Günlük cache süresi doldu, yenileniyor: %s", symbol)
        except Exception:
            logger.warning("Cache okunamadı, yeniden indiriliyor: %s", symbol)

    # yfinance ile indir
    try:
        ticker = yf.Ticker(yahoo_symbol)
        raw = ticker.history(period=period, auto_adjust=True)

        if raw is None or raw.empty:
            logger.warning("Veri bulunamadı: %s", yahoo_symbol)
            return None

        df = _prepare_ohlcv(raw, now=now)
        if df.empty:
            logger.warning("Kalite kontrolü sonrası kullanılabilir veri yok: %s", yahoo_symbol)
            return None
        df.attrs.update(
            {
                "cache_status": "downloaded",
                "downloaded_at": now.isoformat(),
                "period": period,
            }
        )

        # Eski cache dosyalarını temizle, yenisini yaz
        _clean_old_cache(symbol, today)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_file)

        logger.info(
            "İndirildi: %s (%d tamamlanmış satır, %d eksik bar atıldı)",
            symbol,
            len(df),
            df.attrs.get("dropped_incomplete_bars", 0),
        )
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
    now = _utc_now()
    today = _as_istanbul(now).strftime("%Y%m%d")
    cache_file = _intraday_cache_path(symbol, interval, today)

    if not force and cache_file.exists():
        try:
            cached = pd.read_parquet(cache_file)
            cached_period = cached.attrs.get("period")
            cached_interval = cached.attrs.get("interval")
            df = _prepare_ohlcv(cached, now=now, interval=interval)
            cache_is_usable = (
                len(df) > 0
                and cached_period == period
                and cached_interval == interval
                and _cache_file_is_fresh(
                    cache_file, now=now, intraday=True
                )
                and _intraday_bar_is_recent(df, interval, now=now)
            )
            if cache_is_usable:
                df.attrs["cache_status"] = "fresh"
                logger.debug("Intraday cache'ten okundu: %s %s (%d satır)", symbol, interval, len(df))
                return df
            logger.info("Intraday cache eski veya son bar gecikmiş, yenileniyor: %s", symbol)
        except Exception:
            logger.warning("Intraday cache okunamadı, yeniden indiriliyor: %s", symbol)

    try:
        ticker = yf.Ticker(yahoo_symbol)
        raw = ticker.history(period=period, interval=interval, auto_adjust=True)

        if raw is None or raw.empty:
            logger.warning("Intraday veri bulunamadı: %s %s", yahoo_symbol, interval)
            return None

        df = _prepare_ohlcv(raw, now=now, interval=interval)
        if df.empty:
            logger.warning(
                "Intraday kalite kontrolü sonrası kullanılabilir veri yok: %s %s",
                yahoo_symbol,
                interval,
            )
            return None
        df.attrs.update(
            {
                "cache_status": "downloaded",
                "downloaded_at": now.isoformat(),
                "period": period,
                "interval": interval,
            }
        )

        _clean_old_intraday_cache(symbol, interval, today)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_file)

        logger.info(
            "Intraday indirildi: %s %s (%d tamamlanmış satır, %d eksik bar atıldı)",
            symbol,
            interval,
            len(df),
            df.attrs.get("dropped_incomplete_bars", 0),
        )
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
