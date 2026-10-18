"""Snapshot assembly, canonicalization, and the two hashes derived from a snapshot.

Two distinct hashes -- do not conflate them:
  - content_hash: identifies this exact snapshot, for leakage/replay audits. Changes
    whenever any input to the snapshot changes.
  - agent_cache_key: identifies one agent's *slice* of a snapshot, excluding volatile
    fields (fetched_at, snapshot_id) that would otherwise force a cache miss every run
    even when that agent's actual inputs haven't changed. Computed now, unused until the
    real caching follow-up.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import pandas as pd

from ingest.finnhub_loader import NewsItem, fetch_company_news
from ingest.indicators import (
    FundamentalRatios,
    RiskStats,
    TechnicalIndicators,
    compute_fundamental_ratios,
    compute_risk_stats,
    compute_technicals,
    days_until,
)
from ingest.yfinance_loader import (
    fetch_fundamentals,
    fetch_next_earnings_date,
    fetch_price_history,
)

PRICE_WINDOW_ROWS = 60  # trailing rows actually stored/fed to agents; full history stays
                         # local to the indicator calculations above


def canonicalize(obj: Any) -> str:
    """Deterministic JSON string: sorted keys, fixed float precision, NaN/NaT -> null,
    datetimes -> ISO8601. Stable across runs so identical data always hashes identically.
    """

    def default(value):
        if isinstance(value, (pd.Timestamp, datetime)):
            return value.isoformat()
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return None
            return round(value, 6)
        if pd.isna(value):
            return None
        raise TypeError(f"not serializable: {type(value)}")

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=default)


def compute_content_hash(snapshot_dict: dict) -> str:
    # snapshot_id is a random UUID assigned at write time, not content -- excluding it
    # (along with fetched_at/content_hash) is what makes this a *content* hash: identical
    # inputs on different days/runs must hash identically.
    payload = {
        k: v
        for k, v in snapshot_dict.items()
        if k not in ("content_hash", "fetched_at", "snapshot_id")
    }
    return hashlib.sha256(canonicalize(payload).encode()).hexdigest()


def agent_cache_key(agent: str, prompt_version: str, model: str, agent_input_slice: dict) -> str:
    """agent + prompt_version + model + hash(that agent's normalized input slice only).
    Caller must exclude fetched_at/snapshot_id/content_hash from agent_input_slice.
    """
    digest = hashlib.sha256(canonicalize(agent_input_slice).encode()).hexdigest()
    return f"{agent}:{prompt_version}:{model}:{digest}"


@dataclass
class Snapshot:
    snapshot_id: str
    ticker: str
    sector: Optional[str]
    as_of_ts: str  # ISO8601, the most recent close actually available from the data
    prices: list[dict]  # trailing PRICE_WINDOW_ROWS OHLCV rows
    technicals: TechnicalIndicators
    fundamentals: FundamentalRatios
    risk_stats: RiskStats
    news: list[NewsItem]
    no_news_data: bool
    fetch_errors: list[str] = field(default_factory=list)
    fetched_at: str = ""
    content_hash: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _price_window(price_history: Optional[pd.DataFrame]) -> list[dict]:
    if price_history is None or price_history.empty:
        return []
    window = price_history.tail(PRICE_WINDOW_ROWS)
    rows = []
    for ts, row in window.iterrows():
        rows.append(
            {
                "date": ts.isoformat(),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
            }
        )
    return rows


def build_snapshot(
    ticker: str, sector: Optional[str], spy_history: Optional[pd.DataFrame]
) -> Snapshot:
    """Build a point-in-time snapshot for one ticker. Never raises -- partial failures are
    recorded in fetch_errors and surfaced as None fields rather than aborting the ticker.
    """
    fetch_errors: list[str] = []

    price_history = fetch_price_history(ticker)
    if price_history is None:
        fetch_errors.append("price_history_unavailable")

    if price_history is not None and not price_history.empty:
        as_of_ts = price_history.index[-1].to_pydatetime()
    else:
        as_of_ts = datetime.now(timezone.utc)

    technicals = compute_technicals(price_history)

    raw_fundamentals = fetch_fundamentals(ticker)
    fundamentals = compute_fundamental_ratios(raw_fundamentals)

    next_earnings = fetch_next_earnings_date(ticker)
    dte = days_until(next_earnings, as_of_ts)
    risk_stats = compute_risk_stats(price_history, spy_history, dte)

    news, no_news_data = fetch_company_news(ticker, as_of_ts)

    snapshot = Snapshot(
        snapshot_id=str(uuid4()),
        ticker=ticker,
        sector=sector,
        as_of_ts=as_of_ts.isoformat(),
        prices=_price_window(price_history),
        technicals=technicals,
        fundamentals=fundamentals,
        risk_stats=risk_stats,
        news=news,
        no_news_data=no_news_data,
        fetch_errors=fetch_errors,
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )
    snapshot.content_hash = compute_content_hash(snapshot.to_dict())
    return snapshot
