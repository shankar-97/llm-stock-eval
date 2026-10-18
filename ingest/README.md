# ingest

- `yfinance_loader.py` -- prices, fundamentals, earnings dates, dividend history.
- `finnhub_loader.py` -- company news; degrades to `no_news_data=True` without a key.
- `indicators.py` -- technicals/risk/fundamental ratios computed in code (agents interpret, never calculate).
- `snapshot.py` -- assembles a `Snapshot` per ticker, with the content hash and per-agent cache key.
- `run_daily.py` -- entry point: `python -m ingest.run_daily [--limit N] [--force]`.

SEC EDGAR filing retrieval is not built yet (out of scope for the week-1 slice).

Each run writes a snapshot first: prices through the as-of close, fundamentals as
fetched that day, and only news dated before the as-of time. The snapshot gets an ID
and a content hash so every verdict can be replayed and audited for leakage.
