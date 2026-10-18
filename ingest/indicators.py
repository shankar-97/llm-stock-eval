"""Indicators computed in code. Agents interpret these numbers -- they never calculate
indicators themselves. Every function here is defensive against short/missing history:
insufficient data produces None fields, never an exception.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class TechnicalIndicators:
    close: Optional[float]
    sma_20: Optional[float]
    sma_50: Optional[float]
    sma_200: Optional[float]
    pct_from_sma200: Optional[float]
    rsi_14: Optional[float]
    volume_avg_20d: Optional[float]
    latest_volume: Optional[float]


@dataclass
class RiskStats:
    realized_vol_20d_annualized: Optional[float]
    beta_60d: Optional[float]
    max_drawdown_1y: Optional[float]
    days_to_next_earnings: Optional[int]


@dataclass
class FundamentalRatios:
    trailing_pe: Optional[float]
    forward_pe: Optional[float]
    gross_margin: Optional[float]
    operating_margin: Optional[float]
    net_margin: Optional[float]
    revenue_growth_yoy: Optional[float]
    dividend_yield: Optional[float]
    payout_ratio: Optional[float]
    market_cap: Optional[float]


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _rsi(closes: pd.Series, window: int = 14) -> Optional[float]:
    if len(closes) < window + 1:
        return None
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window).mean().iloc[-1]
    avg_loss = loss.rolling(window).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return _safe_float(100 - (100 / (1 + rs)))


def compute_technicals(price_history: Optional[pd.DataFrame]) -> TechnicalIndicators:
    if price_history is None or price_history.empty:
        return TechnicalIndicators(None, None, None, None, None, None, None, None)

    closes = price_history["Close"]
    volumes = price_history["Volume"]
    close = _safe_float(closes.iloc[-1])
    sma_20 = _safe_float(closes.rolling(20).mean().iloc[-1]) if len(closes) >= 20 else None
    sma_50 = _safe_float(closes.rolling(50).mean().iloc[-1]) if len(closes) >= 50 else None
    sma_200 = _safe_float(closes.rolling(200).mean().iloc[-1]) if len(closes) >= 200 else None
    pct_from_sma200 = (
        _safe_float((close - sma_200) / sma_200) if close is not None and sma_200 else None
    )
    rsi_14 = _rsi(closes)
    volume_avg_20d = _safe_float(volumes.rolling(20).mean().iloc[-1]) if len(volumes) >= 20 else None
    latest_volume = _safe_float(volumes.iloc[-1])

    return TechnicalIndicators(
        close=close,
        sma_20=sma_20,
        sma_50=sma_50,
        sma_200=sma_200,
        pct_from_sma200=pct_from_sma200,
        rsi_14=rsi_14,
        volume_avg_20d=volume_avg_20d,
        latest_volume=latest_volume,
    )


def compute_risk_stats(
    price_history: Optional[pd.DataFrame],
    spy_history: Optional[pd.DataFrame],
    days_to_next_earnings: Optional[int],
) -> RiskStats:
    if price_history is None or price_history.empty:
        return RiskStats(None, None, None, days_to_next_earnings)

    closes = price_history["Close"]
    returns = closes.pct_change().dropna()

    realized_vol_20d_annualized = (
        _safe_float(returns.tail(20).std() * math.sqrt(252)) if len(returns) >= 20 else None
    )

    beta_60d = None
    if spy_history is not None and not spy_history.empty and len(returns) >= 60:
        spy_returns = spy_history["Close"].pct_change().dropna()
        joined = pd.concat(
            [returns.tail(60).rename("asset"), spy_returns.tail(60).rename("spy")], axis=1
        ).dropna()
        if len(joined) >= 30 and joined["spy"].var() > 0:
            cov = np.cov(joined["asset"], joined["spy"])[0, 1]
            beta_60d = _safe_float(cov / joined["spy"].var())

    max_drawdown_1y = None
    trailing = closes.tail(252)
    if len(trailing) > 1:
        running_max = trailing.cummax()
        drawdown = (trailing - running_max) / running_max
        max_drawdown_1y = _safe_float(drawdown.min())

    return RiskStats(
        realized_vol_20d_annualized=realized_vol_20d_annualized,
        beta_60d=beta_60d,
        max_drawdown_1y=max_drawdown_1y,
        days_to_next_earnings=days_to_next_earnings,
    )


def compute_fundamental_ratios(raw_fundamentals: dict) -> FundamentalRatios:
    return FundamentalRatios(
        trailing_pe=_safe_float(raw_fundamentals.get("trailingPE")),
        forward_pe=_safe_float(raw_fundamentals.get("forwardPE")),
        gross_margin=_safe_float(raw_fundamentals.get("grossMargins")),
        operating_margin=_safe_float(raw_fundamentals.get("operatingMargins")),
        net_margin=_safe_float(raw_fundamentals.get("profitMargins")),
        revenue_growth_yoy=_safe_float(raw_fundamentals.get("revenueGrowth")),
        dividend_yield=_safe_float(raw_fundamentals.get("dividendYield")),
        payout_ratio=_safe_float(raw_fundamentals.get("payoutRatio")),
        market_cap=_safe_float(raw_fundamentals.get("marketCap")),
    )


def days_until(target: Optional[datetime], as_of: datetime) -> Optional[int]:
    if target is None:
        return None
    target_naive = target.replace(tzinfo=None) if target.tzinfo else target
    as_of_naive = as_of.replace(tzinfo=None) if as_of.tzinfo else as_of
    return (target_naive.date() - as_of_naive.date()).days
