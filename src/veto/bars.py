"""Closed daily Alpaca bars. Signals never see a still-forming candle."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Mapping

import pandas as pd

from .broker import BrokerError, _require_paper_keys
from .config import RunConfig


class BarsError(RuntimeError):
    """Raised when daily bars cannot be fetched or cleaned."""


def drop_forming_bar(
    df: pd.DataFrame, timeframe: str = "1d", now: datetime | None = None
) -> pd.DataFrame:
    """Drop the last bar if its UTC period has not closed yet."""
    if df.empty:
        return df
    now = now or datetime.now(timezone.utc)
    now_ts = pd.Timestamp(now)
    if now_ts.tzinfo is not None:
        now_ts = now_ts.tz_convert("UTC").tz_localize(None)
    last = pd.Timestamp(df.index[-1])
    if last.tzinfo is not None:
        last = last.tz_convert("UTC").tz_localize(None)
    unit = "h" if timeframe == "1h" else "D"
    forming = last.floor(unit) == now_ts.floor(unit)
    return df.iloc[:-1] if forming else df


def _as_utc(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.to_pydatetime()


def _frame(result: object, symbol: str) -> pd.DataFrame:
    frame = getattr(result, "df", None)
    if frame is None or frame.empty:
        raise BarsError(f"Alpaca returned no daily bars for {symbol}")
    frame = frame.copy()
    if isinstance(frame.index, pd.MultiIndex):
        try:
            frame = frame.xs(symbol, level="symbol")
        except (KeyError, ValueError):
            frame = frame.xs(symbol, level=0)
    rename = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    frame = frame.rename(columns=rename)
    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [column for column in required if column not in frame]
    if missing:
        raise BarsError(f"Alpaca bars for {symbol} are missing {missing}")
    frame = frame[required].apply(pd.to_numeric, errors="coerce").dropna()
    if frame.empty:
        raise BarsError(f"Alpaca returned no complete daily bars for {symbol}")
    index = pd.to_datetime(frame.index, utc=True).tz_localize(None)
    frame.index = pd.DatetimeIndex(index, name="Date")
    return frame.sort_index()


def fetch_daily(symbol: str, asset: str, since: str | None = None) -> pd.DataFrame:
    """Adjusted stock (IEX) or crypto spot daily bars. Paper keys only."""
    try:
        from alpaca.data.enums import Adjustment, DataFeed
        from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
        from alpaca.data.requests import CryptoBarsRequest, StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
    except ImportError as exc:
        raise BarsError("Install alpaca-py: pip install -e '.[broker]'") from exc
    key, secret = _require_paper_keys()
    start = _as_utc(since)
    end = datetime.now(timezone.utc)
    if asset == "stock":
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            adjustment=Adjustment.ALL,
            feed=DataFeed.IEX,
        )
        result = StockHistoricalDataClient(key, secret).get_stock_bars(request)
    elif asset == "crypto":
        request = CryptoBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )
        result = CryptoHistoricalDataClient(key, secret).get_crypto_bars(request)
    else:
        raise BarsError(f"Unknown asset {asset!r}")
    return drop_forming_bar(_frame(result, symbol), "1d")


def fetch_watchlist(cfg: RunConfig, lookback_days: int = 400) -> dict[str, pd.DataFrame]:
    since = (date.today() - timedelta(days=lookback_days)).isoformat()
    bars: dict[str, pd.DataFrame] = {}
    errors: list[str] = []
    for symbol, asset in cfg.symbols:
        try:
            bars[symbol] = fetch_daily(symbol, asset, since=since)
        except (BarsError, BrokerError) as exc:
            errors.append(f"{symbol}: {exc}")
    if not bars:
        raise BarsError("No watchlist bars fetched. " + "; ".join(errors[:3]))
    return bars
