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

See [the design doc](../../Projects/LLM%20Stock%20Analyst%20Eval%20Platform%20%E2%80%94%20Design%20Doc.md)
for the full architecture, evaluation methodology, and build plan.

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

Scaffolding only — see the design doc's Build plan and Definition of done.
