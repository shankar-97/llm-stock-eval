# LLM Stock Analyst Eval Platform

A team of LLM agents analyzes stocks and a portfolio manager agent gives the
final verdict. The project's real subject is what most multi-agent stock
demos skip: **measuring honestly whether those verdicts are any good, and
whether changes to the agents make them better.**

This is an evaluation and reliability platform for LLM stock analysis, not
"AI picks stocks."

**Non-goals:** no trading, no brokerage connection, no real money, and no
claim that the system beats the market. Verdicts are research output, not
investment advice.

See the design doc (kept outside this repo) for the full architecture, evaluation
methodology, and build plan.

## Repo layout

```text
config/       # every tunable value: universe, models, eval, cache, experiments
prompts/      # one file per agent per version, never edited in place
ingest/       # yfinance, news and EDGAR loaders, snapshot writer
retrieval/    # chunking, embedding, pgvector store, retrieval queries
agents/       # analyst, portfolio manager and reviewer agents, cache layer, tracing
evals/        # golden set, gate checks, retrieval labels
warehouse/    # dbt project: staging, intermediate, marts, snapshots, semantic models
api/          # FastAPI service
web/          # Vite + React + TypeScript dashboard
.github/workflows/  # daily run, scoring, dbt build, CI eval gate
```

## Status

Week-1 slice is live: a daily snapshot writer, four analyst agents (fundamentals,
technicals, news sentiment, risk) and a portfolio manager agent run against the universe
in `config/universe.yaml`, producing structured verdicts appended to `data/raw/*.jsonl`.
Retrieval, the CI eval gate, the warehouse/dbt, the API, and the web app are not built
yet — see the design doc's Build plan.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY (required); FINNHUB_API_KEY is optional --
                        # without it the news_sentiment agent runs with no_news_data=true
```

Run the daily pipeline against a small subset first (writes to `data/raw/*.jsonl`):

```bash
python -m ingest.run_daily --limit 3 --force   # --force bypasses the weekend guard for testing
```

Then against the full universe:

```bash
python -m ingest.run_daily --force   # drop --force on a real trading weekday; the
                                      # weekend guard is on by default
```

Nothing is committed automatically outside CI — see `.github/workflows/daily-run.yml`
for the scheduled run, which also needs `ANTHROPIC_API_KEY` and (optionally)
`FINNHUB_API_KEY` set as repo secrets.

`config/universe.yaml` and `config/llm.yaml` are already filled in (50 tickers, Claude
model IDs); freeze the universe once you've confirmed a clean run — editing it later
introduces hindsight bias into the evaluation.
