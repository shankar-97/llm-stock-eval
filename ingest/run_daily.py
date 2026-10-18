"""Daily verdict run entry point. Loads config, builds a point-in-time snapshot per
ticker, runs the 4 analyst agents concurrently + the portfolio manager, and appends the
resulting bronze records to data/raw/*.jsonl. Writes files only -- committing/pushing
those files is a separate step in .github/workflows/daily-run.yml, not done here.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from agents.fundamentals import run_fundamentals_agent
from agents.news_sentiment import run_news_sentiment_agent
from agents.portfolio_manager import run_portfolio_manager_agent
from agents.risk import run_risk_agent
from agents.schemas import AgentSignal, LLMCallTrace, VerdictRecord
from agents.technicals import run_technicals_agent
from ingest.snapshot import Snapshot, build_snapshot
from ingest.yfinance_loader import fetch_spy_history

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = REPO_ROOT / "data" / "raw"
CONFIG_DIR = REPO_ROOT / "config"
MAX_CONCURRENT_TICKERS = 4


def is_trading_weekday(dt: datetime) -> bool:
    """Mon=0 .. Sun=6. A real US holiday calendar is an explicit follow-up, not handled
    here -- this guard only rules out weekends.
    """
    return dt.weekday() < 5


def load_universe(path: Path = CONFIG_DIR / "universe.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_llm_config(path: Path = CONFIG_DIR / "llm.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def append_jsonl(path: Path, records: list[dict]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        for record in records:
            f.write(json.dumps(record, default=str))
            f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def _price_record(run_id: str, s: Snapshot) -> dict:
    return {
        "run_id": run_id,
        "ticker": s.ticker,
        "snapshot_id": s.snapshot_id,
        "as_of_ts": s.as_of_ts,
        "prices": s.prices,
        "fetch_errors": s.fetch_errors,
        "fetched_at": s.fetched_at,
    }


def _fundamentals_record(run_id: str, s: Snapshot) -> dict:
    return {
        "run_id": run_id,
        "ticker": s.ticker,
        "snapshot_id": s.snapshot_id,
        "as_of_ts": s.as_of_ts,
        "fundamentals": asdict(s.fundamentals),
        "fetched_at": s.fetched_at,
    }


def _news_record(run_id: str, s: Snapshot) -> dict:
    return {
        "run_id": run_id,
        "ticker": s.ticker,
        "snapshot_id": s.snapshot_id,
        "as_of_ts": s.as_of_ts,
        "no_news_data": s.no_news_data,
        "articles": [asdict(a) for a in s.news],
        "fetched_at": s.fetched_at,
    }


async def run_for_ticker(
    client: AsyncAnthropic,
    run_id: str,
    ticker_cfg: dict,
    spy_history,
    llm_cfg: dict,
) -> tuple[Snapshot, VerdictRecord, list[LLMCallTrace]]:
    ticker = ticker_cfg["symbol"]
    sector = ticker_cfg.get("sector")
    pricing = llm_cfg.get("pricing_usd_per_mtok", {})
    agents_cfg = llm_cfg["agents"]

    start = time.monotonic()

    snapshot = build_snapshot(ticker, sector, spy_history)

    fund_cfg, tech_cfg, news_cfg, risk_cfg = (
        agents_cfg["fundamentals"],
        agents_cfg["technicals"],
        agents_cfg["news_sentiment"],
        agents_cfg["risk"],
    )
    (fundamentals_out, fundamentals_trace), (technicals_out, technicals_trace), (
        news_out,
        news_trace,
    ), (risk_out, risk_trace) = await asyncio.gather(
        run_fundamentals_agent(client, run_id, snapshot, fund_cfg["model"], fund_cfg["token_budget"], pricing),
        run_technicals_agent(client, run_id, snapshot, tech_cfg["model"], tech_cfg["token_budget"], pricing),
        run_news_sentiment_agent(client, run_id, snapshot, news_cfg["model"], news_cfg["token_budget"], pricing),
        run_risk_agent(client, run_id, snapshot, risk_cfg["model"], risk_cfg["token_budget"], pricing),
    )

    pm_cfg = agents_cfg["portfolio_manager"]
    pm_out, pm_trace = await run_portfolio_manager_agent(
        client,
        run_id,
        ticker,
        fundamentals_out,
        technicals_out,
        news_out,
        risk_out,
        pm_cfg["model"],
        pm_cfg["token_budget"],
        pricing,
    )

    traces = [fundamentals_trace, technicals_trace, news_trace, risk_trace, pm_trace]

    agent_signals = [
        AgentSignal(
            agent="fundamentals",
            signal=fundamentals_out.signal,
            confidence=fundamentals_out.confidence,
            drivers=fundamentals_out.drivers,
        ),
        AgentSignal(
            agent="technicals",
            signal=technicals_out.signal,
            confidence=technicals_out.confidence,
            drivers=technicals_out.drivers,
        ),
        AgentSignal(
            agent="news_sentiment",
            signal=news_out.signal,
            confidence=news_out.confidence,
            drivers=news_out.drivers,
            extra={"cited_article_ids": news_out.cited_article_ids, "no_news_data": news_out.no_news_data},
        ),
        AgentSignal(
            agent="risk",
            signal=risk_out.signal,
            confidence=risk_out.confidence,
            drivers=risk_out.drivers,
            extra={"risk_flags": risk_out.risk_flags, "position_caution_level": risk_out.position_caution_level},
        ),
    ]

    cited_inputs = [snapshot.snapshot_id, snapshot.content_hash, *news_out.cited_article_ids]
    cost_usd = sum(t.cost_usd for t in traces)
    latency_ms = int((time.monotonic() - start) * 1000)  # wall time, not sum of parallel calls
    is_fallback = any(t.schema_validation_failed for t in traces)

    verdict = VerdictRecord(
        run_id=run_id,
        ticker=ticker,
        as_of_ts=snapshot.as_of_ts,
        verdict=pm_out.verdict,
        horizon_days=pm_out.horizon_days,
        p_outperform=pm_out.p_outperform,
        rationale=pm_out.rationale,
        key_drivers=pm_out.key_drivers,
        cited_inputs=cited_inputs,
        agent_signals=agent_signals,
        prompt_version="portfolio_manager@v1",
        model=pm_trace.model,
        input_hash=snapshot.content_hash,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        cache_hit=False,
        is_fallback=is_fallback,
    )
    return snapshot, verdict, traces


async def main(limit: int | None = None, force: bool = False) -> None:
    load_dotenv(REPO_ROOT / ".env")

    now = datetime.now(timezone.utc)
    if not is_trading_weekday(now) and not force:
        logger.info("Weekend — skipping run.")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY is not set — cannot run.")
        sys.exit(1)

    universe = load_universe()
    llm_cfg = load_llm_config()
    tickers = universe["tickers"]
    if limit:
        tickers = tickers[:limit]

    run_id = str(uuid4())
    client = AsyncAnthropic()
    spy_history = fetch_spy_history()
    sem = asyncio.Semaphore(MAX_CONCURRENT_TICKERS)

    async def bounded(ticker_cfg: dict):
        async with sem:
            try:
                return await run_for_ticker(client, run_id, ticker_cfg, spy_history, llm_cfg)
            except Exception:
                logger.exception("ticker %s failed entirely — skipping", ticker_cfg["symbol"])
                return None

    results = await asyncio.gather(*(bounded(t) for t in tickers))
    results = [r for r in results if r is not None]

    if not results:
        logger.warning("Run %s: every ticker failed — nothing to write.", run_id)
        return

    snapshots = [r[0] for r in results]
    verdicts = [r[1] for r in results]
    all_traces = [t for r in results for t in r[2]]

    append_jsonl(DATA_RAW_DIR / "raw_prices.jsonl", [_price_record(run_id, s) for s in snapshots])
    append_jsonl(DATA_RAW_DIR / "raw_fundamentals.jsonl", [_fundamentals_record(run_id, s) for s in snapshots])
    append_jsonl(DATA_RAW_DIR / "raw_news.jsonl", [_news_record(run_id, s) for s in snapshots])
    append_jsonl(DATA_RAW_DIR / "raw_verdicts.jsonl", [v.model_dump(mode="json") for v in verdicts])
    append_jsonl(DATA_RAW_DIR / "raw_llm_calls.jsonl", [t.model_dump(mode="json") for t in all_traces])

    total_cost = sum(v.cost_usd for v in verdicts)
    fallback_count = sum(1 for v in verdicts if v.is_fallback)
    fallback_rate = fallback_count / len(verdicts)
    logger.info(
        "Run %s complete: %d/%d tickers succeeded, %d fallback (%.0f%%), total cost $%.4f",
        run_id,
        len(verdicts),
        len(tickers),
        fallback_count,
        fallback_rate * 100,
        total_cost,
    )

    # A high fallback rate almost always means a systemic failure (bad API key, wrong
    # model ID, server rejecting the schema) rather than a few unlucky tickers -- and it
    # produces plausible-looking neutral verdicts that would otherwise poison the eval
    # dataset silently. Files are already written above for local debugging, but a
    # nonzero exit here fails the CI job before the commit-and-push step runs, so garbage
    # verdicts never make it into the committed data.
    if fallback_rate > 0.5:
        logger.error(
            "Fallback rate %.0f%% exceeds 50%% -- likely a systemic failure, not isolated "
            "ticker issues. Refusing to treat this run as healthy.",
            fallback_rate * 100,
        )
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N tickers (dry-run)")
    parser.add_argument("--force", action="store_true", help="Bypass the weekend guard for manual/dry-run testing")
    args = parser.parse_args()
    asyncio.run(main(limit=args.limit, force=args.force))
