# retrieval

Chunking of SEC filing sections, embedding, a pgvector store next to the
cache store, and the per-agent retrieval queries run at snapshot time.

Top-k passages filed before the as-of time are written into the snapshot,
so retrieval is point-in-time, hashed and cited like any other input. Also
handles news deduplication by embedding similarity.

Configured by `config/retrieval.yaml`. Quality is measured on its own via
recall@k against a hand-labeled question set in `evals/`.
