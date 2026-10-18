# evals

The frozen golden set used by the CI eval gate, the gate check
implementations (schema validity, citation validity, grounding, neutral/
refusal rate, cost and latency budgets), and the hand-labeled retrieval
question set used for recall@k.

A pull request touching `prompts/` or `config/llm.yaml` runs the changed
agents against `golden_set/` and fails if any check in
`config/eval_gate.yaml` regresses beyond its threshold. The gate does not
check whether stocks went up — that question belongs to the live shadow
experiments, not a few hundred golden-set cases.

Refresh the golden set monthly from recent snapshots, versioned like
prompts.
