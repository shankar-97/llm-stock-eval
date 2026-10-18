"""Finnhub company-news loader. Degrades gracefully: if FINNHUB_API_KEY is unset or the
request fails, returns an empty list with no_news_data=True so the news_sentiment agent
still runs (low-confidence/neutral) instead of erroring the whole run.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    article_id: str
    headline: str
    summary: str
    published_at: datetime
    source: str
    url: str


def fetch_company_news(
    ticker: str, as_of: datetime, lookback_days: int = 7
) -> tuple[list[NewsItem], bool]:
    """Returns (articles, no_news_data). Only articles published strictly before `as_of`
    are returned, so news stays point-in-time even if Finnhub returns same-day items.
    """
    api_key = os.environ.get("FINNHUB_API_KEY")
    if not api_key:
        return [], True

    try:
        import finnhub

        client = finnhub.Client(api_key=api_key)
        start = (as_of - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        end = as_of.strftime("%Y-%m-%d")
        raw = client.company_news(ticker, _from=start, to=end)
    except Exception:
        logger.exception("fetch_company_news failed for %s", ticker)
        return [], True

    if not raw:
        return [], True

    items: list[NewsItem] = []
    for article in raw:
        published_at = datetime.fromtimestamp(article.get("datetime", 0), tz=as_of.tzinfo)
        if published_at >= as_of:
            continue  # point-in-time: never include same-day-or-later articles
        items.append(
            NewsItem(
                article_id=str(article.get("id")),
                headline=article.get("headline", ""),
                summary=article.get("summary", ""),
                published_at=published_at,
                source=article.get("source", ""),
                url=article.get("url", ""),
            )
        )
    return items, len(items) == 0
