# warehouse

The dbt project: staging, intermediate, marts, snapshots, and semantic
models (MetricFlow). Snowflake is the warehouse from week 2; DuckDB is used
only for fast local development by switching the dbt profile.

Python writes raw records (bronze); dbt owns everything after that —
renaming/casting/dedup (silver), point-in-time snapshot and baseline
models (silver), and the fact/dim tables behind verdicts, outcomes, LLM
cost, and the screener feature table (gold). See the design doc's Data
model section for the full table list and grain.

Every evaluation metric (hit rate, lift, Brier score, cost per verdict,
etc.) is defined once in the semantic layer here — the dashboard and API
only ever read those definitions.
