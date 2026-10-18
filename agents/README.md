# agents

- `schemas.py` -- pydantic I/O models: per-agent analyst outputs, `PortfolioManagerOutput`,
  and the persisted `VerdictRecord`/`LLMCallTrace` (assembled in Python, never emitted
  directly by an LLM call).
- `base_agent.py` -- `call_agent()`: the Anthropic `messages.parse()` call, with one
  retry on truncation and a neutral/low-confidence fallback on refusal or repeated failure
  so one bad call never crashes the run.
- `prompt_loader.py` -- loads `prompts/<agent>@<version>.md` as the system prompt.
- `fundamentals.py`, `technicals.py`, `news_sentiment.py`, `risk.py`, `portfolio_manager.py`
  -- one module per agent, each builds its input payload from the snapshot (or, for the
  portfolio manager, from the four analyst outputs) and calls `call_agent()`.

Analyst agents run concurrently on the same point-in-time snapshot and interpret numbers
already computed in code — they never calculate indicators themselves. The portfolio
manager reads only their structured reports, not the raw snapshot.

Caching is not implemented yet -- the per-agent cache key is computed and recorded on
every trace row, but every call is currently treated as a cache miss (near-term follow-up).
The weekly offline reviewer agent is also not built yet.

Model names and token budgets are config, not code — see `config/llm.yaml`.
