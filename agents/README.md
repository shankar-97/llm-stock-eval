# agents

The analyst agents (fundamentals, technicals, news sentiment, risk), the
portfolio manager, and the weekly offline reviewer agent, plus the cache
layer and LLM call tracing.

Analyst agents run in parallel on the same point-in-time snapshot and
interpret numbers computed in code — they never calculate indicators
themselves. The portfolio manager reads only their structured reports and
produces the final verdict record (see the design doc's verdict contract).

Model names and token budgets are config, not code — see `config/llm.yaml`.
