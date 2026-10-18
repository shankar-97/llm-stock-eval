"""yfinance loaders. This is the least reliable dependency in the pipeline (unofficial,
actively contested scraping target) -- every function here is defensive: missing fields
become None, failures are caught and logged, and nothing here should ever raise out to the
caller. One bad ticker must never abort the whole run.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

HISTORY_PERIOD = "2y"  # warmup room for SMA200 + 60d beta regression + 1y max drawdown


def fetch_price_history(ticker: str) -> Optional[pd.DataFrame]:
    """OHLCV history, ~2 years. Returns None (not raises) on failure."""
    try:
        df = yf.Ticker(ticker).history(period=HISTORY_PERIOD)
        if df is None or df.empty:
            logger.warning("empty price history for %s", ticker)
            return None
        return df
    except Exception:
        logger.exception("fetch_price_history failed for %s", ticker)
        return None


def fetch_spy_history() -> Optional[pd.DataFrame]:
    """Fetch once per run and reuse across every ticker's beta calc."""
    return fetch_price_history("SPY")


def fetch_fundamentals(ticker: str) -> dict:
    """Raw fundamentals from .get_info(). Every field is Optional -- missing != error."""
    fields = [
        "trailingPE",
        "forwardPE",
        "grossMargins",
        "operatingMargins",
        "profitMargins",
        "revenueGrowth",
        "dividendYield",
        "payoutRatio",
        "sector",
        "longName",
        "marketCap",
        "beta",
    ]
    try:
        info = yf.Ticker(ticker).get_info()
    except Exception:
        logger.exception("fetch_fundamentals failed for %s", ticker)
        return {field: None for field in fields}
    return {field: info.get(field) for field in fields}


def fetch_next_earnings_date(ticker: str) -> Optional[datetime]:
    """Flakiest single call in this module -- wrapped separately, None on any failure."""
    try:
        dates = yf.Ticker(ticker).get_earnings_dates(limit=4)
        if dates is None or dates.empty:
            return None
        now = pd.Timestamp.now(tz=dates.index.tz)
        future = dates.index[dates.index >= now]
        if len(future) == 0:
            return None
        return future.min().to_pydatetime()
    except Exception:
        logger.exception("fetch_next_earnings_date failed for %s", ticker)
        return None


def fetch_dividend_history(ticker: str) -> Optional[pd.Series]:
    try:
        divs = yf.Ticker(ticker).dividends
        if divs is None or divs.empty:
            return None
        return divs
    except Exception:
        logger.exception("fetch_dividend_history failed for %s", ticker)
        return None
