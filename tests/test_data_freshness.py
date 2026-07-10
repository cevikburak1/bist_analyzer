import json
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from analysis.market_regime import MarketRegime
from data import downloader
from reports import web_snapshot


ISTANBUL = ZoneInfo("Europe/Istanbul")


def _ohlcv(index, *, close=10.0) -> pd.DataFrame:
    values = [close] * len(index)
    return pd.DataFrame(
        {
            "Open": values,
            "High": [value + 1 for value in values],
            "Low": [value - 1 for value in values],
            "Close": values,
            "Volume": [100] * len(index),
        },
        index=pd.DatetimeIndex(index),
    )


def test_prepare_intraday_preserves_timezone_deduplicates_and_filters_bad_bars():
    raw = _ohlcv(
        [
            "2026-07-10 10:30",
            "2026-07-10 09:30",
            "2026-07-10 10:30",
            "2026-07-10 11:30",
            "2026-07-10 08:30",
        ]
    )
    raw.iloc[-1, raw.columns.get_loc("High")] = 8.0
    now = datetime(2026, 7, 10, 11, 45, tzinfo=ISTANBUL)

    result = downloader._prepare_ohlcv(raw, now=now, interval="60m")

    assert str(result.index.tz) == "Europe/Istanbul"
    assert result.index.is_monotonic_increasing
    assert result.index.is_unique
    assert [item.strftime("%H:%M") for item in result.index] == ["09:30", "10:30"]
    assert result.attrs["dropped_invalid_bars"] == 1
    assert result.attrs["dropped_incomplete_bars"] == 1
    assert result.attrs["contains_only_completed_bars"] is True


def test_daily_candle_is_excluded_until_closing_auction_finishes():
    raw = _ohlcv(["2026-07-09", "2026-07-10"])

    during_session = downloader._prepare_ohlcv(
        raw,
        now=datetime(2026, 7, 10, 17, 0, tzinfo=ISTANBUL),
    )
    after_close = downloader._prepare_ohlcv(
        raw,
        now=datetime(2026, 7, 10, 18, 16, tzinfo=ISTANBUL),
    )

    assert [item.date().isoformat() for item in during_session.index] == ["2026-07-09"]
    assert during_session.attrs["dropped_incomplete_bars"] == 1
    assert [item.date().isoformat() for item in after_close.index] == [
        "2026-07-09",
        "2026-07-10",
    ]


def test_cache_ttl_is_short_during_session_and_long_when_closed(tmp_path, monkeypatch):
    cache_file = tmp_path / "cache.parquet"
    cache_file.touch()
    monkeypatch.setattr(downloader, "DAILY_CACHE_TTL_MINUTES", 15)
    monkeypatch.setattr(downloader, "CLOSED_MARKET_CACHE_TTL_MINUTES", 360)

    open_now = datetime(2026, 7, 10, 12, 0, tzinfo=ISTANBUL)
    modified = open_now.astimezone(timezone.utc) - timedelta(minutes=16)
    os.utime(cache_file, (modified.timestamp(), modified.timestamp()))

    assert downloader._cache_file_is_fresh(cache_file, now=open_now) is False

    post_close = datetime(2026, 7, 10, 18, 15, tzinfo=ISTANBUL)
    modified = post_close.astimezone(timezone.utc) - timedelta(minutes=16)
    os.utime(cache_file, (modified.timestamp(), modified.timestamp()))
    assert downloader._cache_file_is_fresh(cache_file, now=post_close) is False

    closed_now = datetime(2026, 7, 10, 20, 0, tzinfo=ISTANBUL)
    modified = closed_now.astimezone(timezone.utc) - timedelta(minutes=120)
    os.utime(cache_file, (modified.timestamp(), modified.timestamp()))
    assert downloader._cache_file_is_fresh(cache_file, now=closed_now) is True


def test_intraday_cache_checks_last_bar_age_during_market_hours():
    current_day = _ohlcv(["2026-07-10 09:30"])
    current_day = downloader._prepare_ohlcv(
        current_day,
        now=datetime(2026, 7, 10, 11, 20, tzinfo=ISTANBUL),
        interval="60m",
    )
    previous_day = _ohlcv(["2026-07-09 17:00"])
    previous_day = downloader._prepare_ohlcv(
        previous_day,
        now=datetime(2026, 7, 10, 11, 20, tzinfo=ISTANBUL),
        interval="60m",
    )

    assert downloader._intraday_bar_is_recent(
        current_day,
        "60m",
        now=datetime(2026, 7, 10, 11, 20, tzinfo=ISTANBUL),
    ) is True
    assert downloader._intraday_bar_is_recent(
        previous_day,
        "60m",
        now=datetime(2026, 7, 10, 11, 20, tzinfo=ISTANBUL),
    ) is False


def test_download_stock_refreshes_expired_cache_without_using_incomplete_daily_bar(
    tmp_path, monkeypatch
):
    now = datetime(2026, 7, 10, 12, 0, tzinfo=ISTANBUL)
    monkeypatch.setattr(downloader, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(downloader, "DAILY_CACHE_TTL_MINUTES", 10)
    monkeypatch.setattr(downloader, "_utc_now", lambda: now.astimezone(timezone.utc))

    cache_file = tmp_path / "TEST_20260710.parquet"
    _ohlcv(["2026-07-08"]).to_parquet(cache_file)
    expired = now.astimezone(timezone.utc) - timedelta(minutes=11)
    os.utime(cache_file, (expired.timestamp(), expired.timestamp()))

    calls = []

    class DummyTicker:
        def history(self, **kwargs):
            calls.append(kwargs)
            return _ohlcv(["2026-07-08", "2026-07-09", "2026-07-10"], close=20.0)

    monkeypatch.setattr(downloader.yf, "Ticker", lambda symbol: DummyTicker())

    result = downloader.download_stock("TEST")

    assert len(calls) == 1
    assert result is not None
    assert result.index[-1].date().isoformat() == "2026-07-09"
    assert str(result.index.tz) == "Europe/Istanbul"
    assert result.attrs["cache_status"] == "downloaded"


def test_download_stock_does_not_reuse_cache_for_a_different_period(
    tmp_path, monkeypatch
):
    now = datetime(2026, 7, 10, 12, 0, tzinfo=ISTANBUL)
    monkeypatch.setattr(downloader, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(downloader, "_utc_now", lambda: now.astimezone(timezone.utc))

    cache_file = tmp_path / "TEST_20260710.parquet"
    cached = _ohlcv(["2026-07-08"], close=10.0)
    cached.attrs["period"] = "2y"
    cached.to_parquet(cache_file)
    current = now.astimezone(timezone.utc)
    os.utime(cache_file, (current.timestamp(), current.timestamp()))

    calls = []

    class DummyTicker:
        def history(self, **kwargs):
            calls.append(kwargs)
            return _ohlcv(["2021-07-08", "2026-07-09"], close=20.0)

    monkeypatch.setattr(downloader.yf, "Ticker", lambda symbol: DummyTicker())

    result = downloader.download_stock("TEST", period="5y")

    assert calls == [{"period": "5y", "auto_adjust": True}]
    assert result is not None
    assert result.attrs["period"] == "5y"
    assert result.index[0].year == 2021


def test_download_stock_reuses_confirmed_daily_cache_through_the_session(
    tmp_path, monkeypatch
):
    now = datetime(2026, 7, 10, 15, 0, tzinfo=ISTANBUL)
    monkeypatch.setattr(downloader, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(downloader, "_utc_now", lambda: now.astimezone(timezone.utc))

    cache_file = tmp_path / "TEST_20260710.parquet"
    cached = _ohlcv(["2026-07-09"])
    cached.attrs["period"] = "2y"
    cached.to_parquet(cache_file)
    very_old = now.astimezone(timezone.utc) - timedelta(hours=12)
    os.utime(cache_file, (very_old.timestamp(), very_old.timestamp()))

    def unexpected_ticker(symbol):
        raise AssertionError("Confirmed daily cache should not be downloaded intraday")

    monkeypatch.setattr(downloader.yf, "Ticker", unexpected_ticker)

    result = downloader.download_stock("TEST", period="2y")

    assert result is not None
    assert result.index[-1].date().isoformat() == "2026-07-09"
    assert result.attrs["cache_status"] == "fresh"


def test_download_stock_refreshes_after_close_when_todays_bar_is_missing(
    tmp_path, monkeypatch
):
    now = datetime(2026, 7, 10, 18, 16, tzinfo=ISTANBUL)
    monkeypatch.setattr(downloader, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(downloader, "_utc_now", lambda: now.astimezone(timezone.utc))

    cache_file = tmp_path / "TEST_20260710.parquet"
    cached = _ohlcv(["2026-07-09"])
    cached.attrs["period"] = "2y"
    cached.to_parquet(cache_file)
    current = now.astimezone(timezone.utc)
    os.utime(cache_file, (current.timestamp(), current.timestamp()))
    calls = []

    class DummyTicker:
        def history(self, **kwargs):
            calls.append(kwargs)
            return _ohlcv(["2026-07-09", "2026-07-10"], close=20.0)

    monkeypatch.setattr(downloader.yf, "Ticker", lambda symbol: DummyTicker())

    result = downloader.download_stock("TEST", period="2y")

    assert len(calls) == 1
    assert result is not None
    assert result.index[-1].date().isoformat() == "2026-07-10"

    cached_result = downloader.download_stock("TEST", period="2y")
    assert cached_result is not None
    assert len(calls) == 1


def test_web_snapshot_separates_generation_time_from_market_data_time(
    tmp_path, monkeypatch
):
    now = datetime(2026, 7, 10, 12, 0, tzinfo=ISTANBUL)
    monkeypatch.setattr(web_snapshot, "_utc_now", lambda: now.astimezone(timezone.utc))
    monkeypatch.setattr(web_snapshot, "LATEST_REPORT_PATH", tmp_path / "latest.json")
    monkeypatch.setattr(web_snapshot, "WEB_STOCKS_DIR", tmp_path / "stocks")

    daily = downloader._prepare_ohlcv(
        _ohlcv(["2026-07-09"]),
        now=now,
    )
    intraday = downloader._prepare_ohlcv(
        _ohlcv(["2026-07-10 10:30"]),
        now=now,
        interval="60m",
    )
    regime = MarketRegime(
        regime="YATAY",
        label="Yatay",
        color="yellow",
        sma_short=100.0,
        sma_long=100.0,
        index_price=100.0,
        performance_20d=0.0,
        trend_slope=0.0,
    )

    path = web_snapshot.save_web_snapshot(
        [],
        {"TEST": daily},
        {"TEST": intraday},
        regime,
        requested_symbols=1,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["generated_at"] == "2026-07-10T09:00:00+00:00"
    assert payload["data_as_of"] == "2026-07-10T08:30:00+00:00"
    assert payload["generated_at"] != payload["data_as_of"]
    assert payload["freshness"]["timezone"] == "Europe/Istanbul"
    assert payload["freshness"]["intraday"]["status"] == "fresh"
    assert payload["freshness"]["intraday"]["max_age_minutes"] == 30.0


def test_snapshot_data_as_of_uses_latest_available_source_timestamp():
    assert web_snapshot._latest_data_as_of(
        "2026-07-10T15:10:00+00:00",
        "2026-07-10T14:30:00+00:00",
    ) == "2026-07-10T15:10:00+00:00"
