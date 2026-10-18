# ingest

Loaders for yfinance (prices, dividends, splits, fundamentals), Finnhub
company news, and SEC EDGAR filings, plus the point-in-time snapshot writer.

Each run writes a snapshot first: prices through the as-of close,
fundamentals as fetched that day, and only news/filings dated before the
as-of time. The snapshot gets an ID and a content hash so every verdict can
be replayed and audited for leakage.
