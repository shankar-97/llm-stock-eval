# prompts

One file per agent per version, e.g. `news_sentiment@v3.md`. Never edit a
prompt file in place — bump the version. dbt snapshots (`snap_prompt_versions`)
record which version produced each verdict, and the cache key includes
the prompt version so shadow challengers never share cache entries with
the current version.
